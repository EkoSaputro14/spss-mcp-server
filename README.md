# IBM SPSS Statistics 22 FastMCP Server

A high-performance Python MCP (Model Context Protocol) server based on FastMCP / Official MCP SDK that provides headless statistical automation and dataset analysis for IBM SPSS Statistics 22 running under Wine.

## Architecture

The server uses a modular 3-tier architecture:

```
┌────────────────────────────────────────────────────────┐
│  Agent / MCP Client (Claude Desktop / Hermes)          │
└──────────────────────────┬─────────────────────────────┘
                           │ STDIO MCP Protocol
┌──────────────────────────▼─────────────────────────────┐
│  FastMCP Host Server (server.py - Python 3.10+)         │
│  - Exposes tools: execute_syntax, inspect_dataset, etc │
└──────────────────────────┬─────────────────────────────┘
                           │ Direct Python Call
┌──────────────────────────▼─────────────────────────────┐
│  Host-Wine Bridge (spss_bridge.py)                     │
│  - Path translation (winepath -w / -u)                 │
│  - Subprocess runner with timeout & error trapping     │
│  - Temp file lifecycle in /tmp_downloads_game          │
└──────────────────────────┬─────────────────────────────┘
                           │ Wine Subprocess (statisticspython.bat)
┌──────────────────────────▼─────────────────────────────┐
│  SPSS Internal Engine (spss_runner.py - Python 2.7)    │
│  - Headless execution via spss.Submit()                │
│  - Dataset inspection via spss.Dataset & spss.varlist  │
│  - ASCII statistical tables output to stdout           │
└────────────────────────────────────────────────────────┘
```

## Features & Tools

| MCP Tool | Description | Parameters |
|---|---|---|
| `spss_execute_syntax` | Executes arbitrary SPSS syntax commands headlessly. Automatically prepends `GET FILE` if `dataset_path` is provided. | `syntax` (str, required), `dataset_path` (str, optional) |
| `spss_run_file` | Executes an existing `.sps` syntax file from the filesystem. | `syntax_file_path` (str, required) |
| `spss_inspect_dataset` | Inspects `.sav` dataset and returns structural metadata as JSON (case count, variable names, measurement levels, labels, formats, missing values, and value labels). | `dataset_path` (str, required) |
| `spss_status` | Health-check endpoint verifying Wine prefix, SPSS executable, batch runner, and python bridge readiness. | None |

---

## Environment & Requirements

- **Host OS**: Linux (x86_64)
- **Host Python**: Python 3.10+ (managed via `uv`)
- **Wine Prefix**: `/tmp_downloads_game/Proyek/spss/.wine`
- **SPSS 22 Path**: `C:\Program Files (x86)\IBM\SPSS\Statistics\22`
- **Virtualenv**: `/tmp_downloads_game/Proyek/spss/mcp-server/.venv`

> **Note on Storage:** All temporary files, virtualenvs, and caches are kept under `/tmp_downloads_game` to avoid filling host root or `/home`.

### Setup Virtual Environment

```bash
cd /tmp_downloads_game/Proyek/spss/mcp-server
uv venv .venv
uv pip install -e ".[dev]" --python .venv
```

### Running Tests

```bash
/tmp_downloads_game/Proyek/spss/mcp-server/.venv/bin/pytest tests -v
```

All 7 integration and unit tests validate the exact MANOVA + Independent-Samples T-Test scenario (Wilks' Lambda, Box's M, Levene's Test) from Syefudin's dataset (`Data mentah.sav`).

---

## MCP Client Configuration

### 1. Claude Desktop

Add the following to your Claude Desktop configuration file:
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "spss": {
      "command": "/tmp_downloads_game/Proyek/spss/mcp-server/.venv/bin/python",
      "args": [
        "/tmp_downloads_game/Proyek/spss/mcp-server/server.py"
      ],
      "env": {
        "WINEPREFIX": "/tmp_downloads_game/Proyek/spss/.wine",
        "WINEDEBUG": "-all"
      }
    }
  }
}
```

### 2. Hermes Agent

In your Hermes agent configuration (e.g. `config.yaml` or MCP servers registry):

```yaml
mcp_servers:
  spss:
    command: "/tmp_downloads_game/Proyek/spss/mcp-server/.venv/bin/python"
    args:
      - "/tmp_downloads_game/Proyek/spss/mcp-server/server.py"
    env:
      WINEPREFIX: "/tmp_downloads_game/Proyek/spss/.wine"
      WINEDEBUG: "-all"
```

---

## Example Usage

### 1. Inspecting a Dataset

Tool call:
```json
{
  "name": "spss_inspect_dataset",
  "arguments": {
    "dataset_path": "/tmp_downloads_game/Proyek/spss/Data mentah.sav"
  }
}
```

Sample output:
```json
{
  "status": "success",
  "case_count": 76,
  "variable_count": 3,
  "variables": [
    {
      "index": 0,
      "name": "Prodi",
      "label": "Program studi",
      "measurement_level": "nominal",
      "type": "numeric",
      "value_labels": {
        "1": "Sistem Informasi",
        "2": "Teknik Informatika"
      }
    },
    {
      "index": 1,
      "name": "Layanan_Akademik",
      "label": "Skor layanan",
      "measurement_level": "scale",
      "type": "numeric"
    },
    {
      "index": 2,
      "name": "Kinerja_Dosen",
      "label": "Skor dosen",
      "measurement_level": "scale",
      "type": "numeric"
    }
  ]
}
```

### 2. Executing Multivariate GLM (MANOVA) & T-Test

Tool call:
```json
{
  "name": "spss_execute_syntax",
  "arguments": {
    "dataset_path": "/tmp_downloads_game/Proyek/spss/Data mentah.sav",
    "syntax": "GLM Layanan_Akademik Kinerja_Dosen BY Prodi\n  /METHOD=SSTYPE(3)\n  /INTERCEPT=INCLUDE\n  /PRINT=DESCRIPTIVE HOMOGENEITY ETASQ OPOWER\n  /CRITERIA=ALPHA(.05)\n  /DESIGN= Prodi.\nT-TEST GROUPS=Prodi(1 2)\n  /MISSING=ANALYSIS\n  /VARIABLES=Layanan_Akademik Kinerja_Dosen\n  /CRITERIA=CI(.95)."
  }
}
```

Returns formatted ASCII tables directly from IBM SPSS Statistics 22 including:
- Descriptive Statistics (Means and Standard Deviations)
- Box's Test of Equality of Covariance Matrices (`Box's M = .128`, `Sig. = .989`)
- Multivariate Tests (`Wilks' Lambda = .992`, `F = .281`, `Sig. = .756`)
- Levene's Test of Equality of Error Variances
- Independent Samples Test (`t = .454` and `t = .717`)
