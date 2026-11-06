"""
test_e2e_tutorial.py - End-to-end integration test for SPSS MCP Server.

Validates the exact MANOVA + Independent-Samples T-Test scenario described in:
'6. Tugas Statistika Syefudin REVISI HIPOTESIS.pdf'
Dataset: 'Data mentah.sav' (76 respondents: 38 SI [Prodi=1], 38 TI [Prodi=2])
Variables: Prodi, Layanan_Akademik, Kinerja_Dosen
"""

import os
import json
import tempfile
import pytest

from spss_bridge import SPSSBridge, SPSSExecutionError
import server


DATASET_PATH = "/tmp_downloads_game/Proyek/spss/Data mentah.sav"


@pytest.fixture(scope="module")
def bridge():
    """SPSSBridge instance for testing."""
    return SPSSBridge()


@pytest.mark.integration
def test_spss_status_healthy():
    """Verify that SPSS environment is healthy and operational."""
    status_json = server.spss_status()
    status_data = json.loads(status_json)

    assert status_data["status"] == "healthy"
    assert status_data["wineprefix_exists"] is True
    assert status_data["spss_executable_exists"] is True
    assert status_data["statisticspython_bat_exists"] is True
    assert status_data["runner_exists"] is True


@pytest.mark.integration
def test_inspect_dataset_structure():
    """
    Verify dataset inspection on 'Data mentah.sav':
    - 76 total cases (38 SI + 38 TI)
    - 3 variables: Prodi, Layanan_Akademik, Kinerja_Dosen
    - Prodi value labels: 1 = 'Sistem Informasi', 2 = 'Teknik Informatika'
    """
    assert os.path.exists(DATASET_PATH), f"Dataset not found at {DATASET_PATH}"

    inspect_json = server.spss_inspect_dataset(DATASET_PATH)
    data = json.loads(inspect_json)

    assert data["status"] == "success"
    assert data["case_count"] == 76
    assert data["variable_count"] == 3

    var_names = [v["name"] for v in data["variables"]]
    assert "Prodi" in var_names
    assert "Layanan_Akademik" in var_names
    assert "Kinerja_Dosen" in var_names

    # Check Prodi details
    prodi_var = next(v for v in data["variables"] if v["name"] == "Prodi")
    assert prodi_var["measurement_level"].lower() == "nominal"
    assert prodi_var["type"] == "numeric"
    assert prodi_var["value_labels"].get("1") == "Sistem Informasi"
    assert prodi_var["value_labels"].get("2") == "Teknik Informatika"

    # Check scale variables
    layanan_var = next(v for v in data["variables"] if v["name"] == "Layanan_Akademik")
    assert layanan_var["measurement_level"].lower() == "scale"

    dosen_var = next(v for v in data["variables"] if v["name"] == "Kinerja_Dosen")
    assert dosen_var["measurement_level"].lower() == "scale"


@pytest.mark.integration
def test_manova_analysis_syefudin_scenario(bridge):
    """
    Execute MANOVA (GLM Multivariate) and verify statistical tables match PDF tutorial:
    - Box's M = .128, Sig. = .989
    - Prodi Wilks' Lambda = .992, F = .281, Sig. = .756
    - Levene's Test:
      * Layanan_Akademik F = .287, Sig. = .594
      * Kinerja_Dosen F = .008, Sig. = .928
    """
    manova_syntax = """
GLM Layanan_Akademik Kinerja_Dosen BY Prodi
  /METHOD=SSTYPE(3)
  /INTERCEPT=INCLUDE
  /PRINT=DESCRIPTIVE HOMOGENEITY ETASQ OPOWER
  /CRITERIA=ALPHA(.05)
  /DESIGN= Prodi.
"""
    output = bridge.execute_syntax(manova_syntax, dataset_path=DATASET_PATH)

    # 1. Check descriptive statistics
    assert "Descriptive Statistics" in output
    assert "Skor layanan" in output or "Layanan_Akademik" in output
    assert "Skor dosen" in output or "Kinerja_Dosen" in output
    assert "3.9384" in output  # Mean Skor layanan SI
    assert "3.8842" in output  # Mean Skor layanan TI
    assert "4.2650" in output  # Mean Skor dosen SI
    assert "4.2024" in output  # Mean Skor dosen TI

    # 2. Check Box's Test of Equality of Covariance Matrices
    assert "Box's Test of Equality of Covariance Matrices" in output
    assert ".128" in output   # Box's M
    assert ".989" in output   # Box's M Sig.

    # 3. Check Multivariate Tests (Wilks' Lambda for Prodi)
    assert "Multivariate Tests" in output
    assert "Wilks' Lambda" in output
    assert ".992" in output   # Wilks' Lambda value for Prodi
    assert ".281" in output   # F statistic for Prodi
    assert ".756" in output   # Sig. for Prodi

    # 4. Check Levene's Test of Equality of Error Variances
    assert "Levene's Test" in output
    assert ".287" in output   # Levene F for Layanan
    assert ".594" in output   # Levene Sig for Layanan
    assert ".008" in output   # Levene F for Dosen
    assert ".928" in output   # Levene Sig for Dosen


