# KIS 이상매매 통계룰 백테스트 PoC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KIS Open API의 기간별시세조회(일봉)로 실제 투자경고종목 지정 사례의 과거
시세를 받아, 거래량 z-score + 가격 3-sigma 통계룰을 적용해서 지정일 이전에 이상
신호가 먼저 뜨는지(리드타임)를 숫자로 확인하는 1회성 PoC를 만든다.

**Architecture:** 모듈형 Python 스크립트 5개(`kis_client` / `cases` / `detector` /
`backtest` / `report`) + 엔트리포인트 `run_backtest.py`. 외부 상태 없음 — 매 실행마다
KIS API를 호출해 데이터를 받고, `output/`에 결과(PNG+CSV)를 새로 쓴다.

**Tech Stack:** Python 3, `requests`(KIS REST 호출), `pandas`/`numpy`(통계 계산),
`matplotlib`(차트), `python-dotenv`(`.env`에서 KIS 키 로드), `pytest`(가벼운 sanity
check 전용 — 풀 TDD 아님, 아래 Global Constraints 참고).

**Spec:** `/home/user/bigdata-presentation/anomaly-trading-alert-plan.md`
(2절 데이터원천, 3-1절 통계룰, 6절 실습 아이디어) + 이 세션의 브레인스토밍 대화
(레포: `anomaly-trading-alert`, 경로: `/home/user/anomaly-trading-alert/`)

## Global Constraints

- 통계룰은 2-신호 전용(거래량 z-score + 가격 3-sigma)만 쓴다 — 호가 불균형은
  과거 데이터로 못 구해 제외 (기획서 6절).
- 복합점수 가중치는 2-신호 전용이라 `0.5·z_vol_norm + 0.5·z_price_norm`으로
  재배분한다 — 기획서 3-1절 원래 가중치(0.4/0.4/0.2)는 호가 포함 3-신호 기준이므로
  그대로 쓸 수 없다. 이건 내 결정이고, 문서에도 그렇게 명시한다.
- 기획서 3-1절의 가격 신호는 "1분 수익률 3-sigma"지만 토이 데모는 일봉만 쓰므로
  "1거래일 수익률 3-sigma"로 대체한다 — 타임프레임이 분→일로 바뀌었다는 걸
  코드 주석/문서에 명시한다.
- 베이스라인 구간: 지정일 기준 **-60~-31 거래일**(행 인덱스 기준, 캘린더일 아님).
  관찰구간: **-30~+5 거래일**. (기획서 6절)
- 신호 임계값: 거래량 `z > 3`, 가격 `|r - μ_r| > 3σ_r` (기획서 3-1절).
- 사례는 최소 3건, 각 사례는 실제 뉴스 보도 + 지정일을 근거로 남긴다 — 가짜
  데이터/날짜 금지. 정확한 지정 효력일은 1차 출처가 뉴스 보도라 실행 중 한 번
  더 의심해볼 여지가 있다는 걸 결과표에 각주로 남긴다.
- KIS API 인증키(`KIS_APP_KEY`, `KIS_APP_SECRET`)는 캡스톤에서 이미 쓰던 걸
  재사용한다 — `.env`에만 두고 **절대 커밋하지 않는다**(`.gitignore`에 추가).
- 풀 TDD는 생략한다(사용자 합의, 1회성 PoC). 대신 `detector.py`의 핵심 계산
  (z-score, 3-sigma 판정, 복합점수, 리드타임 계산)에는 `tests/test_detector.py`에
  작은 수치 예시로 된 assert 기반 sanity check를 둔다 — red/green 사이클 없이
  "구현 → 체크 실행 → 통과 확인"만 한다.
- KIS 기간별시세조회(TR_ID `FHKST03010100`)는 1회 호출당 최대 100행 응답으로
  알려져 있다 — 사례당 조회 구간(약 75~80거래일)이 이 한도 안에 들어오므로
  단일 호출로 처리하고, 초과 시에는 조용히 자르지 않고 명확히 에러를 낸다.
