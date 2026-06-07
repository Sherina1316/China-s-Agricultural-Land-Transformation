# Workflow mapping

This repository consolidates the previously separate scripts into a structured workflow.

| Manuscript analysis step | Consolidated script | Core module |
|---|---|---|
| CACD-derived cropland extent extraction | `scripts/01_compute_cropland_extent.py` | `agri_transform.area` |
| Cropland extent--crop sown-area decoupling and decomposition | `scripts/02_cropland_sown_area_diagnostics.py` | `agri_transform.diagnostics` |
| Indicator standardisation and PCA with varimax rotation | `scripts/03_pca_varimax.py` | `agri_transform.pca_tools` |
| Moran's I spatial autocorrelation | `scripts/04_spatial_autocorrelation.py` | `agri_transform.spatial` |
| GWR/TWR/GTWR local regression | `scripts/05_gtwr_gwr_twr.py` | `agri_transform.regression` |
| Monte Carlo coefficient uncertainty | `scripts/06_uncertainty_analysis.py` | `agri_transform.uncertainty` |
| Diagnostic figure generation | `scripts/07_plot_diagnostics.py` | `agri_transform.figures` |

The repository intentionally avoids hard-coded local drive paths. All paths should be passed through command-line arguments or adapted in `configs/config.example.yaml`.
