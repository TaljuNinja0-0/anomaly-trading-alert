# Top-200 Daily Batch Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 코스피+코스닥 통합 시가총액 상위 200종목을 매일 1회 일봉 기준으로
스캔해서 ML(IsolationForest) 이상탐지를 돌리고 결과를 SQLite에 저장하는
배치 파이프라인을 만든다.

**Architecture:** 기존 토이 프로젝트(`kis_client`, `ml_detector`)를 그대로
재사용. 새로 추가하는 건 유니버스 조회(`src/universe.py`), 베이스라인/판정
공유 로직과 "오늘 하루"를 판정하는 로직(`src/scan.py`, `ml_detector.run_case_ml`도
이 공유 로직을 쓰도록 리팩터), 결과 저장(`src/storage.py`), 그리고 이걸
엮는 엔트리포인트(`run_universe_scan.py`) + 크론 등록.

**Tech Stack:** 기존 토이 프로젝트와 동일(Python, pandas, scikit-learn) +
`sqlite3`(표준 라이브러리, 추가 설치 불필요).

**Spec:** `/home/user/anomaly-trading-alert/docs/superpowers/specs/2026-11-13-top200-daily-batch-design.md`
(+ 참고: `/home/user/anomaly-trading-alert/docs/findings.md` — 왜 ML을
골랐는지)

## Global Constraints

- 유니버스는 **코스피+코스닥 통합** 시가총액 상위 200종목 (설계 문서,
  사용자 결정).
- ML 파라미터는 토이 프로젝트 값 그대로 재사용: `contamination=0.05`,
  베이스라인 100거래일(`ml_detector.ML_BASELINE_LOOKBACK`) — 이번 라운드는
  재튜닝하지 않는다(설계 문서 "제약").
- 분봉/실시간, 알림 발송, 매수매도 추천, 대시보드/UI는 전부 이번 계획
  범위 밖(설계 문서 "비목표").
- 크론은 **17:00 KST** 1개, 실행 호스트는 이 환경(`/home/user`) 자체
  (설계 문서 "실행 방식").
- 토큰 발급은 배치 시작 시 1회만(KIS 토큰 발급 1분당 1회 제한, 기존
  `kis_client.py`에 이미 반영된 제약 그대로 적용).
- 개별 종목 처리 실패가 배치 전체를 중단시켜선 안 된다(아래 Review Focus).
- `src/universe.py`의 TR_ID(`FHPST01740000`)·엔드포인트 경로·응답
  필드명은 2차 자료(블로그) 기준 추정치다 — Task 1에서 실제 호출로
  맞는지 확인하고, 틀리면 바로잡는다(기존 `kis_client.get_daily_price`를
  Task 2 때 검증했던 것과 같은 방식).

## Review Focus

- **개별 종목 API 호출/처리 실패** (거래정지·상장폐지 등): 한 종목에서
  예외가 나도 나머지 199종목 처리가 계속돼야 한다 — 배치 전체가 죽으면
  "장마감 후 합리적 시간 안에 못 끝낸다"는 안티골에 바로 걸린다.
- **유니버스 응답이 200개 미만**: API 장애나 데이터 부족으로 200개가
  안 와도 받은 만큼으로 진행해야 한다 — "정확히 200개가 아니면 에러"는
  과도한 가정이다.
- **최신성 체크 실패** (오늘자 데이터가 아직 KIS에 안 올라온 종목):
  해당 종목만 건너뛰고 기록에 남겨야 한다 — 조용히 무시하면 "왜 이
  종목은 매일 안 잡히지"를 아무도 모르게 된다.
- **같은 날 배치가 중복 실행됨** (수동 재실행, 크론 겹침 등): `run_date`
  기준으로 재실행하면 이전 결과를 덮어써야지, 중복 레코드가 쌓이면
  `scan_runs`의 집계 수치가 틀어진다.
- **베이스라인 100행 미달 종목 비율**: 신규상장 등으로 `insufficient_data`가
  많이 나올 수 있다는 건 설계 문서가 이미 인정한 리스크 — 콘솔 로그에만
  남고 사라지면 운영자가 못 알아챈다. `scan_runs` 요약에 집계로 남아야
  한다.

---

## Task 1: `src/universe.py` — 시가총액 상위 유니버스 조회

**Files:**
- Create: `src/universe.py`
- Test: `tests/test_universe.py`