- **신호 판정 임계값은 두 군데서 서로 다른 기준을 쓴다 — 충돌이 아니라
  용도가 다르다**: 3-1절의 "score > 2.5"는 실서비스가 쓸 고정 임계값 제안이고,
  이 백테스트(`backtest.run_case`)는 사례마다 점수 스케일이 다를 수 있어
  "해당 사례 베이스라인 분포의 평균 + k·표준편차"(`threshold` 파라미터,
  기본 2.5)를 신호 기준으로 쓴다. 둘 다 같은 `threshold=2.5`라는 숫자를
  재사용했을 뿐, 계산 방식 자체는 다르다는 걸 구현자가 헷갈리지 않아야 한다.

## Review Focus

- **거래일/휴일 경계**: 지정일 전후로 주말·공휴일이 끼면 "거래일 기준 -60"이
  캘린더일 -60과 다르게 어긋난다 — 행 인덱스(거래일) 기준으로 슬라이싱해야
  하고, 캘린더일로 계산하면 윈도우가 틀어진다.
- **베이스라인 분산 0**: 베이스라인 구간에 가격·거래량이 거의 안 움직여
  표준편차가 0에 가까우면 z-score가 무한대/NaN이 된다 — 0 또는 극소값일 때
  신호를 "판단불가"로 처리해야 하고, 그대로 나누면 죽는다.
- **KIS 응답 행 부족**: 종목 상장일이 늦거나 거래 정지 기간이 있어서 요청한
  구간만큼 행이 안 돌아오면(베이스라인 61행 미만 등) 그 사례는 건너뛰고
  이유를 결과표에 남겨야 한다 — 조용히 짧은 윈도우로 계산하면 왜곡된다.
- **액세스 토큰 재사용**: 사례마다 새로 토큰을 발급받으면 호출이 쌓여 레이트
  리밋에 걸릴 수 있다 — 토큰은 한 번만 받아서 모든 사례 호출에 재사용해야
  한다.
- **지정일이 데이터에 없음**: 뉴스 보도의 지정일이 실제 거래소 효력일과
  하루 이상 어긋나거나, 그 날이 공시만 있고 거래는 없는 날일 수 있다 —
  지정일과 정확히 일치하는 행이 없으면 "지정일 이후 첫 거래일"로 대체하고
  그 사실을 로그/결과에 남겨야 한다.

---

## Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/__init__.py` (빈 파일)
- Create: `tests/__init__.py` (빈 파일)

**Interfaces:**
- Produces: `.env`에서 `KIS_APP_KEY`, `KIS_APP_SECRET`를 읽는다는 전제를 이후
  모든 태스크가 공유.

- [ ] **Step 1: `requirements.txt` 작성**

```
requests
pandas
numpy
matplotlib
python-dotenv
pytest
```

- [ ] **Step 2: `.env.example` 작성**

```
KIS_APP_KEY=
KIS_APP_SECRET=
```

- [ ] **Step 3: `.gitignore` 작성**

`.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/` 를 무시 목록에 넣는다.
(`output/`는 발표용 결과물이라 커밋 대상으로 남겨둔다 — 무시하지 않는다.)

- [ ] **Step 4: 실제 `.env` 파일 생성**

`crontab -l`의 평문 환경변수 블록에서 `KIS_APP_KEY`, `KIS_APP_SECRET` 값을
그대로 가져와 로컬 `.env`에 쓴다(커밋되지 않음 — Step 3에서 무시 목록에 넣음).

- [ ] **Step 5: 설치 확인**

