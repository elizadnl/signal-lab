from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

from .backtest import run_backtest
from .data import load_symbol, load_market_csv
from .data_audit import audit_market_file
from .regimes import classify_volatility_regime
from .stats import (
    strategy_metrics,
    hac_mean_test,
    block_bootstrap_sharpe_ci,
    benjamini_hochberg,
    white_reality_check,
)
from .signals import build_signal
from .walk_forward import WalkForwardConfig, select_lookback, walk_forward_signal


def _safe_float(x):
    if x is None:
        return None
    if isinstance(x, (float, np.floating)) and not np.isfinite(x):
        return None
    return float(x)


def _series_points(dates: pd.Series, values: pd.Series, decimals: int = 6, step: int = 3) -> list[dict]:
    out = []
    dates = dates.iloc[::step]
    values = values.iloc[::step]
    for d, v in zip(dates, values):
        if pd.isna(v):
            continue
        out.append({"date": str(pd.Timestamp(d).date()), "value": round(float(v), decimals)})
    return out


def _rolling_reliability(strategy_return: pd.Series, window: int = 60) -> pd.Series:
    mean = strategy_return.rolling(window).mean()
    std = strategy_return.rolling(window).std(ddof=0).replace(0, np.nan)
    return (mean / std * np.sqrt(365)).replace([np.inf, -np.inf], np.nan)


def _trade_blocks(strategy_return: pd.Series, held_positions: pd.Series, dates: pd.Series, limit: int = 220) -> list[dict]:
    mask = held_positions != 0
    rows = []
    for d, r, p in zip(dates[mask], strategy_return[mask], held_positions[mask]):
        rows.append({
            "date": str(pd.Timestamp(d).date()),
            "return": round(float(r), 6),
            "direction": "long" if p > 0 else "short",
            "outcome": "win" if r > 0 else ("loss" if r < 0 else "flat"),
        })
    return rows[-limit:]






def _execution_delay_stress(
    df: pd.DataFrame,
    signal: pd.Series,
    eval_start: int,
    fee_bps: float,
    holding_period: int,
    delays: tuple[int, ...] = (1, 2, 3, 5),
) -> list[dict]:
    """Re-run a fixed signal path with progressively slower execution.

    Delay=1 is the baseline convention: a signal observed at close t is held
    over the return from t to t+1. Delay d>1 shifts the same signal path by an
    additional d-1 bars, so this isolates implementation fragility without
    re-optimising the model.
    """
    rows: list[dict] = []
    for delay in delays:
        shifted = signal.shift(max(0, int(delay) - 1)).fillna(0.0)
        bt = run_backtest(df, shifted, fee_bps=fee_bps, holding_period=holding_period)
        rr = bt["strategy_return"].iloc[eval_start:].reset_index(drop=True)
        pp = bt["positions"].iloc[eval_start:].reset_index(drop=True)
        hh = bt["held_positions"].iloc[eval_start:].reset_index(drop=True)
        tt = bt["turnover_series"].iloc[eval_start:].reset_index(drop=True)
        sm = strategy_metrics(rr, pp, held_positions=hh, turnover_series=tt)
        rows.append({
            "delay_days": int(delay),
            "total_return": float(sm["total_return"]),
            "sharpe": float(sm["sharpe"]),
        })
    return rows


def _parameter_sensitivity(
    df: pd.DataFrame,
    signal_name: str,
    eval_start: int,
    fee_bps: float,
    holding_period: int,
    lookbacks: tuple[int, ...] = (5, 10, 20, 40, 60),
) -> dict:
    """Ex-post sensitivity map across the pre-declared lookback grid.

    This is not used for inference or model selection. It asks whether the
    apparent edge lives on a broad parameter plateau or a single sharp choice.
    """
    rows: list[dict] = []
    sharpes: list[float] = []
    signs: list[bool] = []
    for lb in lookbacks:
        sig = build_signal(df, signal_name, int(lb))
        sig.iloc[:eval_start] = 0.0
        bt = run_backtest(df, sig, fee_bps=fee_bps, holding_period=holding_period)
        rr = bt["strategy_return"].iloc[eval_start:].reset_index(drop=True)
        pp = bt["positions"].iloc[eval_start:].reset_index(drop=True)
        hh = bt["held_positions"].iloc[eval_start:].reset_index(drop=True)
        tt = bt["turnover_series"].iloc[eval_start:].reset_index(drop=True)
        sm = strategy_metrics(rr, pp, held_positions=hh, turnover_series=tt)
        sh = float(sm["sharpe"])
        tr = float(sm["total_return"])
        sharpes.append(sh)
        signs.append(tr > 0)
        rows.append({"lookback": int(lb), "total_return": tr, "sharpe": sh})

    positive_share = float(np.mean(signs)) if signs else 0.0
    best = max(sharpes) if sharpes else 0.0
    if best <= 0:
        plateau = 0.0
    else:
        # Share of declared parameters retaining at least half of the best Sharpe.
        plateau = float(np.mean([sh >= 0.5 * best for sh in sharpes]))
    return {
        "rows": rows,
        "positive_parameter_share": positive_share,
        "plateau_score": plateau,
    }


