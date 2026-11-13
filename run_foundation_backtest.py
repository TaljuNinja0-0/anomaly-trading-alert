"""Foundation-model stage entry point.

Separate from run_backtest.py because this stage needs chronos-forecasting
and torch>=2.4, which live only in the chronosbolt_env conda env (this
project's requirements.txt intentionally doesn't pull them into the main
env, to avoid the torch 2.3/2.6 version conflict with the DL stage). Run
with:

    /home/user/miniconda3/envs/chronosbolt_env/bin/python run_foundation_backtest.py
"""

import os

from dotenv import load_dotenv

from src.cases import CASES
from src.foundation_detector import load_pipeline, run_case_foundation
from src.report import write_results_csv

OUTPUT_DIR = "output"


def main():
    load_dotenv()
    app_key = os.environ["KIS_APP_KEY"]
    app_secret = os.environ["KIS_APP_SECRET"]

    # kis_client.get_access_token/get_daily_price have no chronos
    # dependency, so this still works from this env.
    import time

    import pandas as pd
    from src.kis_client import get_access_token, get_daily_price

    access_token = get_access_token(app_key, app_secret)
    pipeline = load_pipeline()

    results = []
    for i, case in enumerate(CASES):
        if i > 0:
            time.sleep(1)

        designation = pd.Timestamp(case["designation_date"])
        start_date = (designation - pd.Timedelta(days=250)).strftime("%Y%m%d")
        end_date = (designation + pd.Timedelta(days=10)).strftime("%Y%m%d")
        df = get_daily_price(access_token, app_key, app_secret, case["ticker"], start_date, end_date)

        result = run_case_foundation(df, case, pipeline)
        results.append(result)
        print(result)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    write_results_csv(results, os.path.join(OUTPUT_DIR, "results_foundation.csv"))


if __name__ == "__main__":
    main()
