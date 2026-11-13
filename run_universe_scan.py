"""Daily universe scan: KOSPI+KOSDAQ top-N by market cap, ML anomaly check."""

import os
import time

import pandas as pd
from dotenv import load_dotenv

from src.kis_client import get_access_token, get_daily_price
from src.universe import get_market_cap_ranking
from src.scan import is_data_fresh, scan_today
from src.storage import init_db, record_run, record_result, clear_results


def main(limit: int = 200, db_path: str = "universe_scan.db") -> None:
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

    # A rerun for the same day (manual retrigger, previous partial run)
    # must not leave stale per-ticker rows behind for a universe that's
    # since changed.
    clear_results(db_path, run_date)

    counts = {"ok": 0, "insufficient_data": 0, "stale": 0, "error": 0, "anomaly": 0}

    for i, entry in enumerate(universe):
        if i > 0:
            time.sleep(0.3)
        try:
            df = get_daily_price(token, app_key, app_secret, entry["ticker"], start_date, end_date)
            if not df.empty and is_data_fresh(df["date"].iloc[-1], today_yyyymmdd):
                result = scan_today(df)
            else:
                result = {"status": "stale", "is_anomaly": None, "anomaly_score": None}
            record_result(db_path, run_date, entry["ticker"], entry["name"],
                           result["status"], result["is_anomaly"], result["anomaly_score"])
            counts[result["status"]] += 1
            if result["is_anomaly"]:
                counts["anomaly"] += 1
        except Exception as e:
            record_result(db_path, run_date, entry["ticker"], entry["name"], "error", None, None)
            counts["error"] += 1
            print(f"{entry['ticker']} 처리 실패: {e}")

    elapsed_seconds = time.time() - started
    record_run(db_path, run_date, started_at, len(universe), elapsed_seconds,
               counts["ok"], counts["insufficient_data"], counts["stale"],
               counts["error"], counts["anomaly"])

    print(f"=== {run_date} 스캔 완료 ({elapsed_seconds:.1f}초, 유니버스 {len(universe)}종목) ===")
    print(counts)


if __name__ == "__main__":
    main()
