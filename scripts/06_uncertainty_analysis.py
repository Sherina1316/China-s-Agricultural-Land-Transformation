#!/usr/bin/env python
"""Run Monte Carlo coefficient uncertainty diagnostics."""

from __future__ import annotations

import argparse

from agri_transform.uncertainty import run_uncertainty_from_coefficients


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coefficients", required=True, help="Local coefficient CSV/XLSX file.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--coefficient-columns", nargs="+", default=["SSN", "GM", "IPLG", "RW"])
    parser.add_argument("--n-iter", type=int, default=1000)
    args = parser.parse_args()
    out = run_uncertainty_from_coefficients(args.coefficients, args.output_dir, args.coefficient_columns, args.n_iter)
    print(out)


if __name__ == "__main__":
    main()
