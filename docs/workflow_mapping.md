# Mapping between manuscript analyses and repository scripts

| Manuscript component | Repository script/module | Main outputs |
|---|---|---|
| CACD-derived physical cropland extent | `scripts/01_compute_cropland_extent.py`; `agri_transform.area` | `cropland_extent_by_province.csv` |
| Cropland extent--crop sown-area diagnostic analysis | `scripts/02_cropland_sown_area_diagnostics.py`; `agri_transform.diagnostics` | province summary, national diagnostic timeseries |
| Decoupling index and exact decomposition | `agri_transform.diagnostics.exact_decomposition` | extent effect, use-intensity effect, interaction effect |
| PCA with varimax rotation | `scripts/03_pca_varimax.py`; `agri_transform.pca_tools` | rotated loadings, PCA scores, explained variance |
| Moran's I for outcome variables | `scripts/04_spatial_autocorrelation.py`; `agri_transform.spatial` | Moran's I summary |
| GWR/TWR/GTWR diagnostics | `scripts/05_gtwr_gwr_twr.py`; `agri_transform.regression` | local coefficients, bandwidth search, model diagnostics |
| Monte Carlo uncertainty diagnostics | `scripts/06_uncertainty_analysis.py`; `agri_transform.uncertainty` | coefficient uncertainty summary |
| Diagnostic figures | `scripts/07_plot_diagnostics.py`; `agri_transform.figures` | figure-ready PNG/PDF files |
| Full reproducible workflow | `scripts/run_full_workflow.py` | outputs grouped by workflow step |

## Important interpretation rules

1. Cropland extent is used to quantify physical land-cover redistribution.
2. Crop sown area is used to represent annual planting activity.
3. Their relationship is assessed in a diagnostic step before GTWR/TWR modelling.
4. GTWR/TWR uses sown-area-based PCA components, not raw cropland extent and crop sown area together.
5. Local regression coefficients are spatial-temporal associations, not causal effects.
