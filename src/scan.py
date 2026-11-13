"""Shared IsolationForest classify helper + today-only judgment.

Used both by ml_detector.run_case_ml (backtest, date-anchored) and
scan_today (live daily batch, rolling-window "is today anomalous").
"""

import pandas as pd
from sklearn.ensemble import IsolationForest

from src.ml_detector import ML_BASELINE_LOOKBACK, build_features


def classify_with_isolation_forest(
    baseline_features: pd.DataFrame,
    target_features: pd.DataFrame,
    contamination: float = 0.05,
    random_state: int = 42,
):
    model = IsolationForest(contamination=contamination, random_state=random_state)
    model.fit(baseline_features)
    predictions = model.predict(target_features)
    scores = model.decision_function(target_features)
    return predictions, scores


def is_data_fresh(last_date: str, today: str) -> bool:
    return last_date == today


def scan_today(df: pd.DataFrame, contamination: float = 0.05, random_state: int = 42) -> dict:
    result = {"status": "ok", "is_anomaly": None, "anomaly_score": None}

    features = build_features(df)
    if len(features) < ML_BASELINE_LOOKBACK + 1:
        result["status"] = "insufficient_data"
        return result

    baseline = features.iloc[-(ML_BASELINE_LOOKBACK + 1):-1]
    target = features.iloc[[-1]]

    if baseline.isna().any().any() or target.isna().any().any():
        result["status"] = "insufficient_data"
        return result

    predictions, scores = classify_with_isolation_forest(baseline, target, contamination, random_state)
    result["is_anomaly"] = bool(predictions[0] == -1)
    result["anomaly_score"] = float(scores[0])
    return result
