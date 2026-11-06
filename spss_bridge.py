"""
spss_bridge.py - Host Python 3 Bridge for IBM SPSS Statistics 22 Automation via Wine.

Manages execution of SPSS syntax and dataset inspection through a headless
Wine subprocess invoking SPSS 22 internal Python engine (statisticspython.bat).
"""

import os
import re
import json
import shutil
import logging
import tempfile
import subprocess
from typing import Dict, Any, Optional

logger = logging.getLogger("spss_bridge")


class SPSSBridgeError(Exception):
    """Base exception for SPSS Bridge operations."""
    pass


class SPSSExecutionError(SPSSBridgeError):
    """Raised when SPSS syntax execution fails."""
    pass


class SPSSBridge:
    """
    Bridge interface connecting Host Python 3 to IBM SPSS Statistics 22 running in Wine.
    """

    DEFAULT_WINEPREFIX = "/tmp_downloads_game/Proyek/spss/.wine"
    DEFAULT_SPSS_DIR = r"C:\Program Files (x86)\IBM\SPSS\Statistics\22"
    DEFAULT_TMP_DIR = "/tmp_downloads_game/Proyek/spss/mcp-server/.tmp"

    def __init__(
        self,
        wineprefix: Optional[str] = None,
        spss_dir: Optional[str] = None,
        runner_path: Optional[str] = None,
        temp_dir: Optional[str] = None,
    ) -> None:
        self.wineprefix = os.environ.get("WINEPREFIX", wineprefix or self.DEFAULT_WINEPREFIX)
        self.spss_dir = os.environ.get("SPSS_DIR", spss_dir or self.DEFAULT_SPSS_DIR)

        # Determine runner path
        if runner_path:
            self.runner_path = os.path.abspath(runner_path)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.runner_path = os.path.join(base_dir, "spss_runner.py")

        # Ensure temp directory exists in /tmp_downloads_game to respect disk constraints
        self.temp_dir = temp_dir or self.DEFAULT_TMP_DIR
        os.makedirs(self.temp_dir, exist_ok=True)

    def _get_env(self) -> Dict[str, str]:
        """Build environment dictionary for Wine subprocess calls."""
        env = os.environ.copy()
        env["WINEPREFIX"] = self.wineprefix
        env["WINEDEBUG"] = "-all"
        return env

    def to_windows_path(self, linux_path: str) -> str:
        """
        Convert Linux filesystem path to Windows drive path (Z:\\...) via winepath.
        """
        # If already Windows style path (e.g., C:\... or Z:\...)
        if re.match(r"^[a-zA-Z]:[\\/]", linux_path):
            return linux_path.replace("/", "\\")

        abs_path = os.path.abspath(linux_path)
        try:
            result = subprocess.run(
                ["winepath", "-w", abs_path],
                env=self._get_env(),
                capture_output=True,
                text=True,
                check=True,
            )
            win_path = result.stdout.strip()
            if not win_path:
                raise SPSSBridgeError(f"winepath returned empty string for {linux_path}")
            return win_path
        except subprocess.CalledProcessError as e:
            raise SPSSBridgeError(f"Failed to convert path '{linux_path}' to Windows path: {e.stderr}")

    def to_linux_path(self, windows_path: str) -> str:
        """
        Convert Windows path (Z:\\...) to Linux filesystem path via winepath.
        """
        try:
            result = subprocess.run(
                ["winepath", "-u", windows_path],
                env=self._get_env(),
                capture_output=True,
                text=True,
                check=True,
            )
            linux_path = result.stdout.strip()
            if not linux_path:
                raise SPSSBridgeError(f"winepath returned empty string for {windows_path}")
            return linux_path
        except subprocess.CalledProcessError as e:
            raise SPSSBridgeError(f"Failed to convert path '{windows_path}' to Linux path: {e.stderr}")

    def _get_statisticspython_bat(self) -> str:
        """Get Windows path to statisticspython.bat."""
        return os.path.join(self.spss_dir, "statisticspython.bat").replace("/", "\\")

    def _run_wine_command(self, runner_args: list[str], timeout: int = 120) -> str:
        """
        Invoke statisticspython.bat with spss_runner.py inside Wine.
        """
        runner_win_path = self.to_windows_path(self.runner_path)
        bat_win_path = self._get_statisticspython_bat()

        cmd = ["wine", bat_win_path, runner_win_path] + runner_args
        logger.debug("Executing Wine command: %s", cmd)

        try:
            res = subprocess.run(
                cmd,
                env=self._get_env(),
                cwd=os.path.dirname(self.runner_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise SPSSExecutionError(f"SPSS execution timed out after {timeout} seconds") from e
        except Exception as e:
            raise SPSSBridgeError(f"Subprocess execution failed: {e}") from e

        # Combined output
        output = res.stdout
        if res.stderr and not output:
            output = res.stderr

        return output

    @staticmethod
    def _extract_spss_output(raw_output: str) -> str:
        """
        Extract clean SPSS statistical table output between markers.
        """
        start_marker = "===SPSS_OUTPUT_START==="
        end_marker = "===SPSS_OUTPUT_END==="

        if start_marker in raw_output and end_marker in raw_output:
            part = raw_output.split(start_marker, 1)[1]
            content = part.split(end_marker, 1)[0]
        else:
            content = raw_output

        # Clean up status markers from returned text if desired
        lines = []
        for line in content.splitlines():
            # Filter cmd prompt lines and status markers
            stripped = line.strip()
            if stripped.startswith("Z:\\") and stripped.endswith(">"):
                continue
            if stripped.startswith("C:\\") and stripped.endswith(">"):
                continue
            if stripped == "===SPSS_STATUS:SUCCESS===":
                continue
            lines.append(line)

        return "\n".join(lines).strip()

    def execute_syntax(
        self,
        syntax: str,
        dataset_path: Optional[str] = None,
        timeout: int = 120,
    ) -> str:
        """
        Execute SPSS syntax headlessly and return formatted statistical output.

        Args:
            syntax: SPSS syntax commands to execute.
            dataset_path: Optional path to .sav dataset. If provided and not already
                          referenced in syntax, GET FILE command will be prepended.
            timeout: Subprocess timeout in seconds (default: 120).

        Returns:
            Formatted statistical output text from SPSS.
        """
        final_syntax = syntax.strip()

        # If dataset_path is specified, prepend GET FILE if not already opening the file
        if dataset_path:
            win_dataset = self.to_windows_path(dataset_path)
            escaped_win_dataset = win_dataset.replace("'", "''")
            if "GET FILE=" not in final_syntax.upper():
                final_syntax = f"GET FILE='{escaped_win_dataset}'.\n" + final_syntax

        # Create temporary syntax file in designated temp dir
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sps",
            dir=self.temp_dir,
            delete=False,
            encoding="utf-8",
        )
        try:
            temp_file.write(final_syntax + "\n")
            temp_file.close()

            win_syntax_path = self.to_windows_path(temp_file.name)
            raw_output = self._run_wine_command(["--syntax", win_syntax_path], timeout=timeout)

            # Check for error status
            if "===SPSS_STATUS:ERROR===" in raw_output:
                err_line = ""
                for line in raw_output.splitlines():
                    if "===SPSS_STATUS:ERROR===" in line:
                        err_line = line.replace("===SPSS_STATUS:ERROR===", "").strip()
                        break
                clean_output = self._extract_spss_output(raw_output)
                raise SPSSExecutionError(f"SPSS execution failed: {err_line}\nOutput:\n{clean_output}")

            return self._extract_spss_output(raw_output)

        finally:
            if os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except OSError:
                    pass

    def run_file(self, syntax_file_path: str, timeout: int = 120) -> str:
        """
        Execute an existing SPSS syntax (.sps) file.

        Args:
            syntax_file_path: Linux path to .sps file.
            timeout: Subprocess timeout in seconds (default: 120).

        Returns:
            Formatted statistical output text from SPSS.
        """
        if not os.path.exists(syntax_file_path):
            raise FileNotFoundError(f"SPSS syntax file not found: {syntax_file_path}")

        win_syntax_path = self.to_windows_path(syntax_file_path)
        raw_output = self._run_wine_command(["--syntax", win_syntax_path], timeout=timeout)

        if "===SPSS_STATUS:ERROR===" in raw_output:
            err_line = ""
            for line in raw_output.splitlines():
                if "===SPSS_STATUS:ERROR===" in line:
                    err_line = line.replace("===SPSS_STATUS:ERROR===", "").strip()
                    break
            clean_output = self._extract_spss_output(raw_output)
            raise SPSSExecutionError(f"SPSS execution failed: {err_line}\nOutput:\n{clean_output}")

        return self._extract_spss_output(raw_output)

    def inspect_dataset(self, dataset_path: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Inspect an SPSS .sav data file and return variable metadata as a dictionary.

        Args:
            dataset_path: Linux path to .sav dataset.
            timeout: Subprocess timeout in seconds (default: 60).

        Returns:
            Dictionary containing dataset metadata: case_count, variable_count, variables.
        """
        if not os.path.exists(dataset_path):
            raise FileNotFoundError(f"SPSS dataset file not found: {dataset_path}")

        win_dataset_path = self.to_windows_path(dataset_path)
        raw_output = self._run_wine_command(["--inspect", win_dataset_path], timeout=timeout)

        start_marker = "===SPSS_JSON_START==="
        end_marker = "===SPSS_JSON_END==="

        if start_marker not in raw_output or end_marker not in raw_output:
            raise SPSSBridgeError(f"Failed to parse inspect output from SPSS. Output was:\n{raw_output}")

        json_chunk = raw_output.split(start_marker, 1)[1].split(end_marker, 1)[0].strip()
        try:
            data = json.loads(json_chunk)
        except json.JSONDecodeError as e:
            raise SPSSBridgeError(f"Invalid JSON returned by SPSS runner: {e}\nRaw JSON: {json_chunk}")

        if data.get("status") == "error":
            raise SPSSBridgeError(f"SPSS dataset inspection error: {data.get('error')}")

        return data

    def check_health(self) -> Dict[str, Any]:
        """
        Check connectivity and prerequisite health for SPSS Wine environment.

        Returns:
            Dictionary with health status details.
        """
        wine_bin = shutil.which("wine")
        winepath_bin = shutil.which("winepath")
        wineprefix_exists = os.path.isdir(self.wineprefix)

        # Check Wine SPSS paths
        stats_exe_linux = os.path.join(
            self.wineprefix,
            "drive_c",
            "Program Files (x86)",
            "IBM",
            "SPSS",
            "Statistics",
            "22",
            "stats.exe",
        )
        stats_bat_linux = os.path.join(
            self.wineprefix,
            "drive_c",
            "Program Files (x86)",
            "IBM",
            "SPSS",
            "Statistics",
            "22",
            "statisticspython.bat",
        )
        runner_exists = os.path.isfile(self.runner_path)

        is_healthy = bool(
            wine_bin
            and winepath_bin
            and wineprefix_exists
            and os.path.isfile(stats_bat_linux)
            and runner_exists
        )

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "wine_bin": wine_bin,
            "winepath_bin": winepath_bin,
            "wineprefix": self.wineprefix,
            "wineprefix_exists": wineprefix_exists,
            "spss_executable_exists": os.path.isfile(stats_exe_linux),
            "statisticspython_bat_exists": os.path.isfile(stats_bat_linux),
            "runner_path": self.runner_path,
            "runner_exists": runner_exists,
            "temp_dir": self.temp_dir,
        }
