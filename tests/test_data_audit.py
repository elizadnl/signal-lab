import pandas as pd

from signallab.data_audit import audit_market_frame


def _frame():
    dates = pd.date_range('2025-01-01', periods=5, freq='D', tz='UTC')
    return pd.DataFrame({
        'date': dates,
        'open': [10, 11, 12, 13, 14],
        'high': [12, 13, 14, 15, 16],
        'low': [9, 10, 11, 12, 13],
        'close': [11, 12, 13, 14, 15],
        'volume': [100, 110, 120, 130, 140],
    })


def test_clean_daily_frame_passes_audit():
    audit = audit_market_frame(_frame())
    assert audit['clean'] is True
    assert audit['missing_calendar_days'] == 0
    assert audit['invalid_ohlc_rows'] == 0


def test_gap_and_bad_bar_are_detected():
    df = _frame().drop(index=2).reset_index(drop=True)
    df.loc[1, 'high'] = 9
    audit = audit_market_frame(df)
    assert audit['clean'] is False
    assert audit['missing_calendar_days'] == 1
    assert audit['invalid_ohlc_rows'] == 1


def test_zero_volume_is_flagged_for_daily_crypto():
    df = _frame()
    df.loc[3, 'volume'] = 0
    audit = audit_market_frame(df)
    assert audit['clean'] is False
    assert audit['zero_volume_rows'] == 1
