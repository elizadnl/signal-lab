from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from .backtest import run_backtest
from .signals import build_signal


@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int = 365
    test_days: int = 90
    candidate_lookbacks: tuple[int, ...] = (5, 10, 20, 40, 60)
    fee_bps: float = 10.0
    holding_period: int = 1


def select_lookback(df: pd.DataFrame, signal_name: str, candidate_lookbacks: tuple[int, ...], fee_bps: float, holding_period: int) -> tuple[int, float]:
    scored: list[tuple[float, int]] = []
    for lb in candidate_lookbacks:
        sig = build_signal(df, signal_name, lb)
        bt = run_backtest(df, sig, fee_bps=fee_bps, holding_period=holding_period)
        score = bt["metrics"]["sharpe"]
        if not np.isfinite(score):
            score = -1e9
        scored.append((float(score), int(lb)))
    best_score, best_lb = max(scored, key=lambda x: (x[0], -x[1]))
    return best_lb, best_score


def walk_forward_signal(df: pd.DataFrame, signal_name: str, config: WalkForwardConfig) -> tuple[pd.Series, list[dict]]:
    """Choose a lookback only on trailing data, then lock it for unseen data."""
    final_signal = pd.Series(0.0, index=df.index)
    folds: list[dict] = []

    start = config.train_days
    while start < len(df):
        train_start = max(0, start - config.train_days)
        test_end = min(len(df), start + config.test_days)
        train = df.iloc[train_start:start].copy()

        best_lb, best_score = select_lookback(
            train,
            signal_name,
            config.candidate_lookbacks,
            config.fee_bps,
            config.holding_period,
        )

        # Signal functions are trailing-only, so constructing them on history up
        # to test_end does not expose any row to observations after that row.
        contextual = df.iloc[:test_end].copy()
        sig = build_signal(contextual, signal_name, best_lb)
        final_signal.iloc[start:test_end] = sig.iloc[start:test_end]

        folds.append({
            "train_start": str(df.iloc[train_start]["date"].date()),
            "train_end": str(df.iloc[start - 1]["date"].date()),
            "test_start": str(df.iloc[start]["date"].date()),
            "test_end": str(df.iloc[test_end - 1]["date"].date()),
            "lookback": int(best_lb),
            "train_sharpe": float(best_score),
        })
        start = test_end

    return final_signal, folds
