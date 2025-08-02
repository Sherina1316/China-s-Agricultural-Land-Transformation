import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from factor_analyzer import FactorAnalyzer, calculate_bartlett_sphericity

df = pd.read_excel('pca.xlsx', index_col=0)
X = StandardScaler().fit_transform(df)

# Bartlett
chi2, p = calculate_bartlett_sphericity(X)
print(f"Bartlett χ² = {chi2:.2f}, p = {p:.4f}")
assert p < 0.05, "did not PCA"


fa0 = FactorAnalyzer(rotation=None, method='principal')
fa0.fit(X)
eigenvalues, _ = fa0.get_eigenvalues()
pcs = np.arange(1, len(eigenvalues)+1)

plt.figure(figsize=(6, 4))
plt.plot(pcs, eigenvalues, marker='o')
for x, y in zip(pcs, eigenvalues):
    plt.text(x, y+0.05, f"{y:.2f}", ha='center', fontsize=8)
plt.axhline(1, color='red', linestyle='--')
plt.title('Crushed stone diagram (with characteristic root annotations)')
plt.xlabel('Principal component number')
plt.ylabel('eigenvalue')
plt.grid(True)
plt.tight_layout()
plt.show()

n_factors = max(sum(eigenvalues > 1), 1)
print(f"Retain principal component numbers：{n_factors}")

# Varimax PCA
fa = FactorAnalyzer(n_factors=n_factors, rotation='varimax', method='principal')
fa.fit(X)
loadings = pd.DataFrame(fa.loadings_, index=df.columns, columns=[f'PC{i+1}' for i in range(n_factors)])

# Each variable belongs to only one principal component (maximum absolute load assignment method).
assignments = []
for var in loadings.index:
    pc = loadings.loc[var].abs().idxmax()
    val = loadings.loc[var, pc]
    sign = 'Positive' if val > 0 else 'Negative'
    assignments.append({'Variable': var, 'Assigned_PC': pc, 'Loading': val, 'Sign': sign})
assign_df = pd.DataFrame(assignments)

# Output variable attribution and positive/negative relationship
print("\nVariable allocation to principal component results：")
for pc in loadings.columns:
    vars_pc = assign_df[assign_df['Assigned_PC'] == pc]
    pos_vars = vars_pc[vars_pc['Sign'] == 'Positive']['Variable'].tolist()
    neg_vars = vars_pc[vars_pc['Sign'] == 'Negative']['Variable'].tolist()
    print(f"\n{pc}：")
    print(f"  positively correlated variables：{pos_vars}")
    print(f"  Negatively correlated variables：{neg_vars}")

scores = X @ fa.loadings_
score_df = pd.DataFrame(scores, index=df.index, columns=[f'PC{i+1}' for i in range(n_factors)])


eigvals, prop_var, cum_var = fa.get_factor_variance()
explained_df = pd.DataFrame({
    'Eigenvalue': eigvals,
    'Variance%': prop_var * 100,
    'Cumulative%': cum_var * 100
}, index=[f'PC{i+1}' for i in range(n_factors)])

with pd.ExcelWriter('pca_results_complete.xlsx') as writer:
    loadings.to_excel(writer, sheet_name='Loadings')
    assign_df.to_excel(writer, sheet_name='Assignments', index=False)
    score_df.to_excel(writer, sheet_name='Scores')
    explained_df.to_excel(writer, sheet_name='Explained Variance')

print("\n All principal component analysis results have been saved to 'pca_results_complete.xlsx'")
