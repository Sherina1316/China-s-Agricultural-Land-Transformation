# -*- coding: utf-8 -*-
"""
========================================================
CACD cropland extent - statistical sown area coupling analysis
Publication-level visualization framework

Input tables:
1) CACD-derived cropland extent table
2) Statistical sown area table

Input format for both tables:
FID | Province | 2000 | 2001 | ... | 2023

Conceptual framework:
C_it = CACD-derived cropland extent
S_it = statistical sown area of farm crops
R_it = S_it / C_it

Important:
R_it is NOT a strict multiple cropping index because the numerator and
denominator come from different data systems. It is treated as:

Agricultural-use intensity proxy
= Statistical sown area / CACD-derived cropland extent

Core indicators:
1) gC = relative change of CACD-derived cropland extent
2) gS = relative change of statistical sown area
3) R  = agricultural-use intensity proxy
4) DI = gS - gC
5) Exact decomposition:
   ΔS = R0·ΔC + C0·ΔR + ΔC·ΔR

Key revision in this version:
- Fig.4 no longer uses raw province-level relative trajectories as the only display.
  Raw relative trajectories can be visually dominated by valid but extreme single-year values.
- Fig.4 now uses robust median + IQR + 10–90% trajectory envelopes, with optional
  lightly clipped individual lines only for visual context.
- No source data are modified. Diagnostics are exported for transparency.

Outputs:
Fig.1 Master overview
Fig.2 Coupling typology scatter
Fig.3 Decomposition of statistical sown-area change
Fig.4 Robust temporal trajectory envelope

Units:
C and S: kha
R: dimensionless
DI: percentage points
========================================================
"""

from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd

import matplotlib as mpl
import matplotlib.pyplot as plt

from matplotlib.ticker import MaxNLocator
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

from scipy.stats import linregress

warnings.filterwarnings("ignore", category=FutureWarning)

# =====================================================
# User settings
# =====================================================

CROPLAND_FILE = r"E:/2025/nature communication/返修3/过程/crop_area.xlsx"
SOWN_FILE = r"E:/2025/nature communication/返修3/过程/sown_area.xlsx"

CROPLAND_SHEET = 0
SOWN_SHEET = 0

OUTPUT_DIR = Path(
    r"E:/2025/nature communication/返修3/过程/output_cacd_sown_final_revised"
)

INPUT_SCALE_TO_KHA = 1.0

START_YEAR = 2000
END_YEAR = 2023

# Stable is not equal to 0.
# Provinces within ±5% relative change are classified as stable.
STABLE_TOL_PERCENT = 5.0

FIG_DPI = 300
SAVE_FORMATS = ("png", "pdf")

# Fig.4 robust display settings
FIG4_SHOW_CLIPPED_PROVINCE_LINES = True
FIG4_INDIVIDUAL_LINE_ALPHA = 0.18
FIG4_CENTRAL_BAND = (0.25, 0.75)      # IQR
FIG4_OUTER_BAND = (0.10, 0.90)        # 10–90% envelope
FIG4_AXIS_QUANTILE = (0.02, 0.98)     # robust y-axis range
FIG4_AXIS_PADDING = 0.12

# Diagnostics thresholds; only for reporting, not for deleting data
DIAGNOSTIC_RELATIVE_CHANGE_THRESHOLD = 300.0
DIAGNOSTIC_RATIO_THRESHOLD = 3.0

# =====================================================
# Publication-level color system
# =====================================================

NAVY = "#173A5E"
BLUE = "#244C74"
TEAL = "#2A9D8F"
SAND = "#D9A441"
TERRACOTTA = "#A63A2B"
PLUM = "#6B4C88"
MOSS = "#5C7A66"
BROWN = "#8C6D31"

CHARCOAL = "#222222"
DARK_GRAY = "#555555"
MID_GRAY = "#C8C8C8"
LIGHT_GRAY = "#E9E9E9"
PALE_GRAY = "#F7F7F7"

STATUS_ORDER = ["Expansion", "Stable", "Contraction"]

STATUS_COLORS = {
    "Expansion": TEAL,
    "Stable": SAND,
    "Contraction": TERRACOTTA,
}

COUPLING_ORDER = [
    "C↑–S↑",
    "C≈–S↑",
    "C↓–S↑",
    "C↑–S≈",
    "C≈–S≈",
    "C↓–S≈",
    "C↑–S↓",
    "C≈–S↓",
    "C↓–S↓",
]

COUPLING_NAMES = {
    "C↑–S↑": "Extent-driven expansion",
    "C≈–S↑": "Intensification under stable extent",
    "C↓–S↑": "Intensification under land constraint",
    "C↑–S≈": "Extent expansion with stable planting",
    "C≈–S≈": "Stable utilization",
    "C↓–S≈": "Land contraction with stable planting",
    "C↑–S↓": "Under-utilized extent expansion",
    "C≈–S↓": "Planting decline under stable extent",
    "C↓–S↓": "Dual contraction",
}

COUPLING_COLORS = {
    "C↑–S↑": "#2A9D8F",
    "C≈–S↑": "#5C7A66",
    "C↓–S↑": "#173A5E",
    "C↑–S≈": "#7FB8A7",
    "C≈–S≈": "#D9A441",
    "C↓–S≈": "#B88A3B",
    "C↑–S↓": "#8E6FAE",
    "C≈–S↓": "#C76D3A",
    "C↓–S↓": "#A63A2B",
}

EFFECT_COLORS = {
    "Extent effect": NAVY,
    "Use-intensity effect": TEAL,
    "Interaction effect": SAND,
}

# =====================================================
# Global style
# =====================================================

