from __future__ import annotations

import numpy as np
import pandas as pd


def classify_volatility_regime(df: pd.DataFrame, window: int = 30) -> pd.Series:
    """Classify realized volatility using expanding, point-in-time quantiles.

    Quantile thresholds only use information available before the current row.
    """
    ret = np.log(df["close"]).diff()
    rv = ret.rolling(window).std(ddof=0) * np.sqrt(365)
    q1 = rv.expanding(min_periods=max(window * 2, 60)).quantile(1 / 3).shift(1)
    q2 = rv.expanding(min_periods=max(window * 2, 60)).quantile(2 / 3).shift(1)

    regime = pd.Series("normal", index=df.index, dtype="object")
    regime.loc[rv < q1] = "low"
    regime.loc[rv > q2] = "high"
    regime.loc[q1.isna() | q2.isna()] = "warmup"
    return regime


def classify_trend_regime(df: pd.DataFrame, fast: int = 20, slow: int = 80) -> pd.Series:
    fast_ma = df["close"].rolling(fast).mean()
    slow_ma = df["close"].rolling(slow).mean()
    out = pd.Series("flat", index=df.index, dtype="object")
    out.loc[fast_ma > slow_ma * 1.01] = "uptrend"
    out.loc[fast_ma < slow_ma * 0.99] = "downtrend"
    return out
