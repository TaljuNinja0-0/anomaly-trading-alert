import numpy as np
import pandas as pd

from src.ensemble_detector import combine_flags, run_case_ensemble


def _dates(n, start="20260101"):
    base = pd.Timestamp(start)
    return [(base + pd.Timedelta(days=i)).strftime("%Y%m%d") for i in range(n)]


def _designation_date_for_row(df, row):
    d = df["date"].iloc[row]
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def _noisy_case_df(n, spike_row, spike_multiplier=1.8, spike_volume=50000, seed=0):
    rng = np.random.RandomState(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.15, n))
    volume = 1000 + rng.normal(0, 25, n)
    close[spike_row] = close[spike_row - 1] * spike_multiplier
    volume[spike_row] = spike_volume
    return pd.DataFrame({"date": _dates(n), "close": close, "volume": volume})


def test_combine_flags_unions_both_stages():
    result = combine_flags(flagged_a=[70], flagged_b=[75, 80], d=90, total_obs_days=36)
    assert result["flagged_rows"] == [70, 75, 80]
    assert result["lead_time_days"] == 90 - 70  # earliest across both stages
    assert result["false_positive_rate"] == 3 / 36


def test_combine_flags_dedupes_overlapping_rows():
    result = combine_flags(flagged_a=[70, 75], flagged_b=[75, 80], d=90, total_obs_days=36)
    assert result["flagged_rows"] == [70, 75, 80]
    assert result["false_positive_rate"] == 3 / 36


def test_combine_flags_falls_back_to_whichever_stage_has_flags():
    # stage A found nothing (e.g. undetermined baseline), stage B still useful
    result = combine_flags(flagged_a=[], flagged_b=[82], d=90, total_obs_days=36)
    assert result["lead_time_days"] == 90 - 82
    assert result["false_positive_rate"] == 1 / 36


def test_combine_flags_no_detection_when_neither_stage_flags_anything():
    result = combine_flags(flagged_a=[], flagged_b=[], d=90, total_obs_days=36)
    assert result["flagged_rows"] == []
    assert result["lead_time_days"] is None
    assert result["false_positive_rate"] == 0.0


def test_run_case_ensemble_detects_on_real_case_shape():
    designation_row = 220
    spike_row = 200
    df = _noisy_case_df(n=250, spike_row=spike_row)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": _designation_date_for_row(df, designation_row),
    }
    result = run_case_ensemble(df, case)
    assert result["status"] == "ok"
    assert result["lead_time_days"] is not None
    expected_lead_time = designation_row - spike_row
    assert abs(result["lead_time_days"] - expected_lead_time) <= 8
    assert "stat_status" in result and "ml_status" in result
