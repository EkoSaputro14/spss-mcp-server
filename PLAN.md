# SPSS Python MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or delegate_task to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membangun Python MCP Server berbasis FastMCP/Official MCP SDK di `/tmp_downloads_game/Proyek/spss/mcp-server` yang memfasilitasi automasi analisis data IBM SPSS Statistics 22 (Wine headless) untuk Agentic AI.

**Architecture:** Arsitektur modular 3-layer: Host FastMCP Server (Python 3) -> Wine Bridge (`spss_bridge.py`) dengan konversi path dan error trapping -> SPSS Python 2.7 Internal Engine (`spss_runner.py` via `statisticspython.bat`) yang mengeksekusi sintaks SPSS (`spss.Submit`).

**Tech Stack:** Python 3.10+, `mcp` (Official Python SDK / FastMCP), Wine 11.18 (WoW64 mode), IBM SPSS Statistics 22.

---

## Global Constraints
- Target direktori proyek: `/tmp_downloads_game/Proyek/spss/mcp-server`
- Wineprefix: `/tmp_downloads_game/Proyek/spss/.wine`
- SPSS Install Directory: `C:\Program Files (x86)\IBM\SPSS\Statistics\22`
- Jangan menyimpan file sementara di `/home` karena keterbatasan ruang disk (~1.6GB tersisa). Semua cache dan temp file harus berada di `/tmp_downloads_game/`.
- Tidak boleh membuat GUI freeze; eksekusi harus selalu headless via `statisticspython.bat`.

---

### Task 1: Environment & Project Scaffolding
**Files:**
- Create: `/tmp_downloads_game/Proyek/spss/mcp-server/pyproject.toml`
- Create: `/tmp_downloads_game/Proyek/spss/mcp-server/.gitignore`

- [x] **Step 1: Inisialisasi direktori proyek dan venv**
- [x] **Step 2: Buat pyproject.toml dengan dependensi mcp**
- [x] **Step 3: Verifikasi instalasi paket mcp di venv**

---

### Task 2: SPSS Internal Runner Script
**Files:**
- Create: `/tmp_downloads_game/Proyek/spss/mcp-server/spss_runner.py`

**Interfaces:**
- Produces: CLI interface yang dijalankan di dalam Wine melalui `statisticspython.bat`:
  `statisticspython.bat Z:\...\spss_runner.py --syntax-file <path> --output-file <path>`

- [x] **Step 1: Buat skrip Python 2.7 kompatibel untuk SPSS internal**
- [x] **Step 2: Tangkap output tabel statistik dan error dari `spss.Submit`**
- [x] **Step 3: Uji eksekusi langsung dari Wine terminal**

---

### Task 3: Host SPSS Bridge Layer
**Files:**
- Create: `/tmp_downloads_game/Proyek/spss/mcp-server/spss_bridge.py`

**Interfaces:**
- Consumes: Task 2 runner
- Produces: Python 3 async class `SPSSBridge` dengan method:
  `execute_syntax(syntax: str, dataset_path: Optional[str]) -> str`
  `inspect_dataset(dataset_path: str) -> dict`
  `check_health() -> dict`

- [x] **Step 1: Implementasi konversi Linux path ke Windows path (winepath)**
- [x] **Step 2: Implementasi subprocess runner dengan timeout dan clean output filter**
- [x] **Step 3: Buat unit test mandiri untuk `spss_bridge.py`**

---

### Task 4: FastMCP Server Integration
**Files:**
- Create: `/tmp_downloads_game/Proyek/spss/mcp-server/server.py`

**Interfaces:**
- Tools exposed to Agent:
  - `spss_execute_syntax(syntax: str, dataset_path: str = None) -> str`
  - `spss_run_file(syntax_file_path: str) -> str`
  - `spss_inspect_dataset(dataset_path: str) -> str`
  - `spss_status() -> str`

- [x] **Step 1: Setup FastMCP server instance**
- [x] **Step 2: Daftarkan seluruh tool schema dan handler**
- [x] **Step 3: Uji coba server dengan tool call lokal**

---

### Task 5: End-to-End Validation (Kasus Tutorial PDF)
**Files:**
- Create: `/tmp_downloads_game/Proyek/spss/mcp-server/tests/test_e2e_tutorial.py`
- Create: `/tmp_downloads_game/Proyek/spss/mcp-server/README.md`

- [x] **Step 1: Jalankan uji skenario MANOVA + T-Test sesuai dokumen Syefudin**
- [x] **Step 2: Verifikasi tabel output Box's M, Wilks' Lambda, dan Levene's Test**
- [x] **Step 3: Buat dokumentasi konfigurasi untuk Claude Desktop / Hermes MCP**
