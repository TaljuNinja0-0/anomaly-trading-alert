"""KIS Open API client: OAuth token + domestic daily price inquiry."""

import requests
import pandas as pd

BASE_URL = "https://openapi.koreainvestment.com:9443"


def get_access_token(app_key: str, app_secret: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/oauth2/tokenP",
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret,
        },
    )
    if not resp.ok:
        raise RuntimeError(f"KIS token request failed ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


def get_daily_price(
    access_token: str,
    app_key: str,
    app_secret: str,
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    resp = requests.get(
        f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        headers={
            "authorization": f"Bearer {access_token}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHKST03010100",
        },
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        },
    )
    if not resp.ok:
        raise RuntimeError(f"KIS daily price request failed ({resp.status_code}): {resp.text}")

    rows = resp.json()["output2"]
    df = pd.DataFrame(
        {
            "date": [r["stck_bsop_date"] for r in rows],
            "close": [float(r["stck_clpr"]) for r in rows],
            "volume": [int(r["acml_vol"]) for r in rows],
        }
    )
    return df.sort_values("date").reset_index(drop=True)
