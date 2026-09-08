from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """Return a deterministic SHA-256 digest for a local market-data file."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def audit_market_frame(df: pd.DataFrame) -> dict:
    """Audit a normalized daily crypto OHLCV frame.

    The audit is intentionally conservative and descriptive. Crypto spot trades
    seven days a week, so a calendar-day gap is meaningful rather than a normal
    weekend closure.
    """
    required = {"date", "open", "high", "low", "close", "volume"}
    missing_cols = sorted(required.difference(df.columns))
    if missing_cols:
        return {
            "clean": False,
            "missing_columns": missing_cols,
            "rows": int(len(df)),
        }

    x = df.copy()
    x["date"] = pd.to_datetime(x["date"], utc=True, errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    duplicate_dates = int(x["date"].duplicated().sum())
    missing_values = int(x[list(required)].isna().sum().sum())
    invalid_ohlc = int(
        (
            (x["high"] < x[["open", "close", "low"]].max(axis=1))
            | (x["low"] > x[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    nonpositive_prices = int((x[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    negative_volume = int((x["volume"] < 0).sum())
    zero_volume = int((x["volume"] == 0).sum())

    dates = x["date"].dropna().sort_values().drop_duplicates()
    if len(dates) >= 2:
        gaps = dates.diff().dt.days.dropna().astype(int)
        missing_calendar_days = int(np.maximum(gaps.to_numpy() - 1, 0).sum())
        max_gap_days = int(gaps.max())
    else:
        missing_calendar_days = 0
        max_gap_days = 0

    start = str(dates.iloc[0].date()) if len(dates) else None
    end = str(dates.iloc[-1].date()) if len(dates) else None
    rows = int(len(x))
    clean = (
        not missing_cols
        and duplicate_dates == 0
        and missing_values == 0
        and invalid_ohlc == 0
        and nonpositive_prices == 0
        and negative_volume == 0
        and zero_volume == 0
        and missing_calendar_days == 0
    )

    return {
        "clean": bool(clean),
        "rows": rows,
        "start_date": start,
        "end_date": end,
        "duplicate_dates": duplicate_dates,
        "missing_values": missing_values,
        "invalid_ohlc_rows": invalid_ohlc,
        "nonpositive_price_rows": nonpositive_prices,
        "negative_volume_rows": negative_volume,
        "zero_volume_rows": zero_volume,
        "missing_calendar_days": missing_calendar_days,
        "max_gap_days": max_gap_days,
    }


def audit_market_file(path: str | Path, loader) -> dict:
    """Audit a file and append its content hash.

    ``loader`` is injected to avoid a circular import with ``data.py``.
    """
    p = Path(path)
    result = audit_market_frame(loader(p))
    result["sha256"] = file_sha256(p)
    result["file"] = p.name
    return result