def set_publication_style():
    mpl.rcParams.update({
        "font.family": "serif",
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
        "legend.fontsize": 15,

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

    if suffix == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")

    raise ValueError("Unsupported file format. Please use .xlsx, .xls, or .csv.")


def find_first_matching_column(columns, candidates):
    normalized = {str(c).strip().lower(): c for c in columns}

    for cand in candidates:
        key = cand.strip().lower()
        if key in normalized:
            return normalized[key]

    return None


def detect_year_columns(columns, start_year=2000, end_year=2023):
    year_cols = []

    for c in columns:
        s = str(c).strip()

        # Standard case: 2000, 2001, ...
        if re.fullmatch(r"(19|20)\d{2}", s):
            y = int(s)
            if start_year <= y <= end_year:
                year_cols.append(c)
            continue

        # Robust case: 2000.0
        try:
            y_float = float(s)
            if y_float.is_integer():
                y = int(y_float)
                if start_year <= y <= end_year:
                    year_cols.append(c)
        except Exception:
            pass

    return sorted(year_cols, key=lambda x: int(float(str(x))))


def prepare_wide_table(path, sheet_name, value_name):
    df = read_table(path, sheet_name=sheet_name)

    fid_col = find_first_matching_column(
        df.columns,
        ["FID", "fid", "ID", "Id"]
    )

    province_col = find_first_matching_column(
        df.columns,
        ["Province", "province", "省份", "省市", "地区", "Region", "region"]
    )

    if province_col is None:
        raise ValueError(f"Could not find Province column in {path}")

    year_cols = detect_year_columns(df.columns, START_YEAR, END_YEAR)

    expected_years = list(range(START_YEAR, END_YEAR + 1))
    found_years = [int(float(str(c))) for c in year_cols]
    missing = [y for y in expected_years if y not in found_years]

    if missing:
        raise ValueError(f"{path} is missing year columns: {missing}")

    keep_cols = [c for c in [fid_col, province_col] if c is not None] + year_cols
    df = df[keep_cols].copy()

    df[province_col] = df[province_col].astype(str).str.strip()

    for c in year_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce") * INPUT_SCALE_TO_KHA

    # Interpolate missing annual values within each province if necessary.
    # This does not change non-missing values.
    if df[year_cols].isna().any().any():
        df[year_cols] = (
            df[year_cols]
            .T
            .interpolate(method="linear", limit_direction="both")
            .T
        )

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


def safe_percent_change(new, old):
    if pd.isna(old) or old == 0:
        return np.nan

    return (new - old) / old * 100.0


def classify_status_by_pct(pct_change, tol=STABLE_TOL_PERCENT):
    if pd.isna(pct_change):
        return "Stable"

    if pct_change > tol:
        return "Expansion"

    if pct_change < -tol:
        return "Contraction"

    return "Stable"


def status_symbol(status):
    if status == "Expansion":
        return "↑"

    if status == "Contraction":
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


# =====================================================
# Core analysis
# =====================================================

def build_joint_summary(cacd_df, sown_df, year_cols):
    years = [int(float(str(c))) for c in year_cols]

    cacd = cacd_df.copy()
    sown = sown_df.copy()

    common_provinces = sorted(
        set(cacd["Province"]).intersection(set(sown["Province"]))
    )

    if len(common_provinces) == 0:
        raise ValueError("No common provinces found between CACD and sown-area tables.")

    # Use province names as keys rather than relying on row order.
    cacd = (
        cacd[cacd["Province"].isin(common_provinces)]
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
        c = cacd.loc[i, year_cols].to_numpy(dtype=float)
        s = sown.loc[i, year_cols].to_numpy(dtype=float)

        # Agricultural-use intensity proxy:
        # statistical sown area / CACD-derived cropland extent
        r = np.divide(
            s,
            c,
            out=np.full_like(s, np.nan, dtype=float),
            where=np.isfinite(c) & (c != 0)
        )

        c0, c1 = c[0], c[-1]
        s0, s1 = s[0], s[-1]
        r0, r1 = r[0], r[-1]

        dc = c1 - c0
        ds = s1 - s0
        dr = r1 - r0

        gc = safe_percent_change(c1, c0)
        gs = safe_percent_change(s1, s0)
        gr = safe_percent_change(r1, r0)

        di = gs - gc if pd.notna(gs) and pd.notna(gc) else np.nan

        c_delta = np.diff(c)
        s_delta = np.diff(s)
        r_delta = np.diff(r)

        c_gross_exp = np.nansum(np.clip(c_delta, 0, None))
        c_gross_con = np.nansum(np.clip(-c_delta, 0, None))

        s_gross_exp = np.nansum(np.clip(s_delta, 0, None))
        s_gross_con = np.nansum(np.clip(-s_delta, 0, None))

        r_gross_inc = np.nansum(np.clip(r_delta, 0, None))
        r_gross_dec = np.nansum(np.clip(-r_delta, 0, None))

        c_slope, c_intercept, c_r, c_p = row_trend_stats(years, c)
        s_slope, s_intercept, s_r, s_p = row_trend_stats(years, s)
        r_slope, r_intercept, r_r, r_p = row_trend_stats(years, r)

        c_status = classify_status_by_pct(gc)
        s_status = classify_status_by_pct(gs)

        coupling_class = f"C{status_symbol(c_status)}–S{status_symbol(s_status)}"

        # Exact decomposition:
        # ΔS = R0·ΔC + C0·ΔR + ΔC·ΔR
        extent_effect = r0 * dc
        use_intensity_effect = c0 * dr
        interaction_effect = dc * dr
        reconstructed_ds = extent_effect + use_intensity_effect + interaction_effect

        records.append({
            "FID": cacd.loc[i, "FID"] if "FID" in cacd.columns else np.nan,
            "Province": prov,

            "CACD_Cropland_2000_kha": c0,
            "CACD_Cropland_2023_kha": c1,
            "CACD_Cropland_Net_kha": dc,
            "CACD_Cropland_Net_pct": gc,
            "CACD_Cropland_Gross_Expansion_kha": c_gross_exp,
            "CACD_Cropland_Gross_Contraction_kha": c_gross_con,
            "CACD_Cropland_Turnover_kha": c_gross_exp + c_gross_con,
            "CACD_Cropland_Slope_kha_per_year": c_slope,
            "CACD_Cropland_R2": c_r ** 2 if pd.notna(c_r) else np.nan,
            "CACD_Cropland_Pvalue": c_p,

            "Statistical_Sown_2000_kha": s0,
            "Statistical_Sown_2023_kha": s1,
            "Statistical_Sown_Net_kha": ds,
            "Statistical_Sown_Net_pct": gs,
            "Statistical_Sown_Gross_Expansion_kha": s_gross_exp,
            "Statistical_Sown_Gross_Contraction_kha": s_gross_con,
            "Statistical_Sown_Turnover_kha": s_gross_exp + s_gross_con,
            "Statistical_Sown_Slope_kha_per_year": s_slope,
            "Statistical_Sown_R2": s_r ** 2 if pd.notna(s_r) else np.nan,
            "Statistical_Sown_Pvalue": s_p,

            "Use_Intensity_Proxy_2000": r0,
            "Use_Intensity_Proxy_2023": r1,
            "Use_Intensity_Proxy_Net": dr,
            "Use_Intensity_Proxy_Net_pct": gr,
            "Use_Intensity_Proxy_Gross_Increase": r_gross_inc,
            "Use_Intensity_Proxy_Gross_Decrease": r_gross_dec,
            "Use_Intensity_Proxy_Turnover": r_gross_inc + r_gross_dec,
            "Use_Intensity_Proxy_Slope_per_year": r_slope,
            "Use_Intensity_Proxy_R2": r_r ** 2 if pd.notna(r_r) else np.nan,
            "Use_Intensity_Proxy_Pvalue": r_p,

            "Decoupling_Index_pp": di,

            "Extent_Effect_kha": extent_effect,
            "Use_Intensity_Effect_kha": use_intensity_effect,
            "Interaction_Effect_kha": interaction_effect,
            "Reconstructed_Sown_Change_kha": reconstructed_ds,
            "Decomposition_Error_kha": ds - reconstructed_ds,

            "CACD_Cropland_Status": c_status,
            "Statistical_Sown_Status": s_status,
            "Coupling_Class": coupling_class,
            "Coupling_Name": COUPLING_NAMES.get(coupling_class, coupling_class),
        })

    summary = pd.DataFrame(records)

    summary["Coupling_Class"] = pd.Categorical(
        summary["Coupling_Class"],
        categories=COUPLING_ORDER,
        ordered=True
    )

    summary = summary.sort_values(
        ["Coupling_Class", "CACD_Cropland_Net_pct", "Province"],
        ascending=[True, False, True]
    ).reset_index(drop=True)

    national = pd.DataFrame({
        "Year": years,
        "CACD_Cropland_Extent_kha": cacd[year_cols].sum(axis=0).to_numpy(dtype=float),
        "Statistical_Sown_Area_kha": sown[year_cols].sum(axis=0).to_numpy(dtype=float),
    })

    national["Agricultural_Use_Intensity_Proxy"] = (
        national["Statistical_Sown_Area_kha"] /
        national["CACD_Cropland_Extent_kha"]
    )

    national["CACD_Cropland_Relative_Change_pct"] = (
        (national["CACD_Cropland_Extent_kha"] -
         national["CACD_Cropland_Extent_kha"].iloc[0]) /
        national["CACD_Cropland_Extent_kha"].iloc[0] * 100.0
    )

    national["Statistical_Sown_Relative_Change_pct"] = (
        (national["Statistical_Sown_Area_kha"] -
         national["Statistical_Sown_Area_kha"].iloc[0]) /
        national["Statistical_Sown_Area_kha"].iloc[0] * 100.0
    )

    national["Use_Intensity_Proxy_Change"] = (
        national["Agricultural_Use_Intensity_Proxy"] -
        national["Agricultural_Use_Intensity_Proxy"].iloc[0]
    )

    national["National_Decoupling_Index_pp"] = (
        national["Statistical_Sown_Relative_Change_pct"] -
        national["CACD_Cropland_Relative_Change_pct"]
    )

    group_summary = (
        summary.groupby("Coupling_Class", observed=False)
        .agg(
            Provinces=("Province", "count"),
            Mean_CACD_Cropland_Net_pct=("CACD_Cropland_Net_pct", "mean"),
            Mean_Statistical_Sown_Net_pct=("Statistical_Sown_Net_pct", "mean"),
            Mean_Decoupling_Index_pp=("Decoupling_Index_pp", "mean"),
            Mean_Use_Intensity_Proxy_Net=("Use_Intensity_Proxy_Net", "mean"),
            Mean_Extent_Effect_kha=("Extent_Effect_kha", "mean"),
            Mean_Use_Intensity_Effect_kha=("Use_Intensity_Effect_kha", "mean"),
            Mean_Interaction_Effect_kha=("Interaction_Effect_kha", "mean"),
        )
        .reset_index()
    )

    coupling_summary = (
        summary["Coupling_Class"]
        .value_counts()
        .rename_axis("Coupling_Class")
        .reset_index(name="Count")
    )

    cacd_matrix = cacd[["Province"] + year_cols].copy()
    sown_matrix = sown[["Province"] + year_cols].copy()

    proxy_matrix = pd.DataFrame({"Province": cacd["Province"]})
    for yr in year_cols:
        proxy_matrix[yr] = sown[yr] / cacd[yr]

    return (
        summary,
        national,
        group_summary,
        coupling_summary,
        cacd_matrix,
        sown_matrix,
        proxy_matrix,
        years
    )


# =====================================================
# Diagnostics
# =====================================================

def export_temporal_diagnostics(cacd_matrix, sown_matrix, proxy_matrix, year_cols, out_dir):
    """
    Export diagnostics for temporal values.
    No values are deleted or modified. This only helps identify which raw
    year-province values dominate raw relative-trajectory plots.
    """
    cacd_idx = cacd_matrix.set_index("Province")
    sown_idx = sown_matrix.set_index("Province")
    proxy_idx = proxy_matrix.set_index("Province")

    records = []

    for province in sown_idx.index:
        s0 = sown_idx.loc[province, year_cols[0]]
        c0 = cacd_idx.loc[province, year_cols[0]]
        r0 = proxy_idx.loc[province, year_cols[0]]

        for yr in year_cols:
            c_val = cacd_idx.loc[province, yr]
            s_val = sown_idx.loc[province, yr]
            r_val = proxy_idx.loc[province, yr]

            c_rel = safe_percent_change(c_val, c0)
            s_rel = safe_percent_change(s_val, s0)
            r_abs = r_val - r0 if pd.notna(r_val) and pd.notna(r0) else np.nan

            records.append({
                "Province": province,
                "Year": int(float(str(yr))),
                "CACD_kha": c_val,
                "Sown_kha": s_val,
                "Use_intensity_proxy": r_val,
                "CACD_relative_change_pct": c_rel,
                "Sown_relative_change_pct": s_rel,
                "Use_intensity_proxy_change": r_abs,
            })

    diag = pd.DataFrame(records)

    diag["Flag_large_sown_relative_change"] = (
        diag["Sown_relative_change_pct"].abs() > DIAGNOSTIC_RELATIVE_CHANGE_THRESHOLD
    )

    diag["Flag_large_proxy_ratio"] = (
        diag["Use_intensity_proxy"] > DIAGNOSTIC_RATIO_THRESHOLD
    )

    diag["Flag_any"] = (
        diag["Flag_large_sown_relative_change"] |
        diag["Flag_large_proxy_ratio"]
    )

    all_path = out_dir / "temporal_value_diagnostics_all.csv"
    flagged_path = out_dir / "temporal_value_diagnostics_flagged.csv"

    diag.to_csv(all_path, index=False, encoding="utf-8-sig")
    diag[diag["Flag_any"]].to_csv(flagged_path, index=False, encoding="utf-8-sig")

    print("\nTemporal diagnostics saved:")
    print(" -", all_path)
    print(" -", flagged_path)

    flagged = diag[diag["Flag_any"]].copy()
    if len(flagged) > 0:
        print("\nTop flagged temporal values:")
        print(
            flagged.sort_values(
                ["Sown_relative_change_pct"],
                key=lambda x: x.abs(),
                ascending=False
            ).head(15).to_string(index=False)
        )


# =====================================================
# Figure 1: Master overview
# =====================================================

def plot_master_overview(summary, national, out_dir):
    fig = plt.figure(figsize=(20.5, 15.2))

    gs = fig.add_gridspec(
        2, 2,
        height_ratios=[1.0, 1.06],
        width_ratios=[1.0, 1.0],
        left=0.075,
        right=0.985,
        top=0.895,
        bottom=0.075,
        wspace=0.27,
        hspace=0.46
    )

    x = national["Year"].to_numpy()
    cacd = national["CACD_Cropland_Extent_kha"].to_numpy()
    sown = national["Statistical_Sown_Area_kha"].to_numpy()
    ratio = national["Agricultural_Use_Intensity_Proxy"].to_numpy()

    # -------------------------------------------------
    # a: national area comparison
    # -------------------------------------------------

    ax1 = fig.add_subplot(gs[0, 0])
    panel_label(ax1, "a")

    ax1.plot(
        x, cacd,
        color=NAVY,
        marker="o",
        markersize=6.8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.5,
        label="CACD-derived cropland extent"
    )

    ax1.plot(
        x, sown,
        color=TERRACOTTA,
        marker="o",
        markersize=6.8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.5,
        label="Statistical sown area"
    )

    ax1.set_title("National CACD extent and statistical sown area", pad=16)
    ax1.set_xlabel("Year", labelpad=10)
    ax1.set_ylabel("Area (kha)", labelpad=10)
    ax1.grid(axis="y", color=LIGHT_GRAY, linewidth=0.9)
    ax1.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=7))
    ax1.tick_params(axis="x", pad=8)
    ax1.tick_params(axis="y", pad=8)
    despine(ax1)

    ax1.legend(
        loc="upper center",
        bbox_to_anchor=(0.50, 1.26),
        ncol=1,
        frameon=False,
        fontsize=15,
        handlelength=2.3,
        handletextpad=0.8,
        borderaxespad=0.0
    )

    # -------------------------------------------------
    # b: use-intensity proxy
    # -------------------------------------------------

    ax2 = fig.add_subplot(gs[0, 1])
    panel_label(ax2, "b")

    ax2.plot(
        x, ratio,
        color=TEAL,
        marker="o",
        markersize=6.8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.5
    )

    ax2.fill_between(
        x,
        ratio,
        np.nanmin(ratio),
        color=TEAL,
        alpha=0.10,
        linewidth=0
    )

    ax2.set_title("Agricultural-use intensity proxy", pad=16)
    ax2.set_xlabel("Year", labelpad=10)
    ax2.set_ylabel("Sown area / CACD extent", labelpad=10)
    ax2.grid(axis="y", color=LIGHT_GRAY, linewidth=0.9)
    ax2.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=7))
    ax2.tick_params(axis="x", pad=8)
    ax2.tick_params(axis="y", pad=8)
    despine(ax2)

    # -------------------------------------------------
    # c: simplified coupling by CACD status
    # -------------------------------------------------

    ax3 = fig.add_subplot(gs[1, 0])
    panel_label(ax3, "c")

    for status in STATUS_ORDER:
        sub = summary[summary["CACD_Cropland_Status"] == status]

        if len(sub) == 0:
            continue

        turnover = sub["CACD_Cropland_Turnover_kha"].to_numpy(dtype=float)

        if len(turnover) > 1 and np.nanmax(turnover) > np.nanmin(turnover):
            sizes = 75 + 175 * (
                turnover - np.nanmin(turnover)
            ) / (
                np.nanmax(turnover) - np.nanmin(turnover)
            )
        else:
            sizes = np.full(len(sub), 105)

        ax3.scatter(
            sub["CACD_Cropland_Net_pct"],
            sub["Statistical_Sown_Net_pct"],
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

    ax3.set_title("Coupling between spatial extent and planting activity", pad=16)
    ax3.set_xlabel("CACD cropland extent change (%)", labelpad=10)
    ax3.set_ylabel("Statistical sown area change (%)", labelpad=10)
    ax3.grid(color=LIGHT_GRAY, linewidth=0.85)
    ax3.tick_params(axis="x", pad=8)
    ax3.tick_params(axis="y", pad=8)
    despine(ax3)

    ax3.text(
        0.03, 0.96,
        f"Stable band: ±{STABLE_TOL_PERCENT:.0f}%",
        transform=ax3.transAxes,
        ha="left",
        va="top",
        fontsize=14,
        color=DARK_GRAY
    )

    ax3.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.19),
        ncol=3,
        frameon=False,
        fontsize=14,
        handletextpad=0.6,
        columnspacing=1.3,
        borderaxespad=0.0
    )

    # -------------------------------------------------
    # d: national decoupling index
    # -------------------------------------------------

    ax4 = fig.add_subplot(gs[1, 1])
    panel_label(ax4, "d")

    decoupling = national["National_Decoupling_Index_pp"].to_numpy()

    ax4.plot(
        x,
        decoupling,
        color=PLUM,
        marker="o",
        markersize=6.8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.5
    )

    ax4.axhline(0, color=CHARCOAL, linewidth=1.0)

    ax4.fill_between(
        x,
        decoupling,
        0,
        where=decoupling >= 0,
        color=TEAL,
        alpha=0.13,
        interpolate=True
    )

    ax4.fill_between(
        x,
        decoupling,
        0,
        where=decoupling < 0,
        color=TERRACOTTA,
        alpha=0.13,
        interpolate=True
    )

    ax4.set_title("National decoupling between sown area and CACD extent", pad=16)
    ax4.set_xlabel("Year", labelpad=10)
    ax4.set_ylabel("DI = gS - gC (percentage points)", labelpad=10)
    ax4.grid(axis="y", color=LIGHT_GRAY, linewidth=0.9)
    ax4.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=7))
    ax4.tick_params(axis="x", pad=8)
    ax4.tick_params(axis="y", pad=8)
    despine(ax4)

    fig.suptitle(
        "Coupling between CACD-derived cropland extent and statistical sown area in China (2000–2023)",
        fontsize=25,
        fontweight="bold",
        y=0.985
    )

    save_figure(fig, out_dir / "Fig1_master_overview")
    plt.close(fig)


