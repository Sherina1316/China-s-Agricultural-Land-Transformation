# Reproducibility checklist

Before running the workflow, verify the following items.

## Data availability

- Annual CACD or equivalent cropland rasters are available for every year from
  2000 to 2023.
- Province boundaries are in a valid shapefile or GeoPackage and contain a
  province name field.
- Official crop sown-area statistics are formatted as province-by-year tables.
- PCA indicator tables contain the variables listed in the manuscript.
- GTWR/TWR modelling tables contain coordinates, year, PCA components and
  outcome variables.

## Units

- CACD-derived cropland extent and crop sown area should be harmonised to the
  same area unit before diagnostics. The example workflow uses kha.
- Percentage variables should be kept as percentages, not fractions, unless the
  manuscript table has been updated accordingly.
- Per-area variables such as machinery power, plastic-film use and grain yield
  should retain consistent denominators.

## Model interpretation

- The decomposition analysis is an accounting identity based on S = C x R.
- PCA components summarize covariance among standardized indicators.
- GWR, TWR and GTWR coefficients are local associations rather than causal
  effects.
- The CP outcome is modelled using TWR when Moran's I is not significant.

## Code checks

Run:

```bash
python -m compileall src scripts
python scripts/00_validate_inputs.py --help
python scripts/run_full_workflow.py --help
```
