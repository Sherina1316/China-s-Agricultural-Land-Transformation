#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Run the complete reproducible workflow from a YAML configuration file.

This orchestrator intentionally prints each command before running it. It is
useful for reviewers because the full analysis can be reproduced step by step or
executed as a single workflow.

Typical sequence
----------------
1. Validate inputs.
2. Prepare or extract CACD-derived cropland extent by province.
3. Run cropland extent--crop sown area diagnostics and exact decomposition.
4. Run PCA with varimax rotation for agricultural-use indicators.
5. Test spatial autocorrelation for socio-environmental outcomes.
6. Run GWR/TWR/GTWR local-regression models.
7. Run coefficient uncertainty diagnostics.
8. Generate publication-style diagnostic figures.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
import yaml


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get(cfg: dict, *keys, default=None):
    cur = cfg
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def run(command: list[str], dry_run: bool = False) -> None:
    print("\n$ " + " ".join(map(str, command)))
    if not dry_run:
        subprocess.run(list(map(str, command)), check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the complete China agricultural land-transformation workflow.")
    parser.add_argument("--config", default="configs/config.example.yaml")
    parser.add_argument("--skip-cacd", action="store_true", help="Skip raster extraction and use the configured processed cropland table.")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_yaml(args.config)
    py = sys.executable

    start = str(get(cfg, "project", "start_year", default=2000))
    end = str(get(cfg, "project", "end_year", default=2023))
    threshold = str(get(cfg, "project", "stable_threshold_percent", default=5.0))
    out_dir = Path(get(cfg, "paths", "output_dir", default="outputs"))
    out_dir.mkdir(parents=True, exist_ok=True)

    cropland_processed = Path(get(cfg, "paths", "cropland_extent_processed", default="data/processed/cropland_extent_by_province.csv"))
    sown_table = Path(get(cfg, "paths", "crop_sown_area", default="data/raw/crop_sown_area_by_province.csv"))
    pca_table = Path(get(cfg, "paths", "pca_indicator_table", default="data/processed/pca_indicators.csv"))
    model_table = Path(get(cfg, "paths", "gtwr_model_table", default="data/processed/gtwr_model_table.csv"))

    responses = get(cfg, "variables", "response_variables", default=["CWE", "CS", "HQ", "NDR", "SDR", "RHI", "CP"])
    explanatory = get(cfg, "variables", "explanatory_variables", default=["SSN", "GM", "IPLG", "RW"])
    lon_col = get(cfg, "variables", "coordinate_columns", "longitude", default="longitude")
    lat_col = get(cfg, "variables", "coordinate_columns", "latitude", default="latitude")
    time_col = get(cfg, "variables", "time_column", default="year")

    if not args.skip_validation:
        run([
            py, "scripts/00_validate_inputs.py",
            "--cropland", cropland_processed,
            "--sown", sown_table,
            "--model-table", model_table,
            "--output", out_dir / "validation" / "input_validation_report.csv",
            "--start-year", start,
            "--end-year", end,
            "--responses", *responses,
            "--explanatory", *explanatory,
            "--lon-col", lon_col,
            "--lat-col", lat_col,
            "--time-col", time_col,
        ], args.dry_run)

    if not args.skip_cacd:
        if get(cfg, "paths", "prepared_cropland_table", default=None):
            run([
                py, "scripts/01_compute_cropland_extent.py",
                "--prepared-table", get(cfg, "paths", "prepared_cropland_table"),
                "--output", cropland_processed,
                "--start-year", start,
                "--end-year", end,
            ], args.dry_run)
        else:
            run([
                py, "scripts/01_compute_cropland_extent.py",
                "--raster-dir", get(cfg, "paths", "raw_cacd_rasters"),
                "--province-boundaries", get(cfg, "paths", "province_boundaries"),
                "--output", cropland_processed,
                "--start-year", start,
                "--end-year", end,
                "--cropland-values", str(get(cfg, "parameters", "cropland_values", default="1")),
            ], args.dry_run)

    diagnostic_dir = out_dir / "cropland_sown_diagnostics"
    run([
        py, "scripts/02_cropland_sown_area_diagnostics.py",
        "--cropland", cropland_processed,
        "--sown", sown_table,
        "--output-dir", diagnostic_dir,
        "--start-year", start,
        "--end-year", end,
        "--stable-threshold", threshold,
    ], args.dry_run)

    pca_dir = out_dir / "pca"
    run([
        py, "scripts/03_pca_varimax.py",
        "--input", pca_table,
        "--output-dir", pca_dir,
        "--component-labels", "SSN,GM,IPLG,RW",
    ], args.dry_run)

    moran_dir = out_dir / "spatial_autocorrelation"
    run([
        py, "scripts/04_spatial_autocorrelation.py",
        "--input", model_table,
        "--output", moran_dir / "moran_i_summary.csv",
        "--lon-col", lon_col,
        "--lat-col", lat_col,
        "--year-col", time_col,
        "--value-columns", *responses,
        "--plot",
    ], args.dry_run)

    regression_dir = out_dir / "gtwr_gwr_twr"
    run([
        py, "scripts/05_gtwr_gwr_twr.py",
        "--input", model_table,
        "--output-dir", regression_dir,
        "--responses", *responses,
        "--explanatory", *explanatory,
        "--lon-col", lon_col,
        "--lat-col", lat_col,
        "--time-col", time_col,
        "--twr-responses", "CP",
    ], args.dry_run)

    # The combined coefficient table is used for general uncertainty diagnostics.
    coef_table = regression_dir / "all_local_coefficients_long.csv"
    unc_dir = out_dir / "uncertainty"
    run([
        py, "scripts/06_uncertainty_analysis.py",
        "--coefficients", coef_table,
        "--output-dir", unc_dir,
        "--coefficient-columns", "coef_SSN", "coef_GM", "coef_IPLG", "coef_RW",
    ], args.dry_run)

    if not args.skip_figures:
        fig_dir = out_dir / "publication_figures"
        run([
            py, "scripts/07_plot_publication_figures.py",
            "phase-space",
            "--national-timeseries", diagnostic_dir / "tables" / "national_timeseries_coupling.csv",
            "--output-base", fig_dir / "national_phase_space",
            "--threshold", threshold,
        ], args.dry_run)
        run([
            py, "scripts/07_plot_publication_figures.py",
            "decomposition",
            "--cumulative-decomposition", diagnostic_dir / "tables" / "national_cumulative_sown_area_decomposition.csv",
            "--output-base", fig_dir / "national_cumulative_decomposition",
        ], args.dry_run)


if __name__ == "__main__":
    main()
