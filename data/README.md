# Data directory

Raw datasets are not distributed in this repository because most source data are third-party products or official statistics. Place input files in this directory following the templates.

Required inputs:

1. **CACD-derived annual cropland extent rasters**  
   Binary annual GeoTIFFs where cropland pixels are coded as `1` and non-cropland pixels as `0`. The repository supports China’s 30-m Annual Cropland Dataset (CACD) and its 2022--2023 extension.

2. **Province boundary file**  
   A shapefile or GeoPackage containing mainland China provincial boundaries.

3. **Official crop sown-area table**  
   Province-by-year table with columns `Province, 2000, 2001, ..., 2023`; values should be in thousand hectares (kha), unless a scale factor is applied before use.

4. **PCA indicator table**  
   Numeric indicators used to construct PCA-derived agricultural-use components.

5. **GTWR/TWR modelling table**  
   Province-year table containing coordinates, year, PCA components and response variables.

See `data/templates/` for minimal input examples.
