"""Spatial autocorrelation diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import geopandas as gpd
import numpy as np
import pandas as pd


def moran_by_year(
    gdf: gpd.GeoDataFrame,
    value_columns: Sequence[str],
    id_column: str | None = None,
    queen_weights: bool = True,
    permutations: int = 999,
) -> pd.DataFrame:
    """Calculate global Moran's I for each variable column.

    The function requires libpysal and esda. It returns Moran's I, z-score and
    pseudo p-value for each requested variable.
    """
    try:
        from libpysal.weights import Queen, KNN
        from esda.moran import Moran
    except ImportError as exc:
        raise ImportError("Spatial autocorrelation requires libpysal and esda.") from exc

    if queen_weights:
        weights = Queen.from_dataframe(gdf, use_index=True)
    else:
        weights = KNN.from_dataframe(gdf, k=4)
    weights.transform = "R"

    records = []
    for col in value_columns:
        values = pd.to_numeric(gdf[col], errors="coerce").values
        valid = np.isfinite(values)
        if valid.sum() != len(values):
            sub = gdf.loc[valid].copy()
            if queen_weights:
                weights_sub = Queen.from_dataframe(sub, use_index=True)
            else:
                weights_sub = KNN.from_dataframe(sub, k=4)
            weights_sub.transform = "R"
            moran = Moran(values[valid], weights_sub, permutations=permutations)
        else:
            moran = Moran(values, weights, permutations=permutations)
        records.append(
            {
                "indicator": col,
                "moran_i": float(moran.I),
                "z_score": float(moran.z_sim),
                "p_value": float(moran.p_sim),
                "significant_95": bool(moran.p_sim < 0.05),
            }
        )
    return pd.DataFrame(records)


def run_moran_from_points(
    input_file: str | Path,
    output_file: str | Path,
    lon_col: str = "lon",
    lat_col: str = "lat",
    value_columns: Sequence[str] | None = None,
    crs: str = "EPSG:4326",
) -> pd.DataFrame:
    """Run Moran's I from a table containing point coordinates."""
    input_file = Path(input_file)
    if input_file.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(input_file)
    elif input_file.suffix.lower() == ".csv":
        df = pd.read_csv(input_file)
    else:
        raise ValueError("Input must be .xlsx, .xls or .csv")
    if value_columns is None:
        value_columns = [c for c in df.columns if c not in {lon_col, lat_col} and pd.api.types.is_numeric_dtype(df[c])]
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon_col], df[lat_col]), crs=crs)
    out = moran_by_year(gdf, value_columns=value_columns)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_file, index=False, encoding="utf-8-sig")
    return out
