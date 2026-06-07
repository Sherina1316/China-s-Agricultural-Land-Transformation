#!/usr/bin/env python
"""Run cropland extent--crop sown area diagnostics and decomposition."""

from __future__ import annotations

import argparse

from agri_transform.diagnostics import run_diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cropland", required=True, help="Province-by-year CACD-derived cropland extent table, in kha.")
    parser.add_argument("--sown", required=True, help="Province-by-year statistical crop sown-area table, in kha.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--stable-threshold", type=float, default=5.0, help="Stable threshold in percent.")
    parser.add_argument("--sheet-name", default=0)
    args = parser.parse_args()
    run_diagnostics(
        cropland_file=args.cropland,
        sown_file=args.sown,
        output_dir=args.output_dir,
        start_year=args.start_year,
        end_year=args.end_year,
        stable_threshold_percent=args.stable_threshold,
        sheet_name=args.sheet_name,
    )


if __name__ == "__main__":
    main()