def _return_concentration(
    strategy_return: pd.Series,
    held_positions: pd.Series,
    n_best: int = 10,
) -> dict:
    """Measure how dependent the result is on a handful of active sessions."""
    r = strategy_return.astype(float).reset_index(drop=True)
    held = held_positions.astype(float).reset_index(drop=True)
    active = r[held != 0]
    if active.empty:
        return {
            "active_sessions": 0,
            "top_profit_share": None,
            "top_loss_share": None,
            "return_without_best_sessions": 0.0,
            "removed_sessions": 0,
        }

    positives = active[active > 0].sort_values(ascending=False)
    negatives = active[active < 0].sort_values()
    k = int(min(n_best, len(active)))
    best_idx = active.nlargest(k).index
    stripped = r.copy()
    stripped.loc[best_idx] = 0.0

    gross_profit = float(positives.sum())
    gross_loss = float(-negatives.sum())
    top_profit_share = float(positives.head(n_best).sum() / gross_profit) if gross_profit > 0 else None
    top_loss_share = float((-negatives.head(n_best).sum()) / gross_loss) if gross_loss > 0 else None
    stripped_return = float((1.0 + stripped).prod() - 1.0)
    return {
        "active_sessions": int(len(active)),
        "top_profit_share": top_profit_share,
        "top_loss_share": top_loss_share,
        "return_without_best_sessions": stripped_return,
        "removed_sessions": k,
    }


def _yearly_performance(
    dates: pd.Series,
    strategy_return: pd.Series,
    positions: pd.Series,
    held_positions: pd.Series,
    turnover_series: pd.Series,
) -> list[dict]:
    years = pd.to_datetime(dates, utc=True).dt.year
    rows: list[dict] = []
    for year in sorted(years.dropna().unique()):
        m = years == year
        rr = strategy_return[m].reset_index(drop=True)
        pp = positions[m].reset_index(drop=True)
        hh = held_positions[m].reset_index(drop=True)
        tt = turnover_series[m].reset_index(drop=True)
        if len(rr) == 0:
            continue
        sm = strategy_metrics(rr, pp, held_positions=hh, turnover_series=tt)
        active = rr[hh != 0]
        rows.append({
            "year": int(year),
            "return": float(sm["total_return"]),
            "sharpe": float(sm["sharpe"]),
            "max_drawdown": float(sm["max_drawdown"]),
            "hit_rate": float((active > 0).mean()) if len(active) else 0.0,
            "active_sessions": int((hh != 0).sum()),
        })
    return rows


def _break_even_cost_bps(
    df: pd.DataFrame,
    signal: pd.Series,
    eval_start: int,
    holding_period: int,
    max_bps: float = 100.0,
) -> float | None:
    """Approximate the one-way fee at which compounded OOS return reaches zero."""
    def total(cost: float) -> float:
        bt = run_backtest(df, signal, fee_bps=cost, holding_period=holding_period)
        r = bt["strategy_return"].iloc[eval_start:]
        return float((1.0 + r).prod() - 1.0)

    if total(0.0) <= 0:
        return 0.0
    if total(max_bps) > 0:
        return None
    lo, hi = 0.0, float(max_bps)
    for _ in range(30):
        mid = (lo + hi) / 2.0
        if total(mid) > 0:
            lo = mid
        else:
            hi = mid
    return float((lo + hi) / 2.0)


