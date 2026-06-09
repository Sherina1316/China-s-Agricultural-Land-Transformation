# -*- coding: utf-8 -*-
"""
Nature-style cropland expansion / contraction analysis
Optimized for:
- Larger readable typography
- Italic y-axis labels
- Times New Roman throughout
- Non-overlapping legends
- Nature-style whitespace
- Publication-ready layout
- Enhanced heatmap perception

Author: Optimized Edition
"""

from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.ticker import MaxNLocator
from matplotlib.patches import Patch

from scipy.stats import linregress

warnings.filterwarnings("ignore", category=FutureWarning)

# =====================================================
# User settings
# =====================================================

INPUT_FILE = r"E:/2025/nature communication/返修3/过程/crop_area.xlsx"
SHEET_NAME = 0

OUTPUT_DIR = Path(
    r"E:/2025/nature communication/返修3/过程/output1"
)

INPUT_SCALE_TO_KHA = 1.0
STABLE_TOL_KHA = 1e-9

FIG_DPI = 300
SAVE_FORMATS = ("png", "pdf")

# =====================================================
# Nature-style palette
# =====================================================

NAVY = "#1B365D"
DEEP_BLUE = "#264653"
TEAL = "#2A9D8F"
GOLD = "#D4A017"
ORANGE = "#C76D3A"
RED = "#A63A2B"

LIGHT_GRAY = "#ECECEC"
MID_GRAY = "#CFCFCF"
CHARCOAL = "#222222"

NATURE_CMAP = LinearSegmentedColormap.from_list(
    "NatureBalance",
    [
        "#264653",
        "#4C6F7A",
        "#EAEAEA",
        "#D9A441",
        "#A63A2B"
    ],
    N=256
)

# =====================================================
# Global style
# =====================================================

def set_nature_style():
    mpl.rcParams.update({

        "font.family": "Times New Roman",
        "font.serif": [
            "Times New Roman",
            "Times",
            "DejaVu Serif"
        ],

        "mathtext.fontset": "stix",

        "figure.dpi": FIG_DPI,
        "savefig.dpi": FIG_DPI,

        "figure.facecolor": "white",
        "axes.facecolor": "white",

        "axes.edgecolor": "#222222",
        "axes.linewidth": 1.1,

        "axes.titlesize": 24,
        "axes.titleweight": "bold",

        "axes.labelsize": 22,

        "xtick.labelsize": 19,
        "ytick.labelsize": 19,

        "legend.fontsize": 19,

        "lines.linewidth": 2.8,

        "xtick.direction": "out",
        "ytick.direction": "out",

        "xtick.major.width": 1.0,
        "ytick.major.width": 1.0,

        "xtick.major.size": 6,
        "ytick.major.size": 6,

        "pdf.fonttype": 42,
        "ps.fonttype": 42,

        "axes.unicode_minus": False,
    })


# =====================================================
# Utilities
# =====================================================

def despine(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def panel_label(ax, label):
    ax.text(
        -0.12,
        1.08,
        label,
        transform=ax.transAxes,
        fontsize=28,
        fontweight="bold",
        va="top",
        ha="left",
        color="#111111"
    )


def italicize_yticklabels(ax):
    for label in ax.get_yticklabels():
        label.set_fontstyle("italic")
        label.set_fontfamily("Times New Roman")


def save_figure(fig, out_base: Path):
    out_base.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    for ext in SAVE_FORMATS:
        fig.savefig(
            str(out_base.with_suffix(f".{ext}")),
            dpi=FIG_DPI,
            bbox_inches="tight",
            facecolor="white"
        )


# =====================================================
# Reading data
# =====================================================

def read_table(input_file, sheet_name=0):
    path = Path(input_file)

    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path, sheet_name=sheet_name)

    elif suffix == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")

    else:
        raise ValueError("Unsupported file format")


def find_first_matching_column(columns, candidates):
    normalized = {
        str(c).strip().lower(): c
        for c in columns
    }

    for cand in candidates:
        key = cand.strip().lower()
        if key in normalized:
            return normalized[key]

    return None


