"""Investor-warning designation cases researched from news reports.

Primary source is news coverage, not the KRX disclosure itself — the exact
effective designation date is worth re-checking against KIND
(kind.krx.co.kr) if the result looks off.
"""

CASES = [
    {
        "name": "SK하이닉스",
        "ticker": "000660",
        "designation_date": "2025-12-11",
        "source": "헤럴드경제 2025-12-10 보도, SK하이닉스 투자경고종목 지정",
        "anomaly_type": "trend",  # ~1년간 200%+ 상승 사유
    },
    {
        "name": "SK스퀘어",
        "ticker": "402340",
        "designation_date": "2025-12-11",
        "source": "헤럴드경제 2025-12-10 보도, SK하이닉스 최대주주 SK스퀘어 동시 지정",
        "anomaly_type": "trend",
    },
    {
        "name": "현대로템",
        "ticker": "064350",
        "designation_date": "2025-12-10",
        "source": "아시아경제 2025-12-15 보도, 12/10 투자경고 지정 후 5.62% 하락",
        "anomaly_type": "trend",
    },
    {
        "name": "두산에너빌리티",
        "ticker": "034020",
        "designation_date": "2025-12-08",
        "source": "아시아경제 보도 + KRX 공시, 2025-12-08 투자경고종목 지정",
        "anomaly_type": "trend",
    },
    {
        "name": "상지건설",
        "ticker": "042940",
        "designation_date": "2025-04-10",
        "source": (
            "뉴시스/이코노미스트 2025-04-18 보도, 2025-04-02~04-17 11거래일간 "
            "1593% 상승(10거래일 연속 상한가) 중 04-10 투자경고(2단계) 지정, "
            "04-15 투자위험종목 지정 — 정확한 지정일은 뉴스 보도 기준 추정치, "
            "KIND 재확인 권장(다른 사례보다 출처가 덜 명확함)"
        ),
        "anomaly_type": "spike",  # 11거래일 만에 1593% — 단기 급등형, trend 4건과 대비용
    },
]
