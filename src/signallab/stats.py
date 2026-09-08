from __future__ import annotations

import math
import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    if len(equity) == 0:
        return 0.0
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def longest_streak(values: pd.Series, positive: bool) -> int:
    best = current = 0
    for x in values:
        ok = x > 0 if positive else x < 0
        if ok:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def strategy_metrics(
    strategy_return: pd.Series,
    positions: pd.Series,
    periods_per_year: int = 365,
    *,
    held_positions: pd.Series | None = None,
    turnover_series: pd.Series | None = None,
) -> dict:
    """Compute strategy metrics on an explicitly supplied evaluation sample.

    ``held_positions`` and ``turnover_series`` are optional because a sliced
    evaluation window otherwise loses the position/cost alignment at its first
    row. The backtester supplies those series when exact evaluation metrics are
    required.
    """
    r = strategy_return.astype(float).fillna(0.0)
    eq = (1.0 + r).cumprod()
    held = held_positions.reindex(r.index).fillna(0.0) if held_positions is not None else positions.reindex(r.index).shift(1).fillna(0.0)
    active = r[held != 0]

    std = float(r.std(ddof=0))
    mean = float(r.mean())
    sharpe = 0.0 if not np.isfinite(std) or std == 0 else mean / std * math.sqrt(periods_per_year)

    downside = r[r < 0]
    downside_std = float(downside.std(ddof=0)) if len(downside) else 0.0
    sortino = None if downside_std == 0 or not np.isfinite(downside_std) else mean / downside_std * math.sqrt(periods_per_year)

    wins = active[active > 0]
    losses = active[active < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    if turnover_series is None:
        changes = positions.reindex(r.index).diff().abs().fillna(positions.reindex(r.index).abs())
    else:
        changes = turnover_series.reindex(r.index).fillna(0.0)
    trades = int((changes > 0).sum())
    turnover = float(changes.sum())

    terminal = float(eq.iloc[-1]) if len(eq) else 1.0
    annualized = terminal ** (periods_per_year / max(len(r), 1)) - 1.0 if terminal > 0 else -1.0
    mdd = max_drawdown(eq)
    calmar = None if mdd >= 0 else float(annualized / abs(mdd))
    ann_vol = std * math.sqrt(periods_per_year)

    return {
        "total_return": terminal - 1.0,
        "annualized_return": float(annualized),
        "annualized_volatility": float(ann_vol),
        "sharpe": float(sharpe),
        "sortino": None if sortino is None else float(sortino),
        "calmar": calmar,
        "max_drawdown": mdd,
        "win_rate": float((active > 0).mean()) if len(active) else 0.0,
        "profit_factor": profit_factor,
        "exposure": float((held != 0).mean()) if len(held) else 0.0,
        "trades": trades,
        "turnover": turnover,
        "longest_win_streak": longest_streak(active, True),
        "longest_loss_streak": longest_streak(active, False),
    }


def hac_mean_test(returns: pd.Series, max_lag: int = 7) -> dict:
    """Newey-West/HAC t-test for a non-zero mean return.

    The p-value uses the large-sample standard normal approximation. This keeps
    the project dependency-light while correcting the standard error for short
    horizon serial correlation and heteroskedasticity.
    """
    x = np.asarray(pd.Series(returns).dropna(), dtype=float)
    n = len(x)
    if n < 3:
        return {"t_stat": None, "p_value": None, "se_mean": None, "lags": int(max_lag)}

    mu = float(x.mean())
    u = x - mu
    lag = int(min(max_lag, n - 1))
    gamma0 = float(np.dot(u, u) / n)
    lrv = gamma0
    for k in range(1, lag + 1):
        weight = 1.0 - k / (lag + 1.0)
        gamma = float(np.dot(u[k:], u[:-k]) / n)
        lrv += 2.0 * weight * gamma
    lrv = max(lrv, 0.0)
    se = math.sqrt(lrv / n) if lrv > 0 else 0.0
    if se == 0:
        t_stat = 0.0 if mu == 0 else math.copysign(float("inf"), mu)
        p_value = 1.0 if mu == 0 else 0.0
    else:
        t_stat = mu / se
        p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
    return {"t_stat": float(t_stat), "p_value": float(p_value), "se_mean": float(se), "lags": lag}


def block_bootstrap_sharpe_ci(
    returns: pd.Series,
    *,
    periods_per_year: int = 365,
    block_size: int = 7,
    n_boot: int = 400,
    seed: int = 1729,
    alpha: float = 0.05,
) -> tuple[float | None, float | None]:
    """Moving-block bootstrap confidence interval for the Sharpe ratio."""
    x = np.asarray(pd.Series(returns).dropna(), dtype=float)
    n = len(x)
    if n < max(30, block_size * 2):
        return None, None
    if np.std(x) == 0:
        return 0.0, 0.0

    block = int(max(1, min(block_size, n)))
    n_blocks = int(math.ceil(n / block))
    max_start = n - block
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, max_start + 1, size=(n_boot, n_blocks))
    offsets = np.arange(block)
    idx = (starts[..., None] + offsets).reshape(n_boot, -1)[:, :n]
    sampled = x[idx]
    means = sampled.mean(axis=1)
    stds = sampled.std(axis=1)
    sharpes = np.divide(means, stds, out=np.zeros_like(means), where=stds > 0) * math.sqrt(periods_per_year)
    lo, hi = np.quantile(sharpes, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lo), float(hi)