**Interfaces:**
- Consumes: `src.kis_client.BASE_URL`
- Produces:
  - `get_market_cap_ranking(access_token: str, app_key: str, app_secret: str, market: str = "0000", limit: int = 200) -> list[dict]`
    반환: `[{"ticker": str, "name": str}, ...]`, 시가총액 순위 오름차순,
    최대 `limit`개.

- [ ] **Step 1: `_parse_ranking_rows(rows: list[dict], limit: int) -> list[dict]` 테스트 작성**

```python
def test_parse_ranking_rows_extracts_ticker_and_name():
    rows = [
        {"mksc_shrn_iscd": "005930", "hts_kor_isnm": "삼성전자"},
        {"mksc_shrn_iscd": "000660", "hts_kor_isnm": "SK하이닉스"},
    ]
    result = _parse_ranking_rows(rows, limit=200)
    assert result == [
        {"ticker": "005930", "name": "삼성전자"},
        {"ticker": "000660", "name": "SK하이닉스"},
    ]


def test_parse_ranking_rows_truncates_to_limit():
    rows = [{"mksc_shrn_iscd": str(i).zfill(6), "hts_kor_isnm": f"종목{i}"} for i in range(10)]
    result = _parse_ranking_rows(rows, limit=3)
    assert len(result) == 3
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `pytest tests/test_universe.py -v`
Expected: FAIL (`_parse_ranking_rows` not defined)

- [ ] **Step 3: `_parse_ranking_rows`와 `get_market_cap_ranking` 구현**

`_parse_ranking_rows`는 각 row에서 `mksc_shrn_iscd`→`ticker`,
`hts_kor_isnm`→`name`을 뽑아 `limit`개로 자른다(필드명은 추정치 —
Step 5에서 실제 응답과 다르면 여기서 바로잡는다).

`get_market_cap_ranking`은 `GET {BASE_URL}/uapi/domestic-stock/v1/ranking/market-cap`,
헤더에 `tr_id: FHPST01740000`, 쿼리파라미터에
`fid_cond_scr_div_code=20174`, `fid_input_iscd=market`,
`fid_div_cls_code=0`, `fid_trgt_cls_code=0`, `fid_trgt_exls_cls_code=0`,
`fid_input_price_1=""`, `fid_input_price_2=""`, `fid_vol_cnt=""`를
보낸다(일부 파라미터는 2차 자료 기준 추정 — Step 5 실호출에서 400
에러가 나면 KIS 공식 GitHub 예제(`koreainvestment/open-trading-api`)
기준으로 바로잡는다). 응답 `output`을 `_parse_ranking_rows`에 넘긴다.
`rt_cd != "0"`이면 `kis_client._fetch_daily_price_chunk`와 같은 패턴으로
에러를 던진다.

- [ ] **Step 4: 실행해서 통과 확인**

Run: `pytest tests/test_universe.py -v`
Expected: PASS

- [ ] **Step 5: 실제 호출로 확인**

Run: `python -c "from dotenv import load_dotenv; load_dotenv(); import os; from src.kis_client import get_access_token; from src.universe import get_market_cap_ranking; t=get_access_token(os.environ['KIS_APP_KEY'], os.environ['KIS_APP_SECRET']); r=get_market_cap_ranking(t, os.environ['KIS_APP_KEY'], os.environ['KIS_APP_SECRET'], limit=10); print(r)"`
Expected: 에러 없이 종목코드·종목명 10개 리스트 출력(1위가 삼성전자일
가능성이 높음 — 상식과 맞는지 눈으로 확인). 틀리면 Step 3의 TR_ID/
파라미터/필드명을 고치고 Step 1의 테스트도 실제 필드명에 맞게 고친
뒤 이 Task를 다시 돈다.

- [ ] **Step 6: Commit**

```bash
git add src/universe.py tests/test_universe.py
git commit -m "feat: market-cap ranking (KOSPI+KOSDAQ top-N universe)"
```

---

## Task 2: `src/scan.py` — 공유 판정 로직 + "오늘" 스캔

**Files:**
- Create: `src/scan.py`
- Test: `tests/test_scan.py`
- Modify: `src/ml_detector.py` (기존 `run_case_ml`이 새 공유 함수를 쓰도록
  리팩터)

**Interfaces:**
- Consumes: `src.ml_detector.build_features`, `src.ml_detector.ML_BASELINE_LOOKBACK`
- Produces:
  - `classify_with_isolation_forest(baseline_features: pandas.DataFrame, target_features: pandas.DataFrame, contamination: float = 0.05, random_state: int = 42) -> tuple[numpy.ndarray, numpy.ndarray]`
    `(predictions, scores)` — `predictions`는 -1/1 배열, `scores`는
    `decision_function` 연속값 배열(낮을수록 이상).
  - `is_data_fresh(last_date: str, today: str) -> bool`
  - `scan_today(df: pandas.DataFrame, contamination: float = 0.05, random_state: int = 42) -> dict`
    반환: `{"status": "ok"|"insufficient_data", "is_anomaly": bool|None, "anomaly_score": float|None}`.
    `df`의 **마지막 행이 "오늘"**이라고 가정한다(최신성 확인은 호출자
    책임 — Task 4에서 `is_data_fresh`로 먼저 확인한 뒤에만 부른다).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
import numpy as np
import pandas as pd

from src.scan import classify_with_isolation_forest, is_data_fresh, scan_today
from src.ml_detector import ML_BASELINE_LOOKBACK


def _dates(n, start="20260101"):
    base = pd.Timestamp(start)
    return [(base + pd.Timedelta(days=i)).strftime("%Y%m%d") for i in range(n)]


def test_classify_with_isolation_forest_flags_outlier():
    rng = np.random.RandomState(0)
    baseline = pd.DataFrame(rng.normal(0, 0.1, size=(60, 4)))
    target = pd.DataFrame([[5.0, 5.0, 5.0, 5.0]])
    predictions, scores = classify_with_isolation_forest(baseline, target)
    assert predictions[0] == -1
    assert scores[0] < 0


def test_is_data_fresh_true_when_dates_match():
    assert is_data_fresh("20261113", "20261113") is True


def test_is_data_fresh_false_when_dates_differ():
    assert is_data_fresh("20261112", "20261113") is False


def test_scan_today_insufficient_data_when_too_short():
    n = ML_BASELINE_LOOKBACK  # one row short of the required baseline+today
    df = pd.DataFrame({
        "date": _dates(n),
        "close": [100.0 + i * 0.1 for i in range(n)],
        "volume": [1000 + i * 5 for i in range(n)],
    })
    result = scan_today(df)
    assert result["status"] == "insufficient_data"
    assert result["is_anomaly"] is None


def test_scan_today_detects_known_anomaly():
    n = ML_BASELINE_LOOKBACK + 20  # baseline + warm-up + today, comfortable margin
    rng = np.random.RandomState(0)
    close = 100 + np.cumsum(rng.normal(0, 0.15, n))
    volume = 1000 + rng.normal(0, 25, n)
    close[-1] = close[-2] * 1.8  # today is a sharp spike
    volume[-1] = 50000
    df = pd.DataFrame({"date": _dates(n), "close": close, "volume": volume})
    result = scan_today(df)
    assert result["status"] == "ok"
    assert result["is_anomaly"] is True
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `pytest tests/test_scan.py -v`
Expected: FAIL (`src.scan` 모듈 없음)

- [ ] **Step 3: `src/scan.py` 구현**

`classify_with_isolation_forest`는 `ml_detector.run_case_ml`에 있던
`IsolationForest(contamination=...).fit(baseline).predict(obs)` 로직을
그대로 옮기되 `decision_function` 결과도 같이 반환한다.

`is_data_fresh`는 문자열 비교 1줄.

`scan_today`는 `build_features(df)`로 피처를 만들고, 마지막
`ML_BASELINE_LOOKBACK`행을 베이스라인, 마지막 1행을 타깃으로 써서
(전체 길이가 `ML_BASELINE_LOOKBACK + 1` 미만이거나 베이스라인/타깃에
NaN이 있으면 `insufficient_data`) `classify_with_isolation_forest`를
호출한다.

- [ ] **Step 4: 실행해서 통과 확인**

Run: `pytest tests/test_scan.py -v`
Expected: PASS

- [ ] **Step 5: `ml_detector.run_case_ml`이 `classify_with_isolation_forest`를 쓰도록 리팩터**

`src/ml_detector.py:84-88`(현재 `IsolationForest` 인라인 생성·`fit`·
`predict` 부분)을 `src.scan.classify_with_isolation_forest` 호출로
바꾼다. 동작은 그대로여야 한다 — 새 기능 추가 아님, 순수 리팩터.

- [ ] **Step 6: 회귀 확인**

Run: `pytest tests/test_ml_detector.py -v`
Expected: 기존 테스트 전부 PASS (특히
`test_run_case_ml_flags_the_known_spike`) — 리팩터가 기존 동작을 안
깼는지 확인.

- [ ] **Step 7: Commit**

```bash
git add src/scan.py tests/test_scan.py src/ml_detector.py
git commit -m "feat: shared IsolationForest classify helper + scan_today (today-only judgment)"
```

---

## Task 3: `src/storage.py` — SQLite 결과 저장

**Files:**
- Create: `src/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Produces:
  - `init_db(db_path: str) -> None`
  - `record_run(db_path: str, run_date: str, started_at: str, universe_size: int, elapsed_seconds: float, ok_count: int, insufficient_count: int, stale_count: int, error_count: int, anomaly_count: int) -> None`
    같은 `run_date`로 다시 부르면 **덮어쓴다**(Review Focus "중복 실행").
  - `record_result(db_path: str, run_date: str, ticker: str, name: str, status: str, is_anomaly: bool | None, anomaly_score: float | None) -> None`
    같은 `(run_date, ticker)`로 다시 부르면 덮어쓴다.
  - `get_run(db_path: str, run_date: str) -> dict | None`
  - `get_results(db_path: str, run_date: str) -> list[dict]`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
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
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `pytest tests/test_storage.py -v`
Expected: FAIL (`src.storage` 모듈 없음)

