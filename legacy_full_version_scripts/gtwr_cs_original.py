# -*- coding: utf-8 -*-
"""
Ultimate optimized composite mechanism figure for:
- CACD-derived cropland extent
- Statistical sown area
- Coupling typology
- National decoupling
- National phase-space trajectory
- Cumulative decomposition

Layout:
a. Upper-left: province-level exact decomposition
b. Upper-right top: coupling typology
c. Upper-right middle: national decoupling index
d. Upper-right bottom: national phase-space trajectory
e. Bottom full-width: cumulative decomposition since 2000

Input table format:
FID | Province | 2000 | 2001 | ... | 2023

Required files:
1) crop_area.xlsx
2) sown_area.xlsx

Output:
Composite_Fig3_mechanism_landscape_ultimate.jpg

Core identity:
C = CACD-derived cropland extent
S = statistical sown area
R = S / C

Exact decomposition:
ΔS = R0ΔC + C0ΔR + ΔCΔR
"""

from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.colors import Normalize
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

warnings.filterwarnings("ignore", category=FutureWarning)

# =========================================================
# User settings
# =========================================================

CROPLAND_FILE = r"E:/2025/nature communication/返修3/过程/crop_area.xlsx"
SOWN_FILE = r"E:/2025/nature communication/返修3/过程/sown_area.xlsx"

OUTPUT_DIR = Path(r"E:/2025/nature communication/返修3/过程/output_composite")
OUTPUT_NAME = "Composite_Fig3_mechanism_landscape_ultimate.jpg"

SHEET_NAME = 0
INPUT_SCALE_TO_KHA = 1.0

START_YEAR = 2000
END_YEAR = 2023

# Stable is not zero. Provinces within ±5% are classified as stable.
STABLE_TOL_PERCENT = 5.0

FIG_DPI = 300

# =========================================================
# Nature-style palette
# =========================================================

NAVY = "#24476E"
TEAL = "#36A295"
SAND = "#D5A03A"
TERRACOTTA = "#C05640"
PLUM = "#7E5A9B"
FOREST = "#5E7D67"
MOSS = "#6A8B74"
SLATE = "#3F5E85"
GOLD = "#D8A648"
BRICK = "#B84F3D"
SOFT_ORANGE = "#D17D4A"
LAVENDER = "#9A7ABF"

LIGHT_GRAY = "#E8E8E8"
VERY_LIGHT_GRAY = "#F2F2F2"
MID_GRAY = "#B8B8B8"
CHARCOAL = "#222222"
DARK_GRAY = "#555555"

# =========================================================
# Global style
# =========================================================

def set_nature_style():
    mpl.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",

        "figure.dpi": FIG_DPI,
        "savefig.dpi": FIG_DPI,
        "figure.facecolor": "white",
        "axes.facecolor": "white",

        "axes.edgecolor": CHARCOAL,
        "axes.linewidth": 1.05,

        "axes.titlesize": 23,
        "axes.titleweight": "bold",
        "axes.labelsize": 18,

        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 14,

        "lines.linewidth": 2.3,

        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.width": 1.0,
        "ytick.major.width": 1.0,
        "xtick.major.size": 5.2,
        "ytick.major.size": 5.2,

        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.unicode_minus": False,
    })


# =========================================================
# Utilities
# =========================================================

def despine(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def panel_label(ax, label, x=-0.085, y=1.055, size=26):
    """
    Unified panel label style.
    """
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        fontsize=size,
        fontweight="bold",
        va="top",
        ha="left",
        color="#111111"
    )


def italicize_yticklabels(ax):
    for lbl in ax.get_yticklabels():
        lbl.set_fontstyle("italic")
        lbl.set_fontfamily("Times New Roman")


def save_figure(fig, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(
        str(out_path),
        dpi=FIG_DPI,
        bbox_inches="tight",
        facecolor="white",
        format="jpg",
        pil_kwargs={"quality": 96}
    )


def read_table(input_file, sheet_name=0):
    path = Path(input_file)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path, sheet_name=sheet_name)

    if suffix == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")

    raise ValueError(f"Unsupported file format: {suffix}")


