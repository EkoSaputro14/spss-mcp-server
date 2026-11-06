# -*- coding: utf-8 -*-
"""
spss_runner.py - Internal runner script for IBM SPSS Statistics 22 (Python 2.7)
Executed headlessly via statisticspython.bat inside Wine environment.

Modes:
  --syntax <path>   : Executes SPSS syntax file via spss.Submit()
  --inspect <path>  : Inspects .sav dataset and outputs variable metadata as JSON
  --output-file <p> : (Optional) Write output to file in addition to stdout
"""

import sys
import os
import json
import argparse
import traceback

try:
    import spss
except ImportError:
    sys.stderr.write("Error: spss module not found. Must run via statisticspython.bat\n")
    sys.exit(1)


def sanitize_value_labels(raw_labels):
    """Convert value label dict keys from float (e.g. 1.0) to int/str for clean JSON."""
    clean_labels = {}
    if not raw_labels:
        return clean_labels
    for k, v in raw_labels.items():
        if isinstance(k, float) and k.is_integer():
            clean_k = str(int(k))
        else:
            clean_k = str(k)
        clean_labels[clean_k] = unicode(v) if isinstance(v, (str, unicode)) else str(v)
    return clean_labels


def run_inspect(sav_path, output_file=None):
    """Inspects an SPSS .sav data file and outputs metadata JSON."""
    result = {
        "status": "error",
        "dataset_path": sav_path,
        "case_count": 0,
        "variable_count": 0,
        "variables": []
    }

    try:
        # Load dataset
        # Escape backslashes in Windows path for SPSS syntax string
        escaped_path = sav_path.replace("\\", "\\\\")
        spss.Submit("GET FILE='%s'." % escaped_path)

        err_level = spss.GetLastErrorLevel()
        if err_level > 2:
            err_msg = spss.GetLastErrorMessage()
            raise Exception("Failed to open file: %s (Error level %d)" % (err_msg, err_level))

        case_count = spss.GetCaseCount()
        var_count = spss.GetVariableCount()
        variables = []

        data_step_active = False
        try:
            spss.StartDataStep()
            data_step_active = True
            ds = spss.Dataset()

            for i, v in enumerate(ds.varlist):
                v_name = v.name
                v_type = v.type
                v_label = v.label if v.label else ""
                v_format = v.format
                v_level = v.measurementLevel
                v_missing = list(v.missingValues) if v.missingValues else []
                v_val_labels = {}
                if hasattr(v, "valueLabels") and hasattr(v.valueLabels, "data"):
                    v_val_labels = sanitize_value_labels(v.valueLabels.data)

                variables.append({
                    "index": i,
                    "name": v_name,
                    "type": "numeric" if v_type == 0 else "string",
                    "type_code": v_type,
                    "label": v_label,
                    "measurement_level": v_level.lower() if isinstance(v_level, (str, unicode)) else str(v_level),
                    "format": v_format,
                    "missing_values": v_missing,
                    "value_labels": v_val_labels
                })
        finally:
            if data_step_active:
                try:
                    spss.EndDataStep()
                except Exception:
                    pass

        result["status"] = "success"
        result["case_count"] = case_count
        result["variable_count"] = var_count
        result["variables"] = variables

    except spss.SpssError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)

    json_str = json.dumps(result, indent=2)

    sys.stdout.write("\n===SPSS_JSON_START===\n")
    sys.stdout.write(json_str)
    sys.stdout.write("\n===SPSS_JSON_END===\n")
    sys.stdout.flush()

    if output_file:
        try:
            with open(output_file, "w") as f:
                f.write(json_str)
        except Exception as e:
            sys.stderr.write("Warning: failed to write to output file %s: %s\n" % (output_file, e))

    if result["status"] == "success":
        sys.stdout.write("===SPSS_STATUS:SUCCESS===\n")
        return 0
    else:
        sys.stdout.write("===SPSS_STATUS:ERROR=== %s\n" % result.get("error", "Unknown error"))
        return 1


def run_syntax(syntax_path, output_file=None):
    """Executes an SPSS syntax file via spss.Submit()."""
    if not os.path.exists(syntax_path):
        sys.stderr.write("Error: Syntax file not found: %s\n" % syntax_path)
        sys.stdout.write("===SPSS_OUTPUT_START===\n")
        sys.stdout.write("===SPSS_STATUS:ERROR=== Syntax file not found: %s\n" % syntax_path)
        sys.stdout.write("===SPSS_OUTPUT_END===\n")
        sys.stdout.flush()
        return 1

    try:
        with open(syntax_path, "r") as f:
            syntax_content = f.read()
    except Exception as e:
        sys.stderr.write("Error reading syntax file: %s\n" % e)
        sys.stdout.write("===SPSS_OUTPUT_START===\n")
        sys.stdout.write("===SPSS_STATUS:ERROR=== Failed to read syntax file: %s\n" % e)
        sys.stdout.write("===SPSS_OUTPUT_END===\n")
        sys.stdout.flush()
        return 1

    sys.stdout.write("===SPSS_OUTPUT_START===\n")
    sys.stdout.flush()

    exit_code = 0
    status_msg = "===SPSS_STATUS:SUCCESS==="

    try:
        spss.Submit(syntax_content)
        err_level = spss.GetLastErrorLevel()
        if err_level > 2:
            err_msg = spss.GetLastErrorMessage()
            status_msg = "===SPSS_STATUS:ERROR=== [Level %d] %s" % (err_level, err_msg)
            exit_code = 1
    except spss.SpssError as e:
        status_msg = "===SPSS_STATUS:ERROR=== %s" % str(e)
        exit_code = 1
    except Exception as e:
        status_msg = "===SPSS_STATUS:ERROR=== %s" % str(e)
        exit_code = 1

    sys.stdout.write("\n%s\n" % status_msg)
    sys.stdout.write("===SPSS_OUTPUT_END===\n")
    sys.stdout.flush()

    if output_file:
        try:
            with open(output_file, "w") as f:
                f.write(status_msg)
        except Exception as e:
            sys.stderr.write("Warning: failed to write to output file %s: %s\n" % (output_file, e))

    return exit_code


def main():
    parser = argparse.ArgumentParser(description="SPSS 22 Internal Python Runner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--syntax", "--syntax-file", dest="syntax_file",
                       help="Path to SPSS syntax (.sps) file to execute")
    group.add_argument("--inspect", "--inspect-file", dest="inspect_file",
                       help="Path to SPSS dataset (.sav) file to inspect")
    parser.add_argument("--output-file", dest="output_file", default=None,
                        help="Optional file path to write output")

    args = parser.parse_args()

    if args.inspect_file:
        return run_inspect(args.inspect_file, args.output_file)
    elif args.syntax_file:
        return run_syntax(args.syntax_file, args.output_file)
    else:
        sys.stderr.write("Error: Either --syntax or --inspect must be specified.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
