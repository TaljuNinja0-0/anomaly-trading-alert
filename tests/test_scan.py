import numpy as np
import pandas as pd

from src.scan import classify_with_isolation_forest, is_data_fresh, scan_today
from src.ml_detector import ML_BASELINE_LOOKBACK


def _dates(n, start="20260101"):
    base = pd.Timestamp(start)
    return [(base + pd.Timedelta(days=i)).strftime("%Y%m%d") for i in range(n)]


def test_classify_with_isolation_forest_flags_outlier():
    rng = np.random.RandomState(0)
    baseline = pd.DataFrame(rng.normal(0, 0.1, size=(60, 4)))
    target = pd.DataFrame([[5.0, 5.0, 5.0, 5.0]])
    predictions, scores = classify_with_isolation_forest(baseline, target)
    assert predictions[0] == -1
    assert scores[0] < 0


def test_is_data_fresh_true_when_dates_match():
    assert is_data_fresh("20261113", "20261113") is True


def test_is_data_fresh_false_when_dates_differ():
    assert is_data_fresh("20261112", "20261113") is False


def test_scan_today_insufficient_data_when_too_short():
    n = ML_BASELINE_LOOKBACK  # one row short of the required baseline+today
    df = pd.DataFrame({
        "date": _dates(n),
        "close": [100.0 + i * 0.1 for i in range(n)],
        "volume": [1000 + i * 5 for i in range(n)],
    })
    result = scan_today(df)
    assert result["status"] == "insufficient_data"
    assert result["is_anomaly"] is None


def test_scan_today_detects_known_anomaly():
    n = ML_BASELINE_LOOKBACK + 30  # baseline + detector warm-up (~21 rows) + today, with margin
    rng = np.random.RandomState(0)
    close = 100 + np.cumsum(rng.normal(0, 0.15, n))
    volume = 1000 + rng.normal(0, 25, n)
    close[-1] = close[-2] * 1.8  # today is a sharp spike
    volume[-1] = 50000
    df = pd.DataFrame({"date": _dates(n), "close": close, "volume": volume})
    result = scan_today(df)
    assert result["status"] == "ok"
    assert result["is_anomaly"] is True
