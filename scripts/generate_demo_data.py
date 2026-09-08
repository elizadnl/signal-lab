from __future__ import annotations

from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import json


def synthetic_asset(symbol: str, start: str, end: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="D", tz="UTC")
    n = len(dates)

    # A deliberately non-stationary process for an offline UI demo.
    regime = np.sin(np.linspace(0, 14 * np.pi, n))
    drift = 0.00055 + 0.0008 * (regime > 0.35) - 0.0007 * (regime < -0.55)
    vol = 0.018 + 0.018 * (np.sin(np.linspace(0, 7 * np.pi, n)) > 0.55)
    eps = rng.normal(0, vol)
    # weak serial structure so some signals work only in some regimes
    eps[1:] += 0.12 * eps[:-1] * (regime[1:] > 0)
    log_ret = drift + eps

    base = {"BTCUSDT": 29000, "ETHUSDT": 1800, "SOLUSDT": 35}.get(symbol, 100)
    close = base * np.exp(np.cumsum(log_ret))
    open_ = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, 0.004, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0.008, 0.005, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0.008, 0.005, n)))
    volume = np.exp(11 + 0.8 * np.abs(log_ret) / np.maximum(vol, 1e-6) + rng.normal(0, 0.45, n))

    return pd.DataFrame({"date": dates, "open": open_, "high": high, "low": low, "close": close, "volume": volume})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", default="data/processed")
    args = p.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "kind": "synthetic",
        "label": "Synthetic offline demo",
        "claim_status": "Illustrative only — not empirical trading results",
    }
    (out / "DATA_SOURCE.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    for i, symbol in enumerate(["BTCUSDT", "ETHUSDT", "SOLUSDT"], start=1):
        df = synthetic_asset(symbol, "2021-01-01", "2026-08-31", seed=100 + i)
        df.to_csv(out / f"{symbol}.csv", index=False)
        print(f"wrote {symbol}: {len(df)} rows")


if __name__ == "__main__":
    main()
