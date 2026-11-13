import pandas as pd

from src.backtest import find_designation_row, run_case


def _dates(n, start="20260101"):
    base = pd.Timestamp(start)
    return [(base + pd.Timedelta(days=i)).strftime("%Y%m%d") for i in range(n)]


def test_find_designation_row_exact_match():
    df = pd.DataFrame({"date": _dates(5)})
    assert find_designation_row(df, "2026-01-03") == 2


def test_find_designation_row_falls_back_to_next_available_date():
    dates = _dates(5)
    del dates[2]  # remove 2026-01-03, so it's not present
    df = pd.DataFrame({"date": dates})
    # designation falls on the missing date -> next available row (was index 3, now 2)
    assert find_designation_row(df, "2026-01-03") == 2


def test_find_designation_row_raises_when_no_future_date():
    df = pd.DataFrame({"date": _dates(5)})
    try:
        find_designation_row(df, "2026-01-10")
        assert False, "expected ValueError"
    except ValueError:
        pass


def _alternating_case_df(n=120, spike_row=70):
    dates = _dates(n)
    close = []
    volume = []
    for i in range(n):
        if i == spike_row:
            close.append(200.0)
            volume.append(50000)
        else:
            close.append(100.0 if i % 2 == 0 else 100.5)
            volume.append(1000 if i % 2 == 0 else 1010)
    return pd.DataFrame({"date": dates, "close": close, "volume": volume})


def _designation_date_for_row(df, row):
    d = df["date"].iloc[row]
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def test_run_case_lead_time_matches_known_spike_position():
    designation_row = 90
    spike_row = 70
    df = _alternating_case_df(n=120, spike_row=spike_row)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": _designation_date_for_row(df, designation_row),
    }
    result = run_case(df, case)
    assert result["status"] == "ok"
    assert result["lead_time_days"] == designation_row - spike_row
    assert result["effective_date"] == case["designation_date"]
    assert result["breach_level"] is not None


def test_run_case_insufficient_data_when_baseline_too_short():
    df = _alternating_case_df(n=40, spike_row=None)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": _designation_date_for_row(df, 35),
    }
    result = run_case(df, case)
    assert result["status"] == "insufficient_data"
    assert result["lead_time_days"] is None
    assert result["false_positive_rate"] is None
    assert result["breach_level"] is None


def test_run_case_insufficient_data_when_baseline_has_warmup_nan():
    # Baseline starts right at row d-60=0, which is inside the detector's
    # own rolling-window warm-up (first ~20 rows are NaN) even though the
    # row count looks sufficient by the naive "baseline_start >= 0" check.
    df = _alternating_case_df(n=96, spike_row=None)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": _designation_date_for_row(df, 60),
    }
    result = run_case(df, case)
    assert result["status"] == "insufficient_data"


def test_run_case_effective_date_reflects_fallback():
    designation_row = 90
    df = _alternating_case_df(n=120, spike_row=None)
    nominal_date = _designation_date_for_row(df, designation_row)
    df = df.drop(index=designation_row).reset_index(drop=True)
    case = {"name": "테스트종목", "ticker": "000000", "designation_date": nominal_date}
    result = run_case(df, case)
    assert result["effective_date"] != nominal_date
    assert result["effective_date"] == _designation_date_for_row(df, designation_row)


def test_run_case_undetermined_when_baseline_variance_is_zero():
    # A perfectly linear close/volume trend makes the per-day composite
    # score converge to the same constant every day once past warm-up, so
    # the baseline's own std is ~0 -- "can't judge", not "no detection".
    n = 120
    dates = _dates(n)
    close = [100.0 + 0.1 * i for i in range(n)]
    volume = [1000 + 10 * i for i in range(n)]
    df = pd.DataFrame({"date": dates, "close": close, "volume": volume})
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": _designation_date_for_row(df, 90),
    }
    result = run_case(df, case)
    assert result["status"] == "undetermined"
    assert result["lead_time_days"] is None
    assert result["breach_level"] is None
