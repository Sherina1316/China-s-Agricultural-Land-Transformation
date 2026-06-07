"""Uncertainty diagnostics for local regression coefficients."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats


def monte_carlo_coefficients(
    coefficients: pd.DataFrame,
    coefficient_columns: Sequence[str],
    standard_error_columns: Sequence[str] | None = None,
    n_iter: int = 1000,
    random_seed: int = 42,
    relative_error: float = 0.1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Propagate coefficient uncertainty using Monte Carlo simulation.

    If standard-error columns are not provided, a relative uncertainty is derived
    from the absolute coefficient magnitude. This fallback is intended only for
    sensitivity diagnostics and should be reported as such.
    """
    rng = np.random.default_rng(random_seed)
    coeff = coefficients[list(coefficient_columns)].astype(float).to_numpy()
    if standard_error_columns is not None:
        se = coefficients[list(standard_error_columns)].astype(float).to_numpy()
    else:
        se = np.maximum(np.abs(coeff) * relative_error, 1e-8)

    n, p = coeff.shape
    sims = rng.normal(loc=coeff[None, :, :], scale=se[None, :, :], size=(n_iter, n, p))
    records = []
    for j, name in enumerate(coefficient_columns):
        values = sims[:, :, j].ravel()
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1))
        z = abs(mean / std) if std > 0 else np.inf
        p_value = float(2 * (1 - stats.norm.cdf(z))) if np.isfinite(z) else 0.0
        records.append(
            {
                "coefficient": name,
                "mean": mean,
                "std": std,
                "ci95_low": float(np.percentile(values, 2.5)),
                "ci95_high": float(np.percentile(values, 97.5)),
                "p_value": p_value,
                "significant_95": p_value < 0.05,
            }
        )
    summary = pd.DataFrame(records)
    sim_mean_by_observation = pd.DataFrame(np.mean(sims, axis=0), columns=coefficient_columns)
    return summary, sim_mean_by_observation


def run_uncertainty_from_coefficients(
    coefficient_file: str | Path,
    output_dir: str | Path,
    coefficient_columns: Sequence[str] = ("SSN", "GM", "IPLG", "RW"),
    n_iter: int = 1000,
) -> pd.DataFrame:
    coefficient_file = Path(coefficient_file)
    if coefficient_file.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(coefficient_file)
    else:
        df = pd.read_csv(coefficient_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, sim_mean = monte_carlo_coefficients(df, coefficient_columns, n_iter=n_iter)
    summary.to_csv(output_dir / "monte_carlo_coefficient_summary.csv", index=False)
    sim_mean.to_csv(output_dir / "monte_carlo_mean_coefficients_by_observation.csv", index=False)
    return summary
