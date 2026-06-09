import numpy as np
import pandas as pd

from agri_transform.pca_tools import varimax, bartlett_sphericity


def test_varimax_shape():
    rng = np.random.default_rng(42)
    loadings = rng.normal(size=(6, 3))
    rotated, rotation = varimax(loadings)
    assert rotated.shape == loadings.shape
    assert rotation.shape == (3, 3)


def test_bartlett_returns_values():
    rng = np.random.default_rng(42)
    X = rng.normal(size=(50, 5))
    out = bartlett_sphericity(X)
    assert {"chi_square", "df", "p_value"} <= set(out)
