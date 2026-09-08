# SignalLab research report

**Data:** Synthetic offline demo  
**Status:** Illustrative only — not empirical trading results  
**Validation:** walk-forward, 10 bps transaction costs

> **Synthetic demo only.** The values below are generated to exercise the research pipeline and dashboard. They are not empirical trading results.

## Walk-forward leaderboard

| Asset | Signal | Return | Sharpe | 95% Sharpe CI | HAC p | FDR q | Reality p | Cross-asset + | Asset holdout | Evidence | Gate | Break-even fee | 25 bps return | t+3 return | w/o best 10 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
| BTCUSDT | volatility breakout | +122.2% | 0.71 | -0.19 to 1.59 | 0.123 | 0.245 | 0.208 | +66.7% | +144.9% | weak | fail (4/9) | 18.0 bps | -50.3% | -80.3% | +5.7% |
| BTCUSDT | abnormal volume | +18.2% | 0.28 | -0.55 to 1.10 | 0.530 | 0.706 | 0.208 | +66.7% | -5.1% | weak | fail (2/9) | 13.4 bps | -43.4% | -47.7% | -39.7% |
| BTCUSDT | momentum | -37.0% | 0.05 | -0.79 to 0.94 | 0.924 | 0.924 | 0.208 | +33.3% | +3.2% | no evidence | fail (2/9) | 0.0 bps | -59.3% | -47.2% | -71.9% |
| BTCUSDT | mean reversion | -97.3% | -1.33 | -2.26 to -0.46 | 0.003 | 0.014 | 0.208 | +0.0% | -93.7% | no evidence | fail (1/9) | 0.0 bps | -98.6% | -93.0% | -98.9% |
| ETHUSDT | volatility breakout | -8.6% | 0.09 | -0.85 to 1.06 | 0.848 | 0.848 | 1.000 | +66.7% | -27.4% | no evidence | fail (2/9) | 9.1 bps | -78.8% | -58.6% | -61.8% |
| ETHUSDT | mean reversion | -60.4% | -0.15 | -1.02 to 0.96 | 0.765 | 0.848 | 1.000 | +0.0% | -88.6% | no evidence | fail (1/9) | 0.0 bps | -77.0% | -69.3% | -84.4% |
| ETHUSDT | momentum | -74.2% | -0.33 | -1.33 to 0.51 | 0.484 | 0.848 | 1.000 | +33.3% | -61.0% | no evidence | fail (0/9) | 0.0 bps | -86.8% | -90.1% | -90.2% |
| ETHUSDT | abnormal volume | -54.9% | -0.67 | -1.67 to 0.22 | 0.150 | 0.600 | 1.000 | +66.7% | -34.3% | no evidence | fail (0/9) | 0.0 bps | -80.6% | -39.3% | -76.8% |
| SOLUSDT | abnormal volume | +46.6% | 0.50 | -0.49 to 1.29 | 0.296 | 0.395 | 0.337 | +66.7% | +78.0% | weak | fail (4/9) | 17.0 bps | -35.7% | -60.1% | -21.1% |
| SOLUSDT | volatility breakout | +56.7% | 0.47 | -0.43 to 1.41 | 0.280 | 0.395 | 0.337 | +66.7% | +183.3% | weak | fail (4/9) | 14.7 bps | -62.4% | -63.1% | -20.7% |
| SOLUSDT | momentum | +17.4% | 0.31 | -0.72 to 1.24 | 0.534 | 0.534 | 0.337 | +33.3% | -27.1% | weak | fail (3/9) | 14.3 bps | -33.1% | -28.8% | -52.8% |
| SOLUSDT | mean reversion | -94.0% | -1.05 | -2.04 to -0.16 | 0.022 | 0.087 | 0.337 | +0.0% | -93.6% | no evidence | fail (2/9) | 0.0 bps | -96.9% | -94.4% | -97.3% |

## Deployment gate

The gate is intentionally harder to clear than the headline backtest. A walk-forward run must pass nine checks: positive OOS return, Sharpe above 0.5, FDR q below 0.10, a positive lower bootstrap Sharpe bound, positive return at 25 bps, at least 50% parameter stability, positive performance in at least half of calendar years, a search-space reality-check p-value below 0.10, and a cross-asset check that requires both broad replication and a positive asset-held-out transfer test.

`PASS` means all nine checks clear. `WATCH` means most checks clear but the run is not robust enough to call deployable. `FAIL` means the evidence is insufficient under this rule.

## Interpretation rules

- Treat the walk-forward result as the primary view; the in-sample result is only an optimism comparator.
- Prefer signals that survive both statistical correction and transaction-cost stress rather than ranking on raw return alone.
- A wide bootstrap Sharpe interval indicates material uncertainty even when the point estimate looks attractive.
- Parameter instability is a warning that performance may depend on repeatedly changing the model specification.
- The search-space reality check asks whether the best mean return across the 20 declared fixed signal/lookback rules is unusually large after data-snooping adjustment; it does not directly test the adaptive walk-forward selector.
- Execution-delay and best-session-removal stress tests expose timing fragility and return concentration without re-optimising the signal.
- Cross-asset validation asks whether the signal family is positive across multiple assets and whether a lookback selected only on the other assets transfers to the held-out target.
- The forward-horizon decay panel is exploratory because multi-day observations overlap.

## Reproduction

```bash
signallab build --data-dir data/processed --output dashboard/public/results.json
signallab report --payload dashboard/public/results.json --output docs/RESEARCH_REPORT.md
```