def find_first_matching_column(columns, candidates):
    mapping = {str(c).strip().lower(): c for c in columns}

    for cand in candidates:
        key = cand.strip().lower()
        if key in mapping:
            return mapping[key]

    return None


def detect_year_columns(columns, start_year=2000, end_year=2023):
    year_cols = []

    for c in columns:
        s = str(c).strip()

        if re.fullmatch(r"(19|20)\d{2}", s):
            y = int(s)
            if start_year <= y <= end_year:
                year_cols.append(c)
            continue

        try:
            f = float(s)
            if f.is_integer():
                y = int(f)
                if start_year <= y <= end_year:
                    year_cols.append(c)
        except Exception:
            pass

    return sorted(year_cols, key=lambda x: int(float(str(x))))


def normalize_year_column_name(c):
    s = str(c).strip()

    if re.fullmatch(r"(19|20)\d{2}", s):
        return int(s)

    try:
        f = float(s)
        if f.is_integer() and 1900 <= int(f) <= 2100:
            return int(f)
    except Exception:
        pass

    return c


def classify_change(v, tol=STABLE_TOL_PERCENT):
    if pd.isna(v):
        return "Stable"

    if v > tol:
        return "Expansion"

    if v < -tol:
        return "Contraction"

    return "Stable"


# =========================================================
# Data preparation
# =========================================================

def prepare_dataset(file_path, value_name):
    df = read_table(file_path, sheet_name=SHEET_NAME)

    fid_col = find_first_matching_column(
        df.columns,
        ["FID", "fid", "ID", "Id"]
    )

    province_col = find_first_matching_column(
        df.columns,
        ["Province", "province", "省份", "省市", "地区", "Region", "region"]
    )

    year_cols_raw = detect_year_columns(df.columns, START_YEAR, END_YEAR)

    if province_col is None:
        raise ValueError(f"Could not find province column in {file_path}")

    expected_years = list(range(START_YEAR, END_YEAR + 1))
    found_years = [int(float(str(c))) for c in year_cols_raw]
    missing = [y for y in expected_years if y not in found_years]

    if missing:
        raise ValueError(f"Missing year columns in {file_path}: {missing}")

    keep_cols = [c for c in [fid_col, province_col] if c is not None] + year_cols_raw
    df = df[keep_cols].copy()

    df[province_col] = df[province_col].astype(str).str.strip()

    rename_map = {province_col: "Province"}

    if fid_col is not None:
        rename_map[fid_col] = "FID"

    for c in year_cols_raw:
        rename_map[c] = int(float(str(c)))

    df = df.rename(columns=rename_map)

    years = expected_years

    for y in years:
        df[y] = pd.to_numeric(df[y], errors="coerce") * INPUT_SCALE_TO_KHA

    if df[years].isna().any().any():
        df[years] = (
            df[years]
            .T
            .interpolate(method="linear", limit_direction="both")
            .T
        )

    return df[["Province"] + years].copy(), years


# =========================================================
# Exact decomposition
# =========================================================

def exact_decomposition(C0, C1, S0, S1):
    """
    S = C × R
    ΔS = R0ΔC + C0ΔR + ΔCΔR
    """

    if C0 == 0 or C1 == 0 or pd.isna(C0) or pd.isna(C1):
        return np.nan, np.nan, np.nan, np.nan, np.nan, np.nan

    R0 = S0 / C0
    R1 = S1 / C1

    dC = C1 - C0
    dS = S1 - S0
    dR = R1 - R0

    extent_effect = R0 * dC
    use_intensity_effect = C0 * dR
    interaction_effect = dC * dR

    return extent_effect, use_intensity_effect, interaction_effect, dS, R0, R1


# =========================================================
# Core metrics
# =========================================================

