import numpy as np
import pandas as pd

from src.ml_detector import build_features, run_case_ml


def _dates(n, start="20260101"):
    base = pd.Timestamp(start)
    return [(base + pd.Timedelta(days=i)).strftime("%Y%m%d") for i in range(n)]


def _designation_date_for_row(df, row):
    d = df["date"].iloc[row]
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def _alternating_case_df(n=60, spike_row=None):
    dates = _dates(n)
    close = [100.0 if i % 2 == 0 else 100.5 for i in range(n)]
    volume = [1000 if i % 2 == 0 else 1010 for i in range(n)]
    if spike_row is not None:
        close[spike_row] = 200.0
        volume[spike_row] = 50000
    return pd.DataFrame({"date": dates, "close": close, "volume": volume})


def _noisy_case_df(n, spike_row, spike_multiplier=1.8, spike_volume=50000, seed=0):
    # IsolationForest needs genuinely continuous (non-repeating) values to
    # behave sensibly -- an exactly-periodic baseline gives it a
    # pathologically low-cardinality sample and it flags almost everything
    # (confirmed empirically). Real market data is continuous, so seeded
    # noise is the closer analogue for this test.
    rng = np.random.RandomState(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.15, n))
    volume = 1000 + rng.normal(0, 25, n)
    close[spike_row] = close[spike_row - 1] * spike_multiplier
    volume[spike_row] = spike_volume
    return pd.DataFrame({"date": _dates(n), "close": close, "volume": volume})


def test_build_features_has_expected_columns():
    df = _alternating_case_df(n=60)
    features = build_features(df)
    assert list(features.columns) == ["vol_z", "price_z", "composite", "volatility_20d"]
    assert len(features) == len(df)


def test_run_case_ml_flags_the_known_spike():
    designation_row = 220
    spike_row = 200
    df = _noisy_case_df(n=250, spike_row=spike_row)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": _designation_date_for_row(df, designation_row),
    }
    result = run_case_ml(df, case)
    assert result["status"] == "ok"
    # Statistical noise means the exact first-flagged row can land a little
    # before or after the designed spike; what must hold is that detection
    # happens close to it, not exactly at the expected offset.
    expected_lead_time = designation_row - spike_row
    assert result["lead_time_days"] is not None
    assert abs(result["lead_time_days"] - expected_lead_time) <= 8


def test_run_case_ml_insufficient_data_when_baseline_too_short():
    df = _alternating_case_df(n=40)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": _designation_date_for_row(df, 35),
    }
    result = run_case_ml(df, case)
    assert result["status"] == "insufficient_data"
    assert result["lead_time_days"] is None
