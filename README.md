# China Agricultural Land Transformation: Reproducible Analysis Code

This repository contains the reproducible Python workflow for the manuscript on China’s agricultural land-use transformation from 2000 to 2023. The code has been expanded from the original working scripts into a detailed, reviewable and GitHub-ready workflow. Each numbered Python file now contains explicit calculation steps, input checks, intermediate outputs and detailed comments.

## Core analytical logic

The workflow follows the revised manuscript framework:

1. **Separate physical cropland extent from statistical crop sown area.**
   - Physical cropland extent is derived from China’s 30-m Annual Cropland Dataset (CACD) or a prepared province-by-year CACD table.
   - Statistical crop sown area comes from official agricultural statistics and represents annual planting activity.

2. **Diagnose cropland extent--crop sown area decoupling.**
   - Relative change in cropland extent: `gC = 100 × (C_t − C_0) / C_0`.
   - Relative change in crop sown area: `gS = 100 × (S_t − S_0) / S_0`.
   - Decoupling index: `DI = gS − gC`.
   - Agricultural-use intensity proxy: `R = S / C`.
   - Exact decomposition: `ΔS = R0 × ΔC + C0 × ΔR + ΔC × ΔR`.

3. **Construct agricultural-use components.**
   - Standardized PCA with varimax rotation is used to derive interpretable agricultural-use components such as SSN, GM, IPLG and RW.
   - Components are treated as dominant covariance structures, not as causal mechanisms.

4. **Evaluate spatial and temporal associations.**
   - Moran’s I is used to check spatial autocorrelation of response variables.
   - GWR, TWR and GTWR are implemented as local weighted regressions.
   - Coefficients are interpreted as spatially and temporally heterogeneous associations, not direct causal effects.

5. **Assess uncertainty and visualize trajectories.**
   - Monte Carlo and bootstrap diagnostics summarize coefficient stability.
   - Figure scripts create phase-space, decomposition, heatmap and socio-environmental trajectory plots.

## Repository structure

```text
.
├── README.md
├── requirements.txt
├── environment.yml
├── pyproject.toml
├── CITATION.cff
├── LICENSE
├── configs/
│   └── config.example.yaml
├── data/
│   ├── README.md
│   └── templates/
├── docs/
│   ├── code_availability_response.md
│   ├── gtwr_gwr_twr_method_notes.md
│   ├── reproducibility_checklist.md
│   └── workflow_mapping.md
├── scripts/
│   ├── 00_validate_inputs.py
│   ├── 01_compute_cropland_extent.py
│   ├── 02_cropland_sown_area_diagnostics.py
│   ├── 03_pca_varimax.py
│   ├── 04_spatial_autocorrelation.py
│   ├── 05_gtwr_gwr_twr.py
│   ├── 06_uncertainty_analysis.py
│   ├── 07_plot_publication_figures.py
│   └── run_full_workflow.py
├── src/agri_transform/
│   └── reusable helper modules
├── tests/
│   └── lightweight unit tests
└── legacy_full_version_scripts/
    └── original working scripts retained for traceability
```

## Installation

A minimal environment for tabular analysis is:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows Git Bash
pip install -r requirements.txt
```

For raster-based CACD extraction, install optional geospatial dependencies:

```bash
conda env create -f environment.yml
conda activate china-agricultural-land-transformation
```

## Input data

Raw third-party data are not redistributed. Prepare the following files:

```text
data/raw/crop_sown_area_by_province.csv
data/raw/cropland_extent_by_province_prepared.csv       # optional prepared CACD table
data/processed/pca_indicators.csv
data/processed/gtwr_model_table.csv
```

Templates are available in `data/templates/`.

## Step-by-step execution

### 0. Validate inputs

```bash
python scripts/00_validate_inputs.py \
  --cropland data/raw/cropland_extent_by_province_prepared.csv \
  --sown data/raw/crop_sown_area_by_province.csv \
  --model-table data/processed/gtwr_model_table.csv \
  --output outputs/validation/input_validation_report.csv
```

### 1. Prepare CACD-derived cropland extent

If a province-by-year CACD-derived table is already prepared:

```bash
python scripts/01_compute_cropland_extent.py \
  --prepared-table data/raw/cropland_extent_by_province_prepared.csv \
  --output data/processed/cropland_extent_by_province.csv \
  --start-year 2000 --end-year 2023