# =====================================================
# Figure 2: Full coupling typology scatter
# =====================================================

def plot_coupling_typology(summary, out_dir):
    fig = plt.figure(figsize=(14.8, 12.8))
    ax = fig.add_subplot(111)

    panel_label(ax, "a", x=-0.09, y=1.04)

    present_classes = [
        cls for cls in COUPLING_ORDER
        if cls in summary["Coupling_Class"].astype(str).unique()
    ]

    for cls in present_classes:
        sub = summary[summary["Coupling_Class"].astype(str) == cls]

        di = sub["Decoupling_Index_pp"].to_numpy(dtype=float)
        size_var = np.abs(di)

        if len(size_var) > 1 and np.nanmax(size_var) > np.nanmin(size_var):
            sizes = 90 + 220 * (
                size_var - np.nanmin(size_var)
            ) / (
                np.nanmax(size_var) - np.nanmin(size_var)
            )
        else:
            sizes = np.full(len(sub), 120)

        ax.scatter(
            sub["CACD_Cropland_Net_pct"],
            sub["Statistical_Sown_Net_pct"],
            s=sizes,
            color=COUPLING_COLORS.get(cls, MID_GRAY),
            edgecolor="white",
            linewidth=0.9,
            alpha=0.90,
            label=f"{cls}: {COUPLING_NAMES.get(cls, '')} (n={len(sub)})"
        )

    ax.axhline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.1, linestyle="--")
    ax.axhline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.1, linestyle="--")
    ax.axvline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.1, linestyle="--")
    ax.axvline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.1, linestyle="--")
    ax.axhline(0, color=CHARCOAL, linewidth=1.1)
    ax.axvline(0, color=CHARCOAL, linewidth=1.1)

    ax.set_title("Coupling typology between CACD cropland extent and statistical sown area", pad=18)
    ax.set_xlabel("CACD-derived cropland extent change (%)", labelpad=12)
    ax.set_ylabel("Statistical sown area change (%)", labelpad=12)

    ax.grid(color=LIGHT_GRAY, linewidth=0.9)
    ax.tick_params(axis="x", pad=8)
    ax.tick_params(axis="y", pad=8)

    ax.text(
        0.03, 0.97,
        f"Stable threshold: ±{STABLE_TOL_PERCENT:.0f}%",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=15,
        color=DARK_GRAY
    )

    despine(ax)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=1,
        frameon=False,
        fontsize=13,
        handletextpad=0.7,
        columnspacing=1.2
    )

    fig.subplots_adjust(left=0.12, right=0.98, top=0.91, bottom=0.32)

    save_figure(fig, out_dir / "Fig2_coupling_typology")
    plt.close(fig)