def benjamini_hochberg(p_values: list[float | None]) -> list[float | None]:
    """Benjamini-Hochberg FDR adjusted q-values, preserving input order."""
    valid = [(i, float(p)) for i, p in enumerate(p_values) if p is not None and np.isfinite(p)]
    out: list[float | None] = [None] * len(p_values)
    if not valid:
        return out

    ordered = sorted(valid, key=lambda z: z[1])
    m = len(ordered)
    adjusted = [0.0] * m
    running = 1.0
    for rank_rev in range(m - 1, -1, -1):
        rank = rank_rev + 1
        p = ordered[rank_rev][1]
        q = min(running, p * m / rank)
        running = q
        adjusted[rank_rev] = min(1.0, q)
    for (item, _), q in zip(ordered, adjusted):
        out[item] = float(q)
    return out


def white_reality_check(
    returns_matrix: pd.DataFrame,
    *,
    block_size: int = 7,
    n_boot: int = 500,
    seed: int = 2718,
) -> dict:
    """Simplified White reality check across a fixed strategy search space.

    ``returns_matrix`` contains aligned strategy returns, one specification per
    column. The test compares the best observed mean return with the bootstrap
    distribution of the best *centered* strategy mean. A common moving-block
    resample is used across columns so serial and cross-strategy dependence are
    retained.

    This is a search-space diagnostic, not a proof that an adaptive selector is
    profitable. It is intentionally reported separately from the per-signal HAC
    and FDR diagnostics.
    """
    frame = pd.DataFrame(returns_matrix).replace([np.inf, -np.inf], np.nan).dropna(how="all")
    if frame.empty or frame.shape[1] == 0:
        return {
            "p_value": None,
            "best_specification": None,
            "best_mean_return": None,
            "trials": int(frame.shape[1]),
            "block_size": int(block_size),
            "bootstrap_samples": int(n_boot),
        }

    x = frame.fillna(0.0).to_numpy(dtype=float)
    n, m = x.shape
    if n < max(30, block_size * 2):
        return {
            "p_value": None,
            "best_specification": str(frame.columns[0]) if m else None,
            "best_mean_return": float(np.max(x.mean(axis=0))) if m else None,
            "trials": int(m),
            "block_size": int(block_size),
            "bootstrap_samples": int(n_boot),
        }

    means = x.mean(axis=0)
    best_idx = int(np.argmax(means))
    observed = float(means[best_idx])
    if observed <= 0:
        p_value = 1.0
    else:
        centered = x - means
        block = int(max(1, min(block_size, n)))
        n_blocks = int(math.ceil(n / block))
        max_start = n - block
        rng = np.random.default_rng(seed)
        starts = rng.integers(0, max_start + 1, size=(n_boot, n_blocks))
        offsets = np.arange(block)
        idx = (starts[..., None] + offsets).reshape(n_boot, -1)[:, :n]
        # n_boot x n x m; small for the 20-specification baseline search.
        boot_means = centered[idx].mean(axis=1)
        boot_max = boot_means.max(axis=1)
        p_value = float((1 + np.sum(boot_max >= observed)) / (n_boot + 1))

    return {
        "p_value": float(p_value),
        "best_specification": str(frame.columns[best_idx]),
        "best_mean_return": observed,
        "trials": int(m),
        "block_size": int(block_size),
        "bootstrap_samples": int(n_boot),
    }
