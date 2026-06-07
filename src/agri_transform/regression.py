"""OLS, GWR, TWR and GTWR models for spatiotemporal association analysis.

The implementation is intentionally transparent. It uses local weighted least
squares and Gaussian kernels so that bandwidth selection, coefficient surfaces
and diagnostics can be inspected and reproduced without proprietary software.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Iterable, Literal, Sequence

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.metrics import r2_score


ModelKind = Literal["OLS", "GWR", "TWR", "GTWR"]


@dataclass
class LocalRegressionResult:
    model: str
    bandwidth_spatial: float | None
    bandwidth_temporal: float | None
    coefficients: pd.DataFrame
    predictions: np.ndarray
    residuals: np.ndarray
    diagnostics: dict[str, float]


def _ensure_2d(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.ndim == 1:
        return values.reshape(-1, 1)
    return values


def add_intercept(X: np.ndarray) -> np.ndarray:
    X = _ensure_2d(X)
    return np.column_stack([np.ones(X.shape[0]), X])


def haversine_distance_km(lon_lat: np.ndarray) -> np.ndarray:
    """Pairwise haversine distance matrix in kilometres."""
    coords = np.radians(np.asarray(lon_lat, dtype=float))
    lon = coords[:, 0]
    lat = coords[:, 1]
    dlon = lon[:, None] - lon[None, :]
    dlat = lat[:, None] - lat[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    return 6371.0088 * c


def normalize_distance_matrix(D: np.ndarray) -> np.ndarray:
    max_val = np.nanmax(D)
    if max_val == 0 or not np.isfinite(max_val):
        return np.zeros_like(D)
    return D / max_val


def gaussian_weights(
    spatial_dist: np.ndarray | None,
    temporal_dist: np.ndarray | None,
    bandwidth_spatial: float | None,
    bandwidth_temporal: float | None,
    model: ModelKind,
) -> np.ndarray:
    """Build a full n x n weight matrix for OLS, GWR, TWR or GTWR."""
    if model == "OLS":
        if spatial_dist is not None:
            n = spatial_dist.shape[0]
        elif temporal_dist is not None:
            n = temporal_dist.shape[0]
        else:
            raise ValueError("At least one distance matrix is required.")
        return np.ones((n, n), dtype=float)

    if model in {"GWR", "GTWR"} and spatial_dist is None:
        raise ValueError("Spatial distance matrix is required for GWR/GTWR.")
    if model in {"TWR", "GTWR"} and temporal_dist is None:
        raise ValueError("Temporal distance matrix is required for TWR/GTWR.")

    terms = []
    if model in {"GWR", "GTWR"}:
        if bandwidth_spatial is None or bandwidth_spatial <= 0:
            raise ValueError("Positive spatial bandwidth is required.")
        terms.append((spatial_dist / bandwidth_spatial) ** 2)
    if model in {"TWR", "GTWR"}:
        if bandwidth_temporal is None or bandwidth_temporal <= 0:
            raise ValueError("Positive temporal bandwidth is required.")
        terms.append((temporal_dist / bandwidth_temporal) ** 2)
    return np.exp(-sum(terms))


def weighted_least_squares(X: np.ndarray, y: np.ndarray, weights: np.ndarray, ridge: float = 1e-8) -> np.ndarray:
    """Solve local weighted least squares with a tiny ridge term for stability."""
    w = np.asarray(weights, dtype=float)
    Xw = X * w[:, None]
    xtwx = X.T @ Xw
    xtwy = X.T @ (w * y)
    xtwx = xtwx + ridge * np.eye(xtwx.shape[0])
    return np.linalg.solve(xtwx, xtwy)


def fit_local_regression(
    X: np.ndarray,
    y: np.ndarray,
    lon: np.ndarray | None = None,
    lat: np.ndarray | None = None,
    time: np.ndarray | None = None,
    model: ModelKind = "GTWR",
    bandwidth_spatial: float | None = 0.1,
    bandwidth_temporal: float | None = 0.3,
    normalize_distances: bool = True,
    variable_names: Sequence[str] | None = None,
) -> LocalRegressionResult:
    """Fit OLS/GWR/TWR/GTWR using local weighted least squares.

    Bandwidths are interpreted in the same units as the distance matrices. When
    ``normalize_distances=True`` (default), spatial and temporal distances are
    scaled to [0, 1], so bandwidths such as 0.11--0.33 are directly comparable
    to the values reported in the manuscript tables.
    """
    X_raw = _ensure_2d(X)
    y = np.asarray(y, dtype=float)
    valid = np.isfinite(y) & np.all(np.isfinite(X_raw), axis=1)
    if not valid.all():
        X_raw = X_raw[valid]
        y = y[valid]
        if lon is not None:
            lon = np.asarray(lon)[valid]
        if lat is not None:
            lat = np.asarray(lat)[valid]
        if time is not None:
            time = np.asarray(time)[valid]

    X_design = add_intercept(X_raw)
    n, p = X_design.shape
    if variable_names is None:
        variable_names = [f"x{i + 1}" for i in range(X_raw.shape[1])]
    coef_names = ["Intercept"] + list(variable_names)

    spatial_dist = None
    temporal_dist = None
    if lon is not None and lat is not None:
        spatial_dist = haversine_distance_km(np.column_stack([lon, lat]))
        if normalize_distances:
            spatial_dist = normalize_distance_matrix(spatial_dist)
    if time is not None:
        time = np.asarray(time, dtype=float).reshape(-1, 1)
        temporal_dist = cdist(time, time, metric="euclidean")
        if normalize_distances:
            temporal_dist = normalize_distance_matrix(temporal_dist)

    W = gaussian_weights(spatial_dist, temporal_dist, bandwidth_spatial, bandwidth_temporal, model)
    coefficients = np.zeros((n, p), dtype=float)
    predictions = np.zeros(n, dtype=float)
    for i in range(n):
        beta = weighted_least_squares(X_design, y, W[i])
        coefficients[i] = beta
        predictions[i] = X_design[i] @ beta
    residuals = y - predictions
    rss = float(np.sum(residuals**2))
    tss = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - rss / tss if tss > 0 else np.nan
    adj_r2 = 1 - (1 - r2) * (n - 1) / max(n - p, 1) if np.isfinite(r2) else np.nan
    sigma = float(np.sqrt(rss / max(n - p, 1)))
    # Practical AICc approximation for local regression diagnostics.
    aic = n * np.log(max(rss / n, np.finfo(float).tiny)) + 2 * p
    aicc = aic + (2 * p * (p + 1)) / max(n - p - 1, 1)
    diagnostics = {
        "n": float(n),
        "p": float(p),
        "residual_squares": rss,
        "sigma": sigma,
        "aic": float(aic),
        "aicc": float(aicc),
        "r2": float(r2),
        "adjusted_r2": float(adj_r2),
    }
    coef_df = pd.DataFrame(coefficients, columns=coef_names)
    return LocalRegressionResult(model, bandwidth_spatial, bandwidth_temporal, coef_df, predictions, residuals, diagnostics)


def grid_search_bandwidths(
    X: np.ndarray,
    y: np.ndarray,
    lon: np.ndarray | None,
    lat: np.ndarray | None,
    time: np.ndarray | None,
    model: ModelKind,
    spatial_grid: Iterable[float] | None = None,
    temporal_grid: Iterable[float] | None = None,
    variable_names: Sequence[str] | None = None,
) -> tuple[LocalRegressionResult, pd.DataFrame]:
    """Select bandwidths by minimum AICc over a grid."""
    if model == "GWR":
        spatial_grid = list(spatial_grid or np.linspace(0.05, 0.5, 10))
        temporal_grid = [None]
    elif model == "TWR":
        spatial_grid = [None]
        temporal_grid = list(temporal_grid or np.linspace(0.05, 0.8, 10))
    elif model == "GTWR":
        spatial_grid = list(spatial_grid or np.linspace(0.05, 0.5, 10))
        temporal_grid = list(temporal_grid or np.linspace(0.05, 0.8, 10))
    else:
        spatial_grid = [None]
        temporal_grid = [None]

    records = []
    best: LocalRegressionResult | None = None
    for bs, bt in product(spatial_grid, temporal_grid):
        try:
            res = fit_local_regression(
                X=X,
                y=y,
                lon=lon,
                lat=lat,
                time=time,
                model=model,
                bandwidth_spatial=bs,
                bandwidth_temporal=bt,
                variable_names=variable_names,
            )
            records.append({"model": model, "bandwidth_spatial": bs, "bandwidth_temporal": bt, **res.diagnostics})
            if best is None or res.diagnostics["aicc"] < best.diagnostics["aicc"]:
                best = res
        except Exception as exc:
            records.append({"model": model, "bandwidth_spatial": bs, "bandwidth_temporal": bt, "error": str(exc)})
    if best is None:
        raise RuntimeError("No bandwidth candidate produced a valid model.")
    return best, pd.DataFrame(records)


def run_models_from_table(
    input_table: str | Path,
    output_dir: str | Path,
    response_columns: Sequence[str],
    explanatory_columns: Sequence[str],
    lon_col: str = "longitude",
    lat_col: str = "latitude",
    time_col: str = "year",
    cp_column: str = "CP",
    spatial_grid: Sequence[float] | None = None,
    temporal_grid: Sequence[float] | None = None,
) -> pd.DataFrame:
    """Run GTWR for spatially structured responses and TWR for CP by convention.

    The input table should contain one row per province-year observation.
    Required columns include coordinates, year, explanatory components and
    response variables.
    """
    input_table = Path(input_table)
    if input_table.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(input_table)
    else:
        df = pd.read_csv(input_table)

    X = df[list(explanatory_columns)].to_numpy(float)
    lon = df[lon_col].to_numpy(float)
    lat = df[lat_col].to_numpy(float)
    time = df[time_col].to_numpy(float)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_records = []
    for response in response_columns:
        model = "TWR" if response == cp_column else "GTWR"
        y = df[response].to_numpy(float)
        best, search = grid_search_bandwidths(
            X=X,
            y=y,
            lon=lon,
            lat=lat,
            time=time,
            model=model,
            spatial_grid=spatial_grid,
            temporal_grid=temporal_grid,
            variable_names=explanatory_columns,
        )
        coef = best.coefficients.copy()
        for col in [lon_col, lat_col, time_col]:
            coef[col] = df[col].values[: len(coef)]
        if "Province" in df.columns:
            coef["Province"] = df["Province"].values[: len(coef)]
        coef.to_csv(output_dir / f"{response}_{model}_local_coefficients.csv", index=False)
        search.to_csv(output_dir / f"{response}_{model}_bandwidth_search.csv", index=False)
        summary_records.append(
            {
                "dependent_variable": response,
                "model": model,
                "bandwidth_spatial": best.bandwidth_spatial,
                "bandwidth_temporal": best.bandwidth_temporal,
                **best.diagnostics,
            }
        )
    summary = pd.DataFrame(summary_records)
    summary.to_csv(output_dir / "model_diagnostics_summary.csv", index=False)
    return summary
