#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Detailed extraction of CACD-derived cropland extent by province.

This script converts annual cropland rasters into a province-by-year cropland
extent table. It is designed for China’s 30-m Annual Cropland Dataset (CACD) or
other binary/multi-class annual LULC products.

Two processing modes are supported.

1. Raster-zone mode (recommended):
   Requires rasterio, geopandas and rasterstats. For each annual raster, the
   script calculates cropland pixels within each province polygon and converts
   pixel counts to area.

2. Tabular pass-through mode:
   If a province-by-year cropland table has already been prepared externally,
   the script can validate and standardize it into the format used by later
   scripts.

The output table follows:
    Province, 2000, 2001, ..., 2023
where values are in kha by default.
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


def configure_logging(verbose: bool = True) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(asctime)s | %(levelname)s | %(message)s")


def find_raster_for_year(raster_dir: Path, year: int, suffixes: Sequence[str] = (".tif", ".tiff")) -> Path:
    candidates = []
    for suffix in suffixes:
        candidates.extend(raster_dir.glob(f"*{year}*{suffix}"))
    if not candidates:
        raise FileNotFoundError(f"No raster file containing year {year} was found in {raster_dir}")
    if len(candidates) > 1:
        logging.warning("Multiple raster candidates for %s; using %s", year, candidates[0])
    return candidates[0]


def infer_province_field(gdf, requested: str | None = None) -> str:
    if requested and requested in gdf.columns:
        return requested
    candidates = ["Province", "province", "NAME", "Name", "NAME_1", "NL_NAME_1"]
    for c in candidates:
        if c in gdf.columns:
            return c
    raise ValueError(f"Could not infer province field from columns: {list(gdf.columns)}")


def cropland_area_from_rasters(
    raster_dir: str | Path,
    province_path: str | Path,
    start_year: int,
    end_year: int,
    output: str | Path,
    province_field: str | None = None,
    cropland_values: Sequence[int | float] = (1,),
    output_unit: str = "kha",
) -> pd.DataFrame:
    try:
        import geopandas as gpd
        import rasterio
        from rasterstats import zonal_stats
    except Exception as exc:
        raise ImportError("Raster-zone mode requires geopandas, rasterio and rasterstats. Install them or use --prepared-table.") from exc

    raster_dir = Path(raster_dir)
    provinces = gpd.read_file(province_path)
    field = infer_province_field(provinces, province_field)
    provinces = provinces[[field, "geometry"]].copy()
    provinces["Province"] = provinces[field].astype(str).str.strip()
    results = pd.DataFrame({"Province": provinces["Province"]})

    for year in range(start_year, end_year + 1):
        raster_path = find_raster_for_year(raster_dir, year)
        logging.info("Processing %s: %s", year, raster_path.name)
        with rasterio.open(raster_path) as src:
            pixel_area_m2 = abs(src.transform.a * src.transform.e)
            nodata = src.nodata
        stats = zonal_stats(provinces, raster_path, categorical=True, nodata=nodata, all_touched=False)
        areas = []
        for st in stats:
            count = sum(st.get(v, 0) for v in cropland_values)
            area_ha = count * pixel_area_m2 / 10000.0
            if output_unit.lower() == "kha":
                area = area_ha / 1000.0
            elif output_unit.lower() == "ha":
                area = area_ha
            elif output_unit.lower() == "km2":
                area = area_ha / 100.0
            else:
                raise ValueError("output_unit must be kha, ha or km2.")
            areas.append(area)
        results[str(year)] = areas

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() in {".xlsx", ".xls"}:
        results.to_excel(output, index=False)
    else:
        results.to_csv(output, index=False, encoding="utf-8-sig")
    logging.info("Saved cropland extent table: %s", output)
    return results


def standardize_prepared_table(prepared_table: str | Path, output: str | Path, start_year: int, end_year: int, province_col: str = "Province", input_scale_to_kha: float = 1.0) -> pd.DataFrame:
    path = Path(prepared_table)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    if province_col not in df.columns:
        raise ValueError(f"Province column {province_col!r} not found.")
    out = pd.DataFrame({"Province": df[province_col].astype(str).str.strip()})
    for year in range(start_year, end_year + 1):
        col = str(year)
        if col not in df.columns:
            raise ValueError(f"Missing year column {col}")
        out[col] = pd.to_numeric(df[col], errors="coerce") * input_scale_to_kha
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() in {".xlsx", ".xls"}:
        out.to_excel(output, index=False)
    else:
        out.to_csv(output, index=False, encoding="utf-8-sig")
    logging.info("Saved standardized cropland table: %s", output)
    return out


def parse_values(text: str) -> tuple[int | float, ...]:
    values = []
    for item in text.split(","):
        item = item.strip()
        values.append(float(item) if "." in item else int(item))
    return tuple(values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute annual CACD-derived cropland extent by province.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--raster-dir", default=None, help="Directory containing annual CACD rasters.")
    parser.add_argument("--province-boundaries", default=None, help="Province boundary shapefile/GeoPackage.")
    parser.add_argument("--prepared-table", default=None, help="Optional pre-computed province-by-year table to standardize instead of raster processing.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--province-field", default=None)
    parser.add_argument("--cropland-values", default="1")
    parser.add_argument("--output-unit", default="kha", choices=["kha", "ha", "km2"])
    parser.add_argument("--input-scale-to-kha", type=float, default=1.0)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(not args.quiet)
    if args.prepared_table:
        standardize_prepared_table(args.prepared_table, args.output, args.start_year, args.end_year, province_col=args.province_field or "Province", input_scale_to_kha=args.input_scale_to_kha)
    else:
        if not args.raster_dir or not args.province_boundaries:
            raise ValueError("Either --prepared-table or both --raster-dir and --province-boundaries must be provided.")
        cropland_area_from_rasters(args.raster_dir, args.province_boundaries, args.start_year, args.end_year, args.output, province_field=args.province_field, cropland_values=parse_values(args.cropland_values), output_unit=args.output_unit)


if __name__ == "__main__":
    main()
