import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from libpysal.weights import Queen, lag_spatial
from esda.moran import Moran
import matplotlib as mpl
import matplotlib.font_manager as fm

# 设置全局字体 - 使用Times New Roman
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'font.size': 16,
    'axes.titlesize': 20,
    'axes.labelsize': 18,
    'xtick.labelsize': 16,
    'ytick.labelsize': 16,
    'legend.fontsize': 14,
    'figure.dpi': 300,
    'figure.figsize': (12, 10),
    'lines.linewidth': 2.5,
    'axes.linewidth': 2,
    'grid.linewidth': 1.2,
})

# 1. 读取数据
df = pd.read_excel('SDR.xlsx')
print("Excel文件列名:", df.columns.tolist())

# 修改点1: 找出所有数值类型的列名
# 找出所有数值类型的列名（年份列）
numeric_cols = [col for col in df.columns if isinstance(col, (int, float)) and col >= 2000 and col <= 2023]

# 如果找不到数值列名，尝试找出包含年份的字符串列名
if not numeric_cols:
    # 尝试找出包含年份的字符串列名
    year_cols = []
    for col in df.columns:
        if isinstance(col, str) and any(str(year) in col for year in range(2000, 2024)):
            year_cols.append(col)

    if year_cols:
        print(f"找到以下年份列名: {year_cols}")
        cols = year_cols
    else:
        # 如果还是找不到，使用所有数值列
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        print(f"未找到年份列名，将使用所有数值列: {numeric_cols}")
        cols = numeric_cols
else:
    print(f"找到以下数值年份列名: {numeric_cols}")
    cols = numeric_cols

# 确保至少有一些列可用
if not cols:
    raise ValueError("在Excel文件中没有找到任何可用的列名。请检查数据。")

print(f"将使用以下列进行分析: {cols}")

gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326")

# 2. 构建权重矩阵 - 显式设置use_index避免警告
w = Queen.from_dataframe(gdf, use_index=True)  # 显式设置use_index
w.transform = 'R'

# 3. 标准化
scaler = StandardScaler()
gdf[[f'z_{col}' for col in cols]] = scaler.fit_transform(gdf[cols])

# 4. Nature 风格配色
palette = sns.color_palette("Set2", len(cols))

# 5. 汇总数据用于合并绘图
plot_data = []

for i, col in enumerate(cols):
    z_col = f'z_{col}'
    val = gdf[z_col].values
    lag = lag_spatial(w, val)

    mor = Moran(val, w)
    plot_data.append(pd.DataFrame({
        "Value": val,
        "Lagged": lag,
        "Variable": str(col),  # 确保变量名是字符串
        "Moran_I": mor.I,
        "Z_score": mor.z_sim,
        "P_value": mor.p_sim
    }))

df_all = pd.concat(plot_data, ignore_index=True)

# 6. 绘图：所有变量叠加一个图
plt.figure(figsize=(12, 10), dpi=300)

# 创建自定义图例标签
legend_labels = []
for i, col in enumerate(cols):
    subset = df_all[df_all["Variable"] == str(col)]  # 确保比较字符串
    I = subset.Moran_I.values[0]
    Z = subset.Z_score.values[0]
    P = subset.P_value.values[0]

    # 格式化指标值
    I_str = f"{I:.3f}"
    Z_str = f"{Z:.3f}"
    P_str = f"{P:.3f}"

    # 创建图例标签
    label = f"{col}: I={I_str}, Z={Z_str}, P={P_str}"
    legend_labels.append(label)

# 绘制所有变量
for i, col in enumerate(cols):
    subset = df_all[df_all["Variable"] == str(col)]  # 确保比较字符串
    sns.regplot(
        x="Value", y="Lagged", data=subset,
        scatter_kws={"s": 60, "alpha": 0.7},  # 进一步增大点大小
        line_kws={"linewidth": 2.5},  # 加粗回归线
        color=palette[i]
    )

# 7. 图例与格式美化
plt.xlabel("Standardized Variable", fontsize=18, fontname='Times New Roman', fontweight='bold')
plt.ylabel("Spatial Lag", fontsize=18, fontname='Times New Roman', fontweight='bold')
plt.title("Moran Scatterplots with Spatial Autocorrelation Statistics",
          fontsize=20, pad=20, fontname='Times New Roman', fontweight='bold')

# 设置刻度标签字体
plt.xticks(fontname='Times New Roman', fontsize=16)
plt.yticks(fontname='Times New Roman', fontsize=16)

# 添加图例 - 使用自定义标签
legend = plt.legend(
    handles=[plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=palette[i], markersize=15)
             for i in range(len(cols))],
    labels=legend_labels,
    title="Variables and Statistics",
    title_fontproperties={'family': 'Times New Roman', 'size': 16, 'weight': 'bold'},
    prop={'family': 'Times New Roman', 'size': 14, 'weight': 'normal'},
    loc='best',
    frameon=True,
    framealpha=0.8
)

# 添加网格线
plt.grid(True, linestyle="--", alpha=0.5)

# 调整布局
plt.tight_layout(pad=3.0)

# 8. 保存图像
plt.savefig("Moran_SDR.png", bbox_inches='tight', dpi=300)

plt.show()