def _deployment_gate(run: dict) -> dict:
    if run["mode"] != "walk_forward":
        return {"status": "not_applicable", "passed": 0, "total": 0, "criteria": []}

    q = run["robustness"].get("fdr_q")
    ci_low = run["robustness"].get("sharpe_ci_low")
    stability = run["parameter_stability"].get("stability_score")
    stress25 = next((x for x in run["cost_stress"] if float(x["fee_bps"]) == 25.0), None)
    yearly = run.get("yearly_performance", [])
    reality_p = run.get("selection_bias", {}).get("reality_check_p")
    cross = run.get("cross_asset", {})
    holdout = cross.get("holdout", {}) if isinstance(cross, dict) else {}
    cross_pass = bool(cross.get("replication_pass")) and bool(holdout.get("available")) and bool(holdout.get("positive"))
    positive_year_share = (
        sum(1 for x in yearly if x["return"] > 0) / len(yearly) if yearly else 0.0
    )

    criteria = [
        {"name": "positive_oos_return", "label": "Positive OOS return", "pass": run["metrics"]["total_return"] > 0},
        {"name": "sharpe", "label": "Sharpe > 0.5", "pass": run["metrics"]["sharpe"] > 0.5},
        {"name": "fdr", "label": "FDR q < 0.10", "pass": q is not None and q < 0.10},
        {"name": "bootstrap", "label": "Sharpe CI lower bound > 0", "pass": ci_low is not None and ci_low > 0},
        {"name": "cost_stress", "label": "Positive at 25 bps", "pass": stress25 is not None and stress25["total_return"] > 0},
        {"name": "stability", "label": "Parameter stability ≥ 50%", "pass": stability is not None and stability >= 0.50},
        {"name": "year_consistency", "label": "Positive in ≥ 50% of years", "pass": positive_year_share >= 0.50},
        {"name": "reality_check", "label": "Reality-check p < 0.10", "pass": reality_p is not None and reality_p < 0.10},
        {"name": "cross_asset", "label": "Cross-asset validation clears", "pass": cross_pass},
    ]
    passed = int(sum(bool(c["pass"]) for c in criteria))
    total = len(criteria)
    if passed == total:
        status = "pass"
    elif passed >= 7 and run["metrics"]["total_return"] > 0 and run["metrics"]["sharpe"] > 0:
        status = "watch"
    else:
        status = "fail"
    return {
        "status": status,
        "passed": passed,
        "total": total,
        "positive_year_share": float(positive_year_share),
        "criteria": criteria,
    }

def _signal_state(rolling: pd.Series) -> dict:
    clean = rolling.dropna()
    if len(clean) == 0:
        return {"label": "insufficient history", "score": None, "change_30d": None}
    current = float(clean.iloc[-1])
    prior = float(clean.iloc[-31]) if len(clean) > 30 else float(clean.iloc[0])
    change = current - prior
    if current >= 1.0:
        label = "strong"
    elif current > 0.0:
        label = "weak"
    elif change < -0.35:
        label = "decaying"
    else:
        label = "broken"
    return {"label": label, "score": current, "change_30d": change}


def _edge_decay(df: pd.DataFrame, signal: pd.Series, eval_start: int, horizons: tuple[int, ...] = (1, 3, 7, 14, 30)) -> list[dict]:
    rows = []
    close = df["close"].astype(float)
    active_base = signal != 0
    idx_ok = pd.Series(False, index=df.index)
    idx_ok.iloc[eval_start:] = True
    for h in horizons:
        fwd = close.shift(-h) / close - 1.0
        signed = signal * fwd
        m = active_base & idx_ok & fwd.notna()
        vals = signed[m]
        rows.append({
            "horizon": int(h),
            "mean_edge_bps": _safe_float(vals.mean() * 10_000 if len(vals) else 0.0),
            "hit_rate": _safe_float((vals > 0).mean() if len(vals) else 0.0),
            "observations": int(len(vals)),
        })
    return rows


def _parameter_stability(folds: list[dict]) -> dict:
    lbs = [int(f["lookback"]) for f in folds]
    if not lbs:
        return {"dominant_lookback": None, "unique_lookbacks": 0, "switches": 0, "stability_score": None}
    values, counts = np.unique(lbs, return_counts=True)
    dominant = int(values[int(np.argmax(counts))])
    switches = int(sum(a != b for a, b in zip(lbs, lbs[1:])))
    stability = 1.0 if len(lbs) <= 1 else 1.0 - switches / (len(lbs) - 1)
    return {
        "dominant_lookback": dominant,
        "unique_lookbacks": int(len(values)),
        "switches": switches,
        "stability_score": float(stability),
    }


