# China Agricultural Land Transformation Analysis Code

This repository contains the reproducible analysis code for the manuscript **"Unveiling the Socio-Ecological Impacts of Long-Term Cropland Transformation in China"**. The workflow was reorganised to address the code-availability concern raised during review and to make the distinction between **physical cropland extent** and **statistical crop sown area** explicit.

The code is written in English and is intended for direct upload to a public GitHub repository.

---

## 1. Conceptual scope

The repository follows the revised analytical framework of the manuscript:

1. **Physical cropland extent**  
   Derived from China’s 30-m Annual Cropland Dataset (CACD). It represents the spatial land-cover footprint of cropland.

2. **Statistical crop sown area**  
   Derived from official agricultural statistics. It represents annual planting activity and may exceed physical cropland extent because the same parcel can be planted more than once within a year.

3. **Cropland extent--sown area diagnostics**  
   Quantifies the relationship between physical land availability and annual planting activity through:
   - relative change in cropland extent and crop sown area;
   - coupling typology using a ±5% stable threshold;
   - agricultural-use intensity proxy, `R = S / C`;
   - decoupling index, `DI = gS - gC`;
   - exact decomposition of crop sown-area change:

     `Delta S = R0 * Delta C + C0 * Delta R + Delta C * Delta R`

4. **PCA-derived agricultural-use components**  
   Principal component analysis with varimax rotation is used to summarise sown-area-based agricultural-use, input-intensification and crop-specialisation indicators.

5. **Spatial-temporal association analysis**  
   GTWR/TWR models are used to diagnose spatially and temporally heterogeneous associations between PCA-derived agricultural-use components and socio-ecological outcomes. The coefficients are interpreted as local associations, not causal effects.

---

## 2. Repository structure

```text
china_agricultural_land_transformation/
├── README.md
├── LICENSE
├── CITATION.cff
├── requirements.txt
├── pyproject.toml
├── configs/
│   └── config.example.yaml
├── data/
│   ├── README.md
│   └── templates/
│       ├── cropland_or_sown_area_template.csv
│       ├── pca_indicators_template.csv
│       └── gtwr_model_table_template.csv
├── scripts/
│   ├── 01_compute_cropland_extent.py
│   ├── 02_cropland_sown_area_diagnostics.py
│   ├── 03_pca_varimax.py
│   ├── 04_spatial_autocorrelation.py
│   ├── 05_gtwr_gwr_twr.py
│   ├── 06_uncertainty_analysis.py
│   └── 07_plot_diagnostics.py
└── src/
    └── agri_transform/
        ├── area.py
        ├── diagnostics.py
        ├── figures.py
        ├── io_utils.py
        ├── pca_tools.py
        ├── regression.py
        ├── spatial.py
        ├── style.py
        └── uncertainty.py
```

---

## 3. Installation

Create a clean Python environment:

```bash
conda create -n agri-transform python=3.10 -y
conda activate agri-transform
pip install -r requirements.txt
pip install -e .
```

GeoPandas and Rasterio can be easier to install through conda-forge on some systems:

```bash
conda install -c conda-forge geopandas rasterio pyproj shapely libpysal esda -y
pip install -r requirements.txt
pip install -e .
```

---

## 4. Required input data

Raw data are not included because most datasets are third-party products or official statistics.

Place input data under `data/raw/` and `data/boundaries/` or edit paths in `configs/config.example.yaml`.

### 4.1 CACD-derived cropland extent rasters

Annual binary cropland rasters, preferably from CACD, with cropland coded as `1` and non-cropland coded as `0`.

Expected file naming: each raster filename should contain a year, for example:

```text
CACD_2000.tif
CACD_2001.tif
...
CACD_2023.tif
```

### 4.2 Province boundary file

A provincial boundary layer for mainland China in shapefile or GeoPackage format.

### 4.3 Official crop sown-area table

A province-by-year table in CSV or Excel format:

```text
Province,2000,2001,...,2023
Anhui, ...
Beijing, ...
```

Values should be in **thousand hectares (kha)** unless transformed before analysis.

### 4.4 PCA indicator table

A province-year table containing agricultural-use indicators such as:

```text
Sown_all, C_simpson, U_npp, A_grain, A_maize, I_area, U_power, U_plas, U_Grain_yield, A_rice, A_wheat
```

### 4.5 GTWR/TWR modelling table

A province-year table containing:

```text
Province, year, longitude, latitude, SSN, GM, IPLG, RW, CWE, CS, HQ, NDR, SDR, RHI, CP
```

where:

- `SSN`, `GM`, `IPLG`, `RW` are PCA-derived agricultural-use components;
- `CWE` is crop water evapotranspiration;
- `CS` is carbon storage;
- `HQ` is habitat quality;
- `NDR` is nutrient delivery ratio;
- `SDR` is sediment delivery ratio;
- `RHI` is rural household income;
- `CP` is crop production potential.

---

## 5. Workflow

### Step 1. Compute CACD-derived cropland extent by province

```bash
python scripts/01_compute_cropland_extent.py \
  --raster-dir data/raw/CACD \
  --province-shp data/boundaries/china_provinces.shp \
  --output data/processed/cropland_extent_by_province.csv \
  --start-year 2000 \
  --end-year 2023 \
  --province-field Province
```

Important implementation detail: if the raster is stored in a geographic coordinate system, the code estimates row-specific geodesic pixel areas instead of assuming that every pixel is exactly `30 m × 30 m`. This avoids overestimating national cropland extent when working with longitude-latitude rasters.

### Step 2. Diagnose the relationship between cropland extent and crop sown area

```bash
python scripts/02_cropland_sown_area_diagnostics.py \
  --cropland data/processed/cropland_extent_by_province.csv \
  --sown data/raw/crop_sown_area_by_province.csv \
  --output-dir outputs/diagnostics \
  --start-year 2000 \
  --end-year 2023 \
  --stable-threshold 5
```

