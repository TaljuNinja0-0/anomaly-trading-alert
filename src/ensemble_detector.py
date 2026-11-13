"""Ensemble stage: union of the stat rule's and ML's flagged observation
days. Tests the hypothesis that the stat rule (cheap, low false-positive,
good at sharp single-day spikes) and ML (needs more data/compute, good at
gradual multi-day trend shifts) are complementary rather than redundant.
"""

from src.backtest import run_case
from src.ml_detector import run_case_ml
from src.backtest import find_designation_row, _format_date, OBS_START_OFFSET, OBS_END_OFFSET


def combine_flags(flagged_a, flagged_b, d: int, total_obs_days: int) -> dict:
    flagged_rows = sorted(set(flagged_a) | set(flagged_b))
    lead_time_days = d - flagged_rows[0] if flagged_rows else None
    false_positive_rate = len(flagged_rows) / total_obs_days if total_obs_days else None
    return {
        "flagged_rows": flagged_rows,
        "lead_time_days": lead_time_days,
        "false_positive_rate": false_positive_rate,
    }


def run_case_ensemble(df, case: dict) -> dict:
    stat_result = run_case(df, case)
    ml_result = run_case_ml(df, case)

    result = {
        "name": case["name"],
        "ticker": case["ticker"],
        "designation_date": case["designation_date"],
        "effective_date": None,
        "status": "ok",
        "lead_time_days": None,
        "false_positive_rate": None,
        "stat_status": stat_result["status"],
        "ml_status": ml_result["status"],
    }

    stat_usable = stat_result["status"] == "ok"
    ml_usable = ml_result["status"] == "ok"

    if not stat_usable and not ml_usable:
        result["status"] = "insufficient_data"
        return result

    d = find_designation_row(df, case["designation_date"])
    result["effective_date"] = _format_date(df["date"].iloc[d])
    obs_start = d + OBS_START_OFFSET
    obs_end = d + OBS_END_OFFSET
    total_obs_days = obs_end - obs_start + 1

    flagged_a = stat_result["flagged_rows"] if stat_usable else []
    flagged_b = ml_result["flagged_rows"] if ml_usable else []

    combined = combine_flags(flagged_a, flagged_b, d, total_obs_days)
    result.update(combined)
    return result