# =====================================================
# Figure 3: Decomposition
# =====================================================

def plot_decomposition(summary, out_dir):
    data = summary.copy()
    data = data.sort_values("Statistical_Sown_Net_kha", ascending=True).reset_index(drop=True)

    y = np.arange(len(data))

    fig = plt.figure(figsize=(20.0, 17.0))
    ax = fig.add_subplot(111)

    panel_label(ax, "a", x=-0.09, y=1.04)

    effects = [
        ("Extent_Effect_kha", "Extent effect"),
        ("Use_Intensity_Effect_kha", "Use-intensity effect"),
        ("Interaction_Effect_kha", "Interaction effect"),
    ]

    pos_left = np.zeros(len(data))
    neg_left = np.zeros(len(data))

    for col, label in effects:
        vals = data[col].to_numpy(dtype=float)

        pos_vals = np.where(vals > 0, vals, 0)
        neg_vals = np.where(vals < 0, vals, 0)

        ax.barh(
            y,
            pos_vals,
            left=pos_left,
            color=EFFECT_COLORS[label],
            edgecolor="white",
            linewidth=0.6,
            height=0.72,
            label=label
        )

        ax.barh(
            y,
            neg_vals,
            left=neg_left,
            color=EFFECT_COLORS[label],
            edgecolor="white",
            linewidth=0.6,
            height=0.72
        )

        pos_left += pos_vals
        neg_left += neg_vals

    ax.scatter(
        data["Statistical_Sown_Net_kha"],
        y,
        s=45,
        color=CHARCOAL,
        edgecolor="white",
        linewidth=0.5,
        zorder=5,
        label="Observed ΔS"
    )

    ax.axvline(0, color=CHARCOAL, linewidth=1.0)

    ax.set_yticks(y)
    ax.set_yticklabels(data["Province"], fontsize=16)
    italicize_yticklabels(ax)

    ax.set_title("Exact decomposition of statistical sown-area change", pad=18)
    ax.set_xlabel("Contribution to statistical sown-area change (kha)", labelpad=12)
    ax.set_ylabel("Province", labelpad=12)

    ax.grid(axis="x", color=LIGHT_GRAY, linewidth=0.85)
    ax.tick_params(axis="x", pad=8)
    ax.tick_params(axis="y", pad=7)
    despine(ax)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.08),
        ncol=4,
        frameon=False,
        fontsize=15,
        handlelength=2.0,
        columnspacing=1.6,
        handletextpad=0.6
    )

    fig.suptitle(
        "Disentangling the sources of statistical sown-area change",
        fontsize=25,
        fontweight="bold",
        y=0.985
    )

    fig.subplots_adjust(left=0.20, right=0.98, top=0.90, bottom=0.07)

    save_figure(fig, out_dir / "Fig3_sown_area_decomposition")
    plt.close(fig)