@pytest.mark.integration
def test_t_test_analysis_syefudin_scenario(bridge):
    """
    Execute Independent-Samples T-Test and verify statistical output matches PDF tutorial:
    - Group Statistics: N=38 for both SI and TI
    - Independent Samples Test (Equal variances assumed):
      * Layanan: t = .454, df = 74, Sig. (2-tailed) = .651
      * Dosen: t = .717, df = 74, Sig. (2-tailed) = .476
    """
    ttest_syntax = """
T-TEST GROUPS=Prodi(1 2)
  /MISSING=ANALYSIS
  /VARIABLES=Layanan_Akademik Kinerja_Dosen
  /CRITERIA=CI(.95).
"""
    output = bridge.execute_syntax(ttest_syntax, dataset_path=DATASET_PATH)

    assert "Group Statistics" in output
    assert "Independent Samples Test" in output

    # Check T-Test results for Layanan_Akademik
    assert ".454" in output   # t-statistic for Layanan
    assert ".651" in output   # Sig. (2-tailed) for Layanan

    # Check T-Test results for Kinerja_Dosen
    assert ".717" in output   # t-statistic for Dosen
    assert ".476" in output   # Sig. (2-tailed) for Dosen


@pytest.mark.integration
def test_full_pipeline_via_server_tool():
    """
    Test running the complete MANOVA + T-Test combined syntax through FastMCP server tool.
    """
    combined_syntax = """
GLM Layanan_Akademik Kinerja_Dosen BY Prodi
  /METHOD=SSTYPE(3)
  /INTERCEPT=INCLUDE
  /PRINT=DESCRIPTIVE HOMOGENEITY ETASQ OPOWER
  /CRITERIA=ALPHA(.05)
  /DESIGN= Prodi.
T-TEST GROUPS=Prodi(1 2)
  /MISSING=ANALYSIS
  /VARIABLES=Layanan_Akademik Kinerja_Dosen
  /CRITERIA=CI(.95).
"""
    result = server.spss_execute_syntax(syntax=combined_syntax, dataset_path=DATASET_PATH)

    assert "Multivariate Tests" in result
    assert "Wilks' Lambda" in result
    assert "Independent Samples Test" in result
    assert "Error executing SPSS syntax" not in result


@pytest.mark.integration
def test_run_file_tool(bridge):
    """
    Test spss_run_file tool using a temporary .sps file.
    """
    temp_dir = bridge.temp_dir
    os.makedirs(temp_dir, exist_ok=True)
    sps_path = os.path.join(temp_dir, "test_script.sps")

    win_ds = bridge.to_windows_path(DATASET_PATH)
    escaped_ds = win_ds.replace("'", "''")

    try:
        with open(sps_path, "w", encoding="utf-8") as f:
            f.write(f"GET FILE='{escaped_ds}'.\nDESCRIPTIVES VARIABLES=Layanan_Akademik Kinerja_Dosen.\n")

        result = server.spss_run_file(sps_path)
        assert "Descriptive Statistics" in result
        assert "Error running SPSS syntax file" not in result
    finally:
        if os.path.exists(sps_path):
            os.remove(sps_path)


@pytest.mark.unit
def test_error_handling_invalid_syntax():
    """
    Verify error handling when invalid syntax is submitted.
    """
    invalid_syntax = "NONEXISTENT_SPSS_COMMAND_XYZ123."
    result = server.spss_execute_syntax(syntax=invalid_syntax)
    assert "Error executing SPSS syntax" in result
