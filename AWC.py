import rasterio
import numpy as np

aet_path = 'aet_2023.tif'
awc_out = 'AWC_2023.tif'
tg_out = 'AWC2023_Tg.txt'

#  AET tiff
with rasterio.open(aet_path) as src:
    AET = src.read(1).astype('float32')
    meta = src.meta.copy()
    px_w, px_h = src.res

# 1. calculate AWC (m³)：AET(mm) × s_area(m²) × 0.001
px_area = abs(px_w * px_h)
factor = px_area * 0.001
AWC = AET * factor

# write AWC.tif
meta.update(dtype=rasterio.float32, nodata=src.nodata)
with rasterio.open(awc_out, 'w', **meta) as dst:
    dst.write(AWC, 1)

# 2. (Tg)：sum(AWC)*1000 kg/m³ /1e12
total_m3 = np.nansum(AWC)  #m³
total_kg = total_m3 * 1000  # kg
total_tg = total_kg / 1e12  # Tg

# write Tg
with open(tg_out, 'w') as f:
    f.write(f"Total water mass: {total_tg:.6f} Tg\n")
print(f"{awc_out}")
print(f" {total_tg:.6f} Tg")