def _evidence_grade(mode: str, total_return: float, sharpe: float, ci_low: float | None, q_value: float | None) -> str:
    if mode != "walk_forward":
        return "in-sample only"
    if total_return <= 0 or sharpe <= 0:
        return "no evidence"
    if q_value is not None and q_value < 0.05 and ci_low is not None and ci_low > 0 and sharpe > 1.0:
        return "strong"
    if q_value is not None and q_value < 0.10 and sharpe > 0.5:
        return "promising"
    return "weak"


def analyze_symbol(
    data_dir: str | Path,
    symbol: str,
    signal_name: str,
    fee_bps: float = 10.0,
    holding_period: int = 1,
    mode: str = "walk_forward",
) -> dict:
    df = load_symbol(data_dir, symbol)
    regime = classify_volatility_regime(df)
    cfg = WalkForwardConfig(fee_bps=fee_bps, holding_period=holding_period)
    eval_start = min(cfg.train_days, len(df) - 1)

    if mode == "walk_forward":
        signal, folds = walk_forward_signal(df, signal_name, cfg)
        selected_lookback = None
    elif mode == "in_sample":
        # Deliberately optimistic comparator: select on the full sample, but
        # evaluate on the same post-warmup dates as the walk-forward strategy.
        selected_lookback, _ = select_lookback(
            df, signal_name, cfg.candidate_lookbacks, fee_bps, holding_period
        )
        signal = build_signal(df, signal_name, selected_lookback)
        signal.iloc[:eval_start] = 0.0
        folds = []
    else:
        raise ValueError(f"Unknown mode: {mode}")

    bt = run_backtest(df, signal, fee_bps=fee_bps, holding_period=holding_period)
    eval_dates = df["date"].iloc[eval_start:].reset_index(drop=True)
    eval_ret = bt["strategy_return"].iloc[eval_start:].reset_index(drop=True)
    eval_pos = bt["positions"].iloc[eval_start:].reset_index(drop=True)
    eval_held = bt["held_positions"].iloc[eval_start:].reset_index(drop=True)
    eval_turn = bt["turnover_series"].iloc[eval_start:].reset_index(drop=True)

    metrics_raw = strategy_metrics(
        eval_ret,
        eval_pos,
        held_positions=eval_held,
        turnover_series=eval_turn,
    )
    eval_equity = (1.0 + eval_ret).cumprod()
    eval_drawdown = eval_equity / eval_equity.cummax() - 1.0
    rolling = _rolling_reliability(eval_ret)

    regime_for_return = regime.shift(1).iloc[eval_start:].reset_index(drop=True)
    regime_rows = []
    for name in ["low", "normal", "high"]:
        m = regime_for_return == name
        rr = eval_ret[m]
        pp = eval_pos[m]
        hh = eval_held[m]
        tt = eval_turn[m]
        sub = strategy_metrics(rr, pp, held_positions=hh, turnover_series=tt) if m.any() else None
        active_r = eval_ret[m & (eval_held != 0)]
        regime_rows.append({
            "regime": name,
            "return": _safe_float((1 + rr).prod() - 1 if len(rr) else 0),
            "sharpe": _safe_float(sub["sharpe"] if sub else 0),
            "hit_rate": _safe_float((active_r > 0).mean() if len(active_r) else 0),
            "observations": int(m.sum()),
        })

    hac = hac_mean_test(eval_ret, max_lag=7)
    ci_low, ci_high = block_bootstrap_sharpe_ci(eval_ret, block_size=7, n_boot=350)
    benchmark_return = float(df["close"].iloc[-1] / df["close"].iloc[eval_start] - 1.0)

    cost_stress = []
    for cost in (0.0, 5.0, 10.0, 25.0):
        stressed = run_backtest(df, signal, fee_bps=cost, holding_period=holding_period)
        rr = stressed["strategy_return"].iloc[eval_start:].reset_index(drop=True)
        pp = stressed["positions"].iloc[eval_start:].reset_index(drop=True)
        hh = stressed["held_positions"].iloc[eval_start:].reset_index(drop=True)
        tt = stressed["turnover_series"].iloc[eval_start:].reset_index(drop=True)
        sm = strategy_metrics(rr, pp, held_positions=hh, turnover_series=tt)
        cost_stress.append({"fee_bps": cost, "total_return": float(sm["total_return"]), "sharpe": float(sm["sharpe"])})

    metrics = {
        k: _safe_float(v) if isinstance(v, (float, np.floating)) or v is None else int(v)
        for k, v in metrics_raw.items()
    }
    robustness = {
        "evaluation_start": str(pd.Timestamp(df["date"].iloc[eval_start]).date()),
        "hac_t_stat": _safe_float(hac["t_stat"]),
        "p_value": _safe_float(hac["p_value"]),
        "fdr_q": None,
        "sharpe_ci_low": _safe_float(ci_low),
        "sharpe_ci_high": _safe_float(ci_high),
        "benchmark_return": benchmark_return,
        "excess_vs_benchmark": float(metrics_raw["total_return"] - benchmark_return),
        "evidence_grade": "pending fdr",
    }

    return {
        "symbol": symbol.upper(),
        "signal": signal_name,
        "mode": mode,
        "fee_bps": fee_bps,
        "holding_period": holding_period,
        "selected_lookback": selected_lookback,
        "start_date": str(eval_dates.iloc[0].date()),
        "end_date": str(eval_dates.iloc[-1].date()),
        "metrics": metrics,
        "robustness": robustness,
        "parameter_stability": _parameter_stability(folds),
        "signal_state": _signal_state(rolling),
        "equity": _series_points(eval_dates, eval_equity),
        "drawdown": _series_points(eval_dates, eval_drawdown),
        "rolling_reliability": _series_points(eval_dates, rolling),
        "regime_performance": regime_rows,
        "edge_decay": _edge_decay(df, signal, eval_start),
        "cost_stress": cost_stress,
        "execution_delay_stress": _execution_delay_stress(df, signal, eval_start, fee_bps, holding_period),
        "parameter_sensitivity": _parameter_sensitivity(df, signal_name, eval_start, fee_bps, holding_period, cfg.candidate_lookbacks),
        "return_concentration": _return_concentration(eval_ret, eval_held),
        "selection_bias": {"reality_check_p": None, "best_specification": None, "best_mean_return": None, "trials": 0},
        "cross_asset": {"asset_rows": [], "positive_share": 0.0, "median_sharpe": None, "replication_pass": False, "holdout": {"available": False, "reason": "pending"}},
        "break_even_fee_bps": _safe_float(_break_even_cost_bps(df, signal, eval_start, holding_period)),
        "yearly_performance": _yearly_performance(eval_dates, eval_ret, eval_pos, eval_held, eval_turn),
        "deployment_gate": {"status": "pending", "passed": 0, "total": 0, "criteria": []},
        "trades": _trade_blocks(eval_ret, eval_held, eval_dates),
        "folds": folds,
    }


