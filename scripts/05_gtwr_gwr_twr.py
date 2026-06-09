#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Detailed GWR/TWR/GTWR local-regression workflow.

The manuscript uses geographically and temporally weighted regression (GTWR) to
examine spatially and temporally heterogeneous associations between PCA-derived,
sown-area-based agricultural-use components and socio-environmental outcomes.
This script provides a transparent implementation of the local-regression logic.
It does not claim causal identification; all coefficients should be interpreted
as local associations conditional on the selected model specification.

Supported model types
---------------------
OLS   : one global coefficient vector for all observations.
GWR   : local coefficients weighted by geographic distance only.
TWR   : local coefficients weighted by temporal distance only.
GTWR  : local coefficients weighted by both geographic and temporal distance.

Kernel function
---------------
For GTWR, the default mixed Gaussian kernel is:

    w_ij = exp[-(d_ij / b_s)^2 - ((t_i - t_j) / b_t)^2]

where d_ij is standardized geographic distance and t_i - t_j is standardized
inter-annual distance. GWR and TWR are special cases using only one distance.

Outputs
-------
For each response variable, the script exports:
    - local coefficients by observation
    - fitted values and residuals
    - bandwidth diagnostics for all candidate bandwidths
    - model summary table including RSS, sigma, AICc, R2 and adjusted R2
    - optional heatmap-ready coefficient table

