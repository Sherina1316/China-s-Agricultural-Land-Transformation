import os
import geopandas as gpd


src_shp = r'E:\2025\nature communication\返修\Data\GTWR\sdr\province_point_in.shp'
val_shp = r'E:\2024\crop_test\GWTR_province\RHI\rhi.shp'
output_excel = r'E:\2025\nature communication\返修\Data\GTWR\rhi\province_point_rhi_2000.xlsx'

for fp in (src_shp, val_shp):
    if not os.path.exists(fp):
        raise FileNotFoundError(f"文件未找到：{fp}")
gdf_src = gpd.read_file(src_shp)
gdf_val = gpd.read_file(val_shp)

if 'ORIG_FID' not in gdf_src.columns:
    gdf_src['ORIG_FID'] = gdf_src.index

gdf_merged = gdf_src.merge(
    gdf_val[['ORIG_FID', 'soil2000']],
    on='ORIG_FID',
    how='left'
)

gdf_merged = gdf_merged.sort_values('ORIG_FID').reset_index(drop=True)

df_out = gdf_merged.drop(columns='geometry')
df_out.to_excel(output_excel, index=False)

print(output_excel)
