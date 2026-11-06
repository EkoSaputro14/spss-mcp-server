"""
server.py - FastMCP Server for IBM SPSS Statistics 22 Automation via Wine.

Exposes MCP tools for executing SPSS syntax, running syntax files,
inspecting .sav datasets, and monitoring health status.
"""

import json
import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP

from spss_bridge import SPSSBridge, SPSSBridgeError, SPSSExecutionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("spss_server")

# Initialize FastMCP Server
mcp = FastMCP("spss-statistics")
bridge = SPSSBridge()


@mcp.tool()
def spss_execute_syntax(syntax: str, dataset_path: Optional[str] = None) -> str:
    """
    Execute SPSS syntax commands headlessly in IBM SPSS Statistics 22.

    Args:
        syntax: SPSS syntax string to execute (e.g., DESCRIPTIVES, GLM, T-TEST, FREQUENCIES).
                Commands should terminate with a period ('.').
        dataset_path: Optional path to an SPSS dataset (.sav) file. If provided,
                      a GET FILE command is automatically prepended to the syntax.

    Returns:
        Formatted ASCII tables and statistical output from SPSS.
    """
    try:
        logger.info("Executing syntax (dataset_path=%s)", dataset_path)
        output = bridge.execute_syntax(syntax=syntax, dataset_path=dataset_path)
        return output
    except SPSSExecutionError as e:
        logger.warning("SPSS syntax error: %s", e)
        return f"Error executing SPSS syntax:\n{e}"
    except Exception as e:
        logger.error("Unexpected error executing syntax: %s", e, exc_info=True)
        return f"Unexpected error during SPSS execution: {e}"


@mcp.tool()
def spss_run_file(syntax_file_path: str) -> str:
    """
    Execute an existing SPSS syntax (.sps) file.

    Args:
        syntax_file_path: Path to the .sps syntax file on the filesystem.

    Returns:
        Formatted statistical output from the executed syntax file.
    """
    try:
        logger.info("Running syntax file: %s", syntax_file_path)
        output = bridge.run_file(syntax_file_path=syntax_file_path)
        return output
    except (FileNotFoundError, SPSSBridgeError) as e:
        logger.warning("Error running syntax file: %s", e)
        return f"Error running SPSS syntax file:\n{e}"
    except Exception as e:
        logger.error("Unexpected error running syntax file: %s", e, exc_info=True)
        return f"Unexpected error: {e}"


@mcp.tool()
def spss_inspect_dataset(dataset_path: str) -> str:
    """
    Inspect an SPSS dataset (.sav) and return structural metadata as JSON.

    Retrieves case count, variable count, and details for each variable:
    name, measurement level, type, label, format, missing values, and value labels.

    Args:
        dataset_path: Path to the .sav dataset file on the filesystem.

    Returns:
        JSON string containing dataset schema and variable metadata.
    """
    try:
        logger.info("Inspecting dataset: %s", dataset_path)
        metadata = bridge.inspect_dataset(dataset_path=dataset_path)
        return json.dumps(metadata, indent=2, ensure_ascii=False)
    except (FileNotFoundError, SPSSBridgeError) as e:
        logger.warning("Dataset inspection error: %s", e)
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
    except Exception as e:
        logger.error("Unexpected error inspecting dataset: %s", e, exc_info=True)
        return json.dumps({"status": "error", "error": f"Unexpected error: {e}"}, indent=2)


@mcp.tool()
def spss_status() -> str:
    """
    Check the health, environment, and readiness of the SPSS Wine bridge.

    Verifies availability of Wine binary, winepath, wineprefix directory,
    SPSS installation, and statisticspython.bat runner script.

    Returns:
        JSON string with component status and diagnostic details.
    """
    try:
        status_info = bridge.check_health()
        return json.dumps(status_info, indent=2)
    except Exception as e:
        logger.error("Health check error: %s", e, exc_info=True)
        return json.dumps({"status": "unhealthy", "error": str(e)}, indent=2)


def main() -> None:
    """Run FastMCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
