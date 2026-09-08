from __future__ import annotations

import numpy as np
import pandas as pd

from .stats import strategy_metrics


def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    fee_bps: float = 10.0,
    holding_period: int = 1,
) -> dict:
    """Backtest with next-bar execution and turnover-based costs.

    The signal observed at close ``t`` becomes the position for the return from
    ``t`` to ``t+1``. Entry/exit costs are charged on that same next bar. This
    keeps both P&L and costs aligned to the execution convention and avoids
    look-ahead.
    """
    if holding_period < 1:
        raise ValueError("holding_period must be >= 1")
    if fee_bps < 0:
        raise ValueError("fee_bps must be >= 0")

    raw = signal.reindex(df.index).astype(float).fillna(0.0).clip(-1, 1)
    if holding_period > 1:
        pos = pd.Series(0.0, index=raw.index)
        active = 0.0
        remaining = 0
        for i, x in enumerate(raw):
            if remaining <= 0 and x != 0:
                active = x
                remaining = holding_period
            if remaining > 0:
                pos.iloc[i] = active
                remaining -= 1
            else:
                active = 0.0
    else:
        pos = raw

    asset_ret = df["close"].pct_change().fillna(0.0)

    # pos[t-1] is the position held over the return observed at t.
    held_pos = pos.shift(1).fillna(0.0)
    signal_turnover = pos.diff().abs().fillna(pos.abs())
    execution_turnover = signal_turnover.shift(1).fillna(0.0)
    costs = execution_turnover * (fee_bps / 10_000.0)

    strat_ret = held_pos * asset_ret - costs
    equity = (1.0 + strat_ret).cumprod()
    drawdown = equity / equity.cummax() - 1.0

    metrics = strategy_metrics(strat_ret, pos)
    return {
        "positions": pos,
        "held_positions": held_pos,
        "asset_return": asset_ret,
        "turnover_series": execution_turnover,
        "costs": costs,
        "strategy_return": strat_ret,
        "equity": equity,
        "drawdown": drawdown,
        "metrics": metrics,
    }
