from src.universe import _parse_ranking_rows


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
