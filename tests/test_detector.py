import numpy as np
import pandas as pd

from src.detector import volume_zscore, price_return_zscore, composite_score


def test_volume_zscore_flags_spike_above_3():
    volume = pd.Series([100, 105] * 10 + [1000])  # 20 baseline rows + 1 spike
    z = volume_zscore(volume, window=20)
    assert z.iloc[-1] > 3


def test_volume_zscore_is_nan_when_flat():
    volume = pd.Series([100] * 21)
    z = volume_zscore(volume, window=20)
    assert np.isnan(z.iloc[-1])


def test_volume_zscore_excludes_current_day_from_its_own_baseline():
    # A self-inclusive rolling window caps z at (n-1)/sqrt(n) ~= 4.25 for
    # window=20, no matter how extreme the spike. A trailing window that
    # excludes today has no such cap.
    volume = pd.Series([100, 105] * 10 + [100000])
    z = volume_zscore(volume, window=20)
    assert z.iloc[-1] > 100


def test_price_return_zscore_flags_spike_above_3():
    close = pd.Series(
        [100.0] + [100.5 if i % 2 == 0 else 100.0 for i in range(21)] + [300.0]
    )
    z = price_return_zscore(close, window=20)
    assert abs(z.iloc[-1]) > 3


def test_composite_score_is_weighted_average():
    vol_z = pd.Series([4.0])
    price_z = pd.Series([2.0])
    score = composite_score(vol_z, price_z)
    assert score.iloc[0] == 3.0
