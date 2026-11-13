"""Market-cap ranking (KOSPI+KOSDAQ combined top-N universe).

The KIS REST ranking endpoint (FHPST01740000) hard-caps at 30 rows per
call regardless of parameters (confirmed empirically: default call,
fid_vol_cnt=200, and a tr_cont="N" continuation request all returned the
same top 30, no continuation key in the response). For a 200-ticker
universe, this module instead downloads KIS's own published stock-master
files (kospi_code.mst / kosdaq_code.mst -- the same files KIS's official
GitHub examples, koreainvestment/open-trading-api/stocks_info/, use),
which cover the full listed universe and already carry each ticker's
market cap as a field. No KIS auth is needed for these -- they're public
static files.
"""

import os
import tempfile
import zipfile

import requests

KOSPI_MST_URL = "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip"
KOSDAQ_MST_URL = "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip"

# Field layout copied from KIS's own official parsing examples
# (stocks_info/kis_kospi_code_mst.py, kis_kosdaq_code_mst.py). Each
# script's field_specs sums to one less than its row[-N:] slice width --
# the extra byte is the line's trailing newline, not a data field.
_KOSPI_FIELD_SPECS = [
    2, 1, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 9, 5, 5, 1, 1, 1, 2, 1, 1, 1, 2, 2, 2, 3, 1, 3,
    12, 12, 8, 15, 21, 2, 7, 1, 1, 1, 1, 1, 9, 9, 9, 5, 9, 8, 9, 3, 1, 1, 1,
]
_KOSPI_PART2_COLUMNS = [
    "그룹코드", "시가총액규모", "지수업종대분류", "지수업종중분류", "지수업종소분류",
    "제조업", "저유동성", "지배구조지수종목", "KOSPI200섹터업종", "KOSPI100",
    "KOSPI50", "KRX", "ETP", "ELW발행", "KRX100",
    "KRX자동차", "KRX반도체", "KRX바이오", "KRX은행", "SPAC",
    "KRX에너지화학", "KRX철강", "단기과열", "KRX미디어통신", "KRX건설",
    "Non1", "KRX증권", "KRX선박", "KRX섹터_보험", "KRX섹터_운송",
    "SRI", "기준가", "매매수량단위", "시간외수량단위", "거래정지",
    "정리매매", "관리종목", "시장경고", "경고예고", "불성실공시",
    "우회상장", "락구분", "액면변경", "증자구분", "증거금비율",
    "신용가능", "신용기간", "전일거래량", "액면가", "상장일자",
    "상장주수", "자본금", "결산월", "공모가", "우선주",
    "공매도과열", "이상급등", "KRX300", "KOSPI", "매출액",
    "영업이익", "경상이익", "당기순이익", "ROE", "기준년월",
    "시가총액", "그룹사코드", "회사신용한도초과", "담보대출가능", "대주가능",
]
_KOSPI_MARKET_CAP_COLUMN = "시가총액"


def _is_kospi_common_stock(values: dict) -> bool:
    # "KRX" means "member of a KRX sector index", not "is a regular
    # equity" -- filtering on it silently drops real top-200 companies
    # that just aren't in an index (confirmed against real downloaded
    # data: 9/200 true top-200 names excluded, 9 smaller ones took their
    # place). 그룹코드=="ST" is the actual "this is a stock" flag;
    # 우선주=="0" excludes preferred shares so one company isn't counted
    # twice via its common + preferred listings.
    return values["그룹코드"] == "ST" and values["우선주"] == "0"