def build_all_metrics(crop_df, sown_df, years):
    crop_df = crop_df.copy()
    sown_df = sown_df.copy()

    crop_rename = {}
    for c in crop_df.columns:
        crop_rename[c] = normalize_year_column_name(c)

    crop_df = crop_df.rename(columns=crop_rename)

    sown_rename = {}

    for y in years:
        candidates = [
            y,
            str(y),
            float(y),
            f"{y}.0",
            f"{y}_sown",
            f"{str(y)}_sown"
        ]

        found = None

        for cand in candidates:
            if cand in sown_df.columns:
                found = cand
                break

        if found is None:
            for c in sown_df.columns:
                nc = normalize_year_column_name(c)
                if nc == y:
                    found = c
                    break

        if found is None:
            raise KeyError(
                f"Cannot find sown-area column for year {y}. "
                f"Available columns are: {list(sown_df.columns)}"
            )

        sown_rename[found] = f"{y}_sown"

    sown_df = sown_df.rename(columns=sown_rename)
    sown_cols = [f"{y}_sown" for y in years]

    merged = crop_df[["Province"] + years].merge(
        sown_df[["Province"] + sown_cols],
        on="Province",
        how="inner"
    )

    if len(merged) == 0:
        raise ValueError("No matched Province names between cropland and sown-area tables.")

    province_records = []

    for _, row in merged.iterrows():
        p = row["Province"]

        C_series = np.array([row[y] for y in years], dtype=float)
        S_series = np.array([row[f"{y}_sown"] for y in years], dtype=float)

        C0 = C_series[0]
        C1 = C_series[-1]
        S0 = S_series[0]
        S1 = S_series[-1]

        extent_effect, use_effect, interaction_effect, observed_dS, R0, R1 = exact_decomposition(
            C0, C1, S0, S1
        )

        gC = (C1 - C0) / C0 * 100.0 if C0 != 0 else np.nan
        gS = (S1 - S0) / S0 * 100.0 if S0 != 0 else np.nan
        dR = R1 - R0 if pd.notna(R0) and pd.notna(R1) else np.nan

        c_status = classify_change(gC)
        s_status = classify_change(gS)

        province_records.append({
            "Province": p,
            "C0_kha": C0,
            "C1_kha": C1,
            "S0_kha": S0,
            "S1_kha": S1,
            "Cropland_Change_pct": gC,
            "Sown_Change_pct": gS,
            "R0": R0,
            "R1": R1,
            "dR": dR,
            "Observed_delta_S_kha": observed_dS,
            "Extent_effect_kha": extent_effect,
            "Use_intensity_effect_kha": use_effect,
            "Interaction_effect_kha": interaction_effect,
            "C_status": c_status,
            "S_status": s_status
        })

    province_summary = pd.DataFrame(province_records)

    type_map = {
        ("Expansion", "Expansion"): ("C↑–S↑: Extent-driven expansion", TEAL),
        ("Stable", "Expansion"): ("C≈–S↑: Intensification under stable extent", MOSS),
        ("Contraction", "Expansion"): ("C↓–S↑: Intensification under land constraint", SLATE),
        ("Expansion", "Stable"): ("C↑–S≈: Extent expansion with stable planting", FOREST),
        ("Stable", "Stable"): ("C≈–S≈: Stable utilization", GOLD),
        ("Contraction", "Stable"): ("C↓–S≈: Land contraction with stable planting", PLUM),
        ("Expansion", "Contraction"): ("C↑–S↓: Under-utilized extent expansion", LAVENDER),
        ("Stable", "Contraction"): ("C≈–S↓: Planting decline under stable extent", SOFT_ORANGE),
        ("Contraction", "Contraction"): ("C↓–S↓: Dual contraction", BRICK),
    }

    province_summary["Coupling_Type"] = province_summary.apply(
        lambda r: type_map[(r["C_status"], r["S_status"])][0],
        axis=1
    )

    province_summary["Type_Color"] = province_summary.apply(
        lambda r: type_map[(r["C_status"], r["S_status"])][1],
        axis=1
    )

    abs_obs = province_summary["Observed_delta_S_kha"].abs()
    max_abs_obs = abs_obs.max()

    if max_abs_obs > 0:
        province_summary["Bubble_Size"] = 55 + 220 * (abs_obs / max_abs_obs)
    else:
        province_summary["Bubble_Size"] = 95

    nat_C = crop_df[years].sum(axis=0).to_numpy(dtype=float)
    nat_S = sown_df[sown_cols].sum(axis=0).to_numpy(dtype=float)
    nat_R = nat_S / nat_C

    national = pd.DataFrame({
        "Year": years,
        "CACD_Cropland_Extent_kha": nat_C,
        "Statistical_Sown_Area_kha": nat_S,
        "Agricultural_Use_Intensity_Proxy": nat_R
    })

    national["gC_pct"] = (
        national["CACD_Cropland_Extent_kha"] -
        national["CACD_Cropland_Extent_kha"].iloc[0]
    ) / national["CACD_Cropland_Extent_kha"].iloc[0] * 100.0

    national["gS_pct"] = (
        national["Statistical_Sown_Area_kha"] -
        national["Statistical_Sown_Area_kha"].iloc[0]
    ) / national["Statistical_Sown_Area_kha"].iloc[0] * 100.0

    national["DI_pp"] = national["gS_pct"] - national["gC_pct"]

    annual_records = []

    for i in range(1, len(years)):
        C_prev, C_now = nat_C[i - 1], nat_C[i]
        S_prev, S_now = nat_S[i - 1], nat_S[i]
        R_prev, R_now = nat_R[i - 1], nat_R[i]

        dC = C_now - C_prev
        dS = S_now - S_prev
        dR = R_now - R_prev

        extent_effect = R_prev * dC
        use_effect = C_prev * dR
        interaction_effect = dC * dR

        annual_records.append({
            "Year": years[i],
            "Observed_delta_S_kha": dS,
            "Extent_effect_kha": extent_effect,
            "Use_intensity_effect_kha": use_effect,
            "Interaction_effect_kha": interaction_effect,
            "Reconstructed_delta_S_kha": extent_effect + use_effect + interaction_effect
        })

    annual_df = pd.DataFrame(annual_records)

    cumulative_records = []

    C0_nat = nat_C[0]
    S0_nat = nat_S[0]
    R0_nat = nat_R[0]

    for i, yr in enumerate(years):
        dC = nat_C[i] - C0_nat
        dS = nat_S[i] - S0_nat
        dR = nat_R[i] - R0_nat

        extent_effect = R0_nat * dC
        use_effect = C0_nat * dR
        interaction_effect = dC * dR

        cumulative_records.append({
            "Year": yr,
            "Observed_delta_S_kha": dS,
            "Extent_effect_kha": extent_effect,
            "Use_intensity_effect_kha": use_effect,
            "Interaction_effect_kha": interaction_effect,
            "Reconstructed_delta_S_kha": extent_effect + use_effect + interaction_effect
        })

    cumulative_df = pd.DataFrame(cumulative_records)

    return province_summary, national, annual_df, cumulative_df