# =====================================================
# Figure 4: Robust temporal trajectory envelope
# =====================================================

def make_relative_change_df(df_matrix, year_cols, value_name):
    records = []

    for _, row in df_matrix.iterrows():
        province = row["Province"]
        base = row[year_cols[0]]

        for yr in year_cols:
            val = row[yr]

            if pd.isna(base) or base == 0 or pd.isna(val):
                rel = np.nan
            else:
                rel = (val - base) / base * 100.0

            records.append({
                "Province": province,
                "Year": int(float(str(yr))),
                value_name: rel
            })

    return pd.DataFrame(records)


def make_absolute_change_df(df_matrix, year_cols, value_name):
    records = []

    for _, row in df_matrix.iterrows():
        province = row["Province"]
        base = row[year_cols[0]]

        for yr in year_cols:
            val = row[yr]

            if pd.isna(base) or pd.isna(val):
                diff = np.nan
            else:
                diff = val - base

            records.append({
                "Province": province,
                "Year": int(float(str(yr))),
                value_name: diff
            })

    return pd.DataFrame(records)


def _robust_axis_limits(values, q=(0.02, 0.98), padding=0.12):
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]

    if vals.size == 0:
        return -1.0, 1.0

    lo, hi = np.nanquantile(vals, q)

    if np.isclose(lo, hi):
        lo = np.nanmin(vals)
        hi = np.nanmax(vals)

    if np.isclose(lo, hi):
        pad = abs(lo) * 0.1 + 1.0
        return lo - pad, hi + pad

    span = hi - lo
    return lo - span * padding, hi + span * padding


