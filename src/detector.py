"""Statistical anomaly rule: volume z-score + price-return z-score."""

import numpy as np
import pandas as pd


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    baseline = series.shift(1)  # compare today against the trailing window, excluding today
    mean = baseline.rolling(window).mean()
    std = baseline.rolling(window).std().replace(0, np.nan)
    return (series - mean) / std


def volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series:
    return _rolling_zscore(volume, window)


def price_return_zscore(close: pd.Series, window: int = 20) -> pd.Series:
    returns = close.pct_change()
    return _rolling_zscore(returns, window)


def composite_score(vol_z: pd.Series, price_z: pd.Series) -> pd.Series:
    return 0.5 * vol_z + 0.5 * price_z
