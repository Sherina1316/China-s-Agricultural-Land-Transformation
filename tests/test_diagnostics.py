import pandas as pd
import numpy as np

from agri_transform.diagnostics import exact_decomposition, classify_change, build_diagnostic_tables, DiagnosticConfig


def test_exact_decomposition_identity():
    out = exact_decomposition(C0=100.0, C1=90.0, S0=100.0, S1=120.0)
    reconstructed = out["extent_effect"] + out["use_intensity_effect"] + out["interaction_effect"]
    assert np.isclose(reconstructed, out["delta_S"])


def test_classify_change():
    assert classify_change(6, 5) == "Gain"
    assert classify_change(-6, 5) == "Loss"
    assert classify_change(0, 5) == "Stable"


def test_build_diagnostic_tables():
    C = pd.DataFrame({"Province": ["A", "B"], 2000: [100, 100], 2023: [90, 110]})
    S = pd.DataFrame({"Province": ["A", "B"], 2000: [100, 100], 2023: [120, 110]})
    out = build_diagnostic_tables(C, S, years=[2000, 2023], config=DiagnosticConfig(start_year=2000, end_year=2023))
    assert "province_summary" in out
    assert "national_timeseries" in out
    assert len(out["province_summary"]) == 2
