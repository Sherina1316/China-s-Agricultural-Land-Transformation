#!/usr/bin/env python
"""Run standardized PCA with varimax rotation."""

from __future__ import annotations

import argparse

from agri_transform.pca_tools import run_pca_varimax


def parse_index_col(value: str):
    if value.lower() in {"none", "false", "no"}:
        return None
    try:
        return int(value)
    except ValueError:
        return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Indicator table. Rows are province-year observations; columns are indicators.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--index-col", default="0")
    parser.add_argument("--n-components", type=int, default=None)
    args = parser.parse_args()
    run_pca_varimax(args.input, args.output_dir, index_col=parse_index_col(args.index_col), n_components=args.n_components)


if __name__ == "__main__":
    main()
