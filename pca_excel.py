import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from factor_analyzer import FactorAnalyzer, calculate_bartlett_sphericity

df = pd.read_excel('pca.xlsx', index_col=0)


X = StandardScaler().fit_transform(df)

# Bartlett
chi2, p = calculate_bartlett_sphericity(X)
print(f"Bartlett 检验: χ²={chi2:.2f}, p={p:.4f}")
assert p < 0.05, "变量相关性不足，不适合 PCA"

# Kaiser
fa0 = FactorAnalyzer(rotation=None, method='principal')
fa0.fit(X)
ev, _ = fa0.get_eigenvalues()
n_factors = sum(ev > 1)
print(f"保留主成分数（Eigen>1）：{n_factors}")

# Varimax
fa = FactorAnalyzer(n_factors=n_factors, rotation='varimax', method='principal')
fa.fit(X)

scores = fa.transform(X)  # shape

# DataFrame
pc_cols = [f'PC{i+1}' for i in range(n_factors)]
df_scores = pd.DataFrame(scores, index=df.index, columns=pc_cols)

output_path = 'pca_scores.xlsx'
df_scores.to_excel(output_path)
print(f"-- Saved principal component scores to '{output_path}'")

df_combined = pd.concat([df, df_scores], axis=1)
df_combined.to_excel('pca_with_scores.xlsx')
print(f"-- The table containing the original variables and principal component scores has been saved to 'pca_with_scores.xlsx'")
