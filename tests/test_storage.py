from src.storage import init_db, record_run, record_result, get_run, get_results


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
