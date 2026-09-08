from __future__ import annotations

"""Render a self-contained portfolio preview from a SignalLab payload.

This is intentionally static: it lets the README carry a faithful screenshot
without requiring the React development server during CI or artifact builds.
"""

import argparse
import html
import json
from pathlib import Path


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:+.{digits}f}%"


def num(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}f}"


def esc(s: object) -> str:
    return html.escape(str(s))


def svg_path(points: list[dict], width: int = 720, height: int = 255, pad: int = 10) -> str:
    vals = [float(p["value"]) for p in points]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    span = max(hi - lo, 1e-12)
    n = max(len(vals) - 1, 1)
    coords = []
    for i, v in enumerate(vals):
        x = pad + (width - 2 * pad) * i / n
        y = pad + (height - 2 * pad) * (hi - v) / span
        coords.append((x, y))
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in coords)


def bars(rows: list[dict], value_key: str, label_key: str, suffix: str = "%", scalar: float = 100.0) -> str:
    if not rows:
        return ""
    absmax = max(abs(float(r[value_key])) for r in rows) or 1.0
    parts = []
    for r in rows:
        v = float(r[value_key])
        cls = "pos" if v >= 0 else "neg"
        vclass = "green" if v >= 0 else "red"
        width = max(3.0, abs(v) / absmax * 100)
        display = f"{v * scalar:+.1f}{suffix}"
        parts.append(
            f'<div class="barrow"><span>{esc(r[label_key])}</span>'
            f'<div class="bar"><i class="{cls}" style="width:{width:.1f}%"></i></div>'
            f'<b class="{vclass}">{display}</b></div>'
        )
    return "".join(parts)


