import numpy as np
import pandas as pd

from signallab.backtest import run_backtest
from signallab.signals import momentum


def sample_df(n=220):
    dates = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.linspace(0, 0.35, n) + 0.03 * np.sin(np.arange(n) / 5))
    return pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.linspace(1000, 2000, n),
    })


def test_backtest_has_no_nan_equity():
    df = sample_df()
    sig = momentum(df, lookback=20)
    bt = run_backtest(df, sig, fee_bps=10)
    assert bt["equity"].notna().all()
    assert bt["equity"].iloc[0] > 0


def test_costs_reduce_equity_on_same_signal():
    df = sample_df()
    sig = momentum(df, lookback=10)
    free = run_backtest(df, sig, fee_bps=0)["equity"].iloc[-1]
    costly = run_backtest(df, sig, fee_bps=20)["equity"].iloc[-1]
    assert costly <= free


def test_entry_cost_is_charged_on_execution_bar():
    df = sample_df(n=8)
    sig = pd.Series([0, 1, 1, 1, 0, 0, 0, 0], dtype=float)
    free = run_backtest(df, sig, fee_bps=0)
    costly = run_backtest(df, sig, fee_bps=10)
    # Signal changes at index 1, but position becomes effective over index 2 return.
    assert costly["costs"].iloc[1] == 0
    assert np.isclose(costly["costs"].iloc[2], 0.001)
    assert np.isclose(free["strategy_return"].iloc[2] - costly["strategy_return"].iloc[2], 0.001)
