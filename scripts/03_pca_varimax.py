#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Detailed PCA and varimax-rotation workflow for agricultural-use indicators.

This script implements the PCA procedure described in the manuscript in a fully
transparent and reproducible way. It is intentionally verbose and self-contained
so that reviewers can inspect every calculation step.

Workflow
--------
1. Read an indicator table. Each row should be an analytical observation, for
   example a province-year record. Columns can include identifiers such as
   Province and year; these are excluded from PCA.
2. Select indicator columns explicitly or infer numeric columns.
3. Standardize all selected indicators using z-scores. This step removes the
   influence of different units and magnitudes.
4. Fit PCA using the correlation matrix of standardized indicators.
5. Retain components by user-specified n_components or by eigenvalues > 1.
6. Apply orthogonal varimax rotation to improve interpretability.
7. Export standardized indicators, eigenvalues, explained variance, rotated
   loadings, component scores and a concise interpretation table.

The component names used in the manuscript are optional labels. The script does
not enforce a specific interpretation; it reports loadings so that components can
be labelled in the paper according to dominant covariance structures.
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
from numpy.linalg import eigh, inv, pinv

# -----------------------------------------------------------------------------
# Style and logging
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
            "mathtext.fontset": "stix",
            "figure.dpi": dpi,
            "savefig.dpi": dpi,
            "axes.linewidth": 1.0,
            "axes.edgecolor": "#222222",
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.unicode_minus": False,
        }
    )


def read_table(path: str | Path, sheet_name: str | int | None = 0) -> pd.DataFrame:
    path = Path(path)
    logging.info("Reading PCA input table: %s", path)
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


# -----------------------------------------------------------------------------
# Mathematical helpers
# -----------------------------------------------------------------------------


