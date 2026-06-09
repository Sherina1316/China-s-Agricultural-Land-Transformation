"""Input validation and reproducibility checks.

These utilities are intentionally lightweight. They do not modify raw data; they
only check whether the key tables used in the manuscript workflow have the
expected columns, year coverage, numeric types and missing-value patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .io_utils import read_table, detect_year_columns


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    table: str
    message: str


def _as_issue(table: str, message: str, severity: str = "ERROR") -> ValidationIssue:
    return ValidationIssue(severity=severity, table=table, message=message)


def validate_year_table(
    path: str | Path,
    table_name: str,
    start_year: int,
    end_year: int,
    province_column_candidates: Sequence[str] = ("Province", "province", "Region", "region", "省份", "地区"),
    sheet_name: str | int | None = 0,
) -> list[ValidationIssue]:
    """Validate a province-by-year table.

    Expected structure: Province | 2000 | 2001 | ... | 2023. Additional columns
    such as FID are allowed.
    """
    issues: list[ValidationIssue] = []
    try:
        df = read_table(path, sheet_name=sheet_name)
    except Exception as exc:  # noqa: BLE001
        return [_as_issue(table_name, f"Could not read table: {exc}")]

    lower_cols = {str(c).strip().lower(): c for c in df.columns}
    if not any(c.lower() in lower_cols for c in province_column_candidates):
        issues.append(_as_issue(table_name, "No province/region column was detected."))

    year_cols = detect_year_columns(df.columns, start_year, end_year)
    found = {int(float(str(c))) for c in year_cols}
    missing = [y for y in range(start_year, end_year + 1) if y not in found]
    if missing:
        issues.append(_as_issue(table_name, f"Missing year columns: {missing}"))

    for c in year_cols:
        values = pd.to_numeric(df[c], errors="coerce")
        if values.isna().any():
            issues.append(_as_issue(table_name, f"Column {c} contains non-numeric or missing values.", "WARNING"))
        if (values < 0).any():
            issues.append(_as_issue(table_name, f"Column {c} contains negative values.", "WARNING"))
    return issues


def validate_model_table(
    path: str | Path,
    response_columns: Sequence[str],
    explanatory_columns: Sequence[str],
    coordinate_columns: Sequence[str] = ("longitude", "latitude", "year"),
    sheet_name: str | int | None = 0,
) -> list[ValidationIssue]:
    """Validate the province-year table used for GWR/TWR/GTWR models."""
    issues: list[ValidationIssue] = []
    try:
        df = read_table(path, sheet_name=sheet_name)
    except Exception as exc:  # noqa: BLE001
        return [_as_issue("model_table", f"Could not read table: {exc}")]

    required = list(coordinate_columns) + list(response_columns) + list(explanatory_columns)
    missing = [c for c in required if c not in df.columns]
    if missing:
        issues.append(_as_issue("model_table", f"Missing required columns: {missing}"))
        return issues

    for c in required:
        values = pd.to_numeric(df[c], errors="coerce")
        if values.isna().any():
            issues.append(_as_issue("model_table", f"Column {c} contains missing or non-numeric values.", "WARNING"))

    if "year" in df.columns:
        years = sorted(pd.to_numeric(df["year"], errors="coerce").dropna().astype(int).unique().tolist())
        if len(years) < 2:
            issues.append(_as_issue("model_table", "The model table contains fewer than two unique years.", "WARNING"))
    return issues


def issues_to_dataframe(issues: Iterable[ValidationIssue]) -> pd.DataFrame:
    """Convert validation issues to a tabular report."""
    return pd.DataFrame([issue.__dict__ for issue in issues], columns=["severity", "table", "message"])


def write_validation_report(issues: Iterable[ValidationIssue], output_path: str | Path) -> pd.DataFrame:
    """Write validation issues to CSV/XLSX and return the report."""
    report = issues_to_dataframe(issues)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in {".xlsx", ".xls"}:
        report.to_excel(output_path, index=False)
    else:
        report.to_csv(output_path, index=False, encoding="utf-8-sig")
    return report
