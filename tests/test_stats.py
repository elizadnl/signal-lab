import numpy as np
import pandas as pd

from signallab.stats import benjamini_hochberg, block_bootstrap_sharpe_ci, hac_mean_test


def test_benjamini_hochberg_known_example():
    q = benjamini_hochberg([0.01, 0.04, 0.03, 0.20])
    assert np.allclose(q, [0.04, 0.05333333333333334, 0.05333333333333334, 0.20])


def test_block_bootstrap_is_deterministic():
    rng = np.random.default_rng(123)
    r = pd.Series(rng.normal(0.001, 0.02, 500))
    a = block_bootstrap_sharpe_ci(r, n_boot=100, seed=9)
    b = block_bootstrap_sharpe_ci(r, n_boot=100, seed=9)
    assert np.allclose(a, b)
    assert a[0] <= a[1]


def test_hac_test_detects_zero_mean_as_non_significant():
    r = pd.Series(np.tile([0.01, -0.01], 300))
    out = hac_mean_test(r, max_lag=7)
    assert abs(out["t_stat"]) < 1e-10
    assert out["p_value"] > 0.99


def test_white_reality_check_is_deterministic_and_finds_strong_edge():
    from signallab.stats import white_reality_check

    rng = np.random.default_rng(77)
    n = 700
    frame = pd.DataFrame({
        "noise_a": rng.normal(0.0, 0.01, n),
        "noise_b": rng.normal(0.0, 0.01, n),
        "edge": rng.normal(0.0025, 0.01, n),
    })
    a = white_reality_check(frame, n_boot=200, seed=11)
    b = white_reality_check(frame, n_boot=200, seed=11)
    assert a == b
    assert a["best_specification"] == "edge"
    assert a["p_value"] < 0.05
    assert a["trials"] == 3


def test_white_reality_check_returns_one_when_best_mean_nonpositive():
    from signallab.stats import white_reality_check

    frame = pd.DataFrame({
        "a": np.tile([-0.01, 0.0], 200),
        "b": np.tile([-0.02, 0.0], 200),
    })
    out = white_reality_check(frame, n_boot=50)
    assert out["p_value"] == 1.0
