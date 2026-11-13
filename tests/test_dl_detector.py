import numpy as np
import pandas as pd
import torch

from src.dl_detector import build_sequences, run_case_dl, train_autoencoder


def _dates(n, start="20260101"):
    base = pd.Timestamp(start)
    return [(base + pd.Timedelta(days=i)).strftime("%Y%m%d") for i in range(n)]


def _designation_date_for_row(df, row):
    d = df["date"].iloc[row]
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def _noisy_case_df(n, spike_row, spike_multiplier=1.8, spike_volume=50000, seed=0):
    rng = np.random.RandomState(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.15, n))
    volume = 1000 + rng.normal(0, 25, n)
    close[spike_row] = close[spike_row - 1] * spike_multiplier
    volume[spike_row] = spike_volume
    return pd.DataFrame({"date": _dates(n), "close": close, "volume": volume})


def test_build_sequences_shape():
    features = pd.DataFrame({"vol_z": np.arange(30, dtype=float), "price_z": np.arange(30, dtype=float)})
    sequences = build_sequences(features, seq_len=20)
    # 30 rows, seq_len=20 -> 11 overlapping windows (0..19, 1..20, ..., 10..29)
    assert sequences.shape == (11, 20, 2)


def test_train_autoencoder_is_deterministic_without_external_seeding():
    # The caller shouldn't have to remember to torch.manual_seed() before
    # calling -- weight init must be seeded internally, not left to
    # whatever state torch's global RNG happens to be in.
    features = pd.DataFrame(
        {"vol_z": np.linspace(-1, 1, 60), "price_z": np.linspace(1, -1, 60)}
    )
    sequences = build_sequences(features, seq_len=20)
    _, errors_a = train_autoencoder(sequences, epochs=5)
    _, errors_b = train_autoencoder(sequences, epochs=5)
    assert np.array_equal(errors_a, errors_b)


def test_run_case_dl_flags_the_known_spike():
    designation_row = 220
    spike_row = 200
    df = _noisy_case_df(n=250, spike_row=spike_row)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": _designation_date_for_row(df, designation_row),
    }
    result = run_case_dl(df, case, epochs=30)
    assert result["status"] == "ok"
    expected_lead_time = designation_row - spike_row
    assert result["lead_time_days"] is not None
    assert abs(result["lead_time_days"] - expected_lead_time) <= 8


def test_run_case_dl_insufficient_data_when_baseline_too_short():
    df = _noisy_case_df(n=40, spike_row=35)
    case = {
        "name": "테스트종목",
        "ticker": "000000",
        "designation_date": _designation_date_for_row(df, 35),
    }
    result = run_case_dl(df, case, epochs=5)
    assert result["status"] == "insufficient_data"
    assert result["lead_time_days"] is None