def zscore(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    means = df.mean(axis=0)
    stds = df.std(axis=0, ddof=1)
    if (stds == 0).any():
        zero_cols = stds[stds == 0].index.tolist()
        raise ValueError(f"Cannot standardize zero-variance columns: {zero_cols}")
    standardized = (df - means) / stds
    parameters = pd.DataFrame({"variable": df.columns, "mean": means.values, "std": stds.values})
    return standardized, parameters


def correlation_matrix(x: pd.DataFrame) -> pd.DataFrame:
    corr = x.corr()
    if corr.isna().any().any():
        raise ValueError("Correlation matrix contains NaN values. Check input data.")
    return corr


def eigen_decomposition(corr: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return eigenvalues and eigenvectors sorted in descending order."""
    values, vectors = eigh(corr.values)
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]
    return values, vectors


def choose_n_components(eigenvalues: np.ndarray, n_components: int | None = None, min_eigenvalue: float = 1.0) -> int:
    if n_components is not None:
        if n_components < 1 or n_components > len(eigenvalues):
            raise ValueError("n_components must be between 1 and the number of variables.")
        return n_components
    n = int(np.sum(eigenvalues > min_eigenvalue))
    return max(n, 1)


def component_loadings(eigenvalues: np.ndarray, eigenvectors: np.ndarray, n_components: int) -> np.ndarray:
    eigvals = eigenvalues[:n_components]
    eigvecs = eigenvectors[:, :n_components]
    return eigvecs * np.sqrt(eigvals)


def varimax(loadings: np.ndarray, gamma: float = 1.0, q: int = 100, tol: float = 1e-6) -> tuple[np.ndarray, np.ndarray]:
    """Orthogonal varimax rotation.

    Parameters
    ----------
    loadings:
        Matrix of shape n_variables × n_components.
    gamma:
        Kaiser varimax uses gamma=1.
    q:
        Maximum number of iterations.
    tol:
        Convergence tolerance.
    """
    p, k = loadings.shape
    rotation = np.eye(k)
    previous = 0.0
    for iteration in range(q):
        rotated = loadings @ rotation
        u, s, vh = np.linalg.svd(
            loadings.T
            @ (
                rotated**3
                - (gamma / p) * rotated @ np.diag(np.diag(rotated.T @ rotated))
            )
        )
        rotation = u @ vh
        current = float(s.sum())
        if previous != 0 and current / previous < 1 + tol:
            logging.info("Varimax converged after %s iterations.", iteration + 1)
            break
        previous = current
    return loadings @ rotation, rotation


def compute_scores(standardized: pd.DataFrame, rotated_loadings: np.ndarray) -> np.ndarray:
    """Compute regression-style component scores from rotated loadings."""
    # For standardized variables, a stable score coefficient matrix can be derived
    # from the pseudo-inverse of the loading matrix. This is sufficient for
    # reproducible component scores in the manuscript workflow.
    coefficients = pinv(rotated_loadings).T
    return standardized.values @ coefficients


def bartlett_sphericity_test(corr: pd.DataFrame, n_samples: int) -> dict[str, float]:
    """Approximate Bartlett test of sphericity.

    The p-value is reported only if scipy is available. The test is optional and
    does not affect PCA calculations.
    """
    p = corr.shape[0]
    det = float(np.linalg.det(corr.values))
    det = max(det, np.finfo(float).tiny)
    chi2 = -(n_samples - 1 - (2 * p + 5) / 6) * np.log(det)
    dof = p * (p - 1) / 2
    try:
        from scipy.stats import chi2 as chi2_dist

        p_value = float(chi2_dist.sf(chi2, dof))
    except Exception:
        p_value = np.nan
    return {"bartlett_chi2": chi2, "bartlett_df": dof, "bartlett_p_value": p_value}


def kmo_measure(corr: pd.DataFrame) -> pd.DataFrame:
    """Compute Kaiser-Meyer-Olkin sampling adequacy statistics."""
    r = corr.values
    inv_r = inv(r)
    partial = -inv_r / np.sqrt(np.outer(np.diag(inv_r), np.diag(inv_r)))
    np.fill_diagonal(partial, 0.0)
    r_no_diag = r.copy()
    np.fill_diagonal(r_no_diag, 0.0)
    r2 = r_no_diag**2
    p2 = partial**2
    kmo_overall = r2.sum() / (r2.sum() + p2.sum())
    kmo_vars = r2.sum(axis=0) / (r2.sum(axis=0) + p2.sum(axis=0))
    return pd.DataFrame({"variable": corr.columns, "KMO": kmo_vars}).assign(KMO_overall=kmo_overall)


# -----------------------------------------------------------------------------
# Output helpers and figures
# -----------------------------------------------------------------------------


def build_eigen_table(eigenvalues: np.ndarray) -> pd.DataFrame:
    total = float(eigenvalues.sum())
    explained = eigenvalues / total
    return pd.DataFrame(
        {
            "component": [f"PC{i+1}" for i in range(len(eigenvalues))],
            "eigenvalue": eigenvalues,
            "explained_variance_ratio": explained,
            "explained_variance_percent": explained * 100,
            "cumulative_explained_percent": np.cumsum(explained) * 100,
            "retain_by_kaiser": eigenvalues > 1.0,
        }
    )


def build_loading_table(variables: Sequence[str], loadings: np.ndarray, prefix: str = "RC") -> pd.DataFrame:
    columns = [f"{prefix}{i+1}" for i in range(loadings.shape[1])]
    return pd.DataFrame(loadings, columns=columns).assign(variable=list(variables))[ ["variable"] + columns ]


def build_score_table(ids: pd.DataFrame, scores: np.ndarray, prefix: str = "RC") -> pd.DataFrame:
    columns = [f"{prefix}{i+1}" for i in range(scores.shape[1])]
    return pd.concat([ids.reset_index(drop=True), pd.DataFrame(scores, columns=columns)], axis=1)


def infer_component_labels(loadings: pd.DataFrame, threshold: float = 0.40) -> pd.DataFrame:
    rows = []
    component_cols = [c for c in loadings.columns if c != "variable"]
    for component in component_cols:
        ordered = loadings[["variable", component]].copy()
        ordered["absolute_loading"] = ordered[component].abs()
        ordered = ordered.sort_values("absolute_loading", ascending=False)
        main = ordered[ordered["absolute_loading"] >= threshold]
        if main.empty:
            main = ordered.head(3)
        signed = []
        for _, row in main.iterrows():
            sign = "+" if row[component] >= 0 else "−"
            signed.append(f"{row['variable']} ({sign})")
        rows.append(
            {
                "component": component,
                "dominant_indicators": "; ".join(signed),
                "suggested_interpretation_note": "Review dominant indicators and label as covariance pattern, not as causal mechanism.",
            }
        )
    return pd.DataFrame(rows)


def plot_scree(eigen_table: pd.DataFrame, output_base: Path) -> None:
    fig, ax1 = plt.subplots(figsize=(6.8, 4.8))
    x = np.arange(1, len(eigen_table) + 1)
    ax1.bar(x, eigen_table["explained_variance_percent"], color="#244C74", alpha=0.88, label="Individual")
    ax1.set_xlabel("Principal component")
    ax1.set_ylabel("Explained variance (%)")
    ax1.set_xticks(x)
    ax2 = ax1.twinx()
    ax2.plot(x, eigen_table["cumulative_explained_percent"], color="#A63A2B", marker="o", label="Cumulative")
    ax2.set_ylabel("Cumulative explained variance (%)")
    ax1.axhline(100 / len(eigen_table), color="#888888", ls="--", lw=0.8)
    ax1.set_title("PCA explained variance")
    fig.tight_layout()
    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_loading_heatmap(loadings: pd.DataFrame, output_base: Path) -> None:
    data = loadings.set_index("variable")
    fig, ax = plt.subplots(figsize=(6.4, max(4.5, 0.38 * len(data))))
    vmax = max(0.1, np.nanmax(np.abs(data.values)))
    im = ax.imshow(data.values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(np.arange(data.shape[1]))
    ax.set_xticklabels(data.columns)
    ax.set_yticks(np.arange(data.shape[0]))
    ax.set_yticklabels(data.index)
    ax.set_title("Rotated component loadings")
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("Loading")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data.values[i, j]
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7, color="black")
    fig.tight_layout()
    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


# -----------------------------------------------------------------------------
# Full workflow
# -----------------------------------------------------------------------------


def run_pca_workflow(
    input_path: str | Path,
    output_dir: str | Path,
    sheet_name: str | int | None = 0,
    indicator_columns: Sequence[str] | None = None,
    id_columns: Sequence[str] | None = None,
    n_components: int | None = None,
    component_labels: Sequence[str] | None = None,
    dpi: int = 300,
) -> dict[str, pd.DataFrame]:
    set_style(dpi)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = read_table(input_path, sheet_name=sheet_name)

    if id_columns is None:
        id_columns = [c for c in ["Province", "province", "year", "Year", "climate_zone"] if c in df.columns]
    id_columns = list(id_columns)

    if indicator_columns is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        indicator_columns = [c for c in numeric_cols if c not in id_columns]
    indicator_columns = list(indicator_columns)
    if not indicator_columns:
        raise ValueError("No indicator columns selected for PCA.")

    logging.info("PCA indicator columns: %s", indicator_columns)
    x = df[indicator_columns].apply(pd.to_numeric, errors="coerce")
    if x.isna().any().any():
        missing = x.isna().sum()
        raise ValueError(f"PCA input contains missing values:\n{missing[missing > 0]}")

    standardized, z_params = zscore(x)
    corr = correlation_matrix(standardized)
    eigenvalues, eigenvectors = eigen_decomposition(corr)
    n_retained = choose_n_components(eigenvalues, n_components=n_components)
    logging.info("Retained %s components.", n_retained)
    raw_loadings = component_loadings(eigenvalues, eigenvectors, n_retained)
    rotated_loadings, rotation_matrix = varimax(raw_loadings)
    scores = compute_scores(standardized, rotated_loadings)

    if component_labels is not None:
        if len(component_labels) != n_retained:
            raise ValueError("Number of component labels must equal retained components.")
        prefix_cols = list(component_labels)
    else:
        prefix_cols = [f"RC{i+1}" for i in range(n_retained)]

    eigen_table = build_eigen_table(eigenvalues)
    raw_loading_table = pd.DataFrame(raw_loadings, columns=[f"PC{i+1}" for i in range(n_retained)]).assign(variable=indicator_columns)
    raw_loading_table = raw_loading_table[["variable"] + [f"PC{i+1}" for i in range(n_retained)]]
    rotated_loading_table = pd.DataFrame(rotated_loadings, columns=prefix_cols).assign(variable=indicator_columns)
    rotated_loading_table = rotated_loading_table[["variable"] + prefix_cols]
    score_table = pd.concat([df[id_columns].reset_index(drop=True), pd.DataFrame(scores, columns=prefix_cols)], axis=1)
    interpretation = infer_component_labels(rotated_loading_table)
    if component_labels is not None:
        interpretation["component"] = prefix_cols

    bartlett = pd.DataFrame([bartlett_sphericity_test(corr, len(df))])
    try:
        kmo = kmo_measure(corr)
    except Exception as exc:
        logging.warning("KMO calculation failed: %s", exc)
        kmo = pd.DataFrame({"variable": indicator_columns, "KMO": np.nan, "KMO_overall": np.nan})

    write_table(standardized.assign(**{c: df[c].values for c in id_columns}), output_dir / "standardized_indicators.csv")
    write_table(z_params, output_dir / "standardization_parameters.csv")
    write_table(corr.reset_index().rename(columns={"index": "variable"}), output_dir / "indicator_correlation_matrix.csv")
    write_table(eigen_table, output_dir / "pca_eigenvalues_explained_variance.csv")
    write_table(raw_loading_table, output_dir / "pca_raw_loadings.csv")
    write_table(rotated_loading_table, output_dir / "pca_rotated_loadings.csv")
    write_table(score_table, output_dir / "pca_rotated_component_scores.csv")
    write_table(interpretation, output_dir / "pca_component_interpretation_aid.csv")
    write_table(bartlett, output_dir / "pca_bartlett_test.csv")
    write_table(kmo, output_dir / "pca_kmo_statistics.csv")

    with pd.ExcelWriter(output_dir / "pca_results_complete.xlsx") as writer:
        standardized.assign(**{c: df[c].values for c in id_columns}).to_excel(writer, sheet_name="standardized", index=False)
        z_params.to_excel(writer, sheet_name="zscore_parameters", index=False)
        corr.to_excel(writer, sheet_name="correlation")
        eigen_table.to_excel(writer, sheet_name="eigenvalues", index=False)
        raw_loading_table.to_excel(writer, sheet_name="raw_loadings", index=False)
        rotated_loading_table.to_excel(writer, sheet_name="rotated_loadings", index=False)
        score_table.to_excel(writer, sheet_name="component_scores", index=False)
        interpretation.to_excel(writer, sheet_name="interpretation_aid", index=False)
        bartlett.to_excel(writer, sheet_name="bartlett", index=False)
        kmo.to_excel(writer, sheet_name="kmo", index=False)

    plot_scree(eigen_table, output_dir / "figure_pca_scree")
    plot_loading_heatmap(rotated_loading_table, output_dir / "figure_rotated_loading_heatmap")

    return {
        "standardized": standardized,
        "eigen_table": eigen_table,
        "rotated_loadings": rotated_loading_table,
        "scores": score_table,
        "interpretation": interpretation,
    }


def parse_csv_list(value: str | None) -> list[str] | None:
    if value is None or value.strip() == "":
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run detailed PCA with varimax rotation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="CSV/XLSX indicator table.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sheet-name", default=0)
    parser.add_argument("--indicator-columns", default=None, help="Comma-separated indicator columns. If omitted, numeric columns are inferred.")
    parser.add_argument("--id-columns", default=None, help="Comma-separated identifier columns to preserve.")
    parser.add_argument("--n-components", type=int, default=None, help="If omitted, eigenvalues > 1 rule is used.")
    parser.add_argument("--component-labels", default=None, help="Optional comma-separated labels, e.g. SSN,GM,IPLG,RW.")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(not args.quiet)
    run_pca_workflow(
        input_path=args.input,
        output_dir=args.output_dir,
        sheet_name=args.sheet_name,
        indicator_columns=parse_csv_list(args.indicator_columns),
        id_columns=parse_csv_list(args.id_columns),
        n_components=args.n_components,
        component_labels=parse_csv_list(args.component_labels),
        dpi=args.dpi,
    )


if __name__ == "__main__":
    main()
