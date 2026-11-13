"""Daily universe scan: KOSPI+KOSDAQ top-N by market cap, ML anomaly check."""

import fcntl
import os
import time

import pandas as pd
from dotenv import load_dotenv

from src.kis_client import get_access_token, get_daily_price
from src.universe import get_market_cap_ranking
from src.scan import is_data_fresh, scan_today
from src.storage import init_db, write_run_results

LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".universe_scan.lock")


def run_scan(universe, fetch_price, today_yyyymmdd, sleep_fn=time.sleep):
    """Pure except for the injected fetch_price/sleep_fn -- no KIS calls,
    no SQLite -- so failure/stale/insufficient_data paths are testable
    without a live account or a real clock."""
    results = []
    for i, entry in enumerate(universe):
        if i > 0:
            sleep_fn(0.3)
        try:
            df = fetch_price(entry["ticker"])
            if not df.empty and is_data_fresh(df["date"].iloc[-1], today_yyyymmdd):
                scan_result = scan_today(df)
            else:
                scan_result = {"status": "stale", "is_anomaly": None, "anomaly_score": None}
        except Exception as e:
            scan_result = {"status": "error", "is_anomaly": None, "anomaly_score": None}
            print(f"{entry['ticker']} 처리 실패: {e}")
        results.append({"ticker": entry["ticker"], "name": entry["name"], **scan_result})
    return results


def main(limit: int = 200, db_path: str = "universe_scan.db") -> None:
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("이미 다른 스캔이 실행 중이라 건너뜀 (lock 보유 중)")
        return

    try:
        load_dotenv()
        app_key = os.environ["KIS_APP_KEY"]
        app_secret = os.environ["KIS_APP_SECRET"]

        started = time.time()
        started_at = pd.Timestamp.now().isoformat()

        token = get_access_token(app_key, app_secret)
        init_db(db_path)

        universe = get_market_cap_ranking(token, app_key, app_secret, limit=limit)

        today = pd.Timestamp.now()
        today_yyyymmdd = today.strftime("%Y%m%d")
        run_date = today.strftime("%Y-%m-%d")
        start_date = (today - pd.Timedelta(days=200)).strftime("%Y%m%d")
        end_date = today_yyyymmdd

        def fetch_price(ticker):
            return get_daily_price(token, app_key, app_secret, ticker, start_date, end_date)

        results = run_scan(universe, fetch_price, today_yyyymmdd)

        elapsed_seconds = time.time() - started
        counts = write_run_results(db_path, run_date, started_at, len(universe), elapsed_seconds, results)

        print(f"=== {run_date} 스캔 완료 ({elapsed_seconds:.1f}초, 유니버스 {len(universe)}종목) ===")
        print(counts)
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


if __name__ == "__main__":
    main()