def _load_data_metadata(data_dir: Path) -> dict:
    path = data_dir / "DATA_SOURCE.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "kind": "unknown",
        "label": "Local OHLCV files",
        "claim_status": "Source metadata unavailable",
    }


def _apply_fdr_and_grades(runs: list[dict]) -> None:
    groups: dict[tuple[str, str, float], list[dict]] = {}
    for r in runs:
        key = (r["symbol"], r["mode"], float(r["fee_bps"]))
        groups.setdefault(key, []).append(r)
    for group in groups.values():
        qvals = benjamini_hochberg([r["robustness"]["p_value"] for r in group])
        for r, q in zip(group, qvals):
            r["robustness"]["fdr_q"] = q
            r["robustness"]["evidence_grade"] = _evidence_grade(
                r["mode"],
                float(r["metrics"]["total_return"]),
                float(r["metrics"]["sharpe"]),
                r["robustness"]["sharpe_ci_low"],
                q,
            )




def _search_space_reality_check(
    data_dir: Path,
    symbol: str,
    fee_bps: float,
    signals: tuple[str, ...],
    lookbacks: tuple[int, ...] = (5, 10, 20, 40, 60),
) -> dict:
    """Reality-check the declared fixed-rule search space for one asset."""
    df = load_symbol(data_dir, symbol)
    eval_start = min(365, len(df) - 1)
    matrix: dict[str, pd.Series] = {}
    for signal_name in signals:
        for lb in lookbacks:
            sig = build_signal(df, signal_name, int(lb))
            sig.iloc[:eval_start] = 0.0
            bt = run_backtest(df, sig, fee_bps=fee_bps, holding_period=1)
            matrix[f"{signal_name}:{int(lb)}d"] = bt["strategy_return"].iloc[eval_start:].reset_index(drop=True)
    result = white_reality_check(pd.DataFrame(matrix), block_size=7, n_boot=500)
    return {
        "reality_check_p": result["p_value"],
        "best_specification": result["best_specification"],
        "best_mean_return": result["best_mean_return"],
        "trials": result["trials"],
        "block_size": result["block_size"],
        "bootstrap_samples": result["bootstrap_samples"],
        "scope": "20 pre-declared fixed signal/lookback specifications; diagnostic does not test the adaptive walk-forward selector itself",
    }


