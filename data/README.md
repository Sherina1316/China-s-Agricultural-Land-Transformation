# Data directory

The repository does not redistribute third-party remote-sensing products or official statistical yearbooks. Place data files in the following structure before running the workflow.

```text
data/raw/
  crop_sown_area_by_province.csv
  cropland_extent_by_province_prepared.csv   # optional if using prepared CACD-derived table
  CACD_rasters/                              # optional if extracting from rasters
  boundaries/china_provinces.shp             # optional if extracting from rasters
data/processed/
  pca_indicators.csv
  gtwr_model_table.csv
```

## Province-by-year tables

Cropland extent and crop sown-area tables should follow:

```text
Province,2000,2001,...,2023
```

Values should be in kha unless `--input-scale-to-kha` is specified.

## Model table

The GTWR/TWR table should contain:

```text
Province, year, longitude, latitude, climate_zone, SSN, GM, IPLG, RW, CWE, CS, HQ, NDR, SDR, RHI, CP
```

The template files in `data/templates/` show minimal accepted column names.
