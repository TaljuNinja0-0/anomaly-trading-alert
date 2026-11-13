"""KIS Open API client: OAuth token + domestic daily price inquiry."""

import time

import requests
import pandas as pd

BASE_URL = "https://openapi.koreainvestment.com:9443"

# The quote endpoint (FHKST03010100) returns at most ~100 rows per call; a
# 90-calendar-day chunk stays comfortably under that even on dense trading
# calendars (~60 trading days per 90 calendar days, observed in practice).
MAX_CHUNK_DAYS = 90


def get_access_token(app_key: str, app_secret: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/oauth2/tokenP",
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret,
        },
        timeout=(10, 30),
    )
    if not resp.ok:
        raise RuntimeError(f"KIS token request failed ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


def _chunk_date_ranges(start_date: str, end_date: str, max_days: int = MAX_CHUNK_DAYS):
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    chunks = []
    chunk_start = start_ts
    while chunk_start <= end_ts:
        chunk_end = min(chunk_start + pd.Timedelta(days=max_days), end_ts)
        chunks.append((chunk_start.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        if chunk_end >= end_ts:
            break
        chunk_start = chunk_end + pd.Timedelta(days=1)
    return chunks


def _fetch_daily_price_chunk(
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
        timeout=(10, 30),
    )
    if not resp.ok:
        raise RuntimeError(f"KIS daily price request failed ({resp.status_code}): {resp.text}")

    body = resp.json()
    if body.get("rt_cd") != "0":
        raise RuntimeError(f"KIS daily price request returned an error: {body.get('msg1')} (rt_cd={body.get('rt_cd')})")

    rows = body["output2"]
    if len(rows) >= 100:
        raise RuntimeError(
            f"KIS returned {len(rows)} rows for {ticker} {start_date}-{end_date} "
            "(>= the ~100-row-per-call cap) -- results may be silently truncated; "
            "narrow MAX_CHUNK_DAYS instead of trusting this response as complete."
        )

    return pd.DataFrame(
        {
            "date": [r["stck_bsop_date"] for r in rows],
            "close": [float(r["stck_clpr"]) for r in rows],
            "volume": [int(r["acml_vol"]) for r in rows],
        }
    )


def get_daily_price(
    access_token: str,
    app_key: str,
    app_secret: str,
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    chunks = _chunk_date_ranges(start_date, end_date)
    frames = []
    for i, (chunk_start, chunk_end) in enumerate(chunks):
        if i > 0:
            time.sleep(0.3)  # be polite to the quote endpoint between chunk calls
        frames.append(
            _fetch_daily_price_chunk(access_token, app_key, app_secret, ticker, chunk_start, chunk_end)
        )

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    return df
