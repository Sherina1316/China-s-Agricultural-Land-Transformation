import pandas as pd

# 1. 读取 CSV 文件
df = pd.read_csv('rhi.csv')

if 'rhi' not in df.columns:
    raise KeyError("The CSV file does not contain the ‘rhi’ column. Please check the file or column name.")

# 2. Min–Max 归一化
min_val = df['rhi'].min()
max_val = df['rhi'].max()
df['rhi'] = (df['rhi'] - min_val) / (max_val - min_val)

print(f"min={min_val}, max={max_val}")
print(f"Standardized scope: [ {df['rhi'].min():.4f}, {df['rhi'].max():.4f} ]")

# 3. 保存新的 CSV 文件
df.to_csv('GTWR_rhi.csv', index=False)
print(" Normalized results generated: output_normalized.csv")
