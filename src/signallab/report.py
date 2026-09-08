from __future__ import annotations

import json
from pathlib import Path


def _pct(x: float) -> str:
    return f"{x*100:+.1f}%"


def _num(x, digits: int = 2) -> str:
    return "—" if x is None else f"{x:.{digits}f}"


def _prob(x) -> str:
    if x is None:
        return "—"
    if x < 0.001:
        return "<0.001"
    return f"{x:.3f}"


def build_markdown_report(payload_path: str | Path, output: str | Path, fee_bps: float = 10.0) -> str:
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    runs = [r for r in payload["runs"] if r["mode"] == "walk_forward" and float(r["fee_bps"]) == float(fee_bps)]
    runs.sort(key=lambda r: (r["symbol"], -r["metrics"]["sharpe"]))

    source = payload.get("data_source", {})
    title = "SignalLab research report"
    lines = [
        f"# {title}",
        "",
        f"**Data:** {source.get('label', 'unknown')}  ",
        f"**Status:** {source.get('claim_status', 'unknown')}  ",
        f"**Validation:** walk-forward, {fee_bps:g} bps transaction costs",
        "",
    ]
    if source.get("kind") == "synthetic":
        lines += [
            "> **Synthetic demo only.** The values below are generated to exercise the research pipeline and dashboard. They are not empirical trading results.",
            "",
        ]

    lines += [
        "## Walk-forward leaderboard",
        "",
        "| Asset | Signal | Return | Sharpe | 95% Sharpe CI | HAC p | FDR q | Reality p | Cross-asset + | Asset holdout | Evidence | Gate | Break-even fee | 25 bps return | t+3 return | w/o best 10 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|",
    ]
    for r in runs:
        robust = r["robustness"]
        stress25 = next((x for x in r["cost_stress"] if x["fee_bps"] == 25.0), None)
        gate = r.get("deployment_gate", {})
        be = r.get("break_even_fee_bps")
        reality = r.get("selection_bias", {}).get("reality_check_p")
        delay3 = next((x for x in r.get("execution_delay_stress", []) if int(x["delay_days"]) == 3), None)
        stripped = r.get("return_concentration", {}).get("return_without_best_sessions")
        cross = r.get("cross_asset", {})
        holdout = cross.get("holdout", {})
        holdout_text = _pct(holdout.get("total_return")) if holdout.get("available") and holdout.get("total_return") is not None else "—"
        lines.append(
            f"| {r['symbol']} | {r['signal'].replace('_',' ')} | {_pct(r['metrics']['total_return'])} | "
            f"{_num(r['metrics']['sharpe'])} | {_num(robust['sharpe_ci_low'])} to {_num(robust['sharpe_ci_high'])} | "
            f"{_prob(robust['p_value'])} | {_prob(robust['fdr_q'])} | {_prob(reality)} | {_pct(cross.get('positive_share', 0.0))} | {holdout_text} | {robust['evidence_grade']} | "
            f"{gate.get('status','—')} ({gate.get('passed',0)}/{gate.get('total',0)}) | "
            f"{'>100' if be is None else _num(be,1)} bps | "
            f"{_pct(stress25['total_return']) if stress25 else '—'} | "
            f"{_pct(delay3['total_return']) if delay3 else '—'} | "
            f"{_pct(stripped) if stripped is not None else '—'} |"
        )


    lines += ["", "## Deployment gate", ""]
    lines += [
        "The gate is intentionally harder to clear than the headline backtest. A walk-forward run must pass nine checks: positive OOS return, Sharpe above 0.5, FDR q below 0.10, a positive lower bootstrap Sharpe bound, positive return at 25 bps, at least 50% parameter stability, positive performance in at least half of calendar years, a search-space reality-check p-value below 0.10, and a cross-asset check that requires both broad replication and a positive asset-held-out transfer test.",
        "",
        "`PASS` means all nine checks clear. `WATCH` means most checks clear but the run is not robust enough to call deployable. `FAIL` means the evidence is insufficient under this rule.",
    ]

    lines += ["", "## Interpretation rules", ""]
    lines += [
        "- Treat the walk-forward result as the primary view; the in-sample result is only an optimism comparator.",
        "- Prefer signals that survive both statistical correction and transaction-cost stress rather than ranking on raw return alone.",
        "- A wide bootstrap Sharpe interval indicates material uncertainty even when the point estimate looks attractive.",
        "- Parameter instability is a warning that performance may depend on repeatedly changing the model specification.",
        "- The search-space reality check asks whether the best mean return across the 20 declared fixed signal/lookback rules is unusually large after data-snooping adjustment; it does not directly test the adaptive walk-forward selector.",
        "- Execution-delay and best-session-removal stress tests expose timing fragility and return concentration without re-optimising the signal.",
        "- Cross-asset validation asks whether the signal family is positive across multiple assets and whether a lookback selected only on the other assets transfers to the held-out target.",
        "- The forward-horizon decay panel is exploratory because multi-day observations overlap.",
        "",
        "## Reproduction",
        "",
        "```bash",
        "signallab build --data-dir data/processed --output dashboard/public/results.json",
        "signallab report --payload dashboard/public/results.json --output docs/RESEARCH_REPORT.md",
        "```",
    ]
    text = "\n".join(lines) + "\n"
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return text
