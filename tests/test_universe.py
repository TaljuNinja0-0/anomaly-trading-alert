from src.universe import (
    _parse_master_lines,
    _KOSPI_FIELD_SPECS,
    _KOSPI_PART2_COLUMNS,
)

# Real lines captured from the official kospi_code.mst (2026-11-13), used
# verbatim so the fixed-width offsets are checked against the actual file
# format rather than a hand-built approximation.
SAMSUNG_LINE = (
    '005930   KR7005930003삼성전자                                ST1002700130000 '
    'NN5YYY YY NNNNNN0NNNNNNNY0002080000000100001NNN00NNN000000040Y0900000197215560000'
    '000001001975061100000000584627800000000077804668500012       0 NYY0030537290014672'
    '5200153268211884000031.3920260630012160259511NNY'
)
# An ETN ("한투한미넥스트혁신성장1(A)") -- not a regular equity, KRX flag is "N".
ETN_LINE = (
    'F70100034KR5701000345한투한미넥스트혁신성장1(A)              BC '
    '000000000000NN 0NNN NN    N  0  N     000001073000010000'
    '0NNN00NNN000000100N090000000000000000000001000202601300000000000223030000000000223'
    '03495000         0 NNN00000000000000000000000000000000000000.00        000000239   NNN'
)


def test_parse_master_lines_extracts_regular_equity():
    rows = _parse_master_lines(
        [SAMSUNG_LINE], _KOSPI_FIELD_SPECS, _KOSPI_PART2_COLUMNS, "KRX", "시가총액"
    )
    assert len(rows) == 1
    assert rows[0]["ticker"] == "005930"
    assert rows[0]["name"] == "삼성전자"
    assert rows[0]["market_cap"] == 12160259


def test_parse_master_lines_excludes_non_equity_instruments():
    rows = _parse_master_lines(
        [SAMSUNG_LINE, ETN_LINE], _KOSPI_FIELD_SPECS, _KOSPI_PART2_COLUMNS, "KRX", "시가총액"
    )
    tickers = [r["ticker"] for r in rows]
    assert "005930" in tickers
    assert "F70100034" not in tickers
