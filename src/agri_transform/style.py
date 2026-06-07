"""Figure style utilities."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt


COLORS = {
    "navy": "#24476E",
    "blue": "#3F6F95",
    "teal": "#36A295",
    "sand": "#D5A03A",
    "terracotta": "#C05640",
    "plum": "#7E5A9B",
    "charcoal": "#222222",
    "dark_gray": "#555555",
    "mid_gray": "#B8B8B8",
    "light_gray": "#E8E8E8",
    "very_light_gray": "#F5F5F5",
}


def set_publication_style(dpi: int = 300, font_family: str = "Times New Roman") -> None:
    """Apply a restrained publication-style Matplotlib theme."""
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": [font_family, "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "figure.dpi": dpi,
            "savefig.dpi": dpi,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": COLORS["charcoal"],
            "axes.linewidth": 1.0,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8.5,
            "lines.linewidth": 1.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.major.size": 4,
            "ytick.major.size": 4,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.unicode_minus": False,
        }
    )


def despine(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def panel_label(ax, label: str, x: float = -0.12, y: float = 1.06, size: int = 12) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=size, fontweight="bold", va="top", ha="left")


def save_figure(fig, output_base: str | Path, formats=("png", "pdf"), dpi: int = 300) -> None:
    output_base = Path(output_base)
    output_base.parent.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        fig.savefig(output_base.with_suffix(f".{fmt}"), bbox_inches="tight", dpi=dpi, facecolor="white")
