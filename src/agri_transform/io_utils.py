"""Input/output helpers used across the repository."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence
import re

import numpy as np
import pandas as pd


YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def read_table(path: str | Path, sheet_name: str | int | None = 0) -> pd.DataFrame:
    """Read an Excel or CSV table.

    Parameters
    ----------
    path:
        Input path ending in .xlsx, .xls or .csv.
    sheet_name:
        Excel sheet name or index. Ignored for CSV files.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name)
    if suffix == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    raise ValueError(f"Unsupported table format: {suffix}")


def write_table(df: pd.DataFrame, path: str | Path, index: bool = False) -> None:
    """Write a table to Excel or CSV based on file extension."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df.to_excel(path, index=index)
    elif suffix == ".csv":
        df.to_csv(path, index=index, encoding="utf-8-sig")
    else:
        raise ValueError(f"Unsupported output format: {suffix}")


def find_first_matching_column(columns: Iterable, candidates: Sequence[str]) -> str | int | None:
    """Find the first column whose stripped, lower-case text matches a candidate."""
    mapping = {str(col).strip().lower(): col for col in columns}
    for candidate in candidates:
        key = str(candidate).strip().lower()
        if key in mapping:
            return mapping[key]
    return None


def detect_year_columns(columns: Iterable, start_year: int, end_year: int) -> list:
    """Detect annual columns whose names are years within the requested interval."""
    year_cols = []
    for col in columns:
        text = str(col).strip()
        year = None
        if YEAR_RE.fullmatch(text):
            year = int(text)
        else:
            try:
                value = float(text)
                if value.is_integer():
                    year = int(value)
            except Exception:
                year = None
        if year is not None and start_year <= year <= end_year:
            year_cols.append(col)
    return sorted(year_cols, key=lambda x: int(float(str(x))))


def prepare_wide_year_table(
    path: str | Path,
    value_name: str,
    start_year: int,
    end_year: int,
    sheet_name: str | int | None = 0,
    value_scale: float = 1.0,
    province_candidates: Sequence[str] = ("Province", "province", "Region", "region", "省份", "地区"),
    id_candidates: Sequence[str] = ("FID", "fid", "ID", "Id", "ORIG_FID"),
) -> tuple[pd.DataFrame, list[int]]:
    """Load a province-by-year table and return a clean wide table.

    Expected input format: FID | Province | 2000 | 2001 | ... | 2023.
    Values are multiplied by ``value_scale``. The returned DataFrame contains
    ``Province`` and integer year columns.
    """
    df = read_table(path, sheet_name=sheet_name)
    province_col = find_first_matching_column(df.columns, province_candidates)
    if province_col is None:
        raise ValueError(f"Could not find a province/region column in {path}")

    id_col = find_first_matching_column(df.columns, id_candidates)
    year_cols = detect_year_columns(df.columns, start_year, end_year)
    expected_years = list(range(start_year, end_year + 1))
    found_years = [int(float(str(col))) for col in year_cols]
    missing = [year for year in expected_years if year not in found_years]
    if missing:
        raise ValueError(f"Missing year columns in {path}: {missing}")

    keep_cols = [col for col in [id_col, province_col] if col is not None] + year_cols
    df = df[keep_cols].copy()
    rename_map = {province_col: "Province"}
    if id_col is not None:
        rename_map[id_col] = "FID"
    for col in year_cols:
        rename_map[col] = int(float(str(col)))
    df = df.rename(columns=rename_map)
    df["Province"] = df["Province"].astype(str).str.strip()

    for year in expected_years:
        df[year] = pd.to_numeric(df[year], errors="coerce") * value_scale

    if df[expected_years].isna().any().any():
        df[expected_years] = df[expected_years].T.interpolate(method="linear", limit_direction="both").T

    return df[["Province"] + expected_years], expected_years


def wide_to_long(df: pd.DataFrame, value_name: str, years: Sequence[int]) -> pd.DataFrame:
    """Convert a province-by-year table to long format."""
    return df.melt(id_vars=["Province"], value_vars=list(years), var_name="Year", value_name=value_name)


def safe_percent_change(new: float, old: float) -> float:
    """Percentage change with NaN for zero or missing baseline."""
    if pd.isna(old) or old == 0:
        return np.nan
    return (new - old) / old * 100.0