def _apply_selection_bias(
    runs: list[dict],
    data_dir: Path,
    symbols: tuple[str, ...],
    signals: tuple[str, ...],
) -> None:
    for symbol in symbols:
        for fee_bps in sorted({float(r["fee_bps"]) for r in runs if r["symbol"] == symbol.upper()}):
            diag = _search_space_reality_check(data_dir, symbol, fee_bps, signals)
            for r in runs:
                if r["symbol"] == symbol.upper() and float(r["fee_bps"]) == fee_bps:
                    r["selection_bias"] = dict(diag)



def _asset_holdout_transfer(
    data_dir: Path,
    target_symbol: str,
    donor_symbols: tuple[str, ...],
    signal_name: str,
    fee_bps: float,
    lookbacks: tuple[int, ...] = (5, 10, 20, 40, 60),
    train_days: int = 365,
) -> dict:
    """Choose a lookback on *other assets* and test it on the held-out asset.

    All assets share the same calendar training cut-off. The target asset's
    returns are never used to choose the lookback. This is a transportability
    diagnostic, not part of the main walk-forward selector.
    """
    symbols = (target_symbol,) + tuple(donor_symbols)
    frames = {s: load_symbol(data_dir, s).copy() for s in symbols}
    for frame in frames.values():
        frame["date"] = pd.to_datetime(frame["date"], utc=True)

    common_start = max(frame["date"].min() for frame in frames.values())
    common_end = min(frame["date"].max() for frame in frames.values())
    if pd.isna(common_start) or pd.isna(common_end):
        return {"available": False, "reason": "missing common history"}

    # Use observed daily rows from the common start to define a point-in-time
    # calendar cut-off. Crypto data are daily, but this also tolerates gaps.
    target_common = frames[target_symbol][frames[target_symbol]["date"] >= common_start]
    if len(target_common) <= train_days + 30:
        return {"available": False, "reason": "insufficient common history"}
    train_end = pd.Timestamp(target_common.iloc[train_days - 1]["date"])
    if train_end >= common_end:
        return {"available": False, "reason": "no held-out evaluation period"}

    donor_scores: dict[int, list[float]] = {int(lb): [] for lb in lookbacks}
    for donor in donor_symbols:
        d = frames[donor]
        train = d[(d["date"] >= common_start) & (d["date"] <= train_end)].reset_index(drop=True)
        if len(train) < max(90, max(lookbacks) * 2):
            continue
        for lb in lookbacks:
            sig = build_signal(train, signal_name, int(lb))
            bt = run_backtest(train, sig, fee_bps=fee_bps, holding_period=1)
            score = float(bt["metrics"]["sharpe"])
            if np.isfinite(score):
                donor_scores[int(lb)].append(score)

    scored = [
        (float(np.mean(scores)), lb)
        for lb, scores in donor_scores.items()
        if scores
    ]
    if not scored:
        return {"available": False, "reason": "donor training failed"}
    best_score, chosen = max(scored, key=lambda x: (x[0], -x[1]))

    target = frames[target_symbol].copy().reset_index(drop=True)
    signal = build_signal(target, signal_name, int(chosen))
    signal[target["date"] <= train_end] = 0.0
    bt = run_backtest(target, signal, fee_bps=fee_bps, holding_period=1)
    mask = (target["date"] > train_end) & (target["date"] <= common_end)
    rr = bt["strategy_return"][mask].reset_index(drop=True)
    pp = bt["positions"][mask].reset_index(drop=True)
    hh = bt["held_positions"][mask].reset_index(drop=True)
    tt = bt["turnover_series"][mask].reset_index(drop=True)
    if len(rr) < 30:
        return {"available": False, "reason": "held-out sample too short"}
    sm = strategy_metrics(rr, pp, held_positions=hh, turnover_series=tt)
    return {
        "available": True,
        "target": target_symbol.upper(),
        "donors": [s.upper() for s in donor_symbols],
        "chosen_lookback": int(chosen),
        "donor_mean_train_sharpe": float(best_score),
        "train_start": str(pd.Timestamp(common_start).date()),
        "train_end": str(pd.Timestamp(train_end).date()),
        "test_start": str(pd.Timestamp(target.loc[mask, "date"].iloc[0]).date()),
        "test_end": str(pd.Timestamp(target.loc[mask, "date"].iloc[-1]).date()),
        "observations": int(mask.sum()),
        "total_return": float(sm["total_return"]),
        "sharpe": float(sm["sharpe"]),
        "max_drawdown": float(sm["max_drawdown"]),
        "positive": bool(sm["total_return"] > 0),
        "scope": "lookback chosen on donor assets only; signal family pre-declared; target evaluated after the common training cut-off",
    }


