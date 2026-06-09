#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Detailed input validation for the cropland-transformation workflow.

This script checks common issues before running the analysis:
    - missing required files
    - missing year columns
    - non-numeric values in year tables
    - duplicated province names
    - missing coordinate, time, response or explanatory columns in model tables
    - obviously invalid values such as negative area or missing coordinates

The output is a machine-readable validation report. The script does not modify
input data.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
import pandas as pd
import numpy as np


def read_table(path: str | Path, sheet_name: str | int | None = 0) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name)
    return pd.read_csv(path)


def add_issue(issues: list[dict], table: str, severity: str, field: str, message: str) -> None:
    issues.append({"table": table, "severity": severity, "field": field, "message": message})


def validate_year_table(path: str | Path, label: str, start_year: int, end_year: int, sheet_name: str | int | None = 0) -> list[dict]:
    issues: list[dict] = []
    try:
        df = read_table(path, sheet_name)
    except Exception as exc:
        add_issue(issues, label, "error", "file", f"Cannot read table: {exc}")
        return issues
    province_candidates = [c for c in df.columns if str(c).lower() in {"province", "region", "name"}]
    if not province_candidates:
        add_issue(issues, label, "error", "Province", "No province/name column was detected.")
    else:
        pcol = province_candidates[0]
        if df[pcol].isna().any():
            add_issue(issues, label, "warning", pcol, "Province column contains missing values.")
        if df[pcol].duplicated().any():
            duplicates = df.loc[df[pcol].duplicated(), pcol].astype(str).tolist()
            add_issue(issues, label, "error", pcol, f"Duplicated province names: {duplicates}")
    for year in range(start_year, end_year + 1):
        col = str(year)
        if col not in [str(c) for c in df.columns]:
            add_issue(issues, label, "error", col, "Missing year column.")
            continue
        actual_col = next(c for c in df.columns if str(c) == col)
        values = pd.to_numeric(df[actual_col], errors="coerce")
        if values.isna().any():
            add_issue(issues, label, "error", col, f"{int(values.isna().sum())} non-numeric or missing values.")
        if (values < 0).any():
            add_issue(issues, label, "warning", col, f"{int((values < 0).sum())} negative values detected.")
    return issues


def validate_model_table(
    path: str | Path,
    label: str,
    response_columns: Sequence[str],
    explanatory_columns: Sequence[str],
    lon_col: str,
    lat_col: str,
    time_col: str,
    sheet_name: str | int | None = 0,
) -> list[dict]:
    issues: list[dict] = []
    try:
        df = read_table(path, sheet_name)
    except Exception as exc:
        add_issue(issues, label, "error", "file", f"Cannot read table: {exc}")
        return issues
    required = [lon_col, lat_col, time_col, *response_columns, *explanatory_columns]
    for col in required:
        if col not in df.columns:
            add_issue(issues, label, "error", col, "Required model column is missing.")
            continue
        values = pd.to_numeric(df[col], errors="coerce") if col not in {"Province", "province"} else df[col]
        if col in [lon_col, lat_col, time_col, *response_columns, *explanatory_columns] and pd.to_numeric(df[col], errors="coerce").isna().any():
            add_issue(issues, label, "error", col, "Column contains missing or non-numeric values.")
    if len(df) < len(explanatory_columns) + 5:
        add_issue(issues, label, "warning", "n", "Small sample size relative to number of explanatory variables.")
    return issues


def write_report(issues: list[dict], output: str | Path) -> pd.DataFrame:
    report = pd.DataFrame(issues, columns=["table", "severity", "field", "message"])
    if report.empty:
        report = pd.DataFrame([{"table": "all", "severity": "ok", "field": "all", "message": "No validation issues detected."}])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() in {".xlsx", ".xls"}:
        report.to_excel(output, index=False)
    else:
        report.to_csv(output, index=False, encoding="utf-8-sig")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate input files for the China agricultural land-transformation workflow.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--cropland", default=None)
    parser.add_argument("--sown", default=None)
    parser.add_argument("--model-table", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--responses", nargs="+", default=["CWE", "CS", "HQ", "NDR", "SDR", "RHI", "CP"])
    parser.add_argument("--explanatory", nargs="+", default=["SSN", "GM", "IPLG", "RW"])
    parser.add_argument("--lon-col", default="longitude")
    parser.add_argument("--lat-col", default="latitude")
    parser.add_argument("--time-col", default="year")
    parser.add_argument("--sheet-name", default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    issues = []
    if args.cropland:
        issues.extend(validate_year_table(args.cropland, "cropland_extent", args.start_year, args.end_year, args.sheet_name))
    if args.sown:
        issues.extend(validate_year_table(args.sown, "crop_sown_area", args.start_year, args.end_year, args.sheet_name))
    if args.model_table:
        issues.extend(validate_model_table(args.model_table, "model_table", args.responses, args.explanatory, args.lon_col, args.lat_col, args.time_col, args.sheet_name))
    report = write_report(issues, args.output)
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
