import numpy as np
import pandas as pd

from signallab.walk_forward import WalkForwardConfig, walk_forward_signal


def sample_df(n=900):
    rng = np.random.default_rng(7)
    dates = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    ret = 0.0004 + rng.normal(0, 0.02, n)
    close = 100 * np.exp(np.cumsum(ret))
    return pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.exp(rng.normal(10, 0.5, n)),
    })


def test_walk_forward_returns_full_length_signal():
    df = sample_df()
    sig, folds = walk_forward_signal(df, "momentum", WalkForwardConfig(train_days=300, test_days=60))
    assert len(sig) == len(df)
    assert len(folds) > 2


def test_walk_forward_history_is_invariant_to_appended_future_data():
    df = sample_df(n=900)
    cfg = WalkForwardConfig(train_days=300, test_days=60)
    short = df.iloc[:720].copy()
    sig_short, _ = walk_forward_signal(short, "momentum", cfg)
    sig_full, _ = walk_forward_signal(df, "momentum", cfg)
    pd.testing.assert_series_equal(sig_short, sig_full.iloc[:720], check_names=False)
