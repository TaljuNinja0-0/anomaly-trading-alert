"""Market-cap ranking (KOSPI+KOSDAQ combined top-N universe)."""

import requests

from src.kis_client import BASE_URL


def _parse_ranking_rows(rows: list, limit: int) -> list:
    return [
        {"ticker": r["mksc_shrn_iscd"], "name": r["hts_kor_isnm"]}
        for r in rows[:limit]
    ]


def get_market_cap_ranking(
    access_token: str,
    app_key: str,
    app_secret: str,
    market: str = "0000",
    limit: int = 200,
) -> list:
    resp = requests.get(
        f"{BASE_URL}/uapi/domestic-stock/v1/ranking/market-cap",
        headers={
            "authorization": f"Bearer {access_token}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHPST01740000",
        },
        params={
            "fid_cond_scr_div_code": "20174",
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": market,
            "fid_div_cls_code": "0",
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_input_price_1": "",
            "fid_input_price_2": "",
            "fid_vol_cnt": "",
        },
    )
    if not resp.ok:
        raise RuntimeError(f"KIS market-cap ranking request failed ({resp.status_code}): {resp.text}")

    body = resp.json()
    if body.get("rt_cd") != "0":
        raise RuntimeError(f"KIS market-cap ranking returned an error: {body.get('msg1')} (rt_cd={body.get('rt_cd')})")

    return _parse_ranking_rows(body["output"], limit)
