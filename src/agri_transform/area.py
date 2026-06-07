"""Cropland extent extraction from annual binary cropland rasters."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Geod
from rasterio.mask import mask
from tqdm import tqdm


_YEAR_RE = re.compile(r"(19|20)\d{2}")


def find_annual_rasters(raster_dir: str | Path, start_year: int, end_year: int) -> dict[int, Path]:
    """Locate annual .tif/.tiff files by parsing the year from file names."""
    raster_dir = Path(raster_dir)
    if not raster_dir.exists():
        raise FileNotFoundError(f"Raster directory not found: {raster_dir}")
    paths = list(raster_dir.rglob("*.tif")) + list(raster_dir.rglob("*.tiff"))
    result: dict[int, Path] = {}
    for path in sorted(paths):
        matches = _YEAR_RE.findall(path.name)
        # Regex with group returns partial; parse again with full expression.
        years = re.findall(r"(19\d{2}|20\d{2})", path.name)
        for y_text in years:
            year = int(y_text)
            if start_year <= year <= end_year and year not in result:
                result[year] = path
    missing = [year for year in range(start_year, end_year + 1) if year not in result]
    if missing:
        raise FileNotFoundError(f"Missing annual cropland rasters for years: {missing}")
    return result


def _row_pixel_areas_kha(src: rasterio.io.DatasetReader, rows: Iterable[int], col_count: int) -> dict[int, float]:
    """Estimate row-specific pixel area for geographic rasters using geodesic polygons.

    Returns area in thousand hectares (kha) for one pixel in each requested row.
    """
    geod = Geod(ellps="WGS84")
    transform = src.transform
    areas = {}
    for row in rows:
        # Build one representative pixel polygon at column 0.
        x0, y0 = transform * (0, row)
        x1, y1 = transform * (1, row + 1)
        xs = [x0, x1, x1, x0]
        ys = [y0, y0, y1, y1]
        area_m2, _ = geod.polygon_area_perimeter(xs, ys)
        areas[row] = abs(area_m2) / 10_000_000.0
    return areas


def cropland_area_for_geometry(
    raster_path: str | Path,
    geometry,
    cropland_values: tuple[int | float, ...] = (1,),
) -> float:
    """Calculate cropland area in thousand hectares for a geometry.

    The function supports projected rasters and geographic rasters. For projected
    rasters, pixel area is calculated directly from the affine transform. For
    geographic rasters, row-specific geodesic pixel areas are used to avoid the
    common error of treating degrees as metres.
    """
    raster_path = Path(raster_path)
    with rasterio.open(raster_path) as src:
        out_image, out_transform = mask(src, [geometry], crop=True, nodata=src.nodata, filled=True)
        arr = out_image[0]
        valid = np.isin(arr, cropland_values)
        if not np.any(valid):
            return 0.0

        if src.crs is not None and src.crs.is_projected:
            pixel_area_kha = abs(src.transform.a * src.transform.e) / 10_000_000.0
            return float(valid.sum() * pixel_area_kha)

        # Geographic CRS: compute geodesic area per output row.
        # Use the cropped transform, not the source transform.
        geod = Geod(ellps="WGS84")
        total_kha = 0.0
        for r in range(valid.shape[0]):
            count = int(valid[r, :].sum())
            if count == 0:
                continue
            x0, y0 = out_transform * (0, r)
            x1, y1 = out_transform * (1, r + 1)
            area_m2, _ = geod.polygon_area_perimeter([x0, x1, x1, x0], [y0, y0, y1, y1])
            total_kha += count * abs(area_m2) / 10_000_000.0
        return float(total_kha)


def compute_province_cropland_area(
    raster_dir: str | Path,
    province_shp: str | Path,
    output_path: str | Path,
    start_year: int = 2000,
    end_year: int = 2023,
    province_field: str | None = None,
    cropland_values: tuple[int | float, ...] = (1,),
) -> pd.DataFrame:
    """Compute annual CACD-derived cropland extent by province.

    Output format: Province | 2000 | 2001 | ... | 2023, values in kha.
    """
    raster_paths = find_annual_rasters(raster_dir, start_year, end_year)
    gdf = gpd.read_file(province_shp)
    if province_field is None:
        candidates = ["Province", "province", "name", "NAME", "省份", "地区"]
        province_field = next((c for c in candidates if c in gdf.columns), None)
    if province_field is None:
        raise ValueError("Could not identify a province name field. Please pass province_field explicitly.")

    records = []
    for _, row in tqdm(gdf.iterrows(), total=len(gdf), desc="Provinces"):
        rec = {"Province": str(row[province_field])}
        geom = row.geometry
        for year, raster_path in raster_paths.items():
            with rasterio.open(raster_path) as src:
                geom_use = geom
                if gdf.crs is not None and src.crs is not None and gdf.crs != src.crs:
                    geom_use = gpd.GeoSeries([geom], crs=gdf.crs).to_crs(src.crs).iloc[0]
            rec[year] = cropland_area_for_geometry(raster_path, geom_use, cropland_values=cropland_values)
        records.append(rec)

    out = pd.DataFrame(records).sort_values("Province")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in {".xlsx", ".xls"}:
        out.to_excel(output_path, index=False)
    else:
        out.to_csv(output_path, index=False, encoding="utf-8-sig")
    return out
