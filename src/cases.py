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
    },
    {
        "name": "SK스퀘어",
        "ticker": "402340",
        "designation_date": "2025-12-11",
        "source": "헤럴드경제 2025-12-10 보도, SK하이닉스 최대주주 SK스퀘어 동시 지정",
    },
    {
        "name": "현대로템",
        "ticker": "064350",
        "designation_date": "2025-12-10",
        "source": "아시아경제 2025-12-15 보도, 12/10 투자경고 지정 후 5.62% 하락",
    },
    {
        "name": "두산에너빌리티",
        "ticker": "034020",
        "designation_date": "2025-12-08",
        "source": "아시아경제 보도 + KRX 공시, 2025-12-08 투자경고종목 지정",
    },
]