```

If annual rasters and province boundaries are available:

```bash
python scripts/01_compute_cropland_extent.py \
  --raster-dir data/raw/CACD_rasters \
  --province-boundaries data/raw/boundaries/china_provinces.shp \
  --output data/processed/cropland_extent_by_province.csv \
  --start-year 2000 --end-year 2023 \
  --cropland-values 1
```

### 2. Run cropland extent--crop sown area diagnostics

```bash
python scripts/02_cropland_sown_area_diagnostics.py \
  --cropland data/processed/cropland_extent_by_province.csv \
  --sown data/raw/crop_sown_area_by_province.csv \
  --output-dir outputs/cropland_sown_diagnostics \
  --stable-threshold 5
```

Key outputs:

```text
outputs/cropland_sown_diagnostics/tables/province_summary_coupling_decomposition.csv
outputs/cropland_sown_diagnostics/tables/national_timeseries_coupling.csv
outputs/cropland_sown_diagnostics/tables/national_cumulative_sown_area_decomposition.csv
outputs/cropland_sown_diagnostics/figures/fig3_phase_space.png
outputs/cropland_sown_diagnostics/figures/fig3_cumulative_decomposition.png
```

### 3. Run PCA with varimax rotation

```bash
python scripts/03_pca_varimax.py \
  --input data/processed/pca_indicators.csv \
  --output-dir outputs/pca \
  --component-labels SSN,GM,IPLG,RW
```

Key outputs:

```text
outputs/pca/pca_rotated_loadings.csv
outputs/pca/pca_rotated_component_scores.csv
outputs/pca/pca_results_complete.xlsx
```

### 4. Run Moran’s I spatial autocorrelation diagnostics

```bash
python scripts/04_spatial_autocorrelation.py \
  --input data/processed/gtwr_model_table.csv \
  --output outputs/spatial_autocorrelation/moran_i_summary.csv \
  --lon-col longitude --lat-col latitude --year-col year \
  --value-columns CWE CS HQ NDR SDR RHI CP \
  --plot
```

### 5. Run GWR/TWR/GTWR models

```bash
python scripts/05_gtwr_gwr_twr.py \
  --input data/processed/gtwr_model_table.csv \
  --output-dir outputs/gtwr_gwr_twr \
  --responses CWE CS HQ NDR SDR RHI CP \
  --explanatory SSN GM IPLG RW \
  --lon-col longitude --lat-col latitude --time-col year \
  --twr-responses CP
```

The default setting fits GTWR for spatially autocorrelated socio-environmental responses and TWR for CP. Outputs include bandwidth searches, local coefficients, fitted values, residuals and model summaries.

### 6. Run uncertainty diagnostics

```bash
python scripts/06_uncertainty_analysis.py \
  --coefficients outputs/gtwr_gwr_twr/all_local_coefficients_long.csv \
  --output-dir outputs/uncertainty \
  --coefficient-columns coef_SSN coef_GM coef_IPLG coef_RW \
  --n-iter 2000
```

### 7. Generate additional publication figures

```bash
python scripts/07_plot_publication_figures.py phase-space \
  --national-timeseries outputs/cropland_sown_diagnostics/tables/national_timeseries_coupling.csv \
  --output-base outputs/publication_figures/national_phase_space

python scripts/07_plot_publication_figures.py decomposition \
  --cumulative-decomposition outputs/cropland_sown_diagnostics/tables/national_cumulative_sown_area_decomposition.csv \
  --output-base outputs/publication_figures/national_cumulative_decomposition
```

## Run the complete workflow

Edit `configs/config.example.yaml` and then run:

```bash
python scripts/run_full_workflow.py --config configs/config.example.yaml --skip-cacd
```

Remove `--skip-cacd` if annual CACD rasters and province boundaries are available.

## Notes on model interpretation

- `C` denotes physical cropland extent.
- `S` denotes official statistical crop sown area.
- `R = S/C` is an agricultural-use intensity proxy, not a strict multiple-cropping index.
- GTWR/TWR coefficients are local associations, not causal effects.
- CACD-derived cropland extent is used to diagnose land-cover redistribution; sown-area-based components are used to evaluate planting activity, intensification and specialization.

## Code expansion relative to the earlier repository

The previous repository used short wrapper scripts around helper modules. This version adds detailed standalone scripts for each major analysis step. The scripts include explicit calculations, validation, comments, logging, intermediate output tables, model diagnostics and figure-generation logic. Original working scripts supplied by the authors are retained under `legacy_full_version_scripts/` for traceability.
