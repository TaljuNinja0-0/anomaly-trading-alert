import numpy as np
import pandas as pd

import sqlite3

from run_universe_scan import run_scan, _validate_universe, healthcheck
from src.ml_detector import ML_BASELINE_LOOKBACK


def _dates(n, start="20260101"):
    base = pd.Timestamp(start)
    return [(base + pd.Timedelta(days=i)).strftime("%Y%m%d") for i in range(n)]


def _fresh_df(today_yyyymmdd, n=ML_BASELINE_LOOKBACK + 30):
    rng = np.random.RandomState(0)
    close = 100 + np.cumsum(rng.normal(0, 0.15, n))
    volume = 1000 + rng.normal(0, 25, n)
    dates = _dates(n)
    dates[-1] = today_yyyymmdd
    return pd.DataFrame({"date": dates, "close": close, "volume": volume})


TODAY = "20261113"


def test_run_scan_isolates_one_tickers_failure_from_the_rest():
    universe = [
        {"ticker": "000001", "name": "정상종목"},
        {"ticker": "000002", "name": "터지는종목"},
        {"ticker": "000003", "name": "정상종목2"},
    ]

    def fetch_price(ticker):
        if ticker == "000002":
            raise RuntimeError("KIS 호출 실패")
        return _fresh_df(TODAY)

    results = run_scan(universe, fetch_price, TODAY, sleep_fn=lambda s: None)

    by_ticker = {r["ticker"]: r for r in results}
    assert by_ticker["000001"]["status"] == "ok"
    assert by_ticker["000002"]["status"] == "error"
    assert by_ticker["000003"]["status"] == "ok"  # third ticker still processed


def test_run_scan_marks_non_fresh_data_as_stale():
    universe = [{"ticker": "000001", "name": "어제까지만있음"}]

    def fetch_price(ticker):
        df = _fresh_df(TODAY)
        df.loc[df.index[-1], "date"] = "20261112"  # not today
        return df

    results = run_scan(universe, fetch_price, TODAY, sleep_fn=lambda s: None)
    assert results[0]["status"] == "stale"
    assert results[0]["is_anomaly"] is None


def test_run_scan_marks_short_history_as_insufficient_data():
    universe = [{"ticker": "000001", "name": "상장한지얼마안됨"}]

    def fetch_price(ticker):
        return _fresh_df(TODAY, n=20)

    results = run_scan(universe, fetch_price, TODAY, sleep_fn=lambda s: None)
    assert results[0]["status"] == "insufficient_data"


def _make_universe(n, include_sentinel=True):
    universe = [{"ticker": str(i).zfill(6), "name": f"종목{i}"} for i in range(n)]
    if include_sentinel:
        universe.append({"ticker": "005930", "name": "삼성전자"})
    return universe


def test_validate_universe_accepts_a_normal_sized_universe():
    assert _validate_universe(_make_universe(200)) is None


def test_validate_universe_rejects_a_universe_that_is_too_small():
    reason = _validate_universe(_make_universe(10, include_sentinel=False))
    assert reason is not None
    assert "10" in reason


def test_validate_universe_rejects_a_universe_missing_the_sentinel_ticker():
    reason = _validate_universe(_make_universe(200, include_sentinel=False))
    assert reason is not None
    assert "005930" in reason


def test_healthcheck_runs_against_a_pre_migration_db(tmp_path):
    # A db from before run_status/reason existed -- healthcheck must not
    # crash just because it's the first thing to touch an old db today.
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE scan_runs (
            run_date TEXT PRIMARY KEY, started_at TEXT, universe_size INTEGER,
            elapsed_seconds REAL, ok_count INTEGER, insufficient_count INTEGER,
            stale_count INTEGER, error_count INTEGER, anomaly_count INTEGER
        )
        """
    )
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    conn.execute("INSERT INTO scan_runs VALUES (?, 't', 200, 1.0, 200, 0, 0, 0, 14)", (today,))
    conn.commit()
    conn.close()

    exit_code = healthcheck(db_path)
    assert exit_code == 0


def test_healthcheck_warns_when_almost_nothing_processed_ok(tmp_path):
    # run_status=='ok' (it didn't crash) but nearly every ticker came
    # back stale/error on a weekday would mean something upstream (KIS
    # publishing late, a format change not caught by _validate_universe)
    # is wrong -- "didn't crash" isn't the same as "worked".
    from src.storage import init_db, write_run_results

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    results = [{"ticker": str(i), "name": "x", "status": "stale", "is_anomaly": None, "anomaly_score": None} for i in range(200)]
    write_run_results(db_path, today, "t", 200, 10.0, results)

    exit_code = healthcheck(db_path)
    assert exit_code == 1