# =========================================================
# Plotting
# =========================================================

def plot_composite_figure(province_summary, national, annual_df, cumulative_df, out_dir):
    """
    Ultimate optimized landscape composite figure.

    Spatial order:
    a. upper-left provincial decomposition
    b. upper-right coupling typology
    c. middle-right national decoupling
    d. lower-right national phase-space trajectory
    e. bottom cumulative decomposition
    """

    fig = plt.figure(figsize=(23.0, 18.8))

    outer = fig.add_gridspec(
        2, 2,
        width_ratios=[1.48, 1.42],
        height_ratios=[1.38, 0.82],
        left=0.064,
        right=0.982,
        top=0.918,
        bottom=0.072,
        wspace=0.215,
        hspace=0.285
    )

    # =====================================================
    # a. Province-level exact decomposition
    # =====================================================

    ax_a = fig.add_subplot(outer[0, 0])
    panel_label(ax_a, "a.", x=-0.092, y=1.032, size=26)

    ps = (
        province_summary
        .copy()
        .sort_values("Observed_delta_S_kha", ascending=False)
        .reset_index(drop=True)
    )

    y = np.arange(len(ps))

    effects = [
        ("Extent_effect_kha", "Extent effect", NAVY),
        ("Use_intensity_effect_kha", "Use-intensity effect", TEAL),
        ("Interaction_effect_kha", "Interaction effect", SAND),
    ]

    pos_bottom = np.zeros(len(ps))
    neg_bottom = np.zeros(len(ps))

    for col, label, color in effects:
        vals = ps[col].to_numpy(dtype=float)
        pos_vals = np.where(vals > 0, vals, 0.0)
        neg_vals = np.where(vals < 0, vals, 0.0)

        ax_a.barh(
            y,
            pos_vals,
            left=pos_bottom,
            color=color,
            edgecolor="white",
            linewidth=0.55,
            height=0.70
        )

        ax_a.barh(
            y,
            neg_vals,
            left=neg_bottom,
            color=color,
            edgecolor="white",
            linewidth=0.55,
            height=0.70
        )

        pos_bottom += pos_vals
        neg_bottom += neg_vals

    ax_a.scatter(
        ps["Observed_delta_S_kha"],
        y,
        s=34,
        color=CHARCOAL,
        edgecolor="white",
        linewidth=0.60,
        zorder=4
    )

    ax_a.axvline(0, color=CHARCOAL, linewidth=1.15)

    ax_a.set_yticks(y)
    ax_a.set_yticklabels(ps["Province"], fontsize=14.2)
    ax_a.invert_yaxis()
    italicize_yticklabels(ax_a)

    ax_a.set_xlabel(
        "Contribution to statistical sown-area change (kha)",
        labelpad=12,
        fontsize=18.5
    )
    ax_a.set_ylabel("Province", labelpad=12, fontsize=18.5)

    ax_a.set_title(
        "Exact decomposition of statistical sown-area change",
        pad=15,
        fontsize=23.0
    )

    ax_a.grid(axis="x", color=LIGHT_GRAY, linewidth=0.82)
    ax_a.tick_params(axis="x", labelsize=14.0, pad=6)
    ax_a.tick_params(axis="y", pad=5)
    despine(ax_a)

    handles_a = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="None",
            markersize=7.5,
            markerfacecolor=CHARCOAL,
            markeredgecolor="white",
            label="Observed ΔS"
        ),
        Patch(facecolor=NAVY, edgecolor="none", label="Extent effect"),
        Patch(facecolor=TEAL, edgecolor="none", label="Use-intensity effect"),
        Patch(facecolor=SAND, edgecolor="none", label="Interaction effect"),
    ]

    ax_a.legend(
        handles=handles_a,
        loc="lower right",
        bbox_to_anchor=(0.982, 0.048),
        frameon=True,
        fancybox=False,
        edgecolor="none",
        facecolor="white",
        framealpha=0.90,
        fontsize=15.0,
        handlelength=1.8,
        handletextpad=0.65,
        labelspacing=0.62,
        borderpad=0.48
    )

    # =====================================================
    # Right column: b. c. d.
    # =====================================================

    right = outer[0, 1].subgridspec(
        3, 1,
        height_ratios=[1.10, 1.00, 1.10],
        hspace=0.48
    )

    # =====================================================
    # b. Coupling typology
    # =====================================================

    ax_b = fig.add_subplot(right[0, 0])
    panel_label(ax_b, "b.", x=-0.085, y=1.040, size=25)

    ax_b.axvline(0, color=CHARCOAL, linewidth=1.05)
    ax_b.axhline(0, color=CHARCOAL, linewidth=1.05)
    ax_b.axvline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=0.90, linestyle="--")
    ax_b.axvline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=0.90, linestyle="--")
    ax_b.axhline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=0.90, linestyle="--")
    ax_b.axhline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=0.90, linestyle="--")

    type_order = [
        "C↑–S↑: Extent-driven expansion",
        "C≈–S↑: Intensification under stable extent",
        "C↓–S↑: Intensification under land constraint",
        "C↑–S≈: Extent expansion with stable planting",
        "C≈–S≈: Stable utilization",
        "C↓–S≈: Land contraction with stable planting",
        "C↑–S↓: Under-utilized extent expansion",
        "C≈–S↓: Planting decline under stable extent",
        "C↓–S↓: Dual contraction",
    ]

    short_name_map = {
        "C↑–S↑: Extent-driven expansion": "C↑–S↑ Extent-driven",
        "C≈–S↑: Intensification under stable extent": "C≈–S↑ Stable-extent intensification",
        "C↓–S↑: Intensification under land constraint": "C↓–S↑ Land-constraint intensification",
        "C↑–S≈: Extent expansion with stable planting": "C↑–S≈ Extent expansion/stable planting",
        "C≈–S≈: Stable utilization": "C≈–S≈ Stable utilization",
        "C↓–S≈: Land contraction with stable planting": "C↓–S≈ Land contraction/stable planting",
        "C↑–S↓: Under-utilized extent expansion": "C↑–S↓ Under-utilized expansion",
        "C≈–S↓: Planting decline under stable extent": "C≈–S↓ Stable-extent planting decline",
        "C↓–S↓: Dual contraction": "C↓–S↓ Dual contraction",
    }

    legend_items = []

    for tp in type_order:
        sub = province_summary[province_summary["Coupling_Type"] == tp]

        if len(sub) == 0:
            continue

        color = sub["Type_Color"].iloc[0]

        ax_b.scatter(
            sub["Cropland_Change_pct"],
            sub["Sown_Change_pct"],
            s=sub["Bubble_Size"] * 0.82,
            color=color,
            edgecolor="white",
            linewidth=0.85,
            alpha=0.93
        )

        legend_items.append(
            Line2D(
                [],
                [],
                marker="o",
                linestyle="None",
                markersize=7.4,
                markerfacecolor=color,
                markeredgecolor="white",
                label=f"{short_name_map[tp]} (n={len(sub)})"
            )
        )

    ax_b.text(
        0.026,
        0.940,
        f"Stable threshold: ±{STABLE_TOL_PERCENT:.0f}%",
        transform=ax_b.transAxes,
        ha="left",
        va="top",
        fontsize=12.6,
        color=DARK_GRAY
    )

    ax_b.set_title(
        "Coupling between CACD extent and sown area",
        pad=12,
        fontsize=22.0
    )
    ax_b.set_xlabel("CACD extent change (%)", labelpad=7, fontsize=16.8)
    ax_b.set_ylabel("Sown area change (%)", labelpad=7, fontsize=16.8)

    ax_b.grid(color=LIGHT_GRAY, linewidth=0.78)
    ax_b.tick_params(axis="both", labelsize=13.2, pad=4)
    despine(ax_b)

    ax_b.legend(
        handles=legend_items,
        loc="center right",
        bbox_to_anchor=(0.982, 0.50),
        ncol=1,
        frameon=True,
        fancybox=False,
        edgecolor="none",
        facecolor="white",
        framealpha=0.86,
        fontsize=8.8,
        handlelength=1.0,
        handletextpad=0.36,
        labelspacing=0.30,
        borderpad=0.42
    )

    # =====================================================
    # c. National decoupling index
    # =====================================================

    ax_c_right = fig.add_subplot(right[1, 0])
    panel_label(ax_c_right, "c.", x=-0.085, y=1.040, size=25)

    x = national["Year"].values
    di = national["DI_pp"].values

    ax_c_right.plot(
        x,
        di,
        color=PLUM,
        marker="o",
        markersize=5.8,
        markerfacecolor="white",
        linewidth=2.45
    )

    ax_c_right.fill_between(x, di, 0, where=(di >= 0), color=TEAL, alpha=0.24)
    ax_c_right.fill_between(x, di, 0, where=(di < 0), color=TERRACOTTA, alpha=0.18)
    ax_c_right.axhline(0, color=CHARCOAL, linewidth=1.05)

    ax_c_right.set_title(
        "National decoupling between sown area and CACD extent",
        pad=12,
        fontsize=22.0
    )
    ax_c_right.set_xlabel("Year", labelpad=7, fontsize=16.8)
    ax_c_right.set_ylabel("DI (percentage points)", labelpad=7, fontsize=16.8)

    ax_c_right.grid(axis="y", color=LIGHT_GRAY, linewidth=0.78)
    ax_c_right.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    ax_c_right.tick_params(axis="both", labelsize=13.2, pad=4)
    despine(ax_c_right)

    # =====================================================
    # d. National phase-space trajectory
    # =====================================================

    ax_d = fig.add_subplot(right[2, 0])
    panel_label(ax_d, "d.", x=-0.085, y=1.040, size=25)

    gC = national["gC_pct"].values
    gS = national["gS_pct"].values
    yrs = national["Year"].values

    cmap = plt.get_cmap("viridis")
    norm = Normalize(vmin=yrs.min(), vmax=yrs.max())

    for i in range(len(yrs) - 1):
        color = cmap(norm(yrs[i]))
        ax_d.plot(gC[i:i + 2], gS[i:i + 2], color=color, linewidth=2.25)
        ax_d.scatter(
            gC[i],
            gS[i],
            color=color,
            s=42,
            edgecolor="white",
            linewidth=0.68,
            zorder=3
        )

    ax_d.scatter(
        gC[-1],
        gS[-1],
        color=cmap(norm(yrs[-1])),
        s=54,
        edgecolor="white",
        linewidth=0.68,
        zorder=3
    )

    ax_d.axvline(0, color=CHARCOAL, linewidth=1.05)
    ax_d.axhline(0, color=CHARCOAL, linewidth=1.05)
    ax_d.axvline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=0.85, linestyle="--")
    ax_d.axvline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=0.85, linestyle="--")
    ax_d.axhline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=0.85, linestyle="--")
    ax_d.axhline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=0.85, linestyle="--")

    ax_d.set_title("National phase-space trajectory", pad=12, fontsize=22.0)
    ax_d.set_xlabel("CACD extent change from 2000 (%)", labelpad=7, fontsize=16.8)
    ax_d.set_ylabel("Sown area change from 2000 (%)", labelpad=7, fontsize=16.8)

    ax_d.grid(color=LIGHT_GRAY, linewidth=0.78)
    ax_d.tick_params(axis="both", labelsize=13.2, pad=4)
    despine(ax_d)

    cax = inset_axes(
        ax_d,
        width="2.70%",
        height="72%",
        loc="center right",
        bbox_to_anchor=(0.068, 0.0, 1.0, 1.0),
        bbox_transform=ax_d.transAxes,
        borderpad=0
    )

    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])

    cb = fig.colorbar(sm, cax=cax)
    cb.set_label("Year", fontsize=11.2, labelpad=6)
    cb.ax.tick_params(labelsize=10.2)

    # =====================================================
    # e. Cumulative decomposition since 2000
    # =====================================================

    ax_e = fig.add_subplot(outer[1, :])
    panel_label(ax_e, "e.", x=-0.030, y=1.035, size=26)

    yr = cumulative_df["Year"].values
    extent = cumulative_df["Extent_effect_kha"].values
    use = cumulative_df["Use_intensity_effect_kha"].values
    inter = cumulative_df["Interaction_effect_kha"].values
    obs = cumulative_df["Observed_delta_S_kha"].values

    components = [
        (extent, NAVY),
        (use, TEAL),
        (inter, SAND)
    ]

    pos_base = np.zeros_like(yr, dtype=float)
    neg_base = np.zeros_like(yr, dtype=float)

    for vals, color in components:
        pos = np.where(vals > 0, vals, 0.0)
        neg = np.where(vals < 0, vals, 0.0)

        ax_e.fill_between(
            yr,
            pos_base,
            pos_base + pos,
            color=color,
            alpha=0.78,
            linewidth=0
        )

        ax_e.fill_between(
            yr,
            neg_base,
            neg_base + neg,
            color=color,
            alpha=0.78,
            linewidth=0
        )

        pos_base += pos
        neg_base += neg

    ax_e.plot(
        yr,
        obs,
        color=CHARCOAL,
        marker="o",
        markersize=6.0,
        markerfacecolor="white",
        markeredgewidth=1.0,
        linewidth=2.45,
        zorder=4
    )

    ax_e.axhline(0, color=CHARCOAL, linewidth=1.05)

    ax_e.set_title("Cumulative decomposition since 2000", pad=13, fontsize=23.5)
    ax_e.set_xlabel("Year", labelpad=8, fontsize=18.2)
    ax_e.set_ylabel("Cumulative contribution to ΔS (kha)", labelpad=8, fontsize=18.2)

    ax_e.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
    ax_e.grid(axis="y", color=LIGHT_GRAY, linewidth=0.80)
    ax_e.tick_params(axis="both", labelsize=14.2, pad=5)
    despine(ax_e)

    handles_e = [
        Patch(facecolor=NAVY, edgecolor="none", label="Extent effect"),
        Patch(facecolor=TEAL, edgecolor="none", label="Use-intensity effect"),
        Patch(facecolor=SAND, edgecolor="none", label="Interaction effect"),
        Line2D(
            [],
            [],
            color=CHARCOAL,
            marker="o",
            markersize=6.2,
            markerfacecolor="white",
            linewidth=2.35,
            label="Observed ΔS"
        ),
    ]

    ax_e.legend(
        handles=handles_e,
        loc="upper left",
        bbox_to_anchor=(0.017, 0.968),
        ncol=4,
        frameon=True,
        fancybox=False,
        edgecolor="none",
        facecolor="white",
        framealpha=0.90,
        fontsize=14.4,
        handlelength=1.8,
        handletextpad=0.60,
        columnspacing=1.25,
        labelspacing=0.60,
        borderpad=0.50
    )

    fig.suptitle(
        "Disentangling the sources of statistical sown-area change",
        fontsize=28,
        fontweight="bold",
        y=0.984
    )

    save_figure(fig, out_dir / OUTPUT_NAME)
    plt.close(fig)


