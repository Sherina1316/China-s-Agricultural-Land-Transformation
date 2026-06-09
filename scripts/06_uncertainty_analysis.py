#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Detailed Monte Carlo and bootstrap uncertainty diagnostics for local coefficients.

This script evaluates whether estimated local coefficients are robust to sample
variation and coefficient uncertainty. It is designed for outputs from the GTWR,
GWR or TWR workflow, but it can also be used with any table containing local
coefficient columns.

Main outputs
------------
1. Distribution summary for each coefficient variable.
2. Bootstrap confidence intervals of the coefficient mean and median.
3. Monte Carlo sign-stability diagnostics.
4. Optional temporal summaries if a year column is available.
5. Publication-ready coefficient distribution and temporal envelope figures.
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


def set_style(dpi: int = 300) -> None:
    mpl.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "figure.dpi": dpi, "savefig.dpi": dpi, "pdf.fonttype": 42, "ps.fonttype": 42})


def bootstrap_statistic(values: np.ndarray, statistic: str, n_iter: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = values[np.isfinite(values)]
    out = np.zeros(n_iter, dtype=float)
    for i in range(n_iter):
        sample = rng.choice(values, size=len(values), replace=True)
        out[i] = np.mean(sample) if statistic == "mean" else np.median(sample)
    return out


def monte_carlo_sign(values: np.ndarray, n_iter: int, seed: int, noise_scale: float | None = None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = values[np.isfinite(values)]
    sd = values.std(ddof=1)
    if noise_scale is None:
        noise_scale = 0.10 * sd
    draws = np.zeros(n_iter, dtype=float)
    for i in range(n_iter):
        perturbed = values + rng.normal(0.0, noise_scale, size=len(values))
        draws[i] = np.mean(perturbed)
    return draws


def summarize_coefficients(df: pd.DataFrame, coefficient_columns: Sequence[str], n_iter: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    draws_rows = []
    for col in coefficient_columns:
        values = pd.to_numeric(df[col], errors="coerce").values.astype(float)
        values = values[np.isfinite(values)]
        if len(values) == 0:
            continue
        boot_mean = bootstrap_statistic(values, "mean", n_iter, seed)
        boot_median = bootstrap_statistic(values, "median", n_iter, seed + 100)
        mc_mean = monte_carlo_sign(values, n_iter, seed + 200)
        rows.append(
            {
                "coefficient": col,
                "n": len(values),
                "mean": float(values.mean()),
                "median": float(np.median(values)),
                "std": float(values.std(ddof=1)),
                "p05": float(np.percentile(values, 5)),
                "p25": float(np.percentile(values, 25)),
                "p75": float(np.percentile(values, 75)),
                "p95": float(np.percentile(values, 95)),
                "share_positive": float(np.mean(values > 0)),
                "share_negative": float(np.mean(values < 0)),
                "bootstrap_mean_ci_low": float(np.percentile(boot_mean, 2.5)),
                "bootstrap_mean_ci_high": float(np.percentile(boot_mean, 97.5)),
                "bootstrap_median_ci_low": float(np.percentile(boot_median, 2.5)),
                "bootstrap_median_ci_high": float(np.percentile(boot_median, 97.5)),
                "mc_mean_positive_probability": float(np.mean(mc_mean > 0)),
                "mc_mean_negative_probability": float(np.mean(mc_mean < 0)),
            }
        )
        draws_rows.extend({"coefficient": col, "draw_type": "bootstrap_mean", "draw": i, "value": v} for i, v in enumerate(boot_mean))
        draws_rows.extend({"coefficient": col, "draw_type": "bootstrap_median", "draw": i, "value": v} for i, v in enumerate(boot_median))
        draws_rows.extend({"coefficient": col, "draw_type": "monte_carlo_mean", "draw": i, "value": v} for i, v in enumerate(mc_mean))
    return pd.DataFrame(rows), pd.DataFrame(draws_rows)


def temporal_summary(df: pd.DataFrame, coefficient_columns: Sequence[str], year_col: str) -> pd.DataFrame:
    if year_col not in df.columns:
        return pd.DataFrame()
    rows = []
    for year, sub in df.groupby(year_col):
        for col in coefficient_columns:
            vals = pd.to_numeric(sub[col], errors="coerce").dropna().values
            if len(vals) == 0:
                continue
            rows.append({"year": year, "coefficient": col, "mean": vals.mean(), "median": np.median(vals), "p25": np.percentile(vals, 25), "p75": np.percentile(vals, 75), "share_positive": np.mean(vals > 0)})
    return pd.DataFrame(rows)


def plot_distributions(df: pd.DataFrame, coefficient_columns: Sequence[str], output_base: Path) -> None:
    n = len(coefficient_columns)
    fig, axes = plt.subplots(n, 1, figsize=(7.2, max(3.0, 2.2 * n)), sharex=False)
    if n == 1:
        axes = [axes]
    for ax, col in zip(axes, coefficient_columns):
        vals = pd.to_numeric(df[col], errors="coerce").dropna().values
        ax.hist(vals, bins=30, color="#244C74", alpha=0.82, edgecolor="white")
        ax.axvline(0, color="#A63A2B", lw=1.2, ls="--")
        ax.set_title(col)
        ax.set_ylabel("Count")
    axes[-1].set_xlabel("Local coefficient")
    fig.tight_layout()
    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_temporal(summary: pd.DataFrame, output_base: Path) -> None:
    if summary.empty:
        return
    coef_names = summary["coefficient"].unique().tolist()
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    for coef in coef_names:
        sub = summary[summary["coefficient"] == coef].sort_values("year")
        ax.plot(sub["year"], sub["mean"], marker="o", lw=1.8, label=coef)
        ax.fill_between(sub["year"].astype(float), sub["p25"].astype(float), sub["p75"].astype(float), alpha=0.15)
    ax.axhline(0, color="#555555", lw=0.8)
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean local coefficient")
    ax.legend(frameon=True, ncol=2)
    fig.tight_layout()
    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def infer_coefficients(df: pd.DataFrame) -> list[str]:
    candidates = [c for c in df.columns if c.startswith("coef_") and c != "coef_intercept"]
    if candidates:
        return candidates
    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    return [c for c in numeric if c not in {"year", "longitude", "latitude", "lon", "lat"}]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Monte Carlo/Bootstrap uncertainty diagnostics.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--coefficients", required=True, help="Coefficient table from GTWR/GWR/TWR or other local model.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--coefficient-columns", nargs="+", default=None)
    parser.add_argument("--year-col", default="year")
    parser.add_argument("--n-iter", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(not args.quiet)
    set_style(args.dpi)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = read_table(args.coefficients)
    coefficient_columns = args.coefficient_columns or infer_coefficients(df)
    logging.info("Coefficient columns: %s", coefficient_columns)
    summary, draws = summarize_coefficients(df, coefficient_columns, args.n_iter, args.seed)
    temporal = temporal_summary(df, coefficient_columns, args.year_col)
    write_table(summary, out / "coefficient_uncertainty_summary.csv")
    write_table(draws, out / "coefficient_uncertainty_draws.csv")
    if not temporal.empty:
        write_table(temporal, out / "coefficient_temporal_summary.csv")
    with pd.ExcelWriter(out / "monte_carlo_uncertainty_outputs.xlsx") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        draws.to_excel(writer, sheet_name="draws", index=False)
        if not temporal.empty:
            temporal.to_excel(writer, sheet_name="temporal", index=False)
    plot_distributions(df, coefficient_columns, out / "figure_coefficient_distributions")
    plot_temporal(temporal, out / "figure_coefficient_temporal_evolution")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
