# -*- coding: utf-8 -*-
"""
========================================================
Top-tier Nature-style macro analysis of cropland and sown area

Only uses:
1) Cropland area table
2) Sown area table

Input table format for both tables:
FID | Province | 2000 | 2001 | ... | 2023

Core logic:
1. Compare cropland area and sown area over 2000–2023
2. Derive cropping intensity: I_it = S_it / C_it
3. Classify provinces by cropland relative change:
   Expansion / Stable / Contraction
   using ±5% threshold
4. Analyze sown area and intensity responses within cropland groups
5. Produce publication-level figures:
   Fig.1 Master composite
   Fig.2 Province-level comparison
   Fig.3 Three-panel temporal heatmap

Units: kha
========================================================
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

CROPLAND_FILE = r"E:/2025/nature communication/返修3/过程/crop_area.xlsx"
SOWN_FILE = r"E:/2025/nature communication/返修3/过程/sown_area.xlsx"

CROPLAND_SHEET = 0
SOWN_SHEET = 0

OUTPUT_DIR = Path(r"E:/2025/nature communication/返修3/过程/output_macro_top")

INPUT_SCALE_TO_KHA = 1.0

# Stable is not equal to 0.
# Provinces within ±5% relative change are classified as Stable.
STABLE_TOL_PERCENT = 5.0

FIG_DPI = 300
SAVE_FORMATS = ("png", "pdf")

START_YEAR = 2000
END_YEAR = 2023

# =====================================================
# Top-tier Nature-style palette
# =====================================================

NAVY = "#173A5E"
DEEP_BLUE = "#264653"

TEAL = "#2A9D8F"        # Expansion
SAND = "#D9A441"        # Stable
TERRACOTTA = "#A63A2B"  # Contraction

MOSS = "#5C7A66"
PLUM = "#6B4C88"

CHARCOAL = "#222222"
DARK_GRAY = "#555555"
MID_GRAY = "#C8C8C8"
LIGHT_GRAY = "#EFEFEF"
PALE_GRAY = "#F7F7F7"

STATUS_ORDER = ["Expansion", "Stable", "Contraction"]

STATUS_COLORS = {
    "Expansion": TEAL,
    "Stable": SAND,
    "Contraction": TERRACOTTA,
}

SIGN_COLORS = {
    "positive": TEAL,
    "negative": TERRACOTTA,
    "stable": SAND,
}

DIVERGING_CMAP = LinearSegmentedColormap.from_list(
    "TopNatureDiverging",
    [
        "#244C74",
        "#6E96B9",
        "#F7F7F7",
        "#D9A441",
        "#A63A2B",
    ],
    N=256
)

SEQUENTIAL_CMAP = LinearSegmentedColormap.from_list(
    "TopNatureSequential",
    [
        "#F7F8FA",
        "#DDE7EF",
        "#B7CADB",
        "#7799B8",
        "#254E70",
    ],
    N=256
)

# =====================================================
# Global style
# =====================================================

def set_nature_style():
    mpl.rcParams.update({
        "font.family": "Times New Roman",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",

        "figure.dpi": FIG_DPI,
        "savefig.dpi": FIG_DPI,
        "figure.facecolor": "white",
        "axes.facecolor": "white",

        "axes.edgecolor": CHARCOAL,
        "axes.linewidth": 1.0,

        "axes.titlesize": 23,
        "axes.titleweight": "bold",
        "axes.labelsize": 20,

        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "legend.fontsize": 16,

        "lines.linewidth": 2.5,

        "xtick.direction": "out",
        "ytick.direction": "out",

        "xtick.major.width": 1.0,
        "ytick.major.width": 1.0,
        "xtick.major.size": 5.5,
        "ytick.major.size": 5.5,

        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.unicode_minus": False,
    })


def despine(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def panel_label(ax, label, x=-0.105, y=1.055):
    ax.text(
        x, y, label,
        transform=ax.transAxes,
        fontsize=25,
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
    out_base.parent.mkdir(parents=True, exist_ok=True)
    for ext in SAVE_FORMATS:
        fig.savefig(
            str(out_base.with_suffix(f".{ext}")),
            dpi=FIG_DPI,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none"
        )


# =====================================================
# Data helpers
# =====================================================

def read_table(input_file, sheet_name=0):
    path = Path(input_file)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path, sheet_name=sheet_name)
    elif suffix == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    else:
        raise ValueError("Unsupported file format. Please use .xlsx, .xls, or .csv.")


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

    return sorted(year_cols, key=lambda x: int(str(x)))


def safe_percent_change(new, old):
    if pd.isna(old) or old == 0:
        return np.nan
    return (new - old) / old * 100.0


def classify_status_by_pct(pct_change, tol=STABLE_TOL_PERCENT):
    if pd.isna(pct_change):
        return "Stable"

    if pct_change > tol:
        return "Expansion"
    elif pct_change < -tol:
        return "Contraction"
    else:
        return "Stable"


def status_symbol(status):
    if status == "Expansion":
        return "↑"
    elif status == "Contraction":
        return "↓"
    return "≈"


def row_trend_stats(years, values):
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)

    mask = np.isfinite(x) & np.isfinite(y)

    if mask.sum() < 3:
        return np.nan, np.nan, np.nan, np.nan

    res = linregress(x[mask], y[mask])
    return res.slope, res.intercept, res.rvalue, res.pvalue


def prepare_wide_table(path, sheet_name, value_name):
    df = read_table(path, sheet_name=sheet_name)

    fid_col = find_first_matching_column(df.columns, ["FID", "fid", "ID", "Id"])
    province_col = find_first_matching_column(
        df.columns,
        ["Province", "province", "省份", "省市", "地区", "Region", "region"]
    )

    if province_col is None:
        raise ValueError(f"Could not find Province column in {path}")

    year_cols = detect_year_columns(df.columns, START_YEAR, END_YEAR)
    expected_years = list(range(START_YEAR, END_YEAR + 1))
    found_years = [int(str(c)) for c in year_cols]
    missing = [y for y in expected_years if y not in found_years]

    if missing:
        raise ValueError(f"{path} is missing year columns: {missing}")

    keep_cols = [c for c in [fid_col, province_col] if c is not None] + year_cols
    df = df[keep_cols].copy()

    df[province_col] = df[province_col].astype(str).str.strip()

    for c in year_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce") * INPUT_SCALE_TO_KHA

    rename_map = {province_col: "Province"}
    if fid_col is not None:
        rename_map[fid_col] = "FID"

    df = df.rename(columns=rename_map)

    if "FID" not in df.columns:
        df["FID"] = np.nan

    df = df[["FID", "Province"] + year_cols].copy()
    df.attrs["value_name"] = value_name
    df.attrs["year_cols"] = year_cols

    return df, year_cols


# =====================================================
# Core analysis
# =====================================================

def build_joint_summary(crop_df, sown_df, year_cols):
    years = [int(str(c)) for c in year_cols]

    crop = crop_df.copy()
    sown = sown_df.copy()

    common_provinces = sorted(
        set(crop["Province"]).intersection(set(sown["Province"]))
    )

    if len(common_provinces) == 0:
        raise ValueError("No common provinces found between cropland and sown-area tables.")

    crop = (
        crop[crop["Province"].isin(common_provinces)]
        .set_index("Province")
        .loc[common_provinces]
        .reset_index()
    )

    sown = (
        sown[sown["Province"].isin(common_provinces)]
        .set_index("Province")
        .loc[common_provinces]
        .reset_index()
    )

    records = []

    for i, prov in enumerate(common_provinces):
        c = crop.loc[i, year_cols].to_numpy(dtype=float)
        s = sown.loc[i, year_cols].to_numpy(dtype=float)

        intensity = np.divide(
            s,
            c,
            out=np.full_like(s, np.nan, dtype=float),
            where=np.isfinite(c) & (c != 0)
        )

        # Cropland
        c_delta = np.diff(c)
        c_net = c[-1] - c[0]
        c_pct = safe_percent_change(c[-1], c[0])
        c_exp = np.clip(c_delta, 0, None).sum()
        c_con = np.clip(-c_delta, 0, None).sum()
        c_slope, c_intercept, c_r, c_p = row_trend_stats(years, c)

        # Sown area
        s_delta = np.diff(s)
        s_net = s[-1] - s[0]
        s_pct = safe_percent_change(s[-1], s[0])
        s_exp = np.clip(s_delta, 0, None).sum()
        s_con = np.clip(-s_delta, 0, None).sum()
        s_slope, s_intercept, s_r, s_p = row_trend_stats(years, s)

        # Cropping intensity
        i_net = intensity[-1] - intensity[0]
        i_pct = safe_percent_change(intensity[-1], intensity[0])
        i_slope, i_intercept, i_r, i_p = row_trend_stats(years, intensity)

        crop_status = classify_status_by_pct(c_pct)
        sown_status = classify_status_by_pct(s_pct)

        records.append({
            "FID": crop.loc[i, "FID"] if "FID" in crop.columns else np.nan,
            "Province": prov,

            "Cropland_2000_kha": c[0],
            "Cropland_2023_kha": c[-1],
            "Cropland_Net_kha": c_net,
            "Cropland_Net_pct": c_pct,
            "Cropland_Gross_Expansion_kha": c_exp,
            "Cropland_Gross_Contraction_kha": c_con,
            "Cropland_Turnover_kha": c_exp + c_con,
            "Cropland_Slope_kha_per_year": c_slope,
            "Cropland_R2": c_r ** 2 if pd.notna(c_r) else np.nan,
            "Cropland_Pvalue": c_p,

            "Sown_2000_kha": s[0],
            "Sown_2023_kha": s[-1],
            "Sown_Net_kha": s_net,
            "Sown_Net_pct": s_pct,
            "Sown_Gross_Expansion_kha": s_exp,
            "Sown_Gross_Contraction_kha": s_con,
            "Sown_Turnover_kha": s_exp + s_con,
            "Sown_Slope_kha_per_year": s_slope,
            "Sown_R2": s_r ** 2 if pd.notna(s_r) else np.nan,
            "Sown_Pvalue": s_p,

            "Intensity_2000": intensity[0],
            "Intensity_2023": intensity[-1],
            "Intensity_Net": i_net,
            "Intensity_Net_pct": i_pct,
            "Intensity_Slope_per_year": i_slope,
            "Intensity_R2": i_r ** 2 if pd.notna(i_r) else np.nan,
            "Intensity_Pvalue": i_p,

            "Cropland_Status": crop_status,
            "Sown_Status": sown_status,
            "Coupling_Class": f"C{status_symbol(crop_status)}–S{status_symbol(sown_status)}",
        })

    summary = pd.DataFrame(records)
    summary = summary.sort_values(
        ["Cropland_Net_pct", "Province"],
        ascending=[False, True]
    ).reset_index(drop=True)

    national = pd.DataFrame({
        "Year": years,
        "Cropland_Area_kha": crop[year_cols].sum(axis=0).to_numpy(dtype=float),
        "Sown_Area_kha": sown[year_cols].sum(axis=0).to_numpy(dtype=float),
    })

    national["Cropping_Intensity"] = (
        national["Sown_Area_kha"] /
        national["Cropland_Area_kha"]
    )

    national["Cropland_YoY_kha"] = national["Cropland_Area_kha"].diff()
    national["Sown_YoY_kha"] = national["Sown_Area_kha"].diff()
    national["Intensity_YoY"] = national["Cropping_Intensity"].diff()

    group_summary = (
        summary.groupby("Cropland_Status", dropna=False)
        .agg(
            Provinces=("Province", "count"),
            Mean_Cropland_Net_pct=("Cropland_Net_pct", "mean"),
            Median_Cropland_Net_pct=("Cropland_Net_pct", "median"),
            Mean_Sown_Net_pct=("Sown_Net_pct", "mean"),
            Median_Sown_Net_pct=("Sown_Net_pct", "median"),
            Mean_Intensity_Net=("Intensity_Net", "mean"),
            Median_Intensity_Net=("Intensity_Net", "median"),
        )
        .reset_index()
    )

    group_summary["Cropland_Status"] = pd.Categorical(
        group_summary["Cropland_Status"],
        categories=STATUS_ORDER,
        ordered=True
    )
    group_summary = group_summary.sort_values("Cropland_Status")

    coupling_summary = (
        summary["Coupling_Class"]
        .value_counts()
        .rename_axis("Coupling_Class")
        .reset_index(name="Count")
    )

    # Full time-series matrices for heatmaps
    crop_matrix = crop[["Province"] + year_cols].copy()
    sown_matrix = sown[["Province"] + year_cols].copy()

    intensity_matrix = pd.DataFrame({"Province": crop["Province"]})
    for cyr in year_cols:
        intensity_matrix[cyr] = sown[cyr] / crop[cyr]

    return summary, national, group_summary, coupling_summary, crop_matrix, sown_matrix, intensity_matrix, years


# =====================================================
# Figure 1: Master composite
# =====================================================

def plot_master_figure(summary, national, out_dir):
    fig = plt.figure(figsize=(18.5, 14.0))

    gs = fig.add_gridspec(
        2, 2,
        height_ratios=[1.0, 1.08],
        width_ratios=[1.0, 1.0],
        left=0.075,
        right=0.985,
        top=0.90,
        bottom=0.075,
        wspace=0.26,
        hspace=0.42
    )

    x = national["Year"].to_numpy()
    cropland = national["Cropland_Area_kha"].to_numpy()
    sown = national["Sown_Area_kha"].to_numpy()
    intensity = national["Cropping_Intensity"].to_numpy()

    # -------------------------------------------------
    # a) National area dynamics
    # -------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0])
    panel_label(ax1, "a")

    ax1.plot(
        x, cropland,
        color=NAVY,
        marker="o",
        markersize=6.8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.5,
        label="Cropland area"
    )

    ax1.plot(
        x, sown,
        color=TERRACOTTA,
        marker="o",
        markersize=6.8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.5,
        label="Sown area"
    )

    ax1.set_title("National cropland and sown area dynamics", pad=16)
    ax1.set_xlabel("Year", labelpad=10)
    ax1.set_ylabel("Area (kha)", labelpad=10)
    ax1.grid(axis="y", color="#E9E9E9", linewidth=0.9)
    ax1.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=7))
    ax1.tick_params(axis="x", pad=8)
    ax1.tick_params(axis="y", pad=8)
    despine(ax1)

    ax1.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.21),
        ncol=2,
        frameon=False,
        fontsize=17,
        handlelength=2.2,
        handletextpad=0.7,
        columnspacing=2.2,
        borderaxespad=0.0
    )

    # -------------------------------------------------
    # b) National cropping intensity
    # -------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    panel_label(ax2, "b")

    ax2.plot(
        x, intensity,
        color=TEAL,
        marker="o",
        markersize=6.8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.5
    )

    ax2.fill_between(
        x,
        intensity,
        np.nanmin(intensity),
        color=TEAL,
        alpha=0.10,
        linewidth=0
    )

    ax2.set_title("National cropping intensity", pad=16)
    ax2.set_xlabel("Year", labelpad=10)
    ax2.set_ylabel("Sown area / cropland area", labelpad=10)
    ax2.grid(axis="y", color="#E9E9E9", linewidth=0.9)
    ax2.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=7))
    ax2.tick_params(axis="x", pad=8)
    ax2.tick_params(axis="y", pad=8)
    despine(ax2)

    # -------------------------------------------------
    # c) Coupling scatter
    # -------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 0])
    panel_label(ax3, "c")

    for status in STATUS_ORDER:
        sub = summary[summary["Cropland_Status"] == status]
        if len(sub) == 0:
            continue

        turnover = sub["Cropland_Turnover_kha"].to_numpy(dtype=float)
        if np.nanmax(turnover) > np.nanmin(turnover):
            sizes = 70 + 180 * (turnover - np.nanmin(turnover)) / (np.nanmax(turnover) - np.nanmin(turnover))
        else:
            sizes = np.full(len(sub), 95)

        ax3.scatter(
            sub["Cropland_Net_pct"],
            sub["Sown_Net_pct"],
            s=sizes,
            color=STATUS_COLORS[status],
            edgecolor="white",
            linewidth=0.9,
            alpha=0.88,
            label=f"{status} (n={len(sub)})"
        )

    ax3.axhline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")
    ax3.axhline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")
    ax3.axvline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")
    ax3.axvline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")
    ax3.axhline(0, color=CHARCOAL, linewidth=1.0)
    ax3.axvline(0, color=CHARCOAL, linewidth=1.0)

    ax3.set_title("Coupling between cropland and sown area change", pad=16)
    ax3.set_xlabel("Cropland change (%)", labelpad=10)
    ax3.set_ylabel("Sown area change (%)", labelpad=10)
    ax3.grid(color="#E9E9E9", linewidth=0.85)
    ax3.tick_params(axis="x", pad=8)
    ax3.tick_params(axis="y", pad=8)
    despine(ax3)

    ax3.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.20),
        ncol=3,
        frameon=False,
        fontsize=15,
        handletextpad=0.6,
        columnspacing=1.5,
        borderaxespad=0.0
    )

    ax3.text(
        0.03, 0.96,
        f"Stable band: ±{STABLE_TOL_PERCENT:.0f}%",
        transform=ax3.transAxes,
        ha="left",
        va="top",
        fontsize=14,
        color=DARK_GRAY
    )

    # -------------------------------------------------
    # d) Intensity change distribution
    # -------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 1])
    panel_label(ax4, "d")

    violin_data = []
    positions = []
    labels = []
    colors = []

    for i, status in enumerate(STATUS_ORDER, start=1):
        vals = (
            summary.loc[summary["Cropland_Status"] == status, "Intensity_Net"]
            .dropna()
            .to_numpy()
        )

        if len(vals) == 0:
            continue

        violin_data.append(vals)
        positions.append(i)
        labels.append(f"{status}\n(n={len(vals)})")
        colors.append(STATUS_COLORS[status])

    if len(violin_data) > 0:
        violin_parts = ax4.violinplot(
            violin_data,
            positions=positions,
            widths=0.66,
            showmeans=False,
            showmedians=False,
            showextrema=False,
            bw_method=0.45
        )

        for pc, color in zip(violin_parts["bodies"], colors):
            pc.set_facecolor(color)
            pc.set_alpha(0.32)
            pc.set_edgecolor(CHARCOAL)
            pc.set_linewidth(1.1)

        for pos, vals, color in zip(positions, violin_data, colors):
            q1, med, q3 = np.nanpercentile(vals, [25, 50, 75])

            ax4.plot(
                [pos - 0.22, pos + 0.22],
                [med, med],
                color=CHARCOAL,
                linewidth=2.0,
                solid_capstyle="round"
            )

            ax4.plot(
                [pos, pos],
                [q1, q3],
                color=CHARCOAL,
                linewidth=4.0,
                solid_capstyle="round",
                alpha=0.95
            )

            jitter = np.linspace(-0.09, 0.09, len(vals)) if len(vals) > 1 else np.array([0])
            ax4.scatter(
                pos + jitter,
                vals,
                s=35,
                color=color,
                edgecolor="white",
                linewidth=0.6,
                alpha=0.72,
                zorder=3
            )

    ax4.axhline(0, color=CHARCOAL, linewidth=1.0)
    ax4.set_title("Cropping intensity response by cropland status", pad=16)
    ax4.set_ylabel("Intensity change (2023 - 2000)", labelpad=10)
    ax4.set_xticks(positions)
    ax4.set_xticklabels(labels, fontsize=16)
    ax4.grid(axis="y", color="#E9E9E9", linewidth=0.85)
    ax4.tick_params(axis="x", pad=8)
    ax4.tick_params(axis="y", pad=8)
    despine(ax4)

    fig.suptitle(
        "Cropland area, sown area and cropping intensity across China’s provinces (2000–2023)",
        fontsize=25,
        fontweight="bold",
        y=0.982
    )

    save_figure(fig, out_dir / "Fig1_master_composite")
    plt.close(fig)


# =====================================================
# Figure 2: Province comparison
# =====================================================

def plot_province_comparison(summary, out_dir):
    order = (
        summary.sort_values("Cropland_Net_pct", ascending=True)
        .reset_index(drop=True)
    )

    y = np.arange(len(order))

    fig = plt.figure(figsize=(24, 14.5))
    gs = fig.add_gridspec(
        1, 3,
        left=0.13,
        right=0.985,
        top=0.89,
        bottom=0.08,
        wspace=0.16
    )

    variables = [
        ("Cropland_Net_pct", "Cropland change", "Change (%)"),
        ("Sown_Net_pct", "Sown area change", "Change (%)"),
        ("Intensity_Net", "Cropping intensity change", "Intensity change"),
    ]

    legend_handles = [
        Patch(facecolor=TEAL, edgecolor="none", label=f"Expansion > +{STABLE_TOL_PERCENT:.0f}%"),
        Patch(facecolor=SAND, edgecolor="none", label=f"Stable ±{STABLE_TOL_PERCENT:.0f}%"),
        Patch(facecolor=TERRACOTTA, edgecolor="none", label=f"Contraction < -{STABLE_TOL_PERCENT:.0f}%"),
    ]

    for i, (var, title, xlabel) in enumerate(variables):
        ax = fig.add_subplot(gs[0, i])

        if i == 0:
            panel_label(ax, "a")
        elif i == 1:
            panel_label(ax, "b")
        else:
            panel_label(ax, "c")

        if var == "Cropland_Net_pct":
            colors = [STATUS_COLORS[s] for s in order["Cropland_Status"]]
        elif var == "Sown_Net_pct":
            colors = [
                TEAL if v > STABLE_TOL_PERCENT else
                TERRACOTTA if v < -STABLE_TOL_PERCENT else
                SAND
                for v in order[var]
            ]
        else:
            colors = [
                TEAL if v > 0 else TERRACOTTA if v < 0 else SAND
                for v in order[var]
            ]

        ax.barh(
            y,
            order[var],
            color=colors,
            edgecolor="white",
            linewidth=0.75,
            height=0.72
        )

        ax.axvline(0, color=CHARCOAL, linewidth=1.0)

        if var in ["Cropland_Net_pct", "Sown_Net_pct"]:
            ax.axvline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")
            ax.axvline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")

        ax.set_title(title, pad=16)
        ax.set_xlabel(xlabel, labelpad=10)
        ax.grid(axis="x", color="#E9E9E9", linewidth=0.85)
        ax.tick_params(axis="x", pad=8)
        despine(ax)

        if i == 0:
            ax.set_yticks(y)
            ax.set_yticklabels(order["Province"], fontsize=18)
            italicize_yticklabels(ax)
            ax.tick_params(axis="y", pad=8)
        else:
            ax.set_yticks(y)
            ax.tick_params(labelleft=False, length=0)

    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.54, 0.955),
        ncol=3,
        frameon=False,
        fontsize=17,
        handlelength=2.0,
        columnspacing=2.4,
        handletextpad=0.7
    )

    fig.suptitle(
        "Province-level changes ordered by cropland relative change",
        fontsize=25,
        fontweight="bold",
        y=0.99
    )

    save_figure(fig, out_dir / "Fig2_province_comparison")
    plt.close(fig)


# =====================================================
# Figure 3: Three-panel temporal heatmap
# =====================================================

def relative_change_matrix(df_matrix, year_cols):
    base = df_matrix[year_cols[0]].to_numpy(dtype=float)
    arr = df_matrix[year_cols].to_numpy(dtype=float)

    rel = np.divide(
        arr - base[:, None],
        base[:, None],
        out=np.full_like(arr, np.nan, dtype=float),
        where=np.isfinite(base[:, None]) & (base[:, None] != 0)
    ) * 100.0

    return rel


def absolute_change_matrix(df_matrix, year_cols):
    base = df_matrix[year_cols[0]].to_numpy(dtype=float)
    arr = df_matrix[year_cols].to_numpy(dtype=float)
    return arr - base[:, None]


def plot_temporal_heatmap(summary, crop_matrix, sown_matrix, intensity_matrix, year_cols, out_dir):
    order = (
        summary.sort_values("Cropland_Net_pct", ascending=False)
        ["Province"]
        .tolist()
    )

    crop_plot = crop_matrix.set_index("Province").loc[order].reset_index()
    sown_plot = sown_matrix.set_index("Province").loc[order].reset_index()
    intensity_plot = intensity_matrix.set_index("Province").loc[order].reset_index()

    crop_rel = relative_change_matrix(crop_plot, year_cols)
    sown_rel = relative_change_matrix(sown_plot, year_cols)
    intensity_abs = absolute_change_matrix(intensity_plot, year_cols)

    panels = [
        (crop_rel, "Cropland area relative change", "Change from 2000 (%)"),
        (sown_rel, "Sown area relative change", "Change from 2000 (%)"),
        (intensity_abs, "Cropping intensity change", "Change from 2000"),
    ]

    fig = plt.figure(figsize=(24, 18))
    gs = fig.add_gridspec(
        3, 1,
        left=0.13,
        right=0.94,
        top=0.92,
        bottom=0.10,
        hspace=0.32
    )

    panel_letters = ["a", "b", "c"]

    tick_idx = list(np.arange(0, len(year_cols), 2))
    if (len(year_cols) - 1) not in tick_idx:
        tick_idx.append(len(year_cols) - 1)

    for i, (data, title, cbar_label) in enumerate(panels):
        ax = fig.add_subplot(gs[i, 0])
        panel_label(ax, panel_letters[i], x=-0.115, y=1.04)

        finite_vals = data[np.isfinite(data)]
        if finite_vals.size == 0:
            vmax = 1.0
        else:
            vmax = np.nanpercentile(np.abs(finite_vals), 98)
            vmax = max(vmax, 1e-6)

        norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)

        im = ax.imshow(
            data,
            aspect="auto",
            cmap=DIVERGING_CMAP,
            norm=norm,
            interpolation="none",
            rasterized=True
        )

        ax.set_title(title, pad=12, fontsize=23)
        ax.set_yticks(np.arange(len(order)))
        ax.set_yticklabels(order, fontsize=16)
        italicize_yticklabels(ax)

        ax.set_xticks(tick_idx)
        ax.set_xticklabels(
            [str(year_cols[j]) for j in tick_idx],
            rotation=45,
            ha="right",
            va="top",
            rotation_mode="anchor",
            fontsize=15
        )

        ax.set_ylabel("Province", labelpad=10, fontsize=19)

        if i == len(panels) - 1:
            ax.set_xlabel("Year", labelpad=10, fontsize=19)

        ax.set_xticks(np.arange(-0.5, len(year_cols), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(order), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=0.40)
        ax.tick_params(which="minor", bottom=False, left=False)
        ax.tick_params(axis="x", pad=8)
        ax.tick_params(axis="y", pad=7)

        despine(ax)

        cbar = fig.colorbar(
            im,
            ax=ax,
            fraction=0.026,
            pad=0.015,
            aspect=28
        )
        cbar.set_label(cbar_label, fontsize=16, labelpad=12)
        cbar.ax.tick_params(labelsize=14, pad=5)

    fig.suptitle(
        "Temporal dynamics of cropland area, sown area and cropping intensity (2000–2023)",
        fontsize=25,
        fontweight="bold",
        y=0.985
    )

    save_figure(fig, out_dir / "Fig3_temporal_heatmap")
    plt.close(fig)


# =====================================================
# Main
# =====================================================

def main():
    set_nature_style()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading data...")

    cropland_df, year_cols_crop = prepare_wide_table(
        CROPLAND_FILE,
        CROPLAND_SHEET,
        "Cropland"
    )

    sown_df, year_cols_sown = prepare_wide_table(
        SOWN_FILE,
        SOWN_SHEET,
        "Sown"
    )

    if year_cols_crop != year_cols_sown:
        raise ValueError(
            "The two tables do not have the same year columns. "
            "Please ensure both tables contain identical columns from 2000 to 2023."
        )

    print("Building summary...")

    (
        summary,
        national,
        group_summary,
        coupling_summary,
        crop_matrix,
        sown_matrix,
        intensity_matrix,
        years
    ) = build_joint_summary(
        cropland_df,
        sown_df,
        year_cols_crop
    )

    # Save tables
    summary.to_csv(
        OUTPUT_DIR / "province_summary.csv",
        index=False,
        encoding="utf-8-sig"
    )

    national.to_csv(
        OUTPUT_DIR / "national_timeseries.csv",
        index=False,
        encoding="utf-8-sig"
    )

    group_summary.to_csv(
        OUTPUT_DIR / "cropland_group_summary.csv",
        index=False,
        encoding="utf-8-sig"
    )

    coupling_summary.to_csv(
        OUTPUT_DIR / "coupling_summary.csv",
        index=False,
        encoding="utf-8-sig"
    )

    try:
        with pd.ExcelWriter(OUTPUT_DIR / "macro_analysis_results.xlsx", engine="openpyxl") as writer:
            summary.to_excel(writer, index=False, sheet_name="Province_Summary")
            national.to_excel(writer, index=False, sheet_name="National_Timeseries")
            group_summary.to_excel(writer, index=False, sheet_name="Group_Summary")
            coupling_summary.to_excel(writer, index=False, sheet_name="Coupling_Summary")
    except Exception as e:
        print(f"Excel export skipped: {e}")

    print("Generating figures...")

    plot_master_figure(summary, national, OUTPUT_DIR)

    plot_province_comparison(summary, OUTPUT_DIR)

    plot_temporal_heatmap(
        summary,
        crop_matrix,
        sown_matrix,
        intensity_matrix,
        year_cols_crop,
        OUTPUT_DIR
    )

    print("\n=== Analysis complete ===")
    print(f"Output directory: {OUTPUT_DIR.resolve()}")

    print("\nCropland-status group summary:")
    print(group_summary.to_string(index=False))

    print("\nCoupling summary:")
    print(coupling_summary.to_string(index=False))

    print("\nSaved files:")
    for p in sorted(OUTPUT_DIR.glob("*")):
        print(" -", p.name)


if __name__ == "__main__":
    main()