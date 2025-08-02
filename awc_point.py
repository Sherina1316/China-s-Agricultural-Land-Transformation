import os
import geopandas as gpd
import rasterio

# 输入与输出路径
point_shp = r'province_point_in.shp'
raster_tif = r'2000_soil.tif'
output_excel = r'E:\2025\nature communication\返修\Data\GTWR\sdr\province_point_soil_2000.xlsx'

# 检查文件是否存在
for fp in (point_shp, raster_tif):
    if not os.path.exists(fp):
        raise FileNotFoundError(f"文件未找到：{fp}")

# 1. 读取点数据
pts = gpd.read_file(point_shp)
print(f"读取到 {len(pts)} 个点")

# 2. 提取 raster 值，并添加为 "es" 列
with rasterio.open(raster_tif) as src:
    if pts.crs != src.crs:
        pts = pts.to_crs(src.crs)
    coords = [(pt.x, pt.y) for pt in pts.geometry]
    pts['np'] = [val[0] for val in src.sample(coords)]

# 3. 按 ORIG_FID 排序
if 'ORIG_FID' not in pts.columns:
    print("⚠ 警告：未发现 'ORIG_FID' 字段，输出将按照当前顺序保存")
else:
    pts = pts.sort_values('ORIG_FID').reset_index(drop=True)
    print("已按照 ORIG_FID 从小到大排序")

# 4. 导出属性表到 Excel（不包含几何）
df_out = pts.drop(columns='geometry')
df_out.to_excel(output_excel, index=False)

print(f"属性表已导出为 Excel 文件（省略几何）：\n  {output_excel}")