def _trajectory_quantiles(df_long, value_col):
    q_outer_low, q_outer_high = FIG4_OUTER_BAND
    q_inner_low, q_inner_high = FIG4_CENTRAL_BAND

    qdf = (
        df_long
        .groupby("Year")[value_col]
        .quantile([q_outer_low, q_inner_low, 0.5, q_inner_high, q_outer_high])
        .unstack()
        .reset_index()
    )

    qdf.columns = [
        "Year",
        "q_outer_low",
        "q_inner_low",
        "median",
        "q_inner_high",
        "q_outer_high",
    ]

    return qdf.sort_values("Year")




def plot_temporal_trajectory_bundle(summary, national, cacd_matrix, sown_matrix, proxy_matrix, year_cols, out_dir):
    """
    Fig.4 redesigned as a national dynamic coupling and decomposition figure.

    Rationale:
    - Province-level relative trajectories can be visually dominated by valid
      but extreme local values when the baseline is small or when a province
      has abrupt annual change.
    - For the main-text Fig.4, the more stable and mechanistically interpretable
      solution is to use national aggregate dynamics:
        a) phase-space trajectory between CACD extent change and sown-area change;
        b) annual decomposition of national sown-area change;
        c) cumulative decomposition of national sown-area change.

    No source data are modified.
    """

    nat = national.copy().sort_values("Year").reset_index(drop=True)

    years = nat["Year"].to_numpy(dtype=int)
    C = nat["CACD_Cropland_Extent_kha"].to_numpy(dtype=float)
    S = nat["Statistical_Sown_Area_kha"].to_numpy(dtype=float)
    R = nat["Agricultural_Use_Intensity_Proxy"].to_numpy(dtype=float)

    gC = (C - C[0]) / C[0] * 100.0
    gS = (S - S[0]) / S[0] * 100.0
    DI = gS - gC

    # -------------------------------------------------
    # Annual exact decomposition:
    # ΔS_t = R_{t-1}ΔC_t + C_{t-1}ΔR_t + ΔC_tΔR_t
    # -------------------------------------------------
    annual_records = []
    for i in range(1, len(years)):
        dC = C[i] - C[i - 1]
        dR = R[i] - R[i - 1]
        dS = S[i] - S[i - 1]

        extent_effect = R[i - 1] * dC
        use_effect = C[i - 1] * dR
        interaction_effect = dC * dR

        annual_records.append({
            "Year": years[i],
            "Observed_delta_S_kha": dS,
            "Extent_effect_kha": extent_effect,
            "Use_intensity_effect_kha": use_effect,
            "Interaction_effect_kha": interaction_effect,
            "Reconstructed_delta_S_kha": extent_effect + use_effect + interaction_effect,
        })

    annual_df = pd.DataFrame(annual_records)

    # -------------------------------------------------
    # Cumulative exact decomposition from 2000:
    # ΔS_{0,t} = R_0ΔC_{0,t} + C_0ΔR_{0,t} + ΔC_{0,t}ΔR_{0,t}
    # -------------------------------------------------
    cumulative_records = []
    for i in range(len(years)):
        dC = C[i] - C[0]
        dR = R[i] - R[0]
        dS = S[i] - S[0]

        extent_effect = R[0] * dC
        use_effect = C[0] * dR
        interaction_effect = dC * dR

        cumulative_records.append({
            "Year": years[i],
            "Observed_delta_S_kha": dS,
            "Extent_effect_kha": extent_effect,
            "Use_intensity_effect_kha": use_effect,
            "Interaction_effect_kha": interaction_effect,
            "Reconstructed_delta_S_kha": extent_effect + use_effect + interaction_effect,
            "DI_pp": DI[i],
            "gC_pct": gC[i],
            "gS_pct": gS[i],
        })

    cumulative_df = pd.DataFrame(cumulative_records)

    annual_df.to_csv(
        out_dir / "national_annual_sown_area_decomposition.csv",
        index=False,
        encoding="utf-8-sig"
    )
    cumulative_df.to_csv(
        out_dir / "national_cumulative_sown_area_decomposition.csv",
        index=False,
        encoding="utf-8-sig"
    )

    fig = plt.figure(figsize=(22.2, 15.4))
    gs = fig.add_gridspec(
        2,
        2,
        height_ratios=[1.0, 1.05],
        width_ratios=[1.0, 1.0],
        left=0.075,
        right=0.985,
        top=0.90,
        bottom=0.105,
        wspace=0.28,
        hspace=0.40
    )

    # =================================================
    # a) Phase-space trajectory
    # =================================================
    ax1 = fig.add_subplot(gs[0, 0])
    panel_label(ax1, "a")

    ax1.axhline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")
    ax1.axhline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")
    ax1.axvline(+STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")
    ax1.axvline(-STABLE_TOL_PERCENT, color=MID_GRAY, linewidth=1.0, linestyle="--")
    ax1.axhline(0, color=CHARCOAL, linewidth=1.0)
    ax1.axvline(0, color=CHARCOAL, linewidth=1.0)

    # Gradient-like trajectory using sequential segments.
    cmap = plt.get_cmap("viridis")
    norm_year = mpl.colors.Normalize(vmin=years.min(), vmax=years.max())

    for i in range(len(years) - 1):
        color = cmap(norm_year(years[i]))
        ax1.plot(
            gC[i:i + 2],
            gS[i:i + 2],
            color=color,
            linewidth=2.4,
            zorder=2
        )

        # arrow head for direction
        ax1.annotate(
            "",
            xy=(gC[i + 1], gS[i + 1]),
            xytext=(gC[i], gS[i]),
            arrowprops=dict(
                arrowstyle="-|>",
                color=color,
                lw=1.5,
                shrinkA=0,
                shrinkB=0,
                mutation_scale=9
            ),
            zorder=3
        )

    sc = ax1.scatter(
        gC,
        gS,
        c=years,
        cmap="viridis",
        s=58,
        edgecolor="white",
        linewidth=0.8,
        zorder=4
    )

    ax1.scatter(
        gC[0],
        gS[0],
        s=90,
        color=CHARCOAL,
        edgecolor="white",
        linewidth=0.8,
        zorder=5,
        label="2000"
    )
    ax1.scatter(
        gC[-1],
        gS[-1],
        s=110,
        color=TERRACOTTA,
        edgecolor="white",
        linewidth=0.8,
        zorder=5,
        label="2023"
    )

    ax1.text(
        0.03,
        0.96,
        f"Stable band: ±{STABLE_TOL_PERCENT:.0f}%",
        transform=ax1.transAxes,
        ha="left",
        va="top",
        fontsize=14,
        color=DARK_GRAY
    )

    ax1.set_title("National phase-space trajectory", pad=16)
    ax1.set_xlabel("CACD cropland extent change from 2000 (%)", labelpad=10)
    ax1.set_ylabel("Statistical sown area change from 2000 (%)", labelpad=10)
    ax1.grid(color=LIGHT_GRAY, linewidth=0.85)
    ax1.tick_params(axis="x", pad=8)
    ax1.tick_params(axis="y", pad=8)
    despine(ax1)

    cbar = fig.colorbar(sc, ax=ax1, fraction=0.038, pad=0.025)
    cbar.set_label("Year", fontsize=15, labelpad=10)
    cbar.ax.tick_params(labelsize=13)

    # =================================================
    # b) Annual decomposition
    # =================================================
    ax2 = fig.add_subplot(gs[0, 1])
    panel_label(ax2, "b")

    x_year = annual_df["Year"].to_numpy(dtype=int)
    x_pos = np.arange(len(x_year))

    effects = [
        ("Extent_effect_kha", "Extent effect", NAVY),
        ("Use_intensity_effect_kha", "Use-intensity effect", TEAL),
        ("Interaction_effect_kha", "Interaction effect", SAND),
    ]

    pos_bottom = np.zeros(len(annual_df))
    neg_bottom = np.zeros(len(annual_df))

    for col, label, color in effects:
        vals = annual_df[col].to_numpy(dtype=float)
        pos_vals = np.where(vals > 0, vals, 0.0)
        neg_vals = np.where(vals < 0, vals, 0.0)

        ax2.bar(
            x_pos,
            pos_vals,
            bottom=pos_bottom,
            color=color,
            width=0.72,
            edgecolor="white",
            linewidth=0.5,
            label=label
        )

        ax2.bar(
            x_pos,
            neg_vals,
            bottom=neg_bottom,
            color=color,
            width=0.72,
            edgecolor="white",
            linewidth=0.5
        )

        pos_bottom += pos_vals
        neg_bottom += neg_vals

    ax2.plot(
        x_pos,
        annual_df["Observed_delta_S_kha"],
        color=CHARCOAL,
        marker="o",
        markersize=4.8,
        markerfacecolor="white",
        linewidth=1.8,
        label="Observed annual ΔS",
        zorder=4
    )

    ax2.axhline(0, color=CHARCOAL, linewidth=1.0)
    tick_idx = np.arange(0, len(x_year), 2)
    if len(x_year) - 1 not in tick_idx:
        tick_idx = np.append(tick_idx, len(x_year) - 1)

    ax2.set_xticks(tick_idx)
    ax2.set_xticklabels([str(x_year[i]) for i in tick_idx], rotation=45, ha="right")
    ax2.set_title("Annual decomposition of national sown-area change", pad=16)
    ax2.set_xlabel("Year", labelpad=10)
    ax2.set_ylabel("Annual contribution to ΔS (kha)", labelpad=10)
    ax2.grid(axis="y", color=LIGHT_GRAY, linewidth=0.85)
    ax2.tick_params(axis="x", pad=8)
    ax2.tick_params(axis="y", pad=8)
    despine(ax2)

    # =================================================
    # c) Cumulative decomposition
    # =================================================
    ax3 = fig.add_subplot(gs[1, :])
    panel_label(ax3, "c", x=-0.035, y=1.04)

    years_cum = cumulative_df["Year"].to_numpy(dtype=int)

    extent = cumulative_df["Extent_effect_kha"].to_numpy(dtype=float)
    use = cumulative_df["Use_intensity_effect_kha"].to_numpy(dtype=float)
    interaction = cumulative_df["Interaction_effect_kha"].to_numpy(dtype=float)
    observed = cumulative_df["Observed_delta_S_kha"].to_numpy(dtype=float)

    # Separate positive and negative stacked areas for exact sign-aware display.
    components = [
        (extent, "Extent effect", NAVY),
        (use, "Use-intensity effect", TEAL),
        (interaction, "Interaction effect", SAND),
    ]

    pos_base = np.zeros_like(years_cum, dtype=float)
    neg_base = np.zeros_like(years_cum, dtype=float)

    for vals, label, color in components:
        pos_vals = np.where(vals > 0, vals, 0.0)
        neg_vals = np.where(vals < 0, vals, 0.0)

        ax3.fill_between(
            years_cum,
            pos_base,
            pos_base + pos_vals,
            color=color,
            alpha=0.78,
            linewidth=0,
            label=label
        )

        ax3.fill_between(
            years_cum,
            neg_base,
            neg_base + neg_vals,
            color=color,
            alpha=0.78,
            linewidth=0
        )

        pos_base += pos_vals
        neg_base += neg_vals

    ax3.plot(
        years_cum,
        observed,
        color=CHARCOAL,
        marker="o",
        markersize=5.4,
        markerfacecolor="white",
        markeredgewidth=1.1,
        linewidth=2.4,
        label="Observed cumulative ΔS",
        zorder=4
    )

    ax3.axhline(0, color=CHARCOAL, linewidth=1.0)
    ax3.set_title("Cumulative decomposition since 2000", pad=16)
    ax3.set_xlabel("Year", labelpad=10)
    ax3.set_ylabel("Cumulative contribution to ΔS (kha)", labelpad=10)
    ax3.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
    ax3.grid(axis="y", color=LIGHT_GRAY, linewidth=0.85)
    ax3.tick_params(axis="x", pad=8)
    ax3.tick_params(axis="y", pad=8)
    despine(ax3)

    # -------------------------------------------------
    # Shared legend
    # -------------------------------------------------
    legend_handles = [
        Patch(facecolor=NAVY, edgecolor="none", label="Extent effect"),
        Patch(facecolor=TEAL, edgecolor="none", label="Use-intensity effect"),
        Patch(facecolor=SAND, edgecolor="none", label="Interaction effect"),
        Line2D(
            [],
            [],
            color=CHARCOAL,
            marker="o",
            markersize=5.5,
            markerfacecolor="white",
            linewidth=2.2,
            label="Observed ΔS"
        ),
    ]

    fig.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.025),
        ncol=4,
        frameon=False,
        fontsize=14,
        handlelength=2.0,
        columnspacing=1.8,
        handletextpad=0.7
    )

    fig.suptitle(
        "National dynamic coupling and decomposition of statistical sown-area change",
        fontsize=25,
        fontweight="bold",
        y=0.985
    )

    save_figure(
        fig,
        out_dir / "Fig4_national_dynamic_coupling_decomposition"
    )

    plt.close(fig)


