import json
from pathlib import Path
import numpy as np
import pandas as pd

from signallab.pipeline import analyze_symbol


def test_walk_forward_evaluation_starts_after_training_window(tmp_path: Path):
    rng = np.random.default_rng(12)
    n = 900
    dates = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    ret = rng.normal(0.0003, 0.02, n)
    close = 100 * np.exp(np.cumsum(ret))
    df = pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.exp(rng.normal(10, 0.5, n)),
    })
    df.to_csv(tmp_path / "BTCUSDT.csv", index=False)
    (tmp_path / "DATA_SOURCE.json").write_text(json.dumps({"kind": "test", "label": "test", "claim_status": "test"}))
    run = analyze_symbol(tmp_path, "BTCUSDT", "momentum", fee_bps=10.0, mode="walk_forward")
    assert run["start_date"] == str(dates[365].date())
    assert run["robustness"]["evaluation_start"] == str(dates[365].date())
    assert run["equity"][0]["date"] == str(dates[365].date())


def test_new_robustness_panels_are_populated(tmp_path: Path):
    rng = np.random.default_rng(33)
    n = 900
    dates = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    ret = rng.normal(0.0004, 0.018, n)
    close = 100 * np.exp(np.cumsum(ret))
    df = pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.exp(rng.normal(10, 0.5, n)),
    })
    df.to_csv(tmp_path / "BTCUSDT.csv", index=False)
    (tmp_path / "DATA_SOURCE.json").write_text(json.dumps({"kind": "test", "label": "test", "claim_status": "test"}))
    run = analyze_symbol(tmp_path, "BTCUSDT", "momentum", fee_bps=10.0, mode="walk_forward")
    assert [x["delay_days"] for x in run["execution_delay_stress"]] == [1, 2, 3, 5]
    assert len(run["parameter_sensitivity"]["rows"]) == 5
    assert 0 <= run["parameter_sensitivity"]["plateau_score"] <= 1
    assert run["return_concentration"]["active_sessions"] >= 0
