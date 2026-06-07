"""Publication-oriented figures used in the manuscript workflow."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from .style import COLORS, despine, panel_label, save_figure, set_publication_style


def plot_cropland_sown_diagnostics(
    province_summary: pd.DataFrame,
    national_timeseries: pd.DataFrame,
    output_base: str | Path,
    dpi: int = 300,
) -> None:
    """Create a compact diagnostic figure for cropland extent and crop sown area."""
    set_publication_style(dpi=dpi)
    fig = plt.figure(figsize=(13, 8))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.1], width_ratios=[1.1, 1.0], hspace=0.38, wspace=0.32)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(national_timeseries["Year"], national_timeseries["national_cropland_extent_kha"] / 1000, color=COLORS["navy"], label="Cropland extent")
    ax1.plot(national_timeseries["Year"], national_timeseries["national_crop_sown_area_kha"] / 1000, color=COLORS["terracotta"], label="Crop sown area")
    ax1.set_ylabel("Area (10$^6$ ha)")
    ax1.set_xlabel("Year")
    ax1.legend(frameon=False)
    despine(ax1)
    panel_label(ax1, "a")

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.scatter(
        province_summary["cropland_extent_change_pct"],
        province_summary["crop_sown_area_change_pct"],
        s=40,
        color=COLORS["blue"],
        edgecolor="white",
        linewidth=0.5,
    )
    ax2.axhline(0, color=COLORS["mid_gray"], lw=0.8)
    ax2.axvline(0, color=COLORS["mid_gray"], lw=0.8)
    ax2.set_xlabel("Cropland extent change (%)")
    ax2.set_ylabel("Crop sown-area change (%)")
    despine(ax2)
    panel_label(ax2, "b")

    ax3 = fig.add_subplot(gs[1, 0])
    ordered = province_summary.sort_values("delta_S")
    y = np.arange(len(ordered))
    ax3.barh(y, ordered["extent_effect"], color=COLORS["navy"], label="Cropland-extent effect")
    ax3.barh(y, ordered["use_intensity_effect"], left=ordered["extent_effect"], color=COLORS["teal"], label="Use-intensity effect")
    ax3.scatter(ordered["delta_S"], y, color=COLORS["charcoal"], s=16, label="Observed ΔS", zorder=3)
    ax3.set_yticks(y)
    ax3.set_yticklabels(ordered["Province"], fontsize=6)
    ax3.set_xlabel("Change in crop sown area (kha)")
    ax3.legend(frameon=False, ncol=1, loc="lower right")
    despine(ax3)
    panel_label(ax3, "c")

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(national_timeseries["Year"], national_timeseries["decoupling_index_pct"], color=COLORS["plum"], marker="o", ms=3)
    ax4.axhline(0, color=COLORS["mid_gray"], lw=0.8)
    ax4.set_xlabel("Year")
    ax4.set_ylabel("Decoupling index, DI = gS − gC (%)")
    despine(ax4)
    panel_label(ax4, "d")

    save_figure(fig, output_base, dpi=dpi)
    plt.close(fig)


def plot_model_heatmap(
    coefficient_file: str | Path,
    output_base: str | Path,
    coefficient_columns=("SSN", "GM", "IPLG", "RW"),
    row_label_cols=("Year", "Region"),
    dpi: int = 300,
) -> None:
    """Plot local GTWR/TWR coefficients as a heatmap."""
    set_publication_style(dpi=dpi)
    path = Path(coefficient_file)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    labels = []
    for _, row in df.iterrows():
        parts = [str(row[c]) for c in row_label_cols if c in df.columns]
        labels.append("_".join(parts) if parts else str(_))
    data = df[list(coefficient_columns)].astype(float)
    fig, ax = plt.subplots(figsize=(6.5, max(4, len(data) * 0.08)))
    vmax = np.nanmax(np.abs(data.to_numpy()))
    im = ax.imshow(data.to_numpy(), aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    ax.set_xticks(np.arange(len(coefficient_columns)))
    ax.set_xticklabels(coefficient_columns)
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels, fontsize=5)
    ax.set_title("Local regression coefficients")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Coefficient")
    save_figure(fig, output_base, dpi=dpi)
    plt.close(fig)