- [ ] **Step 3: `src/storage.py` 구현**

`init_db`는 `scan_runs(run_date TEXT PRIMARY KEY, started_at TEXT,
universe_size INTEGER, elapsed_seconds REAL, ok_count INTEGER,
insufficient_count INTEGER, stale_count INTEGER, error_count INTEGER,
anomaly_count INTEGER)`와 `scan_results(run_date TEXT, ticker TEXT, name
TEXT, status TEXT, is_anomaly INTEGER, anomaly_score REAL, PRIMARY
KEY(run_date, ticker))`를 `CREATE TABLE IF NOT EXISTS`로 만든다.
`record_run`/`record_result`는 `INSERT OR REPLACE`로 멱등성을
보장한다(Review Focus "중복 실행"). 매 호출마다 커넥션을 열고
닫는다(상주 커넥션 불필요한 배치 규모).

- [ ] **Step 4: 실행해서 통과 확인**

Run: `pytest tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage.py tests/test_storage.py
git commit -m "feat: SQLite storage for daily scan results"
```

---

## Task 4: `run_universe_scan.py` — 엔트리포인트

**Files:**
- Create: `run_universe_scan.py`

**Interfaces:**
- Consumes: Task 1~3의 모든 공개 함수, `src.kis_client.get_access_token`,
  `src.kis_client.get_daily_price`
