#!/usr/bin/env python
"""Plot cropland extent--sown area diagnostics and coefficient heatmaps."""

from __future__ import annotations

import argparse
import pandas as pd

from agri_transform.figures import plot_cropland_sown_diagnostics, plot_model_heatmap


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_diag = sub.add_parser("cropland-sown", help="Plot cropland-sown diagnostic figure.")
    p_diag.add_argument("--province-summary", required=True)
    p_diag.add_argument("--national-timeseries", required=True)
    p_diag.add_argument("--output-base", required=True)

    p_heat = sub.add_parser("heatmap", help="Plot local coefficient heatmap.")
    p_heat.add_argument("--coefficients", required=True)
    p_heat.add_argument("--output-base", required=True)
    p_heat.add_argument("--coefficient-columns", nargs="+", default=["SSN", "GM", "IPLG", "RW"])

    args = parser.parse_args()
    if args.command == "cropland-sown":
        province = pd.read_csv(args.province_summary)
        national = pd.read_csv(args.national_timeseries)
        plot_cropland_sown_diagnostics(province, national, args.output_base)
    elif args.command == "heatmap":
        plot_model_heatmap(args.coefficients, args.output_base, coefficient_columns=args.coefficient_columns)


if __name__ == "__main__":
    main()
