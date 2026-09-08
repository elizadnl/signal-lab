# SignalLab live app

SignalLab has two genuinely interactive layers.

## 1. Empirical research console

The deployed GitHub Pages build does not publish the synthetic demo as an empirical result. Before deployment, GitHub Actions downloads completed monthly BTCUSDT, ETHUSDT and SOLUSDT daily spot kline archives from Binance's public data archive, verifies the published SHA-256 companion checksums, runs the Python research pipeline, writes `dashboard/public/results.json`, and only then builds the React site.

The deployment workflow fails closed if the payload is not marked `public_market_data`.

The public dashboard therefore supports interactive asset, signal, validation, cost and chart-window selection against the latest completed monthly public dataset available when the workflow runs.

## 2. Local Research Workbench

The React app also contains a browser-side **Live Research Workbench**. A visitor can import a daily OHLCV CSV (or native 12-column Binance kline CSV), choose:

- momentum / mean reversion / abnormal volume / volatility breakout,
- 5 / 10 / 20 / 40 / 60-day lookback,
- 0 / 5 / 10 / 15 / 25 / 50 bps execution cost,
- t+1 / t+2 / t+3 / t+5 execution,

and rerun a fixed-parameter backtest immediately in the browser. The resulting equity curve, Sharpe, drawdown, hit rate, exposure, turnover and recent win/loss sequence update locally. The imported file never leaves the browser.

This workbench is intentionally labelled exploratory. The main empirical console remains the authoritative walk-forward / HAC / FDR / block-bootstrap research pipeline.

## Deployment

Enable **Settings → Pages → Source: GitHub Actions** in the repository, then run **Build empirical dashboard and deploy Pages** from the Actions tab. It also refreshes automatically on the 8th of each month and on relevant pushes to `main`.
