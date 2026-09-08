# SignalLab methodology

SignalLab is designed to make **optimism visible**. It does not treat a full-sample backtest as evidence that a signal would have been known, selected, or executable in real time.

## 1. Data convention

Each input file contains daily `date/open/high/low/close/volume` observations. The public-data path uses Binance spot klines. The included offline payload is synthetic and exists only to make the interface reproducible without network access.

The current market-data layer is deliberately simple. SignalLab treats the daily bars as a research substrate, not as proof that the resulting exposure could have been executed at the displayed close.

## 2. Signals

Four deliberately transparent baselines are included:

- **Momentum:** sign of the `L`-day price change.
- **Mean reversion:** negative sign of the `L`-day log-price z-score.
- **Abnormal volume:** same-day return direction only when log-volume exceeds a trailing z-score threshold.
- **Volatility breakout:** same-day return direction only when the absolute return is large relative to trailing realised volatility.

The candidate lookback set is fixed at `{5, 10, 20, 40, 60}` days. The small search space is intentional: the project is about validation discipline, not maximising degrees of freedom.

## 3. Execution timing

A signal observed at close `t` is not allowed to earn the return that already occurred at `t`.

If `s_t` is the signal and `r_{t+1}` is the next close-to-close return, gross strategy return is

`R_{t+1} = s_t * r_{t+1}`.

Turnover costs are charged on the same execution bar. For fee rate `c` and position `p`,

`net R_{t+1} = p_t * r_{t+1} - c * |p_t - p_{t-1}|`.

This convention is covered by an explicit unit test.

## 4. Walk-forward model selection

The default research path uses:

1. 365 trailing days as the training sample;
2. candidate lookbacks evaluated **inside training only**;
3. the highest training Sharpe selected;
4. the selected lookback locked for the next 90 unseen days;
5. the window rolled forward and repeated.

Appending future rows must not alter already-created historical walk-forward signals. The test suite checks this invariance directly.

### Common evaluation window

Performance statistics begin only after the initial 365-day training period. The in-sample comparator is evaluated over exactly the same post-warmup dates, so the displayed validation gap is not caused by different sample lengths.

## 5. In-sample comparator

The `in_sample` view is intentionally optimistic. It selects the best lookback using the full sample and then evaluates that parameter over the common post-warmup window.

It exists to expose the difference between:

- **what looks best after seeing the sample**, and
- **what survived chronological selection on unseen blocks**.

It is not presented as independent evidence.

## 6. Transaction-cost stress

The main dashboard offers 0 and 10 bps selection/evaluation settings. Each run additionally reprices the **same fixed selected position path** at 0, 5, 10 and 25 bps.

That stress test isolates execution-friction sensitivity from parameter reselection.

SignalLab also estimates a one-way break-even transaction cost by bisection between 0 and 100 bps. The signal path is not re-selected while costs change.

## 7. Execution-delay stress

A signal that only works when executed immediately can be economically fragile even if its backtest is chronological.

SignalLab therefore replays the **same fixed signal path** under execution at `t+1`, `t+2`, `t+3` and `t+5`. For a delay greater than one day, the signal is shifted by the additional number of bars and is not re-optimised.

This is an implementation-robustness diagnostic. It does not model intraday latency or order-book execution.

## 8. Point-in-time volatility regimes

Realised volatility uses a trailing 30-day window. Low/normal/high thresholds are expanding historical terciles shifted by one day, so the current observation cannot influence its own threshold.

A realised strategy return is attributed to the regime known when the corresponding position was chosen. Future rows cannot alter historical regime labels; this is also unit-tested.

## 9. Per-signal statistical evidence

A positive backtest Sharpe is not treated as sufficient evidence.

### HAC mean-return test

SignalLab computes a Newey–West heteroskedasticity/autocorrelation-consistent standard error with 7 lags for the mean daily strategy return. The displayed p-value uses the large-sample normal approximation.

### Benjamini–Hochberg FDR

Within each asset × validation mode × fee setting, raw p-values for the four baseline signals are adjusted with the **Benjamini–Hochberg false discovery rate** procedure. The dashboard displays the resulting q-value.

This correction covers the four displayed signal families. It does not pretend that undocumented experimentation is free.

### Sharpe uncertainty

A 95% Sharpe interval is estimated with a deterministic **7-day moving-block bootstrap**. Blocks preserve short-horizon dependence better than IID resampling.

The interval is descriptive; it is not a guarantee of future performance.

## 10. Search-space reality check

FDR across four headline signals does not fully account for the fact that each signal family also has five candidate lookbacks. SignalLab therefore adds a simplified **White-style reality check** across the 20 pre-declared fixed signal/lookback specifications for each asset and fee setting.

For each fixed rule:

1. strategy returns are aligned over the common post-warmup sample;
2. the best observed mean return is recorded;
3. each strategy return series is centred by its own sample mean;
4. a common 7-day moving-block bootstrap is drawn across all specifications, preserving serial and cross-strategy dependence;
5. the bootstrap distribution of the **maximum centred mean** is compared with the observed best mean.

The reported p-value asks whether the best mean return in the declared search space is unusually large after accounting for data snooping across those 20 fixed rules.

Important limitation: this diagnostic does **not** directly test the adaptive walk-forward selector. It is reported as a search-space stress test, not as a theorem about the full research process.

## 11. Evidence grade

The dashboard includes a deliberately simple heuristic label:

