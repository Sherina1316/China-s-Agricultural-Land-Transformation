#!/usr/bin/env python
"""Calculate global Moran's I for response variables."""

from __future__ import annotations

import argparse

from agri_transform.spatial import run_moran_from_points


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV/XLSX table with longitude and latitude columns.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--lon-col", default="lon")
    parser.add_argument("--lat-col", default="lat")
    parser.add_argument("--value-columns", nargs="*", default=None, help="Variables to test. If omitted, all numeric variables except coordinates are used.")
    args = parser.parse_args()
    run_moran_from_points(args.input, args.output, lon_col=args.lon_col, lat_col=args.lat_col, value_columns=args.value_columns)


if __name__ == "__main__":
    main()
