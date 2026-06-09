# -*- coding: utf-8 -*-
"""
按省统计 2000–2021 年耕地面积（Kha）
高速版本：按省界直接 mask，并显示进度条

输入：
1) tif 影像（0/1）
2) china_province.shp

输出：
Excel：
行 = 年份
列 = 各省耕地面积（Kha）
"""

import os
import re
import glob
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from tqdm.auto import tqdm


# =====================================================
# 1. 路径配置
# =====================================================
TIF_ROOT = r"E:\2025\nature communication\返修3\过程\crop"
SHP_PATH = r"E:\2024\crop_test\china_provience.shp"
OUTPUT_XLSX = r"E:\2025\nature communication\返修3\过程\crop\cropland_area_by_province_2000_2021_fast_progress.xlsx"

START_YEAR = 2000
END_YEAR = 2021

# 30m × 30m = 900m² = 0.00009 Kha
PIXEL_AREA_KHA = 900 / 10_000_000

PROVINCE_FIELD_CANDIDATES = [
     "name"
]


# =====================================================
# 2. 工具函数
# =====================================================
def check_path_exists(path, path_type="file"):
    if path_type == "file" and not os.path.isfile(path):
        raise FileNotFoundError(f"文件不存在：{path}")
    if path_type == "dir" and not os.path.isdir(path):
        raise FileNotFoundError(f"文件夹不存在：{path}")


def find_year_from_path(path):
    basename = os.path.basename(path)
    matches = re.findall(r"(20\d{2})", basename)
    for m in matches:
        y = int(m)
        if START_YEAR <= y <= END_YEAR:
            return y
    return None


def locate_tif_by_year(root_dir):
    tif_paths = glob.glob(os.path.join(root_dir, "**", "*.tif"), recursive=True)
    tif_paths += glob.glob(os.path.join(root_dir, "**", "*.tiff"), recursive=True)

    year_to_path = {}
    for p in sorted(tif_paths):
        y = find_year_from_path(p)
        if y is None:
            continue
        if y in year_to_path:
            warnings.warn(
                f"年份 {y} 出现多个 tif，保留第一个：\n"
                f"{year_to_path[y]}\n忽略：{p}"
            )
            continue
        year_to_path[y] = p

    return year_to_path


def detect_name_field(gdf):
    cols = list(gdf.columns)
    for c in PROVINCE_FIELD_CANDIDATES:
        if c in cols:
            return c
    non_geom_cols = [c for c in cols if c != "geometry"]
    if not non_geom_cols:
        raise ValueError("shp 中未找到区域名称字段")
    return non_geom_cols[0]


# =====================================================
# 3. 核心统计函数
# =====================================================
def calculate_province_area_fast(raster_path, provinces, province_field):
    """
    每个省单独 mask，只读取该省对应窗口。
    带逐省进度条。
    """
    result = {}

    with rasterio.open(raster_path) as src:
        prov = provinces.to_crs(src.crs).reset_index(drop=True)

        for _, row in tqdm(
            prov.iterrows(),
            total=len(prov),
            desc="    省份统计",
            leave=False
        ):
            province_name = str(row[province_field])
            geom = [row.geometry]

            try:
                out_image, _ = mask(
                    src,
                    geom,
                    crop=True,
                    nodata=0,
                    filled=True
                )

                arr = out_image[0]
                cropland_pixels = np.count_nonzero(arr == 1)
                area_kha = cropland_pixels * PIXEL_AREA_KHA
                result[province_name] = area_kha

            except Exception as e:
                print(f"\n    {province_name} 统计失败：{e}")
                result[province_name] = np.nan

    return result


# =====================================================
# 4. 主程序
# =====================================================
def main():
    check_path_exists(TIF_ROOT, "dir")
    check_path_exists(SHP_PATH, "file")

    provinces = gpd.read_file(SHP_PATH)
    province_field = detect_name_field(provinces)

    print(f"识别到的区域名称字段：{province_field}")

    if len(provinces) != 31:
        warnings.warn(f"当前 shp 要素数量 = {len(provinces)}，不是 31。")

    province_names = provinces[province_field].astype(str).tolist()
    year_to_tif = locate_tif_by_year(TIF_ROOT)

    years = list(range(START_YEAR, END_YEAR + 1))
    records = []

    # 逐年进度条
    for year in tqdm(years, desc="年度统计", unit="year"):
        row = {"Year": year}

        if year not in year_to_tif:
            warnings.warn(f"{year} 年 tif 缺失")
            for name in province_names:
                row[name] = np.nan
            row["China_Total_Kha"] = np.nan
            records.append(row)
            continue

        tif_path = year_to_tif[year]
        tqdm.write(f"\n开始统计 {year} 年：{os.path.basename(tif_path)}")

        area_dict = calculate_province_area_fast(
            tif_path,
            provinces,
            province_field
        )

        total = 0.0
        for name in province_names:
            v = area_dict.get(name, np.nan)
            row[name] = v
            if pd.notna(v):
                total += float(v)

        row["China_Total_Kha"] = total
        records.append(row)

    # 输出结果
    df = pd.DataFrame(records)
    df = df[["Year"] + province_names + ["China_Total_Kha"]]

    os.makedirs(os.path.dirname(OUTPUT_XLSX), exist_ok=True)

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Cropland_Area_Kha", index=False)

        meta = pd.DataFrame({
            "Item": [
                "Pixel Size",
                "Area Unit",
                "Raster Meaning",
                "Method",
                "Progress"
            ],
            "Value": [
                "30m × 30m",
                "Kha",
                "1 = cropland",
                "Province mask crop",
                "tqdm progress bars enabled"
            ]
        })
        meta.to_excel(writer, sheet_name="Metadata", index=False)

    print(f"\n完成！结果已输出到：\n{OUTPUT_XLSX}")


if __name__ == "__main__":
    main()