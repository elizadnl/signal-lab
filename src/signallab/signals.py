from __future__ import annotations

import numpy as np
import pandas as pd


def _zscore(s: pd.Series, window: int) -> pd.Series:
    mean = s.rolling(window).mean()
    std = s.rolling(window).std(ddof=0).replace(0, np.nan)
    return (s - mean) / std


def momentum(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    r = df["close"].pct_change(lookback)
    return np.sign(r).replace(0, np.nan).fillna(0.0)


def mean_reversion(df: pd.DataFrame, lookback: int = 10) -> pd.Series:
    z = _zscore(np.log(df["close"]), lookback)
    return (-np.sign(z)).replace(0, np.nan).fillna(0.0)


def abnormal_volume(df: pd.DataFrame, lookback: int = 20, threshold: float = 1.0) -> pd.Series:
    vol_z = _zscore(np.log1p(df["volume"]), lookback)
    direction = np.sign(df["close"].pct_change())
    sig = direction.where(vol_z > threshold, 0.0)
    return sig.fillna(0.0)


def volatility_breakout(df: pd.DataFrame, lookback: int = 20, threshold: float = 1.0) -> pd.Series:
    ret = df["close"].pct_change()
    vol = ret.rolling(lookback).std(ddof=0)
    impulse = ret.abs() / vol.replace(0, np.nan)
    return np.sign(ret).where(impulse > threshold, 0.0).fillna(0.0)


SIGNALS = {
    "momentum": momentum,
    "mean_reversion": mean_reversion,
    "abnormal_volume": abnormal_volume,
    "volatility_breakout": volatility_breakout,
}


def build_signal(df: pd.DataFrame, name: str, lookback: int) -> pd.Series:
    if name not in SIGNALS:
        raise KeyError(f"Unknown signal: {name}")
    return SIGNALS[name](df, lookback=lookback)