- Produces: `universe_scan.db` (SQLite 파일), 콘솔 로그

- [ ] **Step 1: 엔트리포인트 구현**

`.env` 로드 → 토큰 1회 발급 → `init_db("universe_scan.db")` →
`get_market_cap_ranking(..., limit=200)`로 유니버스 조회(200개 미만이
와도 그대로 진행 — Review Focus) → 오늘 날짜(`YYYYMMDD`/`YYYY-MM-DD`
둘 다 필요: 전자는 `is_data_fresh` 비교용, 후자는 `run_date`용) → 종목별로:

```python
for entry in universe:
    try:
        df = get_daily_price(token, app_key, app_secret, entry["ticker"], start_date, end_date)
        if not df.empty and is_data_fresh(df["date"].iloc[-1], today_yyyymmdd):
            result = scan_today(df)
        else:
            result = {"status": "stale", "is_anomaly": None, "anomaly_score": None}
        record_result(db_path, run_date, entry["ticker"], entry["name"],
                       result["status"], result["is_anomaly"], result["anomaly_score"])
        counts[result["status"]] += 1
        if result["is_anomaly"]:
            counts["anomaly"] += 1
    except Exception as e:
        record_result(db_path, run_date, entry["ticker"], entry["name"], "error", None, None)
        counts["error"] += 1
        print(f"{entry['ticker']} 처리 실패: {e}")  # 배치는 계속 진행 (Review Focus)
    time.sleep(0.3)
```