Run: `pip install -r requirements.txt`
Expected: 에러 없이 설치 완료.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .gitignore src/__init__.py tests/__init__.py
git commit -m "chore: project scaffolding"
```

---

## Task 2: `kis_client.py` — 인증 + 기간별시세조회

**Files:**
- Create: `src/kis_client.py`
- Test: `tests/test_kis_client.py` (실제 네트워크 호출 1건 포함 — 가벼운 수동 확인용)

**Interfaces:**
- Consumes: `.env`의 `KIS_APP_KEY`, `KIS_APP_SECRET` (Task 1)
- Produces:
  - `get_access_token(app_key: str, app_secret: str) -> str`
  - `get_daily_price(access_token: str, app_key: str, app_secret: str, ticker: str, start_date: str, end_date: str) -> pandas.DataFrame`
    반환 컬럼: `date`(str, YYYYMMDD), `close`(float), `volume`(int). 날짜 오름차순.

- [ ] **Step 1: `get_access_token` 구현**

`POST https://openapi.koreainvestment.com:9443/oauth2/tokenP`에
`{"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret}`를
보내 응답 JSON의 `access_token`을 반환한다. 실패(4xx/5xx) 시 응답 바디를 포함해
예외를 던진다.

- [ ] **Step 2: `get_daily_price` 구현**

`GET https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice`
호출, 헤더에 `authorization: Bearer {access_token}`, `appkey`, `appsecret`,
`tr_id: FHKST03010100`, 쿼리파라미터에 `FID_COND_MRKT_DIV_CODE=J`,
`FID_INPUT_ISCD=ticker`, `FID_INPUT_DATE_1=start_date`, `FID_INPUT_DATE_2=end_date`,
`FID_PERIOD_DIV_CODE=D`, `FID_ORG_ADJ_PRC=0`. 응답의 `output2` 리스트를
`stck_bsop_date`→`date`, `stck_clpr`→`close`, `acml_vol`→`volume`으로 매핑해
DataFrame으로 변환, `date` 오름차순 정렬 후 반환.

(**주의**: 정확한 엔드포인트 경로·파라미터·응답 필드명은 2차 자료 기준이라
첫 실제 호출에서 어긋나면 `koreainvestment/open-trading-api` 공식 GitHub
저장소 기준으로 바로잡는다 — 이건 이 단계에서 실행하며 확인할 몫이다.)

- [ ] **Step 3: 실제 호출로 확인**

Run: `python -c "from dotenv import load_dotenv; load_dotenv(); import os; from src.kis_client import get_access_token, get_daily_price; t=get_access_token(os.environ['KIS_APP_KEY'], os.environ['KIS_APP_SECRET']); df=get_daily_price(t, os.environ['KIS_APP_KEY'], os.environ['KIS_APP_SECRET'], '000660', '20251001', '20251231'); print(df.head()); print(len(df))"`
Expected: 에러 없이 DataFrame 출력, 행 수 > 0.

- [ ] **Step 4: Commit**

```bash
git add src/kis_client.py
git commit -m "feat: KIS API client for daily price inquiry"
```

---

## Task 3: `cases.py` — 투자경고종목 지정 사례

**Files:**
- Create: `src/cases.py`

**Interfaces:**
- Produces: `CASES: list[dict]`, 각 dict는
  `{"name": str, "ticker": str, "designation_date": "YYYY-MM-DD", "source": str}`.

- [ ] **Step 1: 사례 4건 작성**

뉴스 보도로 확인된 2025년 12월 투자경고종목 지정 사례를 쓴다(1차 출처는 뉴스
보도이며, 정확한 거래소 효력일은 실행 중 KIND 공시로 한 번 더 확인하는 걸
권장 — Global Constraints 참고):

```python
CASES = [
    {"name": "SK하이닉스", "ticker": "000660", "designation_date": "2025-12-11",
     "source": "헤럴드경제 2025-12-10 보도, SK하이닉스 투자경고종목 지정"},
    {"name": "SK스퀘어", "ticker": "402340", "designation_date": "2025-12-11",
     "source": "헤럴드경제 2025-12-10 보도, SK하이닉스 최대주주 SK스퀘어 동시 지정"},
    {"name": "현대로템", "ticker": "064350", "designation_date": "2025-12-10",
     "source": "아시아경제 2025-12-15 보도, 12/10 투자경고 지정 후 5.62% 하락"},
    {"name": "두산에너빌리티", "ticker": "034020", "designation_date": "2025-12-08",
     "source": "아시아경제 보도 + KRX 공시, 2025-12-08 투자경고종목 지정"},
]
```