def detect_year_columns(columns, start_year=2000, end_year=2023):
    year_cols = []

    for c in columns:
        s = str(c).strip()
        if re.fullmatch(r"(19|20)\d{2}", s):
            y = int(s)
            if start_year <= y <= end_year:
                year_cols.append(c)

    return sorted(
        year_cols,
        key=lambda x: int(str(x))
    )


# =====================================================
# Statistics
# =====================================================

def row_trend_stats(years, values):
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)

    mask = np.isfinite(x) & np.isfinite(y)

    if mask.sum() < 3:
        return np.nan, np.nan, np.nan, np.nan

    res = linregress(x[mask], y[mask])

    return (
        res.slope,
        res.intercept,
        res.rvalue,
        res.pvalue
    )


# =====================================================
# Core analysis
# =====================================================

def build_summary(df, province_col, fid_col, year_cols):
    years = [int(str(c)) for c in year_cols]

    keep_cols = (
        [c for c in [fid_col, province_col] if c is not None]
        + year_cols
    )

    df = df[keep_cols].copy()

    for c in year_cols:
        df[c] = (
            pd.to_numeric(df[c], errors="coerce")
            * INPUT_SCALE_TO_KHA
        )

    records = []

    for _, row in df.iterrows():
        province = row[province_col]
        series = row[year_cols].to_numpy(dtype=float)

        annual_delta = np.diff(series)
        expansion = np.clip(annual_delta, 0, None)
        contraction = np.clip(-annual_delta, 0, None)

        gross_expansion = np.sum(expansion)
        gross_contraction = np.sum(contraction)

        turnover = gross_expansion + gross_contraction

        slope, intercept, rvalue, pvalue = row_trend_stats(years, series)

        records.append({
            "Province": province,
            "Area_2000": series[0],
            "Area_2023": series[-1],
            "Net_Change": series[-1] - series[0],
            "Gross_Expansion": gross_expansion,
            "Gross_Contraction": gross_contraction,
            "Turnover": turnover,
            "Slope": slope,
            "Pvalue": pvalue
        })

    summary = pd.DataFrame(records)

    national = pd.DataFrame({
        "Year": years,
        "National_Area": df[year_cols].sum(axis=0).values
    })

    delta = df[year_cols].diff(axis=1).iloc[:, 1:]
    delta.columns = [int(str(c)) for c in delta.columns]
    delta.insert(0, "Province", df[province_col].values)

    return summary, national, delta, years


# =====================================================
# FIGURE 1
# =====================================================