`start_date`/`end_date`는 오늘 기준 `-200일 ~ 오늘`(130거래일 이상
확보용 여유 범위, `kis_client`의 페이지네이션이 자동 처리). 마지막에
`record_run`으로 집계(`counts["ok"]`, `counts["insufficient_data"]`,
`counts["stale"]`, `counts["error"]`, `counts["anomaly"]`, 소요시간)를
남기고 콘솔에도 요약을 찍는다.

- [ ] **Step 2: 소규모 실제 실행으로 확인**

Run: `python -c "import run_universe_scan as m; m.main(limit=10)"`
(엔트리포인트에 `limit` 파라미터를 받는 `main(limit=200, db_path="universe_scan.db")`
형태로 구현해서 테스트 시 작은 규모로 돌릴 수 있게 한다)
Expected: 에러 없이 종료, 콘솔에 10종목 처리 요약 출력, `universe_scan.db`
생성 확인(`sqlite3 universe_scan.db "select * from scan_results;"`로
10행 확인).

- [ ] **Step 3: Commit**

```bash
git add run_universe_scan.py
git commit -m "feat: end-to-end daily universe scan entry point"
```

---

## Task 5: 크론 등록

**Files:**
- Modify: 시스템 crontab (코드 파일 아님)

**Interfaces:**
- Consumes: Task 4의 `run_universe_scan.py`

- [ ] **Step 1: 현재 crontab 백업**

Run: `crontab -l > /home/user/crontab_backup_$(date +%Y%m%d)_top200.txt`
Expected: 백업 파일 생성 확인.

- [ ] **Step 2: 크론 항목 추가**

`crontab -l`에 아래 줄을 추가해 `crontab -`로 반영한다(기존 항목은
그대로 유지 — Thread B에서 이미 캡스톤 관련 항목은 정리된 상태라
새로 추가만 하면 됨):

```
0 17 * * 1-5 cd /home/user/anomaly-trading-alert && /home/user/miniconda3/bin/python run_universe_scan.py >> /home/user/anomaly-trading-alert/universe_scan.log 2>&1
```

- [ ] **Step 3: 반영 확인**

Run: `crontab -l | grep run_universe_scan.py`
Expected: 위에서 추가한 줄이 출력됨.

- [ ] **Step 4: Commit**

크론 자체는 git 대상이 아니므로, 참고용으로 README에 한 줄만 추가:

```bash
git add README.md
git commit -m "docs: document the daily universe-scan cron entry"
```

---

## Task 6: 최종 검증 — 실제 200종목 전체 스캔

**Files:** 없음(검증 전용 태스크)

**Interfaces:**
- Consumes: Task 4의 `run_universe_scan.py`

- [ ] **Step 1: 전체 규모로 실제 실행**

Run: `python run_universe_scan.py` (기본값 `limit=200`)
Expected: 에러 없이 종료. 소요 시간이 설계 문서의 추정치(5~15분대)
안에 드는지 확인 — 크게 벗어나면(예: 30분 이상) 설계 문서의 "성능
추정" 섹션에 실측치로 업데이트할 가치가 있음(이 Task에서 직접 고치지
않고 사용자에게 보고).

- [ ] **Step 2: 결과 확인**

Run: `sqlite3 universe_scan.db "select ok_count, insufficient_count, stale_count, error_count, anomaly_count, elapsed_seconds from scan_runs order by run_date desc limit 1;"`
Expected: `ok_count + insufficient_count + stale_count + error_count`가
유니버스 크기(최대 200)와 일치. `insufficient_count` 비율이 과도하게
높으면(예: 30% 이상) 설계 문서가 예상한 "신규상장 등 일부"를 넘어서는
수준이므로 원인을 짚어보고 사용자에게 보고.

- [ ] **Step 3: 이상치로 잡힌 종목 눈으로 확인**

Run: `sqlite3 universe_scan.db "select ticker, name, anomaly_score from scan_results where is_anomaly=1 order by anomaly_score asc;"`
Expected: 결과를 사용자에게 공유 — 실제로 뉴스가 될 만한 종목인지는
이 Task의 검증 범위 밖(그날그날 달라짐), 파이프라인이 끝까지 동작해서
그럴듯한 개수(0개도 아니고 200개 전체도 아닌)가 나오는지만 확인.
