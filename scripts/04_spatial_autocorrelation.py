#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Detailed global Moran's I workflow for socio-environmental outcome variables.

The manuscript uses spatial autocorrelation diagnostics to decide whether a
spatially weighted model is appropriate for each outcome variable. This script
implements global Moran's I with transparent k-nearest-neighbour weights and an
optional permutation test.

Expected input
--------------
A CSV/XLSX table containing coordinates and outcome variables, for example:

    Province, year, longitude, latitude, CWE, CS, HQ, NDR, SDR, RHI, CP

If multiple years are present, Moran's I can be calculated for each year and each
variable. The output is a tidy table with one row per variable-year combination.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt


def configure_logging(verbose: bool = True) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(asctime)s | %(levelname)s | %(message)s")


def read_table(path: str | Path, sheet_name: str | int | None = 0) -> pd.DataFrame:
    path = Path(path)
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


def pairwise_distance(coords: np.ndarray) -> np.ndarray:
    diff = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(diff**2, axis=2))


def knn_weights(coords: np.ndarray, k: int = 5, row_standardize: bool = True) -> np.ndarray:
    n = coords.shape[0]
    if n <= k:
        raise ValueError("Number of observations must be greater than k.")
    dist = pairwise_distance(coords)
    np.fill_diagonal(dist, np.inf)
    w = np.zeros((n, n), dtype=float)
    neighbours = np.argsort(dist, axis=1)[:, :k]
    for i in range(n):
        w[i, neighbours[i]] = 1.0
    # Symmetrize to avoid directional artefacts.
    w = np.maximum(w, w.T)
    if row_standardize:
        row_sum = w.sum(axis=1)
        row_sum[row_sum == 0] = 1.0
        w = w / row_sum[:, None]
    return w


def morans_i(values: np.ndarray, weights: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    z = x - x.mean()
    denom = float(np.sum(z**2))
    if denom == 0:
        return np.nan
    w_sum = float(weights.sum())
    if w_sum == 0:
        return np.nan
    return float((len(x) / w_sum) * (z @ weights @ z) / denom)


def permutation_p_value(values: np.ndarray, weights: np.ndarray, observed_i: float, n_perm: int, seed: int = 42) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    permuted = np.zeros(n_perm, dtype=float)
    for i in range(n_perm):
        permuted[i] = morans_i(rng.permutation(values), weights)
    p_two_sided = (np.sum(np.abs(permuted) >= abs(observed_i)) + 1) / (n_perm + 1)
    return float(p_two_sided), float(permuted.mean()), float(permuted.std(ddof=1))


def moran_by_year(
    df: pd.DataFrame,
    value_columns: Sequence[str],
    lon_col: str,
    lat_col: str,
    year_col: str | None,
    k: int,
    permutations: int,
    seed: int,
) -> pd.DataFrame:
    rows = []
    if year_col and year_col in df.columns:
        groups = list(df.groupby(year_col))
    else:
        groups = [("all", df)]
    for year, sub in groups:
        coords = sub[[lon_col, lat_col]].apply(pd.to_numeric, errors="coerce").values.astype(float)
        if np.isnan(coords).any():
            raise ValueError("Coordinates contain missing values.")
        weights = knn_weights(coords, k=k)
        for col in value_columns:
            values = pd.to_numeric(sub[col], errors="coerce").values.astype(float)
            values = values[np.isfinite(values)]
            if len(values) != len(sub):
                logging.warning("Skipping %s year %s because it contains missing values.", col, year)
                continue
            observed = morans_i(values, weights)
            if permutations > 0 and np.isfinite(observed):
                p_value, perm_mean, perm_sd = permutation_p_value(values, weights, observed, permutations, seed)
            else:
                p_value, perm_mean, perm_sd = np.nan, np.nan, np.nan
            rows.append(
                {
                    "year": year,
                    "variable": col,
                    "n": len(sub),
                    "k_neighbors": k,
                    "Moran_I": observed,
                    "permutation_p_value": p_value,
                    "permutation_mean": perm_mean,
                    "permutation_sd": perm_sd,
                    "significant_0_05": bool(p_value < 0.05) if np.isfinite(p_value) else None,
                }
            )
    return pd.DataFrame(rows)


def plot_summary(summary: pd.DataFrame, output_base: Path) -> None:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    mpl.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "pdf.fonttype": 42, "ps.fonttype": 42})
    for var, sub in summary.groupby("variable"):
        fig, ax = plt.subplots(figsize=(6.8, 4.2))
        x = sub["year"].astype(str)
        ax.plot(x, sub["Moran_I"], marker="o", color="#173A5E", lw=2.0)
        ax.axhline(0, color="#888888", lw=0.8)
        ax.set_title(f"Global Moran's I: {var}")
        ax.set_xlabel("Year")
        ax.set_ylabel("Moran's I")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(output_base.parent / f"{output_base.name}_{var}.png", bbox_inches="tight")
        fig.savefig(output_base.parent / f"{output_base.name}_{var}.pdf", bbox_inches="tight")
        plt.close(fig)


def infer_value_columns(df: pd.DataFrame, lon_col: str, lat_col: str, year_col: str | None, excluded: Sequence[str]) -> list[str]:
    exclude = {lon_col, lat_col, *(excluded or [])}
    if year_col:
        exclude.add(year_col)
    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    return [c for c in numeric if c not in exclude]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run detailed Moran's I spatial autocorrelation diagnostics.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lon-col", default="longitude")
    parser.add_argument("--lat-col", default="latitude")
    parser.add_argument("--year-col", default="year")
    parser.add_argument("--value-columns", nargs="*", default=None)
    parser.add_argument("--exclude-columns", nargs="*", default=["Province", "FID"])
    parser.add_argument("--k-neighbors", type=int, default=5)
    parser.add_argument("--permutations", type=int, default=999)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(not args.quiet)
    df = read_table(args.input)
    values = args.value_columns or infer_value_columns(df, args.lon_col, args.lat_col, args.year_col, args.exclude_columns)
    logging.info("Testing variables: %s", values)
    summary = moran_by_year(df, values, args.lon_col, args.lat_col, args.year_col, args.k_neighbors, args.permutations, args.seed)
    write_table(summary, args.output)
    if args.plot:
        plot_summary(summary, Path(args.output).with_suffix(""))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
