#!/usr/bin/env python
"""Run transparent GWR/TWR/GTWR local regression diagnostics.

The default workflow fits GTWR for spatially autocorrelated socio-ecological
responses and TWR for CP, matching the manuscript logic.
"""

from __future__ import annotations

import argparse

from agri_transform.regression import run_models_from_table


def parse_grid(value: str | None):
    if value is None or value.strip() == "":
        return None
    return [float(x) for x in value.split(",")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Province-year modelling table.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--responses", nargs="+", default=["CWE", "CS", "HQ", "NDR", "SDR", "RHI", "CP"])
    parser.add_argument("--explanatory", nargs="+", default=["SSN", "GM", "IPLG", "RW"])
    parser.add_argument("--lon-col", default="longitude")
    parser.add_argument("--lat-col", default="latitude")
    parser.add_argument("--time-col", default="year")
    parser.add_argument("--cp-column", default="CP")
    parser.add_argument("--spatial-grid", default="0.08,0.10,0.11,0.12,0.13,0.15,0.20,0.30")
    parser.add_argument("--temporal-grid", default="0.10,0.20,0.27,0.33,0.50,0.80")
    args = parser.parse_args()
    summary = run_models_from_table(
        input_table=args.input,
        output_dir=args.output_dir,
        response_columns=args.responses,
        explanatory_columns=args.explanatory,
        lon_col=args.lon_col,
        lat_col=args.lat_col,
        time_col=args.time_col,
        cp_column=args.cp_column,
        spatial_grid=parse_grid(args.spatial_grid),
        temporal_grid=parse_grid(args.temporal_grid),
    )
    print(summary)


if __name__ == "__main__":
    main()