Outputs:

- `province_summary.csv`
- `national_timeseries.csv`
- `annual_decomposition.csv`
- `coupling_counts.csv`
- `cropland_sown_area_diagnostics.xlsx`

### Step 3. Run PCA with varimax rotation

```bash
python scripts/03_pca_varimax.py \
  --input data/processed/pca_indicators.csv \
  --output-dir outputs/pca \
  --index-col 0
```

Outputs:

- `pca_varimax_loadings.csv`
- `pca_scores.csv`
- `pca_explained_variance.csv`
- `pca_variable_assignments.csv`
- `pca_bartlett_test.csv`
- `pca_results.xlsx`

### Step 4. Test spatial autocorrelation of response variables

```bash
python scripts/04_spatial_autocorrelation.py \
  --input data/processed/gtwr_model_table.csv \
  --output outputs/spatial_autocorrelation/moran_summary.csv \
  --lon-col longitude \
  --lat-col latitude \
  --value-columns CWE CS HQ NDR SDR RHI CP
```

In the manuscript workflow, response variables with significant spatial structure were analysed using GTWR. `CP` was analysed using TWR when Moran's I was not significant at the 95% confidence level.

### Step 5. Run GTWR/TWR local regression models

```bash
python scripts/05_gtwr_gwr_twr.py \
  --input data/processed/gtwr_model_table.csv \
  --output-dir outputs/gtwr \
  --responses CWE CS HQ NDR SDR RHI CP \
  --explanatory SSN GM IPLG RW \
  --lon-col longitude \
  --lat-col latitude \
  --time-col year
```

Outputs:

- `{response}_GTWR_local_coefficients.csv`
- `{response}_GTWR_bandwidth_search.csv`
- `CP_TWR_local_coefficients.csv`
- `CP_TWR_bandwidth_search.csv`
- `model_diagnostics_summary.csv`

### Step 6. Run Monte Carlo uncertainty diagnostics

```bash
python scripts/06_uncertainty_analysis.py \
  --coefficients outputs/gtwr/CWE_GTWR_local_coefficients.csv \
  --output-dir outputs/uncertainty/CWE \
  --coefficient-columns SSN GM IPLG RW \
  --n-iter 1000
```

### Step 7. Plot diagnostic figures

```bash
python scripts/07_plot_diagnostics.py cropland-sown \
  --province-summary outputs/diagnostics/province_summary.csv \
  --national-timeseries outputs/diagnostics/national_timeseries.csv \
  --output-base outputs/figures/cropland_sown_diagnostics

python scripts/07_plot_diagnostics.py heatmap \
  --coefficients outputs/gtwr/CWE_GTWR_local_coefficients.csv \
  --output-base outputs/figures/CWE_GTWR_coefficients
```

---

## 6. Notes on GWR, TWR and GTWR

### 6.1 OLS

Ordinary least squares estimates one global coefficient for each explanatory variable. It assumes that the relationship between agricultural-use components and response variables is constant across all provinces and years.

### 6.2 GWR

Geographically weighted regression allows coefficients to vary across space. Observations closer in geographic distance receive greater weights. In this repository, a Gaussian spatial kernel is used:

```text
w_ij = exp[-(d_ij / b_s)^2]
```

where `d_ij` is the spatial distance between observations `i` and `j`, and `b_s` is the spatial bandwidth.

### 6.3 TWR

Temporally weighted regression allows coefficients to vary over time. Observations from adjacent years receive greater weights:

```text
w_ij = exp[-((t_i - t_j) / b_t)^2]
```

where `b_t` is the temporal bandwidth.

### 6.4 GTWR

Geographically and temporally weighted regression combines spatial and temporal weighting:

```text
w_ij = exp[-(d_ij / b_s)^2 - ((t_i - t_j) / b_t)^2]
```

The model is:

```text
Y_i = beta_0(u_i, v_i, t_i) + sum_k beta_k(u_i, v_i, t_i) X_ik + epsilon_i
```

where `(u_i, v_i)` are spatial coordinates, `t_i` is time, `X_ik` is the kth explanatory variable, and `beta_k(u_i, v_i, t_i)` is a local coefficient.

In this repository, spatial and temporal distances are normalised to `[0, 1]` by default. Bandwidths can therefore be interpreted as relative neighbourhood sizes. The scripts use grid search and AICc to select bandwidths.

### 6.5 Interpretation

GTWR/TWR coefficients are interpreted as **spatially and temporally heterogeneous associations**, not as causal effects. Potential endogeneity may exist among rural household income, policy incentives, land-use change, agricultural inputs and ecosystem-service responses. The models are used as diagnostic tools for regional heterogeneity, not as causal identification frameworks.

---

## 7. Reproducibility checklist

Before uploading to GitHub, verify that:

- the repository is public;
- `README.md` is visible on the GitHub landing page;
- all scripts are under `scripts/` and all reusable code is under `src/agri_transform/`;
- `requirements.txt` and `pyproject.toml` are present;
- input data templates are included;
- raw third-party data are not committed unless licences permit redistribution;
- code runs with `pip install -e .`;
- paths in scripts are command-line arguments, not hard-coded local drive paths.

---

## 8. Code availability statement for manuscript/rebuttal

The analysis code has been reorganised and made publicly available in the GitHub repository. The repository contains scripts for CACD-derived cropland extent extraction, cropland extent--crop sown area diagnostics, exact decomposition, PCA with varimax rotation, spatial autocorrelation testing, GTWR/TWR local regression, Monte Carlo uncertainty diagnostics and figure generation. A README file documents the workflow, input data requirements, software environment and interpretation of GWR/GTWR/TWR outputs.
