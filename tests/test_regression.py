import numpy as np

from agri_transform.regression import fit_local_regression


def test_gtwr_runs_on_synthetic_data():
    rng = np.random.default_rng(42)
    n = 20
    X = rng.normal(size=(n, 2))
    y = 1 + X[:, 0] * 0.5 - X[:, 1] * 0.2 + rng.normal(scale=0.01, size=n)
    lon = np.linspace(100, 110, n)
    lat = np.linspace(30, 40, n)
    time = np.arange(n)
    res = fit_local_regression(X, y, lon=lon, lat=lat, time=time, model="GTWR", bandwidth_spatial=0.5, bandwidth_temporal=0.5)
    assert res.coefficients.shape[0] == n
    assert "r2" in res.diagnostics