- [ ] **Step 2: Commit**

```bash
git add src/cases.py
git commit -m "feat: add researched investor-warning designation cases"
```

---

## Task 4: `detector.py` — 통계룰 핵심 계산

**Files:**
- Create: `src/detector.py`
- Test: `tests/test_detector.py`

**Interfaces:**
- Consumes: `kis_client.get_daily_price`가 반환하는 형태의 DataFrame
  (`date`, `close`, `volume` 컬럼)
- Produces:
  - `volume_zscore(volume: pandas.Series, window: int = 20) -> pandas.Series`
  - `price_return_zscore(close: pandas.Series, window: int = 20) -> pandas.Series`
    (일별 수익률 `close.pct_change()`의 rolling z-score. "3-sigma 이탈"
    판정은 이 z-score의 절댓값으로 바로 비교 가능)
  - `composite_score(vol_z: pandas.Series, price_z: pandas.Series) -> pandas.Series`
    (`0.5 * vol_z + 0.5 * price_z`, Global Constraints의 재배분 가중치)

- [ ] **Step 1: 세 함수 구현**

`volume_zscore`, `price_return_zscore`는 rolling mean/std로 z-score 계산.
표준편차가 0이거나 `NaN`인 구간은 결과를 `NaN`으로 둔다(0으로 나누지 않음 —
Review Focus "베이스라인 분산 0" 항목). `composite_score`는 단순 가중합.

- [ ] **Step 2: `tests/test_detector.py`에 sanity check 작성**

고정된 작은 숫자 배열(예: 20일치 거래량에 마지막 날만 10배 튄 값)을 넣어
`volume_zscore`의 마지막 값이 명확히 3을 넘는지, 변동 없는 구간(표준편차 0)에선
`NaN`이 나오는지 assert로 확인. `composite_score`는 `vol_z=4, price_z=2`일 때
결과가 정확히 `3.0`인지 확인.

- [ ] **Step 3: 실행해서 확인**

Run: `pytest tests/test_detector.py -v`
Expected: 모두 PASS.

- [ ] **Step 4: Commit**

```bash
git add src/detector.py tests/test_detector.py
git commit -m "feat: statistical rule detector (volume/price z-score, composite score)"
```

---

## Task 5: `backtest.py` — 베이스라인/관찰구간 + 리드타임

**Files:**
- Create: `src/backtest.py`
- Test: `tests/test_backtest.py`

**Interfaces:**
- Consumes: `detector.composite_score`의 반환 타입(`pandas.Series`), `cases.CASES`
- Produces:
  - `find_designation_row(df: pandas.DataFrame, designation_date: str) -> int`
    (지정일과 정확히 일치하는 행의 인덱스, 없으면 그 다음 첫 거래일의 인덱스 —
    Review Focus "지정일이 데이터에 없음" 대응)
  - `run_case(df: pandas.DataFrame, case: dict, threshold: float = 2.5) -> dict`
    반환 dict: `{"name", "ticker", "designation_date", "status"
    ("ok"|"insufficient_data"), "lead_time_days": int | None,
    "false_positive_rate": float | None}`

- [ ] **Step 1: `find_designation_row` 구현**

`df['date']`를 지정일과 비교, 정확히 일치하는 행이 없으면 지정일보다 큰 첫
날짜의 행을 반환. 그런 행도 없으면 `ValueError`.

- [ ] **Step 2: `run_case` 구현**

1. `find_designation_row`로 지정일 행 인덱스 `d`를 구한다.
2. 베이스라인 = 행 `[d-60, d-31]`, 관찰구간 = 행 `[d-30, d+5]`.
3. 베이스라인 행 수가 31 미만이면(= `d-60`이 0보다 작음) `status="insufficient_data"`,
   나머지 필드는 `None`으로 반환(Review Focus "KIS 응답 행 부족").
4. `detector`의 세 함수로 전체 구간의 복합점수를 계산하고, 베이스라인 구간
   값으로 평균 `μ`, 표준편차 `σ`를 구한다.
