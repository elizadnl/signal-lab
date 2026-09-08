import numpy as np
import pandas as pd

from signallab.regimes import classify_volatility_regime


def sample_df(n=500):
    rng = np.random.default_rng(17)
    dates = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    ret = rng.normal(0, 0.02, n)
    close = 100 * np.exp(np.cumsum(ret))
    return pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.exp(rng.normal(10, 0.5, n)),
    })


def test_regime_history_does_not_change_when_future_is_appended():
    df = sample_df()
    short = classify_volatility_regime(df.iloc[:350].copy())
    full = classify_volatility_regime(df)
    pd.testing.assert_series_equal(short, full.iloc[:350], check_names=False)