# =========================================================
# Main
# =========================================================

def main():
    set_nature_style()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    crop_df, years1 = prepare_dataset(CROPLAND_FILE, "Cropland")
    sown_df, years2 = prepare_dataset(SOWN_FILE, "Sown")

    if years1 != years2:
        raise ValueError("Year columns in cropland and sown files are inconsistent.")

    province_summary, national, annual_df, cumulative_df = build_all_metrics(
        crop_df=crop_df,
        sown_df=sown_df,
        years=years1
    )

    province_summary.to_csv(
        OUTPUT_DIR / "province_summary_for_composite.csv",
        index=False,
        encoding="utf-8-sig"
    )

    national.to_csv(
        OUTPUT_DIR / "national_timeseries_for_composite.csv",
        index=False,
        encoding="utf-8-sig"
    )

    annual_df.to_csv(
        OUTPUT_DIR / "annual_decomposition_for_composite.csv",
        index=False,
        encoding="utf-8-sig"
    )

    cumulative_df.to_csv(
        OUTPUT_DIR / "cumulative_decomposition_for_composite.csv",
        index=False,
        encoding="utf-8-sig"
    )

    plot_composite_figure(
        province_summary=province_summary,
        national=national,
        annual_df=annual_df,
        cumulative_df=cumulative_df,
        out_dir=OUTPUT_DIR
    )

    print("Ultimate optimized composite figure generated successfully.")
    print("Output JPG:", (OUTPUT_DIR / OUTPUT_NAME).resolve())


if __name__ == "__main__":
    main()