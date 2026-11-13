"""Daily universe scan: KOSPI+KOSDAQ top-N by market cap, ML anomaly check."""

import fcntl
import os
import sys
import time

import pandas as pd
from dotenv import load_dotenv

from src.kis_client import get_access_token, get_daily_price
from src.universe import get_market_cap_ranking
from src.scan import is_data_fresh, scan_today
from src.storage import init_db, write_run_results, record_run_failure, get_latest_run

LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".universe_scan.lock")

MIN_UNIVERSE_SIZE = 150
SENTINEL_TICKER = "005930"  # 삼성전자 -- if a parse of the universe source is
# broken (KIS changes the master-file layout, a download is truncated,
# etc.), this is virtually certain to be missing or the list implausibly
# short. Catches that before it corrupts today's results.


def _validate_universe(universe):
    """Returns None if the universe looks sane, otherwise a reason string."""
    if len(universe) < MIN_UNIVERSE_SIZE:
        return f"유니버스 크기가 비정상적으로 작음 ({len(universe)} < {MIN_UNIVERSE_SIZE})"
    if not any(e["ticker"] == SENTINEL_TICKER for e in universe):
        return f"유니버스에 기준 종목({SENTINEL_TICKER})이 없음 -- 파싱이 깨졌을 가능성"
    return None


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


def healthcheck(db_path: str = "universe_scan.db") -> int:
    """Prints a one-line status and returns a process exit code (0 ok, 1
    not ok) -- cheap enough to run by hand whenever you think to check,
    no need to read raw SQLite output."""
    init_db(db_path)  # migrates an older db missing run_status/reason
    latest = get_latest_run(db_path)
    if latest is None:
        print("상태: 기록 없음 (한 번도 성공적으로 실행된 적 없음)")
        return 1

    days_old = (pd.Timestamp.now().normalize() - pd.Timestamp(latest["run_date"])).days
    if latest["run_status"] != "ok":
        print(f"상태: 실패 (마지막 시도 {latest['run_date']}, 사유: {latest['reason']})")
        return 1
    if days_old > 3:
        print(f"상태: 경고 -- 마지막 성공이 {days_old}일 전({latest['run_date']})")
        return 1
    if latest["universe_size"] > 0 and latest["ok_count"] / latest["universe_size"] < 0.5:
        print(
            f"상태: 경고 -- OK 비율이 낮음 ({latest['ok_count']}/{latest['universe_size']}, "
            f"{latest['run_date']}) -- 휴장일이 아니라면 KIS 쪽 데이터 지연/형식 변경 의심"
        )
        return 1

    print(
        f"상태: 정상 (마지막 성공 {latest['run_date']}, "
        f"{latest['ok_count']}/{latest['universe_size']} 처리, "
        f"이상치 {latest['anomaly_count']}건)"
    )
    return 0


def main(limit: int = 200, db_path: str = "universe_scan.db") -> None:
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("이미 다른 스캔이 실행 중이라 건너뜀 (lock 보유 중)")
        return

    run_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    started_at = pd.Timestamp.now().isoformat()
    init_db(db_path)

    try:
        try:
            load_dotenv()
            app_key = os.environ["KIS_APP_KEY"]
            app_secret = os.environ["KIS_APP_SECRET"]

            started = time.time()
            token = get_access_token(app_key, app_secret)
            universe = get_market_cap_ranking(token, app_key, app_secret, limit=limit)

            validation_error = _validate_universe(universe)
            if validation_error:
                raise RuntimeError(validation_error)

            today = pd.Timestamp.now()
            today_yyyymmdd = today.strftime("%Y%m%d")
            start_date = (today - pd.Timedelta(days=200)).strftime("%Y%m%d")
            end_date = today_yyyymmdd

            def fetch_price(ticker):
                return get_daily_price(token, app_key, app_secret, ticker, start_date, end_date)

            results = run_scan(universe, fetch_price, today_yyyymmdd)

            elapsed_seconds = time.time() - started
            counts = write_run_results(db_path, run_date, started_at, len(universe), elapsed_seconds, results)

            print(f"=== {run_date} 스캔 완료 ({elapsed_seconds:.1f}초, 유니버스 {len(universe)}종목) ===")
            print(counts)
        except Exception as e:
            record_run_failure(db_path, run_date, started_at, str(e))
            raise
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


if __name__ == "__main__":
    if "--healthcheck" in sys.argv:
        sys.exit(healthcheck())
    main()
