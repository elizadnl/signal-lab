from pathlib import Path

import numpy as np
import pandas as pd

from signallab.pipeline import _asset_holdout_transfer


def _write_asset(path: Path, symbol: str, seed: int, n: int = 620) -> None:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    ret = rng.normal(0.0005, 0.018, n)
    # Add weak persistence so candidate lookbacks are not all identical.
    ret[1:] += 0.12 * ret[:-1]
    close = 100 * np.exp(np.cumsum(ret))
    frame = pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.exp(rng.normal(10, 0.4, n)),
    })
    frame.to_csv(path / f"{symbol}.csv", index=False)


def test_asset_holdout_uses_other_assets_and_chronological_cutoff(tmp_path: Path):
    for i, symbol in enumerate(("BTCUSDT", "ETHUSDT", "SOLUSDT"), start=1):
        _write_asset(tmp_path, symbol, 100 + i)
    result = _asset_holdout_transfer(
        tmp_path, "BTCUSDT", ("ETHUSDT", "SOLUSDT"), "momentum", 10.0
    )
    assert result["available"] is True
    assert result["target"] == "BTCUSDT"
    assert result["donors"] == ["ETHUSDT", "SOLUSDT"]
    assert "BTCUSDT" not in result["donors"]
    assert result["train_end"] < result["test_start"]
    assert result["observations"] >= 30


def test_target_data_cannot_change_transferred_lookback_choice(tmp_path: Path):
    for i, symbol in enumerate(("BTCUSDT", "ETHUSDT", "SOLUSDT"), start=1):
        _write_asset(tmp_path, symbol, 200 + i)
    before = _asset_holdout_transfer(
        tmp_path, "BTCUSDT", ("ETHUSDT", "SOLUSDT"), "momentum", 10.0
    )
    target = pd.read_csv(tmp_path / "BTCUSDT.csv")
    # Heavily alter the target path; donor-only parameter selection must not move.
    target["close"] = target["close"] * np.exp(np.linspace(0, 2.0, len(target)))
    target["open"] = target["close"]
    target["high"] = target["close"] * 1.01
    target["low"] = target["close"] * 0.99
    target.to_csv(tmp_path / "BTCUSDT.csv", index=False)
    after = _asset_holdout_transfer(
        tmp_path, "BTCUSDT", ("ETHUSDT", "SOLUSDT"), "momentum", 10.0
    )
    assert before["chosen_lookback"] == after["chosen_lookback"]
    assert before["donor_mean_train_sharpe"] == after["donor_mean_train_sharpe"]
