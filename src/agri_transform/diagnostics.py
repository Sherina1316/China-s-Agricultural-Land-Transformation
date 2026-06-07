"""Cropland extent--crop sown area diagnostics and decomposition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .io_utils import prepare_wide_year_table, safe_percent_change, write_table


@dataclass(frozen=True)
class DiagnosticConfig:
    start_year: int = 2000
    end_year: int = 2023
    stable_threshold_percent: float = 5.0


def classify_change(pct_change: float, threshold: float = 5.0) -> str:
    """Classify a percentage change into Gain, Stable or Loss."""
    if pd.isna(pct_change):
        return "Stable"
    if pct_change > threshold:
        return "Gain"
    if pct_change < -threshold:
        return "Loss"
    return "Stable"


def coupling_type(c_status: str, s_status: str) -> str:
    """Assign a readable cropland extent--sown area coupling type."""
    if c_status == "Gain" and s_status == "Gain":
        return "Joint cropland gain and sown-area increase"
    if c_status == "Stable" and s_status == "Gain":
        return "Sown-area increase under stable cropland extent"
    if c_status == "Loss" and s_status == "Gain":
        return "Sown-area increase under cropland loss"
    if c_status == "Stable" and s_status == "Stable":
        return "Stable utilization"
    if c_status == "Loss" and s_status == "Loss":
        return "Dual decline"
    if c_status == "Gain" and s_status == "Stable":
        return "Cropland gain with stable sown area"
    if c_status == "Gain" and s_status == "Loss":
        return "Cropland gain with sown-area decline"
    if c_status == "Stable" and s_status == "Loss":
        return "Sown-area decline under stable cropland extent"
    return f"{c_status}-{s_status}"


def exact_decomposition(C0: float, C1: float, S0: float, S1: float) -> dict[str, float]:
    """Exact decomposition of crop sown-area change based on S = C * R.

    C is physical cropland extent, S is statistical crop sown area and R=S/C.
    The exact identity is:

        ΔS = R0ΔC + C0ΔR + ΔCΔR

    where R0ΔC is the cropland-extent effect, C0ΔR is the use-intensity
    effect and ΔCΔR is the interaction effect.
    """
    if pd.isna(C0) or pd.isna(C1) or pd.isna(S0) or pd.isna(S1) or C0 == 0 or C1 == 0:
        return {
            "R0": np.nan,
            "R1": np.nan,
            "delta_C": np.nan,
            "delta_S": np.nan,
            "delta_R": np.nan,
            "extent_effect": np.nan,
            "use_intensity_effect": np.nan,
            "interaction_effect": np.nan,
        }
    R0 = S0 / C0
    R1 = S1 / C1
    delta_C = C1 - C0
    delta_S = S1 - S0
    delta_R = R1 - R0
    return {
        "R0": R0,
        "R1": R1,
        "delta_C": delta_C,
        "delta_S": delta_S,
        "delta_R": delta_R,
        "extent_effect": R0 * delta_C,
        "use_intensity_effect": C0 * delta_R,
        "interaction_effect": delta_C * delta_R,
    }


def build_diagnostic_tables(
    cropland_wide: pd.DataFrame,
    sown_wide: pd.DataFrame,
    years: Sequence[int],
    config: DiagnosticConfig = DiagnosticConfig(),
) -> dict[str, pd.DataFrame]:
    """Create province and national diagnostic tables."""
    start_year = config.start_year
    end_year = config.end_year
    threshold = config.stable_threshold_percent

    C = cropland_wide.set_index("Province")[list(years)].copy()
    S = sown_wide.set_index("Province")[list(years)].copy()
    C, S = C.align(S, join="inner", axis=0)

    province_records = []
    for province in C.index:
        C0, C1 = C.loc[province, start_year], C.loc[province, end_year]
        S0, S1 = S.loc[province, start_year], S.loc[province, end_year]
        gC = safe_percent_change(C1, C0)
        gS = safe_percent_change(S1, S0)
        c_status = classify_change(gC, threshold)
        s_status = classify_change(gS, threshold)
        decomp = exact_decomposition(C0, C1, S0, S1)
        province_records.append(
            {
                "Province": province,
                "C_start_kha": C0,
                "C_end_kha": C1,
                "S_start_kha": S0,
                "S_end_kha": S1,
                "cropland_extent_change_pct": gC,
                "crop_sown_area_change_pct": gS,
                "decoupling_index_pct": gS - gC,
                "cropland_extent_status": c_status,
                "crop_sown_area_status": s_status,
                "coupling_type": coupling_type(c_status, s_status),
                **decomp,
            }
        )
    province_summary = pd.DataFrame(province_records)

    national_records = []
    C_nat = C.sum(axis=0)
    S_nat = S.sum(axis=0)
    C0 = C_nat.loc[start_year]
    S0 = S_nat.loc[start_year]
    R0 = S0 / C0
    for year in years:
        C_year = C_nat.loc[year]
        S_year = S_nat.loc[year]
        gC = safe_percent_change(C_year, C0)
        gS = safe_percent_change(S_year, S0)
        decomp = exact_decomposition(C0, C_year, S0, S_year)
        national_records.append(
            {
                "Year": year,
                "national_cropland_extent_kha": C_year,
                "national_crop_sown_area_kha": S_year,
                "agricultural_use_intensity": S_year / C_year,
                "cropland_extent_change_pct_from_start": gC,
                "crop_sown_area_change_pct_from_start": gS,
                "decoupling_index_pct": gS - gC,
                **decomp,
            }
        )
    national_timeseries = pd.DataFrame(national_records)

    annual_records = []
    for year0, year1 in zip(years[:-1], years[1:]):
        decomp = exact_decomposition(C_nat.loc[year0], C_nat.loc[year1], S_nat.loc[year0], S_nat.loc[year1])
        annual_records.append({"start_year": year0, "end_year": year1, **decomp})
    annual_decomposition = pd.DataFrame(annual_records)

    coupling_counts = province_summary["coupling_type"].value_counts().rename_axis("coupling_type").reset_index(name="n_provinces")

    return {
        "province_summary": province_summary,
        "national_timeseries": national_timeseries,
        "annual_decomposition": annual_decomposition,
        "coupling_counts": coupling_counts,
    }


def run_diagnostics(
    cropland_file: str | Path,
    sown_file: str | Path,
    output_dir: str | Path,
    start_year: int = 2000,
    end_year: int = 2023,
    stable_threshold_percent: float = 5.0,
    sheet_name: str | int = 0,
) -> dict[str, pd.DataFrame]:
    """Run the full cropland extent--crop sown area diagnostic workflow."""
    cropland, years = prepare_wide_year_table(cropland_file, "cropland_extent_kha", start_year, end_year, sheet_name)
    sown, _ = prepare_wide_year_table(sown_file, "crop_sown_area_kha", start_year, end_year, sheet_name)
    tables = build_diagnostic_tables(
        cropland,
        sown,
        years,
        DiagnosticConfig(start_year=start_year, end_year=end_year, stable_threshold_percent=stable_threshold_percent),
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        write_table(df, output_dir / f"{name}.csv")
    with pd.ExcelWriter(output_dir / "cropland_sown_area_diagnostics.xlsx") as writer:
        for name, df in tables.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return tables