def _apply_cross_asset_validation(
    runs: list[dict],
    data_dir: Path,
    symbols: tuple[str, ...],
    signals: tuple[str, ...],
) -> None:
    """Attach replication breadth and an asset-held-out transfer test."""
    symbols_u = tuple(s.upper() for s in symbols)
    for signal_name in signals:
        for fee_bps in sorted({float(r["fee_bps"]) for r in runs}):
            wf = [
                r for r in runs
                if r["mode"] == "walk_forward"
                and r["signal"] == signal_name
                and float(r["fee_bps"]) == fee_bps
                and r["symbol"] in symbols_u
            ]
            asset_rows = [
                {
                    "symbol": r["symbol"],
                    "total_return": float(r["metrics"]["total_return"]),
                    "sharpe": float(r["metrics"]["sharpe"]),
                    "fdr_q": r["robustness"].get("fdr_q"),
                    "positive": bool(r["metrics"]["total_return"] > 0),
                }
                for r in sorted(wf, key=lambda x: x["symbol"])
            ]
            positive_share = (
                float(np.mean([row["positive"] for row in asset_rows])) if asset_rows else 0.0
            )
            median_sharpe = (
                float(np.median([row["sharpe"] for row in asset_rows])) if asset_rows else None
            )

            holdouts: dict[str, dict] = {}
            for target in symbols_u:
                donors = tuple(s for s in symbols_u if s != target)
                holdouts[target] = _asset_holdout_transfer(
                    data_dir, target, donors, signal_name, fee_bps
                )

            for r in runs:
                if r["signal"] != signal_name or float(r["fee_bps"]) != fee_bps:
                    continue
                r["cross_asset"] = {
                    "asset_rows": asset_rows,
                    "positive_share": positive_share,
                    "median_sharpe": median_sharpe,
                    "replication_pass": bool(len(asset_rows) >= 2 and positive_share >= (2 / 3 if len(asset_rows) >= 3 else 0.5)),
                    "holdout": holdouts.get(r["symbol"], {"available": False, "reason": "target unavailable"}),
                }

def _finalize_gates(runs: list[dict]) -> None:
    for r in runs:
        r["deployment_gate"] = _deployment_gate(r)

def build_dashboard_payload(
    data_dir: str | Path,
    output: str | Path,
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
    signals: tuple[str, ...] = ("momentum", "mean_reversion", "abnormal_volume", "volatility_breakout"),
) -> dict:
    data_dir = Path(data_dir)
    runs = []
    for symbol in symbols:
        for signal in signals:
            for mode in ("walk_forward", "in_sample"):
                for fee_bps in (0.0, 10.0):
                    runs.append(analyze_symbol(data_dir, symbol, signal, fee_bps=fee_bps, mode=mode))
    _apply_fdr_and_grades(runs)
    _apply_selection_bias(runs, data_dir, symbols, signals)
    _apply_cross_asset_validation(runs, data_dir, symbols, signals)
    _finalize_gates(runs)
    audits = {}
    for symbol in symbols:
        path = data_dir / f"{symbol.upper()}.csv"
        if path.exists():
            audits[symbol.upper()] = audit_market_file(path, load_market_csv)

    payload = {
        "generated_for": "SignalLab dashboard",
        "version": "0.8.0",
        "methodology": "rolling walk-forward selection; next-bar execution; turnover costs; HAC/FDR; block-bootstrap Sharpe uncertainty; search-space reality check; delay/parameter/concentration stress; cross-asset replication and asset-held-out transfer; deployment gate",
        "data_source": _load_data_metadata(data_dir),
        "data_audit": audits,
        "runs": runs,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