def plot_overview(summary, national, delta, years, out_dir):
    fig = plt.figure(figsize=(24, 10))

    gs = fig.add_gridspec(
        1, 3,
        width_ratios=[1.1, 1.25, 1.9],
        wspace=0.52
    )

    # =================================================
    # a
    # =================================================

    ax1 = fig.add_subplot(gs[0, 0])
    panel_label(ax1, "a")

    x = national["Year"]
    y = national["National_Area"]

    ax1.plot(
        x, y,
        color=NAVY,
        marker="o",
        markersize=7,
        markerfacecolor="white",
        markeredgewidth=1.8
    )

    ax1.fill_between(
        x, y, y.min(),
        color=NAVY,
        alpha=0.08
    )

    ax1.set_title("National cropland trend", pad=18, fontsize=24)
    ax1.set_xlabel("Year", labelpad=10, fontsize=22)
    ax1.set_ylabel("Cropland area (kha)", labelpad=12, fontsize=22)

    ax1.grid(axis="y", color="#E8E8E8", linewidth=0.9)

    ax1.tick_params(axis="x", pad=8)
    ax1.tick_params(axis="y", pad=8)

    ax1.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))

    despine(ax1)

    # =================================================
    # b
    # =================================================

    ax2 = fig.add_subplot(gs[0, 1])
    panel_label(ax2, "b")

    s = summary.sort_values("Net_Change", ascending=True)
    y_pos = np.arange(len(s))

    colors = np.where(
        s["Net_Change"] >= 0,
        TEAL,
        ORANGE
    )

    ax2.hlines(
        y=y_pos,
        xmin=0,
        xmax=s["Net_Change"],
        color=MID_GRAY,
        linewidth=2.5
    )

    ax2.scatter(
        s["Net_Change"],
        y_pos,
        s=90,
        c=colors,
        edgecolor="white",
        linewidth=1.0,
        zorder=5
    )

    ax2.axvline(0, color=CHARCOAL, linewidth=1.1)

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(
        s["Province"],
        fontsize=19,
        fontfamily="Times New Roman"
    )
    italicize_yticklabels(ax2)

    ax2.set_title("Province-level net change", pad=18, fontsize=24)
    ax2.set_xlabel("Net change (kha)", labelpad=10, fontsize=22)
    ax2.tick_params(axis="y", pad=8)
    ax2.grid(axis="x", color="#E8E8E8", linewidth=0.8)

    despine(ax2)

    legend_handles = [
        Patch(
            facecolor=TEAL,
            edgecolor="none",
            label="Expansion"
        ),
        Patch(
            facecolor=ORANGE,
            edgecolor="none",
            label="Contraction"
        )
    ]

    ax2.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.18),
        ncol=2,
        frameon=False,
        fontsize=19,
        handlelength=2.2,
        columnspacing=2.4,
        labelspacing=1.2
    )

    # =================================================
    # c heatmap
    # =================================================

    ax3 = fig.add_subplot(gs[0, 2])
    panel_label(ax3, "c")

    top_exp = summary.nlargest(10, "Net_Change")
    top_con = summary.nsmallest(10, "Net_Change")

    selected = pd.concat([top_exp, top_con])

    order = selected.sort_values("Net_Change", ascending=False)["Province"].tolist()

    year_cols = [c for c in delta.columns if isinstance(c, int)]

    heat = (
        delta
        .set_index("Province")
        .loc[order, year_cols]
        .to_numpy(dtype=float)
    )

    vmax = np.nanpercentile(np.abs(heat), 98)

    norm = TwoSlopeNorm(
        vmin=-vmax,
        vcenter=0,
        vmax=vmax
    )

    im = ax3.imshow(
        heat,
        aspect="auto",
        cmap=NATURE_CMAP,
        norm=norm,
        interpolation="none"
    )

    ax3.set_title("Annual change heatmap", pad=18, fontsize=24)

    tick_idx = np.arange(0, len(year_cols), 2)

    ax3.set_xticks(tick_idx)
    ax3.set_xticklabels(
        [str(year_cols[i]) for i in tick_idx],
        fontsize=19,
        fontfamily="Times New Roman"
    )

    ax3.set_yticks(np.arange(len(order)))
    ax3.set_yticklabels(
        order,
        fontsize=19,
        fontfamily="Times New Roman"
    )
    italicize_yticklabels(ax3)

    ax3.tick_params(axis="y", pad=8)
    ax3.tick_params(axis="x", pad=8)

    ax3.set_xlabel("Year", labelpad=10, fontsize=22)
    ax3.set_ylabel("Province", labelpad=10, fontsize=22)

    ax3.set_xticks(np.arange(-0.5, len(year_cols), 1), minor=True)
    ax3.set_yticks(np.arange(-0.5, len(order), 1), minor=True)

    ax3.grid(which="minor", color="white", linewidth=0.4)

    ax3.tick_params(which="minor", bottom=False, left=False)

    despine(ax3)

    cbar = fig.colorbar(
        im,
        ax=ax3,
        fraction=0.030,
        pad=0.045
    )

    cbar.set_label(
        "Annual change (kha)",
        fontsize=20,
        labelpad=18
    )

    cbar.ax.tick_params(
        labelsize=17,
        pad=6
    )

    # =================================================
    # title
    # =================================================

    fig.suptitle(
        "Cropland expansion and contraction across China’s provinces (2000–2023)",
        fontsize=25,
        fontweight="bold",
        y=0.985
    )

    fig.subplots_adjust(
        top=0.82,
        bottom=0.14,
        left=0.06,
        right=0.98
    )

    save_figure(
        fig,
        out_dir / "Fig1_overview"
    )

    plt.close(fig)


# =====================================================
# FIGURE 2
# =====================================================

