import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from libpysal.weights import Queen
from esda.moran import Moran, Moran_Local
from esda.geary import Geary
from splot.esda import moran_scatterplot, lisa_cluster  # 注意用底层函数绘制

df = pd.read_excel('NDR.xlsx')
gdf = gpd.GeoDataFrame(df,
    geometry=gpd.points_from_xy(df.lon, df.lat),
    crs="EPSG:4326"
)

w = Queen.from_dataframe(gdf)
w.transform = 'R'

cols = ['a', 'b', 'c', 'd', 'e', 'f']
print("Variable columns for performing spatial autocorrelation analysis:", cols)

scaler = StandardScaler()
gdf[[f'z_{col}' for col in cols]] = scaler.fit_transform(gdf[cols])

fig_moran, axs_moran = plt.subplots(2, 3, figsize=(18, 10), dpi=300)
fig_lisa, axs_lisa = plt.subplots(2, 3, figsize=(18, 10), dpi=300)

axs_moran = axs_moran.flatten()
axs_lisa = axs_lisa.flatten()

results = []

# Iterate through each variable, plot and record metrics
for i, col in enumerate(cols):
    z_col = f'z_{col}'
    arr = gdf[z_col].values

    mor = Moran(arr, w)
    gce = Geary(arr, w)
    mor_local = Moran_Local(arr, w)

    results.append({
        'Variable': col,
        'Moran_I': mor.I,
        'Z_score': mor.z_sim,
        'P_value': mor.p_sim,
        'Geary_C': gce.C,
        'Geary_p': gce.p_sim
    })

    ax = axs_moran[i]
    moran_scatterplot(mor, ax=ax, aspect_equal=True)
    ax.set_title(
        f"{col} | Moran's I = {mor.I:.3f}\nZ = {mor.z_sim:.2f}, p = {mor.p_sim:.3f}",
        fontsize=10
    )
    ax.set_xlabel("Standardized Variable", fontsize=9)
    ax.set_ylabel("Spatial Lag", fontsize=9)

    ax2 = axs_lisa[i]
    lisa_cluster(mor_local, gdf, p=0.05, ax=ax2)
    ax2.set_title(f"LISA Clusters ({col})", fontsize=10)

fig_moran.tight_layout()
fig_lisa.tight_layout()

fig_moran.savefig("Moran_All_Correct.png", bbox_inches='tight')
fig_lisa.savefig("LISA_All_Correct.png", bbox_inches='tight')

pd.DataFrame(results).to_excel('spatial_autocorr_summary_correct.xlsx', index=False)
print("Finish!")
