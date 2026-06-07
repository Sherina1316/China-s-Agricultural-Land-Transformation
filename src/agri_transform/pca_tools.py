"""Principal component analysis with varimax rotation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


@dataclass
class PCAResult:
    loadings: pd.DataFrame
    scores: pd.DataFrame
    explained_variance: pd.DataFrame
    assignments: pd.DataFrame
    bartlett: dict[str, float]


def varimax(Phi: np.ndarray, gamma: float = 1.0, q: int = 50, tol: float = 1e-6) -> tuple[np.ndarray, np.ndarray]:
    """Varimax rotation for PCA loadings.

    Returns rotated loadings and rotation matrix.
    """
    p, k = Phi.shape
    R = np.eye(k)
    d_old = 0.0
    for _ in range(q):
        Lambda = Phi @ R
        u, s, vh = np.linalg.svd(Phi.T @ (Lambda**3 - (gamma / p) * Lambda @ np.diag(np.diag(Lambda.T @ Lambda))))
        R = u @ vh
        d = s.sum()
        if d_old != 0 and d / d_old < 1 + tol:
            break
        d_old = d
    return Phi @ R, R


def bartlett_sphericity(X: np.ndarray) -> dict[str, float]:
    """Bartlett's test of sphericity for correlation matrix adequacy."""
    n, p = X.shape
    corr = np.corrcoef(X, rowvar=False)
    det_corr = np.linalg.det(corr)
    det_corr = max(det_corr, np.finfo(float).tiny)
    chi_square = -(n - 1 - (2 * p + 5) / 6) * np.log(det_corr)
    degrees = p * (p - 1) / 2
    p_value = 1 - chi2.cdf(chi_square, degrees)
    return {"chi_square": float(chi_square), "df": float(degrees), "p_value": float(p_value)}


def run_pca_varimax(
    input_table: str | Path,
    output_dir: str | Path,
    index_col: str | int | None = 0,
    n_components: int | None = None,
    eigen_threshold: float = 1.0,
) -> PCAResult:
    """Run standardized PCA, retain components and apply varimax rotation.

    Parameters
    ----------
    input_table:
        Excel/CSV file containing numeric indicators. Rows are observations and
        columns are variables.
    output_dir:
        Directory where loadings, scores and diagnostic tables are written.
    n_components:
        Optional fixed number of components. If omitted, Kaiser criterion
        (eigenvalue > 1) is used.
    """
    path = Path(input_table)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, index_col=index_col)
    else:
        df = pd.read_csv(path, index_col=index_col)
    numeric = df.select_dtypes(include=[np.number]).copy()
    if numeric.empty:
        raise ValueError("No numeric columns found for PCA.")

    scaler = StandardScaler()
    X = scaler.fit_transform(numeric)
    bartlett = bartlett_sphericity(X)

    pca_all = PCA().fit(X)
    eigenvalues = pca_all.explained_variance_
    if n_components is None:
        n_components = int(max(1, np.sum(eigenvalues > eigen_threshold)))

    pca = PCA(n_components=n_components)
    raw_scores = pca.fit_transform(X)
    raw_loadings = pca.components_.T * np.sqrt(pca.explained_variance_)
    rotated_loadings, rotation = varimax(raw_loadings)
    rotated_scores = raw_scores @ rotation

    pc_names = [f"PC{i + 1}" for i in range(n_components)]
    loadings = pd.DataFrame(rotated_loadings, index=numeric.columns, columns=pc_names)
    scores = pd.DataFrame(rotated_scores, index=numeric.index, columns=pc_names)
    explained = pd.DataFrame(
        {
            "component": [f"PC{i + 1}" for i in range(len(eigenvalues))],
            "eigenvalue": eigenvalues,
            "explained_variance_ratio": pca_all.explained_variance_ratio_,
            "explained_variance_percent": pca_all.explained_variance_ratio_ * 100,
            "retained": [i < n_components for i in range(len(eigenvalues))],
        }
    )

    assignments_records = []
    for variable in loadings.index:
        pc = loadings.loc[variable].abs().idxmax()
        loading = loadings.loc[variable, pc]
        assignments_records.append(
            {
                "variable": variable,
                "assigned_component": pc,
                "loading": loading,
                "direction": "positive" if loading >= 0 else "negative",
            }
        )
    assignments = pd.DataFrame(assignments_records)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    loadings.to_csv(output_dir / "pca_varimax_loadings.csv")
    scores.to_csv(output_dir / "pca_scores.csv")
    explained.to_csv(output_dir / "pca_explained_variance.csv", index=False)
    assignments.to_csv(output_dir / "pca_variable_assignments.csv", index=False)
    pd.DataFrame([bartlett]).to_csv(output_dir / "pca_bartlett_test.csv", index=False)
    with pd.ExcelWriter(output_dir / "pca_results.xlsx") as writer:
        loadings.to_excel(writer, sheet_name="loadings")
        scores.to_excel(writer, sheet_name="scores")
        explained.to_excel(writer, sheet_name="explained_variance", index=False)
        assignments.to_excel(writer, sheet_name="assignments", index=False)
        pd.DataFrame([bartlett]).to_excel(writer, sheet_name="bartlett", index=False)

    return PCAResult(loadings, scores, explained, assignments, bartlett)