def plot_expansion_contraction(summary, out_dir):
    exp = (
        summary[summary["Net_Change"] > 0]
        .sort_values("Net_Change")
    )

    con = (
        summary[summary["Net_Change"] < 0]
        .sort_values("Net_Change", ascending=False)
    )

    fig = plt.figure(figsize=(20, 12))

    gs = fig.add_gridspec(
        1, 2,
        wspace=0.22
    )

    # ================================================
    # Expansion
    # ================================================

    ax1 = fig.add_subplot(gs[0, 0])
    panel_label(ax1, "a")

    y = np.arange(len(exp))

    ax1.barh(
        y,
        exp["Net_Change"],
        color=TEAL,
        edgecolor="white",
        linewidth=0.8,
        height=0.72
    )

    ax1.set_yticks(y)
    ax1.set_yticklabels(
        exp["Province"],
        fontsize=19,
        fontfamily="Times New Roman"
    )
    italicize_yticklabels(ax1)

    ax1.set_title("Expansion provinces", pad=18, fontsize=24)
    ax1.set_xlabel("Net expansion (kha)", labelpad=12, fontsize=22)

    ax1.grid(axis="x", color="#E8E8E8")
    ax1.tick_params(axis="y", pad=8)

    despine(ax1)

    xmax = exp["Net_Change"].max()

    for i, v in enumerate(exp["Net_Change"]):
        ax1.text(
            v + 0.015 * xmax,
            i,
            f"{v:.1f}",
            fontsize=17,
            fontweight="semibold",
            va="center",
            ha="left"
        )

    # ================================================
    # Contraction
    # ================================================

    ax2 = fig.add_subplot(gs[0, 1])
    panel_label(ax2, "b")

    y = np.arange(len(con))

    ax2.barh(
        y,
        con["Net_Change"],
        color=ORANGE,
        edgecolor="white",
        linewidth=0.8,
        height=0.72
    )

    ax2.set_yticks(y)
    ax2.set_yticklabels(
        con["Province"],
        fontsize=19,
        fontfamily="Times New Roman"
    )
    italicize_yticklabels(ax2)

    ax2.set_title("Contraction provinces", pad=18, fontsize=24)
    ax2.set_xlabel("Net contraction (kha)", labelpad=12, fontsize=22)

    ax2.grid(axis="x", color="#E8E8E8")
    ax2.tick_params(axis="y", pad=8)

    despine(ax2)

    xmin = con["Net_Change"].min()

    for i, v in enumerate(con["Net_Change"]):
        ax2.text(
            v - 0.015 * abs(xmin),
            i,
            f"{v:.1f}",
            fontsize=17,
            fontweight="semibold",
            va="center",
            ha="right"
        )

    fig.suptitle(
        "Province-level cropland expansion and contraction",
        fontsize=24,
        fontweight="bold",
        y=0.97
    )

    fig.subplots_adjust(
        top=0.88,
        left=0.08,
        right=0.98,
        bottom=0.08
    )

    save_figure(
        fig,
        out_dir / "Fig2_expansion_contraction"
    )

    plt.close(fig)


# =====================================================
# MAIN
# =====================================================

def main():
    set_nature_style()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    df = read_table(
        INPUT_FILE,
        sheet_name=SHEET_NAME
    )

    fid_col = find_first_matching_column(
        df.columns,
        ["FID", "fid", "ID"]
    )

    province_col = find_first_matching_column(
        df.columns,
        ["Province", "province", "省份", "地区"]
    )

    year_cols = detect_year_columns(
        df.columns,
        2000,
        2023
    )

    summary, national, delta, years = build_summary(
        df,
        province_col,
        fid_col,
        year_cols
    )

    summary.to_csv(
        OUTPUT_DIR / "summary.csv",
        index=False,
        encoding="utf-8-sig"
    )

    plot_overview(
        summary,
        national,
        delta,
        years,
        OUTPUT_DIR
    )

    plot_expansion_contraction(
        summary,
        OUTPUT_DIR
    )

    print("Analysis complete.")
    print("Output:", OUTPUT_DIR.resolve())


if __name__ == "__main__":
    main()