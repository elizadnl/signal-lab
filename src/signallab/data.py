from __future__ import annotations

from pathlib import Path
import pandas as pd

BINANCE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
]


def load_market_csv(path: str | Path) -> pd.DataFrame:
    """Load a normalized OHLCV CSV.

    Expected columns are date/open/high/low/close/volume. Binance raw kline CSVs
    are also accepted.
    """
    path = Path(path)
    df = pd.read_csv(path)

    if {"date", "open", "high", "low", "close", "volume"}.issubset(df.columns):
        out = df[["date", "open", "high", "low", "close", "volume"]].copy()
        out["date"] = pd.to_datetime(out["date"], utc=True)
    else:
        # Binance monthly kline archives are headerless.
        df = pd.read_csv(path, header=None, names=BINANCE_COLUMNS)
        unit = "us" if pd.to_numeric(df["open_time"], errors="coerce").median() > 1e14 else "ms"
        out = pd.DataFrame({
            "date": pd.to_datetime(df["open_time"], unit=unit, utc=True),
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df["volume"], errors="coerce"),
        })

    out = out.dropna().sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if len(out) < 100:
        raise ValueError(f"Need at least 100 observations, found {len(out)} in {path}")
    return out


def load_symbol(data_dir: str | Path, symbol: str) -> pd.DataFrame:
    path = Path(data_dir) / f"{symbol.upper()}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run scripts/download_binance.py or scripts/generate_demo_data.py.")
    return load_market_csv(path)
