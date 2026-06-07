#!/usr/bin/env python
"""Compute annual CACD-derived cropland extent by province.

Example:
python scripts/01_compute_cropland_extent.py \
  --raster-dir data/raw/CACD \
  --province-shp data/boundaries/china_provinces.shp \
  --output data/processed/cropland_extent_by_province.csv \
  --start-year 2000 --end-year 2023 --province-field Province
"""

from __future__ import annotations

import argparse

from agri_transform.area import compute_province_cropland_area


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raster-dir", required=True, help="Directory containing annual binary cropland GeoTIFFs.")
    parser.add_argument("--province-shp", required=True, help="Province boundary shapefile/GeoPackage.")
    parser.add_argument("--output", required=True, help="Output CSV/XLSX path.")
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--province-field", default=None, help="Province name field. If omitted, common fields are detected.")
    parser.add_argument("--cropland-values", default="1", help="Comma-separated raster values treated as cropland. Default: 1")
    args = parser.parse_args()

    values = tuple(float(v) if "." in v else int(v) for v in args.cropland_values.split(","))
    compute_province_cropland_area(
        raster_dir=args.raster_dir,
        province_shp=args.province_shp,
        output_path=args.output,
        start_year=args.start_year,
        end_year=args.end_year,
        province_field=args.province_field,
        cropland_values=values,
    )


if __name__ == "__main__":
    main()
