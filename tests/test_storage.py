from src.storage import init_db, record_run, record_result, get_run, get_results, clear_results, write_run_results


def test_record_and_get_run_round_trips(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    record_run(db_path, "2026-11-13", "2026-11-13T17:00:00", 200, 123.4, 195, 3, 1, 1, 2)
    run = get_run(db_path, "2026-11-13")
    assert run["universe_size"] == 200
    assert run["anomaly_count"] == 2


def test_record_run_same_date_overwrites(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    record_run(db_path, "2026-11-13", "2026-11-13T17:00:00", 200, 100.0, 200, 0, 0, 0, 0)
    record_run(db_path, "2026-11-13", "2026-11-13T17:05:00", 200, 110.0, 198, 1, 0, 1, 3)
    run = get_run(db_path, "2026-11-13")
    assert run["anomaly_count"] == 3  # second call wins, not a duplicate row


def test_record_and_get_results_round_trip(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    record_result(db_path, "2026-11-13", "005930", "삼성전자", "ok", False, -0.1)
    record_result(db_path, "2026-11-13", "000660", "SK하이닉스", "ok", True, -0.3)
    results = get_results(db_path, "2026-11-13")
    assert len(results) == 2
    assert {r["ticker"] for r in results} == {"005930", "000660"}


def test_clear_results_removes_rows_outside_a_rerun_universe(tmp_path):
    # A rerun whose universe shrinks or changes must not leave the
    # previous attempt's tickers behind for the same run_date.
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    record_result(db_path, "2026-11-13", "005930", "삼성전자", "ok", False, -0.1)
    record_result(db_path, "2026-11-13", "999999", "사라질종목", "ok", False, -0.1)
    clear_results(db_path, "2026-11-13")
    record_result(db_path, "2026-11-13", "005930", "삼성전자", "ok", False, -0.1)
    results = get_results(db_path, "2026-11-13")
    assert {r["ticker"] for r in results} == {"005930"}


def test_clear_results_does_not_touch_other_dates(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    record_result(db_path, "2026-11-12", "005930", "삼성전자", "ok", False, -0.1)
    record_result(db_path, "2026-11-13", "000660", "SK하이닉스", "ok", False, -0.1)
    clear_results(db_path, "2026-11-13")
    assert len(get_results(db_path, "2026-11-12")) == 1
    assert len(get_results(db_path, "2026-11-13")) == 0


def test_write_run_results_writes_results_and_summary_atomically(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    results = [
        {"ticker": "005930", "name": "삼성전자", "status": "ok", "is_anomaly": False, "anomaly_score": -0.1},
        {"ticker": "000660", "name": "SK하이닉스", "status": "ok", "is_anomaly": True, "anomaly_score": -0.3},
        {"ticker": "999999", "name": "품절종목", "status": "insufficient_data", "is_anomaly": None, "anomaly_score": None},
    ]
    counts = write_run_results(db_path, "2026-11-13", "2026-11-13T17:00:00", 3, 42.0, results)

    assert counts == {"ok": 2, "insufficient_data": 1, "stale": 0, "error": 0, "anomaly": 1}
    run = get_run(db_path, "2026-11-13")
    assert run["ok_count"] == 2
    assert run["anomaly_count"] == 1
    stored = {r["ticker"]: r for r in get_results(db_path, "2026-11-13")}
    assert len(stored) == 3
    assert stored["000660"]["is_anomaly"] == 1


def test_write_run_results_clears_previous_rerun_before_writing(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    write_run_results(db_path, "2026-11-13", "t1", 1, 10.0, [
        {"ticker": "005930", "name": "삼성전자", "status": "ok", "is_anomaly": False, "anomaly_score": -0.1},
        {"ticker": "999999", "name": "사라질종목", "status": "ok", "is_anomaly": False, "anomaly_score": -0.1},
    ])
    write_run_results(db_path, "2026-11-13", "t2", 1, 11.0, [
        {"ticker": "005930", "name": "삼성전자", "status": "ok", "is_anomaly": False, "anomaly_score": -0.1},
    ])
    results = get_results(db_path, "2026-11-13")
    assert {r["ticker"] for r in results} == {"005930"}
