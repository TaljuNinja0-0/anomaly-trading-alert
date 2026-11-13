"""ML anomaly stage: Isolation Forest over the statistical-rule features.

Reuses the same baseline (-60..-31 trading days) / observation (-30..+5)
windows as backtest.run_case, fitting the model on the baseline ("normal")
period and flagging observation-window rows it calls outliers.
"""

import pandas as pd
from sklearn.ensemble import IsolationForest

from src.backtest import (
    BASELINE_END_OFFSET,
    OBS_START_OFFSET,
    OBS_END_OFFSET,
    find_designation_row,
    _format_date,
)
from src.detector import volume_zscore, price_return_zscore, composite_score

# The stat rule's 30-row baseline (-60..-31) is enough for a mean/std
# estimate, but IsolationForest trained on only 30 rows is noisy: a tiny,
# low-cardinality sample gives the model an unstable decision boundary
# (verified empirically -- see ledger). A longer "normal" lookback gives
# it more to learn from. The window still ends at the same day
# (BASELINE_END_OFFSET), just starts earlier. kis_client.get_daily_price
# now paginates across multiple calls, so this isn't bounded by a single
# call's ~100-row cap -- the caller just needs to fetch a wide enough
# calendar range (see run_backtest.py).
ML_BASELINE_LOOKBACK = 100
ML_BASELINE_START_OFFSET = BASELINE_END_OFFSET - ML_BASELINE_LOOKBACK + 1


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    vol_z = volume_zscore(df["volume"])
    price_z = price_return_zscore(df["close"])
    composite = composite_score(vol_z, price_z)
    volatility_20d = df["close"].pct_change().rolling(20).std()
    return pd.DataFrame(
        {
            "vol_z": vol_z,
            "price_z": price_z,
            "composite": composite,
            "volatility_20d": volatility_20d,
        }
    )


def run_case_ml(df: pd.DataFrame, case: dict, contamination=0.05, random_state: int = 42) -> dict:
    """contamination=0.05 (not sklearn's 'auto') is an empirical choice: on
    the 4 real cases, 'auto' still caught all 4 but with 8-58% false-positive
    rates; 0.05 keeps all 4 detections while cutting false positives to
    2.8-19%. 0.02 loses every detection -- 0.05 is close to the edge where
    the model stops firing at all, not an arbitrary round number."""
    result = {
        "name": case["name"],
        "ticker": case["ticker"],
        "designation_date": case["designation_date"],
        "effective_date": None,
        "status": "ok",
        "lead_time_days": None,
        "false_positive_rate": None,
        "flagged_rows": [],
    }

    d = find_designation_row(df, case["designation_date"])
    result["effective_date"] = _format_date(df["date"].iloc[d])

    baseline_start = d + ML_BASELINE_START_OFFSET
    baseline_end = d + BASELINE_END_OFFSET
    obs_start = d + OBS_START_OFFSET
    obs_end = d + OBS_END_OFFSET

    if baseline_start < 0:
        result["status"] = "insufficient_data"
        return result

    features = build_features(df)
    baseline_features = features.loc[baseline_start:baseline_end]
    obs_features = features.loc[obs_start:obs_end]

    if baseline_features.isna().any().any() or obs_features.isna().any().any():
        result["status"] = "insufficient_data"
        return result

    model = IsolationForest(contamination=contamination, random_state=random_state)
    model.fit(baseline_features)

    predictions = model.predict(obs_features)  # -1 = outlier, 1 = normal
    flagged = obs_features.index[predictions == -1]
    result["flagged_rows"] = list(flagged)

    if len(flagged) > 0:
        result["lead_time_days"] = d - flagged[0]

    result["false_positive_rate"] = len(flagged) / len(obs_features)
    return result