def render(payload: dict, symbol: str, signal: str, mode: str, fee_bps: float) -> str:
    runs = payload["runs"]
    run = next(
        r for r in runs
        if r["symbol"] == symbol and r["signal"] == signal and r["mode"] == mode and float(r["fee_bps"]) == fee_bps
    )
    counterpart = next(
        (r for r in runs if r["symbol"] == symbol and r["signal"] == signal and r["mode"] == "in_sample" and float(r["fee_bps"]) == fee_bps),
        None,
    )
    m = run["metrics"]
    rob = run["robustness"]
    gate = run["deployment_gate"]
    audit = payload.get("data_audit", {}).get(symbol, {})
    eq = run["equity"]
    dd = run["drawdown"]
    rel = run["rolling_reliability"]
    wf_is_gap = (counterpart["metrics"]["sharpe"] - m["sharpe"]) if counterpart else 0.0

    # Keep leaderboard comparison apples-to-apples: same symbol/mode/fee.
    leaderboard = sorted(
        [r for r in runs if r["symbol"] == symbol and r["mode"] == mode and float(r["fee_bps"]) == fee_bps],
        key=lambda r: r["metrics"]["sharpe"], reverse=True,
    )
    lead_rows = "".join(
        f'<tr class="{"active" if r["signal"] == signal else ""}">'
        f'<td>{i+1}</td><td>{esc(r["signal"].replace("_", " ").title())}</td>'
        f'<td class="{"green" if r["metrics"]["total_return"] >= 0 else "red"}">{pct(r["metrics"]["total_return"])}</td>'
        f'<td>{r["metrics"]["sharpe"]:.2f}</td><td>{r["robustness"].get("fdr_q", 1):.3f}</td>'
        f'<td><span class="gate-pill {r["deployment_gate"]["status"]}">{r["deployment_gate"]["status"].upper()} {r["deployment_gate"]["passed"]}/{r["deployment_gate"]["total"]}</span></td></tr>'
        for i, r in enumerate(leaderboard)
    )

    criteria = "".join(
        f'<div class="criterion {"pass" if c["pass"] else "fail"}"><span>{"✓" if c["pass"] else "×"}</span>{esc(c["label"])}</div>'
        for c in gate["criteria"]
    )

    yearly = "".join(
        f'<div class="year-card"><span>{y["year"]}</span><b class="{"green" if y["return"] >= 0 else "red"}">{pct(y["return"])}</b>'
        f'<small>Sharpe {y["sharpe"]:.2f} · DD {pct(y["max_drawdown"])}</small></div>'
        for y in run["yearly_performance"]
    )

    folds = run.get("folds", [])
    fold_chips = "".join(
        f'<span class="fold" title="{esc(f["test_start"])} → {esc(f["test_end"])}">{int(f["lookback"])}d</span>' for f in folds
    )

    cost_rows = "".join(
        f'<div class="cost"><span>{c["fee_bps"]:.0f} bps</span><div class="cost-line"><i style="width:{min(100,max(4,abs(c["total_return"])*20)):.1f}%" class="{"pos" if c["total_return"] >= 0 else "neg"}"></i></div>'
        f'<b class="{"green" if c["total_return"] >= 0 else "red"}">{pct(c["total_return"])}</b><small>S {c["sharpe"]:.2f}</small></div>'
        for c in run["cost_stress"]
    )

    delay_rows = "".join(
        f'<div class="cost"><span>t+{d["delay_days"]}</span><div class="cost-line"><i style="width:{min(100,max(4,abs(d["total_return"])*20)):.1f}%" class="{"pos" if d["total_return"] >= 0 else "neg"}"></i></div>'
        f'<b class="{"green" if d["total_return"] >= 0 else "red"}">{pct(d["total_return"])}</b><small>S {d["sharpe"]:.2f}</small></div>'
        for d in run.get("execution_delay_stress", [])
    )

    param_rows_raw = run.get("parameter_sensitivity", {}).get("rows", [])
    param_abs = max([abs(x["sharpe"]) for x in param_rows_raw] or [1.0]) or 1.0
    parameter_rows = "".join(
        f'<div class="cost"><span>{x["lookback"]}d</span><div class="cost-line"><i style="width:{max(4,abs(x["sharpe"])/param_abs*100):.1f}%" class="{"pos" if x["sharpe"] >= 0 else "neg"}"></i></div>'
        f'<b class="{"green" if x["sharpe"] >= 0 else "red"}">S {x["sharpe"]:.2f}</b><small>{pct(x["total_return"])}</small></div>'
        for x in param_rows_raw
    )

    decay_max = max(abs(d["mean_edge_bps"]) for d in run["edge_decay"]) or 1
    decay_rows = "".join(
        f'<div class="cost"><span>{d["horizon"]}d</span><div class="cost-line"><i style="width:{max(4,abs(d["mean_edge_bps"])/decay_max*100):.1f}%" class="{"pos" if d["mean_edge_bps"] >= 0 else "neg"}"></i></div>'
        f'<b class="{"green" if d["mean_edge_bps"] >= 0 else "red"}">{d["mean_edge_bps"]:+.1f} bps</b><small>hit {d["hit_rate"]*100:.0f}%</small></div>'
        for d in run["edge_decay"]
    )

    regime_rows = "".join(
        f'<div class="regime-card"><span>{esc(r["regime"].upper())} VOL</span>'
        f'<b class="{"green" if r["return"] >= 0 else "red"}">{pct(r["return"])}</b>'
        f'<small>Sharpe {r["sharpe"]:.2f} · hit {r["hit_rate"]*100:.0f}% · n={r["observations"]}</small></div>'
        for r in run["regime_performance"]
    )

    trades = run.get("trades", [])[-120:]
    trade_grid = "".join(f'<i class="trade {t["outcome"]}" title="{esc(t["date"])} {t["return"]*100:+.2f}%"></i>' for t in trades)

    gate_reason = (
        "All robustness checks cleared." if gate["status"] == "pass" else
        "Attractive headline P&L is not enough: statistical, friction and stability checks still reject deployment."
    )

    concentration = run.get("return_concentration", {})
    selection = run.get("selection_bias", {})
    reality_p = selection.get("reality_check_p")
    reality_text = "—" if reality_p is None else f"{reality_p:.3f}"
    stripped = concentration.get("return_without_best_sessions", 0.0)
    top_profit = concentration.get("top_profit_share")
    top_profit_text = "—" if top_profit is None else f"{top_profit*100:.0f}%"
    plateau = run.get("parameter_sensitivity", {}).get("plateau_score", 0.0)

    cross = run.get("cross_asset", {})
    holdout = cross.get("holdout", {})
    cross_cards = "".join(
        f'<div class="crosscard {"up" if row.get("positive") else "down"}"><span>{esc(row["symbol"].replace("USDT", ""))}</span>'
        f'<b class="{"green" if row.get("positive") else "red"}">{pct(row["total_return"])}</b>'
        f'<small>Sharpe {row["sharpe"]:.2f} · q {("—" if row.get("fdr_q") is None else format(row["fdr_q"], ".3f"))}</small></div>'
        for row in cross.get("asset_rows", [])
    )
    if holdout.get("available"):
        donors = " + ".join(str(x).replace("USDT", "") for x in holdout.get("donors", []))
        cross_cards += (
            f'<div class="crosscard {"up" if holdout.get("positive") else "down"}"><span>ASSET HOLDOUT</span>'
            f'<b class="{"green" if holdout.get("positive") else "red"}">{pct(holdout.get("total_return",0.0))}</b>'
            f'<small>{holdout.get("chosen_lookback","—")}d chosen on {esc(donors)} · S {holdout.get("sharpe",0.0):.2f}</small></div>'
        )
    else:
        cross_cards += f'<div class="crosscard down"><span>ASSET HOLDOUT</span><b>—</b><small>{esc(holdout.get("reason","unavailable"))}</small></div>'

    source_label = payload.get("data_source", {}).get("label", "Synthetic offline demo") if isinstance(payload.get("data_source"), dict) else "Synthetic offline demo"
    claim = payload.get("data_source", {}).get("claim_status", "Synthetic offline demo") if isinstance(payload.get("data_source"), dict) else "Synthetic offline demo"

    return f'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SignalLab v0.8 preview</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#080b0f;color:#edf1f5;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:14px}} .wrap{{width:1380px;margin:0 auto;padding:34px 36px 28px}}