- **Strong:** walk-forward, positive compounded return, q < 0.05, bootstrap Sharpe lower bound > 0, Sharpe > 1.
- **Promising:** walk-forward, positive compounded return, q < 0.10, Sharpe > 0.5.
- **Weak:** positive compounded return and positive walk-forward Sharpe, but does not clear the above evidence thresholds.
- **No evidence:** non-positive compounded return or non-positive walk-forward Sharpe.
- **In-sample only:** comparator view.

The label is a compact UI summary, not a statistical theorem or trading recommendation.

## 12. Signal-decay diagnostic

For active signal observations, SignalLab reports the mean signed forward return at 1, 3, 7, 14 and 30-day horizons:

`edge_h = s_t * (P_{t+h}/P_t - 1)`.

Multi-day observations overlap, so these values are labelled **exploratory** and are not used in the HAC significance test.

## 13. Parameter stability and sensitivity

Two separate diagnostics are used.

### Walk-forward parameter stability

For walk-forward runs the dashboard tracks:

- dominant selected lookback;
- number of unique lookbacks;
- number of parameter switches;
- a stability score `1 - switches/(folds-1)`.

This asks whether the chronological selector keeps changing its preferred specification.

### Ex-post parameter sensitivity

The dashboard also evaluates all five pre-declared lookbacks over the common evaluation window using a fixed rule. It reports:

- return and Sharpe for each lookback;
- the share of lookbacks with positive total return;
- a **plateau score**: the share of lookbacks retaining at least 50% of the best observed Sharpe.

This panel is explicitly labelled ex-post and is not used for inference or model selection. It is there to reveal knife-edge parameter dependence.

## 14. Return concentration

A strategy can have attractive aggregate performance because of a small number of exceptional sessions. SignalLab therefore reports:

- number of active sessions;
- share of gross positive P&L contributed by the best 10 active sessions;
- share of gross losses contributed by the worst 10 active sessions;
- compounded return after the best 10 active sessions are set to zero.

The last statistic is intentionally severe. It is not a forecast of what would happen without those days; it is a fragility diagnostic.

## 15. Year-by-year consistency

The common post-warmup evaluation period is split into calendar years and the same locked strategy path is recomputed by year. SignalLab reports annual return, Sharpe, drawdown, hit rate and active sessions.

No parameter is re-fit at year boundaries.

## 16. Cross-asset transportability

A result that exists only in one instrument can be a market-specific accident. SignalLab therefore adds two diagnostics across the displayed BTC, ETH and SOL universe.

### Replication breadth

For each signal family and fee setting, the dashboard collects the independent walk-forward results for all available assets and reports:

- the share of assets with positive compounded OOS return;
- median OOS Sharpe across assets;
- each asset's OOS return, Sharpe and FDR q-value.

This does **not** pool the assets or treat them as independent observations for a single p-value. It is a breadth diagnostic.

### Asset-held-out parameter transfer

For each target asset, SignalLab then excludes that asset from lookback selection entirely. It:

1. finds the latest common starting date across the target and donor assets;
2. fixes a 365-observation common calendar training cut-off;
3. scores the five declared lookbacks on the **other two assets only** during that training period;
4. chooses the lookback with the highest mean donor training Sharpe;
5. builds the pre-declared signal family on the target using that fixed lookback;
6. evaluates the target only **after** the common training cut-off.

The target's returns are not used to choose the transferred lookback. Target history is still used mechanically to calculate the signal feature itself, so this is a parameter-transport test rather than a claim of complete cross-market independence.

The cross-asset gate clears only when the signal is positive on a broad share of displayed assets and the held-out target test is also positive. This is deliberately stricter than checking the target's own walk-forward backtest in isolation.

## 17. Deployment gate

The dashboard includes a deliberately conservative **nine-check** research gate. A walk-forward run must clear all of the following to receive `PASS`:

1. positive compounded out-of-sample return;
2. out-of-sample Sharpe above 0.5;
3. Benjamini–Hochberg FDR q-value below 0.10;
4. lower bound of the 95% block-bootstrap Sharpe interval above zero;
5. positive compounded return when the same path is repriced at 25 bps;
6. walk-forward lookback stability of at least 50%;
7. positive return in at least half of evaluated calendar years;
8. search-space reality-check p-value below 0.10;
9. cross-asset validation clears: broad positive replication plus a positive asset-held-out transfer test.

`WATCH` requires at least seven checks plus positive headline OOS return and Sharpe. Otherwise the run is labelled `FAIL`.

The rule is intentionally transparent and editable. Passing it is not equivalent to production readiness; failing it is a prompt to investigate rather than to optimise harder until the result passes.

## 18. Data quality and provenance

Before a dashboard payload is written, each normalized market file is audited for:

- duplicate timestamps;
- missing values;
- invalid OHLC relationships;
- non-positive prices;
- negative or zero volume;
- missing calendar days and maximum gap length.

A SHA-256 digest is stored with the audit so a result can be tied to the exact local input file. The official Binance downloader additionally verifies archive-level SHA-256 `CHECKSUM` companion files by default and records the source URL and digest for every downloaded month.

The audit catches mechanical data defects. It does not prove that an exchange feed is economically correct or free from venue-specific anomalies.

## 19. Limitations

SignalLab does not model exchange-specific bid/ask spread variation, market impact, funding, borrow constraints, tax, delistings, venue outages, survivorship, or order-book queue position. Daily bars cannot establish intraday execution feasibility.

The use of spot OHLCV as the research substrate also means that negative exposures should be interpreted as a hypothetical linear return exposure unless the researcher explicitly supplies a tradeable shorting/futures implementation.

The framework is for **research discipline and falsification**, not for claiming deployable alpha from four simple signals.
