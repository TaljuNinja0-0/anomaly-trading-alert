"""End-to-end entry point: fetch, detect, backtest, and report."""

import os
import time

import pandas as pd
from dotenv import load_dotenv

from src.kis_client import get_access_token, get_daily_price
from src.cases import CASES
from src.detector import volume_zscore, price_return_zscore, composite_score
from src.backtest import run_case
from src.ml_detector import run_case_ml
from src.dl_detector import run_case_dl
from src.report import plot_case, write_results_csv

OUTPUT_DIR = "output"


def main():
    load_dotenv()
    app_key = os.environ["KIS_APP_KEY"]
    app_secret = os.environ["KIS_APP_SECRET"]

    access_token = get_access_token(app_key, app_secret)

    results = []
    results_ml = []
    results_dl = []
    for i, case in enumerate(CASES):
        if i > 0:
            time.sleep(1)  # be polite to the quote endpoint between calls

        designation = pd.Timestamp(case["designation_date"])
        # The ML stage's baseline (ml_detector.ML_BASELINE_LOOKBACK=100)
        # needs ~100+31+20(warm-up) ~= 151 trading rows before the
        # designation row; kis_client.get_daily_price now paginates across
        # multiple calls, so a wide calendar range is fine here.
        start_date = (designation - pd.Timedelta(days=250)).strftime("%Y%m%d")
        end_date = (designation + pd.Timedelta(days=10)).strftime("%Y%m%d")

        df = get_daily_price(access_token, app_key, app_secret, case["ticker"], start_date, end_date)

        score = composite_score(volume_zscore(df["volume"]), price_return_zscore(df["close"]))
        result = run_case(df, case)
        results.append(result)

        result_ml = run_case_ml(df, case)
        results_ml.append(result_ml)

        result_dl = run_case_dl(df, case)
        results_dl.append(result_dl)

        if result["status"] == "ok":
            plot_case(df, score, case, OUTPUT_DIR, breach_level=result["breach_level"])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    write_results_csv(results, os.path.join(OUTPUT_DIR, "results.csv"))
    write_results_csv(results_ml, os.path.join(OUTPUT_DIR, "results_ml.csv"))
    write_results_csv(results_dl, os.path.join(OUTPUT_DIR, "results_dl.csv"))

    print("=== 통계룰 (results.csv) ===")
    for r in results:
        print(r)
    print("=== ML / IsolationForest (results_ml.csv) ===")
    for r in results_ml:
        print(r)
    print("=== DL / LSTM Autoencoder (results_dl.csv) ===")
    for r in results_dl:
        print(r)


if __name__ == "__main__":
    main()