_KOSDAQ_FIELD_SPECS = [
    2, 1, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 9, 5, 5, 1, 1, 1, 2, 1, 1, 1, 2, 2, 2, 3, 1, 3, 12, 12, 8, 15,
    21, 2, 7, 1, 1, 1, 1, 9, 9, 9, 5, 9, 8, 9, 3, 1, 1, 1,
]
_KOSDAQ_PART2_COLUMNS = [
    "증권그룹구분코드", "시가총액 규모 구분 코드 유가", "지수업종 대분류 코드",
    "지수 업종 중분류 코드", "지수업종 소분류 코드", "벤처기업 여부 (Y/N)",
    "저유동성종목 여부", "KRX 종목 여부", "ETP 상품구분코드", "KRX100 종목 여부 (Y/N)",
    "KRX 자동차 여부", "KRX 반도체 여부", "KRX 바이오 여부", "KRX 은행 여부", "기업인수목적회사여부",
    "KRX 에너지 화학 여부", "KRX 철강 여부", "단기과열종목구분코드", "KRX 미디어 통신 여부",
    "KRX 건설 여부", "(코스닥)투자주의환기종목여부", "KRX 증권 구분", "KRX 선박 구분",
    "KRX섹터지수 보험여부", "KRX섹터지수 운송여부", "KOSDAQ150지수여부 (Y,N)", "주식 기준가",
    "정규 시장 매매 수량 단위", "시간외 시장 매매 수량 단위", "거래정지 여부", "정리매매 여부",
    "관리 종목 여부", "시장 경고 구분 코드", "시장 경고위험 예고 여부", "불성실 공시 여부",
    "우회 상장 여부", "락구분 코드", "액면가 변경 구분 코드", "증자 구분 코드", "증거금 비율",
    "신용주문 가능 여부", "신용기간", "전일 거래량", "주식 액면가", "주식 상장 일자", "상장 주수(천)",
    "자본금", "결산 월", "공모 가격", "우선주 구분 코드", "공매도과열종목여부", "이상급등종목여부",
    "KRX300 종목 여부 (Y/N)", "매출액", "영업이익", "경상이익", "단기순이익", "ROE(자기자본이익률)",
    "기준년월", "전일기준 시가총액 (억)", "그룹사 코드", "회사신용한도초과여부", "담보대출가능여부", "대주가능여부",
]
_KOSDAQ_MARKET_CAP_COLUMN = "전일기준 시가총액 (억)"


def _is_kosdaq_common_stock(values: dict) -> bool:
    return values["증권그룹구분코드"] == "ST" and values["우선주 구분 코드"] == "0"


def _parse_master_lines(lines, field_specs, part2_columns, is_common_stock, market_cap_column):
    part2_width = sum(field_specs)
    results = []
    for raw in lines:
        row = raw.rstrip("\n")
        if len(row) <= part2_width:
            continue
        part1 = row[: len(row) - part2_width]
        ticker = part1[0:9].strip()
        name = part1[21:].strip()

        part2 = row[-part2_width:]
        pos = 0
        values = {}
        for column, width in zip(part2_columns, field_specs):
            values[column] = part2[pos : pos + width]
            pos += width

        if not is_common_stock(values):
            continue
        try:
            market_cap = int(values[market_cap_column])
        except ValueError:
            continue

        results.append({"ticker": ticker, "name": name, "market_cap": market_cap})
    return results


def _download_and_extract_mst(url: str, dest_dir: str) -> str:
    resp = requests.get(url, timeout=(10, 30))
    resp.raise_for_status()
    zip_path = os.path.join(dest_dir, os.path.basename(url))
    with open(zip_path, "wb") as f:
        f.write(resp.content)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest_dir)
    return os.path.join(dest_dir, os.path.basename(url)[: -len(".zip")])


def get_market_cap_ranking(
    access_token: str,
    app_key: str,
    app_secret: str,
    market: str = "0000",
    limit: int = 200,
) -> list:
    """access_token/app_key/app_secret/market are accepted but unused --
    the master-file source needs no auth and always covers both markets.
    Kept in the signature so callers (run_universe_scan.py) don't change."""
    with tempfile.TemporaryDirectory() as tmp:
        kospi_path = _download_and_extract_mst(KOSPI_MST_URL, tmp)
        with open(kospi_path, encoding="cp949") as f:
            kospi_rows = _parse_master_lines(
                f.readlines(), _KOSPI_FIELD_SPECS, _KOSPI_PART2_COLUMNS,
                _is_kospi_common_stock, _KOSPI_MARKET_CAP_COLUMN,
            )

        kosdaq_path = _download_and_extract_mst(KOSDAQ_MST_URL, tmp)
        with open(kosdaq_path, encoding="cp949") as f:
            kosdaq_rows = _parse_master_lines(
                f.readlines(), _KOSDAQ_FIELD_SPECS, _KOSDAQ_PART2_COLUMNS,
                _is_kosdaq_common_stock, _KOSDAQ_MARKET_CAP_COLUMN,
            )

    all_rows = kospi_rows + kosdaq_rows
    all_rows.sort(key=lambda r: -r["market_cap"])
    return [{"ticker": r["ticker"], "name": r["name"]} for r in all_rows[:limit]]
