"""Baseline/observation window logic and lead-time calculation."""

import pandas as pd

from src.detector import volume_zscore, price_return_zscore, composite_score

BASELINE_START_OFFSET = -60
BASELINE_END_OFFSET = -31
OBS_START_OFFSET = -30
OBS_END_OFFSET = 5


def _normalize_date(date_str: str) -> str:
    """cases.py uses YYYY-MM-DD; df['date'] (from kis_client) uses YYYYMMDD."""
    return date_str.replace("-", "")


def find_designation_row(df: pd.DataFrame, designation_date: str) -> int:
    target = _normalize_date(designation_date)
    dates = df["date"]
    exact = dates[dates == target]
    if len(exact) > 0:
        return exact.index[0]
    after = dates[dates > target]
    if len(after) > 0:
        return after.index[0]
    raise ValueError(f"no row on or after designation date {designation_date}")


def _format_date(yyyymmdd: str) -> str:
    return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


# Below this, the baseline's own std is treated as zero (floating-point
# noise from rolling-window arithmetic on a near-constant series, not a
# genuine non-zero spread) -- see test_run_case_undetermined_when_baseline_variance_is_zero.
ZERO_SIGMA_EPSILON = 1e-3


def run_case(df: pd.DataFrame, case: dict, threshold: float = 2.5) -> dict:
    result = {
        "name": case["name"],
        "ticker": case["ticker"],
        "designation_date": case["designation_date"],
        "effective_date": None,
        "status": "ok",
        "lead_time_days": None,
        "false_positive_rate": None,
        "breach_level": None,
        "flagged_rows": [],
    }

    d = find_designation_row(df, case["designation_date"])
    result["effective_date"] = _format_date(df["date"].iloc[d])

    baseline_start = d + BASELINE_START_OFFSET
    baseline_end = d + BASELINE_END_OFFSET
    obs_start = d + OBS_START_OFFSET
    obs_end = d + OBS_END_OFFSET

    if baseline_start < 0:
        result["status"] = "insufficient_data"
        return result

    score = composite_score(
        volume_zscore(df["volume"]), price_return_zscore(df["close"])
    )

    baseline_scores = score.loc[baseline_start:baseline_end]
    if baseline_scores.isna().any():
        # Enough rows exist, but some fall inside the detector's own
        # rolling-window warm-up and are NaN -- the baseline isn't
        # actually fully populated.
        result["status"] = "insufficient_data"
        return result

    mu = baseline_scores.mean()
    sigma = baseline_scores.std()
    if pd.isna(sigma) or sigma < ZERO_SIGMA_EPSILON:
        result["status"] = "undetermined"
        return result

    breach_level = mu + threshold * sigma
    result["breach_level"] = breach_level

    obs_scores = score.loc[obs_start:obs_end]
    breaches = obs_scores[obs_scores > breach_level]

    result["flagged_rows"] = list(breaches.index)
    if len(breaches) > 0:
        first_breach_row = breaches.index[0]
        result["lead_time_days"] = d - first_breach_row
    else:
        result["lead_time_days"] = None

    result["false_positive_rate"] = len(breaches) / len(obs_scores)
    return result