5. 관찰구간에서 `score > μ + threshold·σ`를 만족하는 첫 행을 찾고, 그 행부터
   지정일 행까지의 거래일 수를 `lead_time_days`로(지정일보다 늦게 튀면 음수,
   한 번도 안 넘으면 `None`).
6. 전체 관찰구간 중 임계값을 넘은 날의 비율을 `false_positive_rate`로.

- [ ] **Step 3: `tests/test_backtest.py`에 sanity check 작성**

합성 DataFrame(베이스라인 구간은 평탄, 관찰구간 특정 지점에서 점수가 크게
튀도록 구성)을 만들어 `run_case`의 `lead_time_days`가 기대한 거래일 수와
정확히 일치하는지, 베이스라인이 짧은 경우 `status="insufficient_data"`가
나오는지 assert로 확인. 또한 `find_designation_row`에 지정일과 정확히
일치하는 행이 없는 DataFrame을 넣어, 그다음 첫 거래일의 인덱스가 반환되는지도
별도로 assert로 확인(Review Focus "지정일이 데이터에 없음").

- [ ] **Step 4: 실행해서 확인**

Run: `pytest tests/test_backtest.py -v`
Expected: 모두 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backtest.py tests/test_backtest.py
git commit -m "feat: backtest window logic and lead-time calculation"
```

---

## Task 6: `report.py` — 차트 + 결과표

**Files:**
- Create: `src/report.py`

**Interfaces:**
- Consumes: `backtest.run_case`가 반환하는 dict들의 리스트, 사례별 원본 DataFrame
  + 복합점수 Series
- Produces:
  - `plot_case(df: pandas.DataFrame, score: pandas.Series, case: dict, output_dir: str) -> str`
    (저장된 PNG 경로 반환 — 종가 라인 + 복합점수 라인(보조축) + 지정일 수직선)
  - `write_results_csv(results: list[dict], output_path: str) -> None`

- [ ] **Step 1: `plot_case` 구현**

matplotlib으로 2단 서브플롯(위: 종가, 아래: 복합점수 + 임계값 가로선) 생성,
지정일 위치에 수직 점선 표시, `{output_dir}/{ticker}_{name}.png`로 저장.

- [ ] **Step 2: `write_results_csv` 구현**

`results` 리스트를 `pandas.DataFrame`으로 바꿔 `output_path`에 CSV로 저장
(컬럼: name, ticker, designation_date, status, lead_time_days,
false_positive_rate).

- [ ] **Step 3: Commit**

```bash
git add src/report.py
git commit -m "feat: chart and CSV report generation"
```

---

## Task 7: `run_backtest.py` — 엔트리포인트 + 실제 실행

**Files:**
- Create: `run_backtest.py`

**Interfaces:**
- Consumes: Task 2~6의 모든 공개 함수
- Produces: `output/` 디렉터리에 사례별 PNG + `output/results.csv`

- [ ] **Step 1: 엔트리포인트 구현**

`.env` 로드 → 토큰 1회 발급(Review Focus "액세스 토큰 재사용") → `cases.CASES`
순회하며 각 사례의 조회 구간(`지정일 - 100일` ~ `지정일 + 15일`, 캘린더일 기준
넉넉하게 — Global Constraints의 거래일 윈도우를 담을 만큼)을 계산해
`get_daily_price` 호출 → `detector`로 점수 계산 → `backtest.run_case` →
`report.plot_case` + 결과 누적 → 마지막에 `report.write_results_csv`.

- [ ] **Step 2: 실제 실행**

Run: `python run_backtest.py`
Expected: 에러 없이 종료, `output/`에 PNG 4개 + `results.csv` 생성, CSV를 열어
4건 모두 `status`, `lead_time_days` 값이 채워져 있는지 확인(또는
`insufficient_data`로 명확히 사유가 남는지).

- [ ] **Step 3: Commit**

```bash
git add run_backtest.py output/
git commit -m "feat: end-to-end backtest entry point + generated results"
```
