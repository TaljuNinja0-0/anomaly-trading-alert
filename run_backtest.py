"""End-to-end entry point: fetch, detect, backtest, and report."""

import os
import time

import pandas as pd
from dotenv import load_dotenv

from src.kis_client import get_access_token, get_daily_price
from src.cases import CASES
from src.detector import volume_zscore, price_return_zscore, composite_score
from src.backtest import run_case
from src.report import plot_case, write_results_csv

OUTPUT_DIR = "output"


def main():
    load_dotenv()
    app_key = os.environ["KIS_APP_KEY"]
    app_secret = os.environ["KIS_APP_SECRET"]

    access_token = get_access_token(app_key, app_secret)

    results = []
    for i, case in enumerate(CASES):
        if i > 0:
            time.sleep(1)  # be polite to the quote endpoint between calls

        designation = pd.Timestamp(case["designation_date"])
        # Baseline needs 60 trading rows plus ~20 for the detector's own
        # rolling-window warm-up before the designation row; ~135 calendar
        # days covers that with margin while staying under the KIS
        # 100-row-per-call cap (see Global Constraints in the plan).
        start_date = (designation - pd.Timedelta(days=135)).strftime("%Y%m%d")
        end_date = (designation + pd.Timedelta(days=10)).strftime("%Y%m%d")

        df = get_daily_price(access_token, app_key, app_secret, case["ticker"], start_date, end_date)

        score = composite_score(volume_zscore(df["volume"]), price_return_zscore(df["close"]))
        result = run_case(df, case)
        results.append(result)

        if result["status"] == "ok":
            plot_case(df, score, case, OUTPUT_DIR, breach_level=result["breach_level"])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    write_results_csv(results, os.path.join(OUTPUT_DIR, "results.csv"))

    for r in results:
        print(r)


if __name__ == "__main__":
    main()
