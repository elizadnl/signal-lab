from __future__ import annotations

"""Download official Binance public monthly 1d spot klines.

Primary source: https://data.binance.vision/
No API key is required. Each archive can optionally be verified against the
published SHA-256 CHECKSUM companion file.
"""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

import pandas as pd

COLS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
]
BASE = "https://data.binance.vision/data/spot/monthly/klines"


def month_range(start: str, end: str):
    for p in pd.period_range(start=start, end=end, freq="M"):
        yield str(p)


def archive_url(symbol: str, month: str) -> str:
    return f"{BASE}/{symbol}/1d/{symbol}-1d-{month}.zip"


def _fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SignalLab/0.6"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _verify_checksum(payload: bytes, checksum_payload: bytes, filename: str) -> None:
    text = checksum_payload.decode("utf-8", errors="replace").strip()
    expected = text.split()[0].strip().lower()
    actual = hashlib.sha256(payload).hexdigest().lower()
    if not expected or actual != expected:
        raise ValueError(f"Checksum mismatch for {filename}: expected {expected}, got {actual}")


def fetch_month(symbol: str, month: str, verify_checksum: bool = True) -> tuple[pd.DataFrame | None, dict | None]:
    url = archive_url(symbol, month)
    try:
        payload = _fetch(url)
        if verify_checksum:
            checksum = _fetch(url + ".CHECKSUM")
            _verify_checksum(payload, checksum, url.rsplit("/", 1)[-1])
    except Exception as exc:
        print(f"skip {symbol} {month}: {exc}")
        return None, None

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as f:
            df = pd.read_csv(f, header=None, names=COLS)

    meta = {
        "month": month,
        "url": url,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "checksum_verified": bool(verify_checksum),
    }
    return df, meta


def normalize(frames: list[pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat(frames, ignore_index=True)
    t = pd.to_numeric(df["open_time"], errors="coerce")

    dates = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")

    ms_mask = t < 1e14
    us_mask = t >= 1e14

    dates.loc[ms_mask] = pd.to_datetime(
        t.loc[ms_mask],
        unit="ms",
        utc=True,
        errors="coerce",
    )

    dates.loc[us_mask] = pd.to_datetime(
        t.loc[us_mask],
        unit="us",
        utc=True,
        errors="coerce",
    )

    out = pd.DataFrame({
        "date": dates,
        "open": pd.to_numeric(df["open"], errors="coerce"),
        "high": pd.to_numeric(df["high"], errors="coerce"),
        "low": pd.to_numeric(df["low"], errors="coerce"),
        "close": pd.to_numeric(df["close"], errors="coerce"),
        "volume": pd.to_numeric(df["volume"], errors="coerce"),
    })

    return (
        out.dropna()
        .sort_values("date")
        .drop_duplicates("date")
        .reset_index(drop=True)
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    p.add_argument("--start", default="2021-01")
    default_end = str(pd.Timestamp.now("UTC").tz_localize(None).to_period("M") - 1)
    p.add_argument("--end", default=default_end)
    p.add_argument("--output-dir", default="data/processed")
    p.add_argument("--no-checksum", action="store_true", help="Skip Binance SHA-256 checksum verification")
    args = p.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    symbols = [s.upper() for s in args.symbols]
    provenance: dict[str, list[dict]] = {}

    for symbol in symbols:
        frames: list[pd.DataFrame] = []
        provenance[symbol] = []
        for month in month_range(args.start, args.end):
            frame, meta = fetch_month(symbol, month, verify_checksum=not args.no_checksum)
            if frame is not None:
                frames.append(frame)
                if meta is not None:
                    provenance[symbol].append(meta)
        if not frames:
            raise RuntimeError(f"No data downloaded for {symbol}")
        data = normalize(frames)
        data.to_csv(out / f"{symbol}.csv", index=False, quoting=csv.QUOTE_MINIMAL)
        print(f"wrote {symbol}: {len(data)} rows ({data['date'].iloc[0].date()} → {data['date'].iloc[-1].date()})")

    meta = {
        "kind": "public_market_data",
        "label": "Binance public spot klines",
        "claim_status": "Empirical public market data",
        "source": "data.binance.vision",
        "interval": "1d",
        "market": "spot",
        "symbols": symbols,
        "requested_start_month": args.start,
        "requested_end_month": args.end,
        "retrieved_at_utc": pd.Timestamp.now("UTC").isoformat(),
        "checksum_verification": not args.no_checksum,
        "provenance": provenance,
    }
    (out / "DATA_SOURCE.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
