"""SQLite storage for daily universe-scan results."""

import sqlite3


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_runs (
                run_date TEXT PRIMARY KEY,
                started_at TEXT,
                universe_size INTEGER,
                elapsed_seconds REAL,
                ok_count INTEGER,
                insufficient_count INTEGER,
                stale_count INTEGER,
                error_count INTEGER,
                anomaly_count INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_results (
                run_date TEXT,
                ticker TEXT,
                name TEXT,
                status TEXT,
                is_anomaly INTEGER,
                anomaly_score REAL,
                PRIMARY KEY (run_date, ticker)
            )
            """
        )


def record_run(
    db_path: str,
    run_date: str,
    started_at: str,
    universe_size: int,
    elapsed_seconds: float,
    ok_count: int,
    insufficient_count: int,
    stale_count: int,
    error_count: int,
    anomaly_count: int,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO scan_runs
                (run_date, started_at, universe_size, elapsed_seconds,
                 ok_count, insufficient_count, stale_count, error_count, anomaly_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_date, started_at, universe_size, elapsed_seconds,
             ok_count, insufficient_count, stale_count, error_count, anomaly_count),
        )


def record_result(
    db_path: str,
    run_date: str,
    ticker: str,
    name: str,
    status: str,
    is_anomaly,
    anomaly_score,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO scan_results
                (run_date, ticker, name, status, is_anomaly, anomaly_score)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_date, ticker, name, status,
             None if is_anomaly is None else int(is_anomaly), anomaly_score),
        )


def clear_results(db_path: str, run_date: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM scan_results WHERE run_date = ?", (run_date,))


def get_run(db_path: str, run_date: str):
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM scan_runs WHERE run_date = ?", (run_date,)
        ).fetchone()
        return dict(row) if row else None


def get_results(db_path: str, run_date: str) -> list:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM scan_results WHERE run_date = ?", (run_date,)
        ).fetchall()
        return [dict(r) for r in rows]
