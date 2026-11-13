import numpy as np
import pandas as pd

from run_universe_scan import run_scan
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