# =====================================================
# Main
# =====================================================

def main():
    set_publication_style()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading data...")

    cacd_df, year_cols_cacd = prepare_wide_table(
        CROPLAND_FILE,
        CROPLAND_SHEET,
        "CACD-derived cropland extent"
    )

    sown_df, year_cols_sown = prepare_wide_table(
        SOWN_FILE,
        SOWN_SHEET,
        "Statistical sown area"
    )

    if year_cols_cacd != year_cols_sown:
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
        cacd_matrix,
        sown_matrix,
        proxy_matrix,
        years
    ) = build_joint_summary(
        cacd_df,
        sown_df,
        year_cols_cacd
    )

    print("Saving tables...")

    summary.to_csv(
        OUTPUT_DIR / "province_summary_coupling_decomposition.csv",
        index=False,
        encoding="utf-8-sig"
    )

    national.to_csv(
        OUTPUT_DIR / "national_timeseries_coupling.csv",
        index=False,
        encoding="utf-8-sig"
    )

    group_summary.to_csv(
        OUTPUT_DIR / "coupling_group_summary.csv",
        index=False,
        encoding="utf-8-sig"
    )

    coupling_summary.to_csv(
        OUTPUT_DIR / "coupling_type_counts.csv",
        index=False,
        encoding="utf-8-sig"
    )

    export_temporal_diagnostics(
        cacd_matrix,
        sown_matrix,
        proxy_matrix,
        year_cols_cacd,
        OUTPUT_DIR
    )

    try:
        with pd.ExcelWriter(
            OUTPUT_DIR / "cacd_sown_coupling_analysis_results.xlsx",
            engine="openpyxl"
        ) as writer:
            summary.to_excel(writer, index=False, sheet_name="Province_Summary")
            national.to_excel(writer, index=False, sheet_name="National_Timeseries")
            group_summary.to_excel(writer, index=False, sheet_name="Coupling_Group_Summary")
            coupling_summary.to_excel(writer, index=False, sheet_name="Coupling_Type_Counts")
    except Exception as e:
        print(f"Excel export skipped: {e}")

    interpretation_note = (
        "Conceptual note:\n"
        "C_it denotes CACD-derived cropland extent, while S_it denotes statistical "
        "sown area of farm crops. The ratio R_it = S_it / C_it is treated as an "
        "agricultural-use intensity proxy, not as a strict multiple cropping index.\n\n"
        "Decoupling index:\n"
        "DI_i = gS_i - gC_i, where gS_i is the relative change in statistical "
        "sown area and gC_i is the relative change in CACD-derived cropland extent.\n\n"
        "Exact decomposition:\n"
        "ΔS_i = R_i0·ΔC_i + C_i0·ΔR_i + ΔC_i·ΔR_i.\n\n"
        "Fig.4 note:\n"
        "Fig.4 uses robust median and quantile envelopes. Province-level trajectories "
        "are optionally clipped for display only; source data and calculations remain "
        "unchanged. Temporal diagnostics are exported as CSV files.\n"
    )

    with open(
        OUTPUT_DIR / "interpretation_note.txt",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(interpretation_note)

    print("Generating figures...")

    plot_master_overview(summary, national, OUTPUT_DIR)

    plot_coupling_typology(summary, OUTPUT_DIR)

    plot_decomposition(summary, OUTPUT_DIR)

    plot_temporal_trajectory_bundle(
        summary,
        national,
        cacd_matrix,
        sown_matrix,
        proxy_matrix,
        year_cols_cacd,
        OUTPUT_DIR
    )

    print("\n=== Analysis complete ===")
    print(f"Output directory: {OUTPUT_DIR.resolve()}")

    print("\nCoupling type counts:")
    print(coupling_summary.to_string(index=False))

    print("\nKey interpretation:")
    print(
        "The ratio Statistical sown area / CACD-derived cropland extent "
        "is treated as an agricultural-use intensity proxy, not as a strict "
        "multiple cropping index."
    )

    print("\nDecomposition identity:")
    print("ΔS = R0·ΔC + C0·ΔR + ΔC·ΔR")

    print("\nSaved files:")
    for p in sorted(OUTPUT_DIR.glob("*")):
        print(" -", p.name)


if __name__ == "__main__":
    main()