The implementation uses weighted least squares solved independently for each
observation. Ridge stabilization is used only when a local design matrix is near
singular, and the ridge penalty is reported.
"""

from __future__ import annotations

import argparse
import itertools
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# Logging and style
# -----------------------------------------------------------------------------


def configure_logging(verbose: bool = True) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def set_style(dpi: int = 300) -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "figure.dpi": dpi,
            "savefig.dpi": dpi,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.unicode_minus": False,
        }
    )


# -----------------------------------------------------------------------------
# Data classes
# -----------------------------------------------------------------------------


@dataclass
class LocalRegressionResult:
    response: str
    model: str
    bandwidth_spatial: float | None
    bandwidth_temporal: float | None
    coefficients: pd.DataFrame
    fitted: np.ndarray
    residuals: np.ndarray
    summary: dict[str, float | str | None]
    bandwidth_search: pd.DataFrame


# -----------------------------------------------------------------------------
# I/O helpers
# -----------------------------------------------------------------------------


def read_table(path: str | Path, sheet_name: str | int | None = 0) -> pd.DataFrame:
    path = Path(path)
    logging.info("Reading modelling table: %s", path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name)
    return pd.read_csv(path)


def write_table(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    logging.info("Saved: %s", path)


def parse_float_grid(value: str | None) -> list[float] | None:
    if value is None or value.strip() == "":
        return None
    return [float(v.strip()) for v in value.split(",") if v.strip()]


# -----------------------------------------------------------------------------
# Matrix preparation
# -----------------------------------------------------------------------------


def standardize_vector(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    sd = values.std(ddof=1)
    if sd == 0:
        return np.zeros_like(values)
    return (values - values.mean()) / sd


def prepare_design_matrix(df: pd.DataFrame, explanatory_columns: Sequence[str], add_intercept: bool = True) -> tuple[np.ndarray, list[str]]:
    missing = [c for c in explanatory_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing explanatory columns: {missing}")
    x = df[list(explanatory_columns)].apply(pd.to_numeric, errors="coerce")
    if x.isna().any().any():
        raise ValueError("Explanatory matrix contains missing values after numeric conversion.")
    names = list(explanatory_columns)
    if add_intercept:
        x_matrix = np.column_stack([np.ones(len(df)), x.values])
        names = ["intercept"] + names
    else:
        x_matrix = x.values
    return x_matrix.astype(float), names


def prepare_response(df: pd.DataFrame, response: str) -> np.ndarray:
    if response not in df.columns:
        raise ValueError(f"Response column {response!r} not found.")
    y = pd.to_numeric(df[response], errors="coerce").values.astype(float)
    if np.isnan(y).any():
        raise ValueError(f"Response column {response!r} contains missing/non-numeric values.")
    return y


def prepare_coordinates(df: pd.DataFrame, lon_col: str, lat_col: str, time_col: str) -> tuple[np.ndarray, np.ndarray]:
    for col in [lon_col, lat_col, time_col]:
        if col not in df.columns:
            raise ValueError(f"Required coordinate/time column {col!r} not found.")
    coords = df[[lon_col, lat_col]].apply(pd.to_numeric, errors="coerce").values.astype(float)
    time = pd.to_numeric(df[time_col], errors="coerce").values.astype(float)
    if np.isnan(coords).any() or np.isnan(time).any():
        raise ValueError("Coordinate or time columns contain missing/non-numeric values.")
    coords = np.column_stack([standardize_vector(coords[:, 0]), standardize_vector(coords[:, 1])])
    time = standardize_vector(time)
    return coords, time


# -----------------------------------------------------------------------------
# Distances and kernels
# -----------------------------------------------------------------------------


def pairwise_euclidean(coords: np.ndarray) -> np.ndarray:
    diff = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(diff**2, axis=2))


def pairwise_time_distance(time: np.ndarray) -> np.ndarray:
    return np.abs(time[:, None] - time[None, :])


def gaussian_weights(
    spatial_distance: np.ndarray | None,
    temporal_distance: np.ndarray | None,
    bandwidth_spatial: float | None,
    bandwidth_temporal: float | None,
    model: str,
) -> np.ndarray:
    model = model.upper()
    if model == "OLS":
        n = spatial_distance.shape[0] if spatial_distance is not None else temporal_distance.shape[0]
        return np.ones((n, n), dtype=float)
    exponent = 0.0
    if model in {"GWR", "GTWR"}:
        if spatial_distance is None or bandwidth_spatial is None:
            raise ValueError("Spatial distance and spatial bandwidth are required for GWR/GTWR.")
        exponent = exponent + (spatial_distance / bandwidth_spatial) ** 2
    if model in {"TWR", "GTWR"}:
        if temporal_distance is None or bandwidth_temporal is None:
            raise ValueError("Temporal distance and temporal bandwidth are required for TWR/GTWR.")
        exponent = exponent + (temporal_distance / bandwidth_temporal) ** 2
    return np.exp(-exponent)


# -----------------------------------------------------------------------------
# Weighted least squares
# -----------------------------------------------------------------------------


def weighted_least_squares(x: np.ndarray, y: np.ndarray, weights: np.ndarray, ridge: float = 1e-8) -> tuple[np.ndarray, float]:
    """Solve local WLS and return coefficient vector and ridge penalty used."""
    w = np.asarray(weights, dtype=float)
    xw = x * w[:, None]
    xtwx = x.T @ xw
    xtwy = x.T @ (w * y)
    try:
        beta = np.linalg.solve(xtwx, xtwy)
        penalty_used = 0.0
    except np.linalg.LinAlgError:
        penalty = ridge * np.trace(xtwx) / max(1, xtwx.shape[0])
        beta = np.linalg.solve(xtwx + penalty * np.eye(xtwx.shape[0]), xtwy)
        penalty_used = float(penalty)
    return beta, penalty_used


def fit_local_model(
    x: np.ndarray,
    y: np.ndarray,
    weights_matrix: np.ndarray,
    coef_names: Sequence[str],
    metadata: pd.DataFrame,
    response: str,
    model: str,
    bandwidth_spatial: float | None,
    bandwidth_temporal: float | None,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, dict[str, float | str | None]]:
    n, p = x.shape
    betas = np.zeros((n, p), dtype=float)
    fitted = np.zeros(n, dtype=float)
    penalties = np.zeros(n, dtype=float)
    effective_n = np.zeros(n, dtype=float)
    for i in range(n):
        w = weights_matrix[i]
        beta, penalty = weighted_least_squares(x, y, w)
        betas[i] = beta
        fitted[i] = float(x[i] @ beta)
        penalties[i] = penalty
        effective_n[i] = float(np.sum(w > 1e-6))
    residuals = y - fitted
    rss = float(np.sum(residuals**2))
    tss = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else np.nan
    adjusted_r2 = 1.0 - (1.0 - r2) * (n - 1) / max(n - p - 1, 1) if np.isfinite(r2) else np.nan
    sigma = float(np.sqrt(rss / max(n - p, 1)))
    # A conservative effective parameter approximation. For strict GTWR, trace(S)
    # requires the full hat matrix. Here we report p as a transparent approximation.
    k = p
    if n - k - 1 > 0:
        aicc = float(n * np.log(max(rss / n, np.finfo(float).tiny)) + 2 * k + (2 * k * (k + 1)) / (n - k - 1))
    else:
        aicc = np.inf
    coef_df = metadata.reset_index(drop=True).copy()
    for j, name in enumerate(coef_names):
        coef_df[f"coef_{name}"] = betas[:, j]
    coef_df[f"fitted_{response}"] = fitted
    coef_df[f"residual_{response}"] = residuals
    coef_df["local_effective_n"] = effective_n
    coef_df["ridge_penalty_used"] = penalties
    summary = {
        "response": response,
        "model": model,
        "bandwidth_spatial": bandwidth_spatial,
        "bandwidth_temporal": bandwidth_temporal,
        "n_observations": n,
        "n_parameters": p,
        "residual_squares": rss,
        "sigma": sigma,
        "AICc": aicc,
        "R2": r2,
        "R2_adjusted": adjusted_r2,
        "mean_effective_n": float(np.mean(effective_n)),
        "max_ridge_penalty": float(np.max(penalties)),
    }
    return coef_df, fitted, residuals, summary


# -----------------------------------------------------------------------------
# Bandwidth search
# -----------------------------------------------------------------------------


def candidate_pairs(model: str, spatial_grid: Sequence[float], temporal_grid: Sequence[float]) -> list[tuple[float | None, float | None]]:
    model = model.upper()
    if model == "OLS":
        return [(None, None)]
    if model == "GWR":
        return [(s, None) for s in spatial_grid]
    if model == "TWR":
        return [(None, t) for t in temporal_grid]
    if model == "GTWR":
        return list(itertools.product(spatial_grid, temporal_grid))
    raise ValueError(f"Unsupported model: {model}")


def search_bandwidths(
    x: np.ndarray,
    y: np.ndarray,
    spatial_distance: np.ndarray,
    temporal_distance: np.ndarray,
    coef_names: Sequence[str],
    metadata: pd.DataFrame,
    response: str,
    model: str,
    spatial_grid: Sequence[float],
    temporal_grid: Sequence[float],
) -> tuple[float | None, float | None, pd.DataFrame]:
    rows = []
    best = None
    for bs, bt in candidate_pairs(model, spatial_grid, temporal_grid):
        weights = gaussian_weights(spatial_distance, temporal_distance, bs, bt, model)
        _, _, _, summary = fit_local_model(x, y, weights, coef_names, metadata, response, model, bs, bt)
        rows.append(summary)
        current = summary["AICc"]
        if best is None or current < best[2]:
            best = (bs, bt, current)
    search = pd.DataFrame(rows).sort_values("AICc").reset_index(drop=True)
    return best[0], best[1], search


# -----------------------------------------------------------------------------
# Figures
# -----------------------------------------------------------------------------


def plot_bandwidth_search(search: pd.DataFrame, output_base: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    x = np.arange(len(search))
    ax.plot(x, search["AICc"], color="#173A5E", marker="o", lw=1.8)
    ax.set_xlabel("Candidate model ordered by AICc")
    ax.set_ylabel("AICc")
    ax.set_title("Bandwidth search diagnostic")
    ax.grid(axis="y", color="#E6E6E6", lw=0.6)
    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_coefficient_heatmap(coef_df: pd.DataFrame, coefficient_columns: Sequence[str], output_base: Path, group_col: str | None = None, time_col: str = "year") -> None:
    available = [c for c in coefficient_columns if c in coef_df.columns]
    if not available:
        return
    data = coef_df.copy()
    if group_col and group_col in data.columns:
        data["row_label"] = data[group_col].astype(str) + "_" + data[time_col].astype(str)
    elif "Province" in data.columns:
        data["row_label"] = data["Province"].astype(str) + "_" + data[time_col].astype(str)
    else:
        data["row_label"] = np.arange(len(data)).astype(str)
    mat = data.set_index("row_label")[available]
    vmax = max(0.1, float(np.nanpercentile(np.abs(mat.values), 98)))
    fig, ax = plt.subplots(figsize=(6.8, max(5.0, 0.12 * len(mat))))
    im = ax.imshow(mat.values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(np.arange(len(available)))
    ax.set_xticklabels([c.replace("coef_", "") for c in available], rotation=45, ha="right")
    step = max(1, len(mat) // 25)
    ax.set_yticks(np.arange(0, len(mat), step))
    ax.set_yticklabels(mat.index[::step])
    ax.set_title("Local coefficient heatmap")
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("Local coefficient")
    fig.tight_layout()
    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


# -----------------------------------------------------------------------------
# Full workflow
# -----------------------------------------------------------------------------


def run_single_response(
    df: pd.DataFrame,
    response: str,
    explanatory_columns: Sequence[str],
    metadata_columns: Sequence[str],
    lon_col: str,
    lat_col: str,
    time_col: str,
    model: str,
    spatial_grid: Sequence[float],
    temporal_grid: Sequence[float],
    output_dir: Path,
) -> LocalRegressionResult:
    logging.info("Fitting %s for response %s", model, response)
    x, coef_names = prepare_design_matrix(df, explanatory_columns, add_intercept=True)
    y = prepare_response(df, response)
    coords, time = prepare_coordinates(df, lon_col, lat_col, time_col)
    spatial_distance = pairwise_euclidean(coords)
    temporal_distance = pairwise_time_distance(time)
    metadata = df[[c for c in metadata_columns if c in df.columns]].copy()

    bs, bt, search = search_bandwidths(
        x=x,
        y=y,
        spatial_distance=spatial_distance,
        temporal_distance=temporal_distance,
        coef_names=coef_names,
        metadata=metadata,
        response=response,
        model=model,
        spatial_grid=spatial_grid,
        temporal_grid=temporal_grid,
    )
    logging.info("Selected bandwidths for %s: spatial=%s temporal=%s", response, bs, bt)
    weights = gaussian_weights(spatial_distance, temporal_distance, bs, bt, model)
    coef_df, fitted, residuals, summary = fit_local_model(x, y, weights, coef_names, metadata, response, model, bs, bt)

    response_dir = output_dir / response
    response_dir.mkdir(parents=True, exist_ok=True)
    write_table(search, response_dir / f"{response}_{model}_bandwidth_search.csv")
    write_table(coef_df, response_dir / f"{response}_{model}_local_coefficients.csv")
    write_table(pd.DataFrame([summary]), response_dir / f"{response}_{model}_summary.csv")
    plot_bandwidth_search(search, response_dir / f"{response}_{model}_bandwidth_search")
    coefficient_cols = [f"coef_{name}" for name in coef_names if name != "intercept"]
    plot_coefficient_heatmap(coef_df, coefficient_cols, response_dir / f"{response}_{model}_coefficient_heatmap", time_col=time_col)
    return LocalRegressionResult(response, model, bs, bt, coef_df, fitted, residuals, summary, search)


def run_model_workflow(
    input_path: str | Path,
    output_dir: str | Path,
    response_columns: Sequence[str],
    explanatory_columns: Sequence[str],
    lon_col: str = "longitude",
    lat_col: str = "latitude",
    time_col: str = "year",
    metadata_columns: Sequence[str] | None = None,
    default_model: str = "GTWR",
    twr_responses: Sequence[str] | None = None,
    gwr_responses: Sequence[str] | None = None,
    spatial_grid: Sequence[float] | None = None,
    temporal_grid: Sequence[float] | None = None,
    sheet_name: str | int | None = 0,
    dpi: int = 300,
) -> pd.DataFrame:
    set_style(dpi)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = read_table(input_path, sheet_name=sheet_name)
    if metadata_columns is None:
        metadata_columns = [c for c in ["Province", "province", "year", "climate_zone", lon_col, lat_col] if c in df.columns]
    spatial_grid = list(spatial_grid or [0.08, 0.10, 0.11, 0.12, 0.13, 0.15, 0.20, 0.30])
    temporal_grid = list(temporal_grid or [0.10, 0.20, 0.27, 0.33, 0.50, 0.80])
    twr_responses = set(twr_responses or [])
    gwr_responses = set(gwr_responses or [])

    all_summaries = []
    combined_coefficients = []
    for response in response_columns:
        if response in twr_responses:
            model = "TWR"
        elif response in gwr_responses:
            model = "GWR"
        else:
            model = default_model.upper()
        result = run_single_response(
            df=df,
            response=response,
            explanatory_columns=explanatory_columns,
            metadata_columns=metadata_columns,
            lon_col=lon_col,
            lat_col=lat_col,
            time_col=time_col,
            model=model,
            spatial_grid=spatial_grid,
            temporal_grid=temporal_grid,
            output_dir=output_dir,
        )
        all_summaries.append(result.summary)
        tmp = result.coefficients.copy()
        tmp.insert(0, "response", response)
        tmp.insert(1, "model", model)
        combined_coefficients.append(tmp)

    summary_df = pd.DataFrame(all_summaries)
    write_table(summary_df, output_dir / "model_diagnostic_summary.csv")
    combined = pd.concat(combined_coefficients, ignore_index=True)
    write_table(combined, output_dir / "all_local_coefficients_long.csv")
    with pd.ExcelWriter(output_dir / "GTWR_GWR_TWR_complete_outputs.xlsx") as writer:
        summary_df.to_excel(writer, sheet_name="model_summary", index=False)
        combined.to_excel(writer, sheet_name="local_coefficients", index=False)
    return summary_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run detailed GWR/TWR/GTWR local regression workflow.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Province-year modelling table.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--responses", nargs="+", default=["CWE", "CS", "HQ", "NDR", "SDR", "RHI", "CP"])
    parser.add_argument("--explanatory", nargs="+", default=["SSN", "GM", "IPLG", "RW"])
    parser.add_argument("--lon-col", default="longitude")
    parser.add_argument("--lat-col", default="latitude")
    parser.add_argument("--time-col", default="year")
    parser.add_argument("--metadata-columns", default="Province,year,climate_zone,longitude,latitude")
    parser.add_argument("--default-model", default="GTWR", choices=["OLS", "GWR", "TWR", "GTWR"])
    parser.add_argument("--twr-responses", default="CP", help="Comma-separated responses fitted by TWR instead of default model.")
    parser.add_argument("--gwr-responses", default="", help="Comma-separated responses fitted by GWR instead of default model.")
    parser.add_argument("--spatial-grid", default="0.08,0.10,0.11,0.12,0.13,0.15,0.20,0.30")
    parser.add_argument("--temporal-grid", default="0.10,0.20,0.27,0.33,0.50,0.80")
    parser.add_argument("--sheet-name", default=0)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def main() -> None:
    args = parse_args()
    configure_logging(not args.quiet)
    summary = run_model_workflow(
        input_path=args.input,
        output_dir=args.output_dir,
        response_columns=args.responses,
        explanatory_columns=args.explanatory,
        lon_col=args.lon_col,
        lat_col=args.lat_col,
        time_col=args.time_col,
        metadata_columns=split_csv(args.metadata_columns),
        default_model=args.default_model,
        twr_responses=split_csv(args.twr_responses),
        gwr_responses=split_csv(args.gwr_responses),
        spatial_grid=parse_float_grid(args.spatial_grid),
        temporal_grid=parse_float_grid(args.temporal_grid),
        sheet_name=args.sheet_name,
        dpi=args.dpi,
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
