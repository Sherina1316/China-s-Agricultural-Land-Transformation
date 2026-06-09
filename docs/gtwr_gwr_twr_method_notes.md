# GWR, TWR and GTWR model notes

This document explains how the local regression code in this repository maps to
the manuscript methods.

## Model interpretation

The local regression workflow is designed to diagnose spatially and temporally
heterogeneous **associations** between PCA-derived agricultural-use components
and socio-environmental outcomes. The coefficients should not be interpreted as
causal effects.

## OLS

OLS provides a global baseline:

`Y_i = beta_0 + sum_k beta_k X_ik + epsilon_i`

The same coefficient is assumed for all provinces and years.

## GWR

Geographically weighted regression allows coefficients to vary by location:

`Y_i = beta_0(u_i, v_i) + sum_k beta_k(u_i, v_i) X_ik + epsilon_i`

Nearby observations receive greater weight through a Gaussian spatial kernel.

## TWR

Temporally weighted regression allows coefficients to vary through time but not
space. In the manuscript workflow, CP was analysed using TWR when spatial
autocorrelation was not significant at the 95% confidence level.

## GTWR

Geographically and temporally weighted regression allows coefficients to vary in
both space and time:

`Y_i = beta_0(u_i, v_i, t_i) + sum_k beta_k(u_i, v_i, t_i) X_ik + epsilon_i`

The mixed Gaussian spatiotemporal kernel is:

`w_ij = exp[-(d_ij / b_s)^2 - ((t_i - t_j) / b_t)^2]`

where `d_ij` is spatial distance, `b_s` is spatial bandwidth and `b_t` is
temporal bandwidth.

## Bandwidth selection

The implementation performs grid search over user-defined spatial and temporal
bandwidth candidates. For each candidate combination, it fits the model and
computes AICc, R2, adjusted R2, residual sum of squares and sigma. The candidate
with the minimum AICc is selected.

## Why cropland extent and crop sown area are not jointly entered

CACD-derived cropland extent represents physical land-cover availability. Crop
sown area represents annual planting activity, which may change through multiple
cropping, crop-calendar adjustment and production organization. The manuscript
therefore analyses the relationship between the two variables in a diagnostic
step, then uses sown-area-based agricultural-use components in the GTWR/TWR
models. This avoids conflating physical land availability with planting
activity.
