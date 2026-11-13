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


def test_run_case_lead_time_matches_known_spike_position():
    designation_row = 90
    spike_row = 70
    df = _alternating_case_df(n=120, spike_row=spike_row)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": "2026-" + df["date"].iloc[designation_row][4:6] + "-" + df["date"].iloc[designation_row][6:8],
    }
    result = run_case(df, case)
    assert result["status"] == "ok"
    assert result["lead_time_days"] == designation_row - spike_row


def test_run_case_insufficient_data_when_baseline_too_short():
    df = _alternating_case_df(n=40, spike_row=None)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": "2026-" + df["date"].iloc[35][4:6] + "-" + df["date"].iloc[35][6:8],
    }
    result = run_case(df, case)
    assert result["status"] == "insufficient_data"
    assert result["lead_time_days"] is None
    assert result["false_positive_rate"] is None
