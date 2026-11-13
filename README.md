# anomaly-trading-alert

빅데이터 활용 사례 발표("이상매매 패턴 탐지 알리미") 기획안의 6절 실습 아이디어를
검증하는 토이 데모(proof of concept). 기획 전체 내용은 발표용 기획서를 참고.

KIS Open API의 기간별 시세조회로 투자경고종목·투자주의종목 지정 사례의 과거
시세를 받아, 기획서 3절의 4단계 로드맵(통계룰 → ML → DL → 시계열 파운데이션
모델)을 각각 구현해서 지정일 이전에 이상 신호가 먼저 뜨는지(리드타임)를
단계별로 비교한다.

## 실행

```bash
pip install -r requirements.txt
python run_backtest.py          # 통계룰 + ML + DL, output/results*.csv
```

파운데이션 모델(Chronos-bolt) 단계는 별도 conda 환경이 필요하다(이
프로젝트의 requirements.txt에는 일부러 안 넣음 — DL 단계가 쓰는
torch 2.3과 chronos-forecasting이 요구하는 torch>=2.4가 충돌해서):

```bash
/home/user/miniconda3/envs/chronosbolt_env/bin/python run_foundation_backtest.py
```

## 단계별 결과물

| 단계 | 출력 | 탐지 결과(4건 중) |
|---|---|---|
| 통계룰 | `output/results.csv` + 종목별 PNG | 1/4 |
| ML (IsolationForest) | `output/results_ml.csv` | 4/4 |
| DL (LSTM Autoencoder) | `output/results_dl.csv` | 1/4 |
| 파운데이션 모델 (Chronos-bolt 임베딩) | `output/results_foundation.csv` | 4/4 |

각 단계의 설계 결정·튜닝 근거(왜 이 파라미터인지, 왜 이 트레이드오프를
받아들였는지)는 `src/*.py`의 모듈/함수 docstring과 git 커밋 메시지에
남겨뒀다.

## 일일 전종목 스캔 (코스피+코스닥 상위 200)

토이 프로젝트 검증(`docs/findings.md`)에서 ML(IsolationForest)이 가장
성능이 좋았던 걸 근거로, 설계 문서
(`docs/superpowers/specs/2026-11-13-top200-daily-batch-design.md`)와
구현 계획(`docs/superpowers/plans/2026-11-13-top200-daily-batch.md`)에
따라 코스피+코스닥 통합 시가총액 상위 200종목을 매일 1회 스캔하는
배치를 추가했다.

```bash
python run_universe_scan.py   # 기본 limit=200, universe_scan.db에 결과 저장
```

크론: 매일 17:00 KST(평일), `0 17 * * 1-5 cd /home/user/anomaly-trading-alert && ... run_universe_scan.py`.
`universe_scan.db`/`universe_scan.log`은 매일 갱신되는 운영 상태라 git
추적 대상이 아니다(`.gitignore`).