header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:22px}} .brand{{display:flex;gap:14px;align-items:center}} .logo{{width:42px;height:42px;border-radius:11px;background:linear-gradient(135deg,#6de5b7,#5b7cff);display:grid;place-items:center;color:#07100d;font-weight:900;font-size:18px;box-shadow:0 0 30px #4ed5aa22}} h1{{font-size:22px;margin:0 0 4px;letter-spacing:-.02em}} .sub{{color:#7d8897;font-size:12px}} .badges{{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;max-width:610px}} .badge{{border:1px solid #28313c;background:#10151b;color:#abb6c4;padding:7px 10px;border-radius:999px;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}} .badge.warn{{border-color:#57471d;color:#f6cc68;background:#1c170c}} .badge.clean{{border-color:#1d513e;color:#67e4b2;background:#0b1b15}}
.live-lab{{display:flex;justify-content:space-between;align-items:center;gap:18px;margin:-6px 0 14px;border:1px solid #293645;background:linear-gradient(90deg,#0d151f,#0d1116);border-radius:12px;padding:12px 14px}} .live-lab .copy span{{display:block;color:#6f7c8d;font-size:8px;letter-spacing:.12em;font-weight:800}} .live-lab .copy b{{display:block;margin-top:4px;font-size:12px}} .live-lab .copy small{{display:block;color:#657181;margin-top:3px;font-size:9px}} .live-lab .controls{{display:flex;gap:7px;align-items:center}} .live-lab .chip{{border:1px solid #283544;background:#0b1118;color:#8c9bad;border-radius:7px;padding:7px 9px;font-size:9px}} .live-lab .run{{border-color:#36567d;color:#8bbcff;background:#101d2c}}
.filters{{display:grid;grid-template-columns:repeat(6,1fr);gap:9px;margin-bottom:16px}} .filter{{background:#0f141a;border:1px solid #222b35;border-radius:10px;padding:9px 12px}} .filter span{{display:block;color:#677485;font-size:9px;text-transform:uppercase;letter-spacing:.11em;margin-bottom:4px}} .filter b{{font-size:12px;font-weight:600}} .panel{{background:linear-gradient(180deg,#10151b,#0d1217);border:1px solid #242d37;border-radius:14px;padding:18px 20px;box-shadow:0 8px 30px #00000020}} .grid2{{display:grid;grid-template-columns:1.62fr 1fr;gap:14px;margin-bottom:14px}} .gridhalf{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}} .head{{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:12px}} .eye{{font-size:9px;letter-spacing:.14em;color:#677485;font-weight:800}} h2{{font-size:15px;margin:4px 0 0;font-weight:650}} .status{{font-weight:800;color:#62e7af;font-size:14px}} .status.fail{{color:#ff6f76}} .note{{color:#647181;font-size:10px;line-height:1.45}} .chart{{height:274px;position:relative}} svg{{width:100%;height:244px;overflow:visible}} .grid{{stroke:#202933;stroke-width:1}} .equity{{fill:none;stroke:#72a8ff;stroke-width:2.2}} .draw{{fill:none;stroke:#f06a73;stroke-width:1.6}} .reliability{{fill:none;stroke:#a887ff;stroke-width:1.8}} .axis{{display:flex;justify-content:space-between;color:#53606f;font-size:9px;margin-top:-2px}}
.metrics{{display:grid;grid-template-columns:1fr 1fr;gap:9px}} .metric{{background:#0b1015;border:1px solid #202833;border-radius:10px;padding:12px;min-height:84px}} .metric span{{font-size:8px;color:#657181;letter-spacing:.1em;font-weight:800}} .metric b{{font-size:22px;display:block;margin-top:8px;letter-spacing:-.025em}} .metric small{{display:block;color:#6e7b8b;margin-top:5px;font-size:9px}} .green{{color:#59dfaa!important}} .red{{color:#ff6f76!important}} .violet{{color:#b89aff!important}}
.evidence{{display:grid;grid-template-columns:repeat(6,1fr);gap:9px}} .ev{{background:#0b1015;border:1px solid #202833;border-radius:9px;padding:11px}} .ev span{{display:block;color:#657181;font-size:8px;letter-spacing:.1em}} .ev b{{display:block;margin-top:7px;font-size:16px}} .gate{{display:grid;grid-template-columns:230px 1fr;gap:18px;align-items:stretch}} .gate-score{{background:#0b1015;border:1px solid #3c2428;border-radius:11px;padding:16px;display:flex;flex-direction:column;justify-content:center}} .gate-score strong{{font-size:36px;color:#ff6f76;line-height:1}} .gate-score b{{font-size:14px;margin-top:8px}} .gate-score small{{color:#788596;margin-top:8px;line-height:1.5}} .criteria{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}} .criterion{{border-radius:9px;padding:10px;font-size:10px;border:1px solid #25303b;background:#0b1015;color:#9ba6b4;display:flex;gap:7px;align-items:center}} .criterion.pass{{border-color:#1c4938;color:#5addaa;background:#0b1713}} .criterion.fail{{border-color:#49272a;color:#ff7a81;background:#170d0f}} .criterion span{{font-size:14px;font-weight:900}}
table{{width:100%;border-collapse:collapse;font-size:11px}} th{{text-align:left;color:#657181;font-size:8px;letter-spacing:.09em;padding:7px 8px;border-bottom:1px solid #222b35}} td{{padding:9px 8px;border-bottom:1px solid #171e26;color:#aeb8c5}} tr.active td{{background:#111b24;color:#e8eef4}} .gate-pill{{font-size:8px;padding:4px 6px;border-radius:999px;border:1px solid #493034;color:#ff7a81}} .gate-pill.pass{{color:#56dfa9;border-color:#245040}} .gate-pill.watch{{color:#f5c96a;border-color:#594820}} .folds{{display:flex;gap:5px;flex-wrap:wrap;margin-top:15px}} .fold{{font-size:9px;padding:5px 7px;border-radius:6px;background:#121a22;border:1px solid #28333f;color:#aab6c4}} .years{{display:grid;grid-template-columns:repeat(5,1fr);gap:9px}} .crossassets{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}} .crosscard{{background:#0b1015;border:1px solid #202833;border-radius:10px;padding:12px}} .crosscard.up{{border-color:#1d513e}} .crosscard.down{{border-color:#4b272c}} .crosscard span{{font-size:9px;color:#687586;letter-spacing:.09em}} .crosscard b{{font-size:18px;display:block;margin-top:8px}} .crosscard small{{display:block;color:#657181;font-size:9px;margin-top:6px}} .year-card,.regime-card{{background:#0b1015;border:1px solid #202833;border-radius:10px;padding:12px}} .year-card span,.regime-card span{{font-size:9px;color:#687586;letter-spacing:.09em}} .year-card b,.regime-card b{{font-size:18px;display:block;margin-top:8px}} .year-card small,.regime-card small{{display:block;color:#657181;font-size:9px;margin-top:6px}}
.costs{{display:grid;gap:8px}} .cost{{display:grid;grid-template-columns:60px 1fr 78px 55px;gap:10px;align-items:center;font-size:10px}} .cost-line{{height:7px;background:#171f28;border-radius:8px;overflow:hidden}} .cost-line i{{display:block;height:100%;border-radius:8px}} .pos{{background:#3bc98f}} .neg{{background:#e76069}} .cost b{{text-align:right}} .cost small{{color:#627080;text-align:right}} .regimes{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}} .tradegrid{{display:grid;grid-template-columns:repeat(40,1fr);gap:3px}} .trade{{aspect-ratio:1;border-radius:2px;background:#26313b}} .trade.win{{background:#2cbd82}} .trade.loss{{background:#d4535d}} .strip{{margin-top:13px;padding:11px 12px;border-radius:9px;border:1px solid #202833;background:#0b1015;color:#8996a6;font-size:10px;display:flex;justify-content:space-between;gap:12px}} footer{{display:flex;justify-content:space-between;color:#52606f;font-size:9px;padding:15px 4px 0}} .auditline{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#637183;font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:9px}}
</style></head><body><div class="wrap">
<header><div class="brand"><div class="logo">S</div><div><h1>SignalLab</h1><div class="sub">Walk-forward signal research · regime intelligence · robustness before P&amp;L</div></div></div><div class="badges"><span class="badge warn">{esc(claim)}</span><span class="badge {'clean' if audit.get('clean') else 'warn'}">DATA AUDIT {'CLEAN' if audit.get('clean') else 'FLAGGED'}</span><span class="badge">OOS · HAC/FDR · REALITY CHECK · CROSS-ASSET</span></div></header>
<div class="live-lab"><div class="copy"><span>LIVE RESEARCH WORKBENCH</span><b>Import OHLCV and rerun a strategy directly in the browser</b><small>Private local file · signal / lookback / costs / execution delay · exportable result</small></div><div class="controls"><span class="chip">Load CSV</span><span class="chip">20d lookback</span><span class="chip">10 bps</span><span class="chip">t+1</span><span class="chip run">Run experiment</span></div></div>
<div class="filters"><div class="filter"><span>Asset</span><b>{symbol}</b></div><div class="filter"><span>Signal</span><b>{esc(signal.replace('_',' ').title())}</b></div><div class="filter"><span>Validation</span><b>{esc(mode.replace('_',' ').title())}</b></div><div class="filter"><span>Fees</span><b>{fee_bps:.0f} bps / turnover</b></div><div class="filter"><span>Holding period</span><b>{run['holding_period']} day</b></div><div class="filter"><span>Evaluation</span><b>{run['start_date']} → {run['end_date']}</b></div></div>
<div class="grid2"><section class="panel"><div class="head"><div><span class="eye">STRATEGY PERFORMANCE</span><h2>Out-of-sample equity curve</h2></div><div class="status">↗ {pct(m['total_return'])}</div></div><div class="chart"><svg viewBox="0 0 720 255"><line class="grid" x1="10" x2="710" y1="52" y2="52"/><line class="grid" x1="10" x2="710" y1="102" y2="102"/><line class="grid" x1="10" x2="710" y1="152" y2="152"/><line class="grid" x1="10" x2="710" y1="202" y2="202"/><path class="equity" d="{svg_path(eq)}"/></svg><div class="axis"><span>{run['start_date']}</span><span>{run['end_date']}</span></div></div></section>
<section class="panel"><div class="head"><div><span class="eye">CORE METRICS</span><h2>Research snapshot</h2></div></div><div class="metrics"><div class="metric"><span>ANNUALISED RETURN</span><b class="green">{pct(m['annualized_return'])}</b></div><div class="metric"><span>SHARPE</span><b>{m['sharpe']:.2f}</b></div><div class="metric"><span>MAX DRAWDOWN</span><b class="red">{pct(m['max_drawdown'])}</b></div><div class="metric"><span>SORTINO</span><b>{m['sortino']:.2f}</b></div><div class="metric"><span>SIGNAL STATE</span><b class="violet">{esc(run['signal_state']['label'].upper())}</b><small>60d score {run['signal_state']['score']:.2f}</small></div><div class="metric"><span>WF → IS SHARPE GAP</span><b>{wf_is_gap:+.2f}</b><small>IS {counterpart['metrics']['sharpe']:.2f} vs WF {m['sharpe']:.2f}</small></div></div></section></div>
<section class="panel" style="margin-bottom:14px"><div class="head"><div><span class="eye">OUT-OF-SAMPLE EVIDENCE</span><h2>Does the edge survive statistical scrutiny?</h2></div><div class="status fail">{esc(rob['evidence_grade'].upper())} EVIDENCE</div></div><div class="evidence"><div class="ev"><span>HAC t-STAT</span><b>{rob['hac_t_stat']:.2f}</b></div><div class="ev"><span>RAW p-VALUE</span><b>{rob['p_value']:.3f}</b></div><div class="ev"><span>FDR q-VALUE</span><b class="red">{rob['fdr_q']:.3f}</b></div><div class="ev"><span>BOOTSTRAP SHARPE 95%</span><b>{rob['sharpe_ci_low']:.2f} → {rob['sharpe_ci_high']:.2f}</b></div><div class="ev"><span>REALITY-CHECK p</span><b class="{'green' if (selection.get('reality_check_p') is not None and selection.get('reality_check_p') < .10) else 'red'}">{reality_text}</b></div><div class="ev"><span>EXCESS VS BENCHMARK</span><b class="green">{pct(rob['excess_vs_benchmark'])}</b></div></div></section>
<section class="panel" style="margin-bottom:14px"><div class="head"><div><span class="eye">DEPLOYMENT GATE</span><h2>Nine checks must agree before a signal is considered robust</h2></div><div class="status fail">{gate['status'].upper()} · {gate['passed']}/{gate['total']}</div></div><div class="gate"><div class="gate-score"><strong>{gate['passed']}/{gate['total']}</strong><b>{gate['status'].upper()} RESEARCH GATE</b><small>{esc(gate_reason)}</small><small>Break-even cost: <b style="color:#eef3f7">{run['break_even_fee_bps']:.1f} bps</b></small></div><div class="criteria">{criteria}</div></div></section>
<div class="gridhalf"><section class="panel"><div class="head"><div><span class="eye">SIGNAL LEADERBOARD</span><h2>Same asset · same OOS window · same costs</h2></div></div><table><thead><tr><th>#</th><th>Signal</th><th>Return</th><th>Sharpe</th><th>FDR q</th><th>Gate</th></tr></thead><tbody>{lead_rows}</tbody></table></section>
<section class="panel"><div class="head"><div><span class="eye">PARAMETER STABILITY</span><h2>Walk-forward lookback path</h2></div><div class="note">stability {run['parameter_stability']['stability_score']*100:.0f}% · {run['parameter_stability']['switches']} switches</div></div><div class="folds">{fold_chips}</div><div class="strip"><span>Dominant lookback <b>{run['parameter_stability']['dominant_lookback']}d</b></span><span>{len(folds)} unseen test folds</span><span>5 candidate lookbacks</span></div></section></div>
<div class="gridhalf"><section class="panel"><div class="head"><div><span class="eye">DRAWDOWN</span><h2>Underwater curve</h2></div><div class="status fail">{pct(m['max_drawdown'])}</div></div><div class="chart"><svg viewBox="0 0 720 255"><line class="grid" x1="10" x2="710" y1="52" y2="52"/><line class="grid" x1="10" x2="710" y1="102" y2="102"/><line class="grid" x1="10" x2="710" y1="152" y2="152"/><line class="grid" x1="10" x2="710" y1="202" y2="202"/><path class="draw" d="{svg_path(dd)}"/></svg><div class="axis"><span>{run['start_date']}</span><span>{run['end_date']}</span></div></div></section>
<section class="panel"><div class="head"><div><span class="eye">ROLLING RELIABILITY</span><h2>60-day rolling signal quality</h2></div><div class="status fail">{run['signal_state']['label'].upper()}</div></div><div class="chart"><svg viewBox="0 0 720 255"><line class="grid" x1="10" x2="710" y1="52" y2="52"/><line class="grid" x1="10" x2="710" y1="102" y2="102"/><line class="grid" x1="10" x2="710" y1="152" y2="152"/><line class="grid" x1="10" x2="710" y1="202" y2="202"/><path class="reliability" d="{svg_path(rel)}"/></svg><div class="axis"><span>rolling Sharpe</span><span>latest {run['signal_state']['score']:.2f}</span></div></div></section></div>
<div class="gridhalf"><section class="panel"><div class="head"><div><span class="eye">FRICTION ROBUSTNESS</span><h2>Transaction-cost stress</h2></div><div class="note">fixed signal path · BE {run['break_even_fee_bps']:.1f} bps</div></div><div class="costs">{cost_rows}</div></section>
<section class="panel"><div class="head"><div><span class="eye">SIGNAL DECAY</span><h2>Signed forward return by horizon</h2></div><div class="note">exploratory · overlapping horizons</div></div><div class="costs">{decay_rows}</div></section></div>
<div class="gridhalf"><section class="panel"><div class="head"><div><span class="eye">IMPLEMENTATION ROBUSTNESS</span><h2>Execution-delay stress</h2></div><div class="note">same fixed signal path</div></div><div class="costs">{delay_rows}</div><div class="strip"><span>baseline t+1</span><span>no re-optimisation</span><span>timing fragility test</span></div></section>
<section class="panel"><div class="head"><div><span class="eye">PARAMETER ROBUSTNESS</span><h2>Lookback sensitivity</h2></div><div class="note">plateau {plateau*100:.0f}%</div></div><div class="costs">{parameter_rows}</div><div class="strip"><span>5 declared lookbacks</span><span>ex-post diagnostic only</span><span>not used for inference</span></div></section></div>
<section class="panel" style="margin-bottom:14px"><div class="head"><div><span class="eye">SELECTION &amp; CONCENTRATION RISK</span><h2>Could the edge be a lucky rule or a few exceptional sessions?</h2></div><div class="status fail">REALITY p {reality_text}</div></div><div class="evidence"><div class="ev"><span>SEARCH-SPACE TRIALS</span><b>{selection.get('trials',0)}</b></div><div class="ev"><span>BEST FIXED SPEC</span><b>{esc(selection.get('best_specification','—'))}</b></div><div class="ev"><span>TOP-10 PROFIT SHARE</span><b>{top_profit_text}</b></div><div class="ev"><span>WITHOUT BEST 10</span><b class="{'green' if stripped >= 0 else 'red'}">{pct(stripped)}</b></div><div class="ev"><span>PARAMETER PLATEAU</span><b>{plateau*100:.0f}%</b></div><div class="ev"><span>ACTIVE SESSIONS</span><b>{concentration.get('active_sessions',0)}</b></div></div><div class="strip"><span>White-style moving-block reality check</span><span>20 fixed signal/lookback rules</span><span>adaptive selector tested separately by walk-forward</span></div></section>
<section class="panel" style="margin-bottom:14px"><div class="head"><div><span class="eye">CROSS-ASSET VALIDATION</span><h2>Does the signal travel beyond one market?</h2></div><div class="note">replication {cross.get('positive_share',0.0)*100:.0f}% positive · median Sharpe {cross.get('median_sharpe',0.0):.2f}</div></div><div class="crossassets">{cross_cards}</div><div class="strip"><span>same signal family across BTC / ETH / SOL</span><span>held-out target parameter selected on other assets only</span><span>common point-in-time training cut-off</span></div></section>
<section class="panel" style="margin-bottom:14px"><div class="head"><div><span class="eye">YEAR-BY-YEAR CONSISTENCY</span><h2>Does the result depend on one lucky episode?</h2></div><div class="note">positive in {gate['positive_year_share']*100:.0f}% of calendar years</div></div><div class="years">{yearly}</div></section>
<div class="gridhalf"><section class="panel"><div class="head"><div><span class="eye">REGIME PERFORMANCE</span><h2>Conditional behaviour by volatility state</h2></div></div><div class="regimes">{regime_rows}</div></section>
<section class="panel"><div class="head"><div><span class="eye">RECENT OUTCOMES</span><h2>Last 120 active sessions</h2></div><div class="note">green = win · red = loss</div></div><div class="tradegrid">{trade_grid}</div><div class="strip"><span>Win rate <b>{m['win_rate']*100:.1f}%</b></span><span>Longest win streak <b>{m['longest_win_streak']}</b></span><span>Longest loss streak <b>{m['longest_loss_streak']}</b></span></div></section></div>
<section class="panel"><div class="head"><div><span class="eye">DATA &amp; METHODOLOGY</span><h2>Reproducibility is part of the result</h2></div><div class="status {'green' if audit.get('clean') else 'fail'}">{audit.get('rows','?')} rows · {'CLEAN' if audit.get('clean') else 'CHECK'}</div></div><div class="strip"><span>Next-bar execution</span><span>365d train / 90d test</span><span>HAC inference + BH-FDR</span><span>Moving-block bootstrap</span><span>Point-in-time regimes</span><span>Cost stress + break-even</span><span>Reality check + delay stress</span><span>Cross-asset holdout</span></div><div class="auditline">{esc(source_label)} · {esc(audit.get('start_date',''))} → {esc(audit.get('end_date',''))} · SHA256 {esc(audit.get('sha256',''))}</div></section>
<footer><span>SignalLab v{esc(payload.get('version','0.8.0'))}</span><span>Synthetic preview only · research software · not investment advice</span></footer>
</div></body></html>'''


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--payload", default="dashboard/public/demo-results.json")
    p.add_argument("--output", default="docs/dashboard-preview.html")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--signal", default="volatility_breakout")
    p.add_argument("--mode", default="walk_forward")
    p.add_argument("--fee-bps", type=float, default=10.0)
    args = p.parse_args()
    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(payload, args.symbol, args.signal, args.mode, args.fee_bps), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
