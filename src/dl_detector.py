"""DL anomaly stage: LSTM Autoencoder reconstruction error over sequences.

Adapts plan section 3-3 to the toy demo's daily bars and available
signals: 2 channels (volume z-score, price-return z-score) instead of 3
(order-book imbalance excluded, same as the stat-rule and ML stages), and
a sequence length in trading days rather than 1-minute bars.
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from src.backtest import (
    BASELINE_END_OFFSET,
    OBS_START_OFFSET,
    OBS_END_OFFSET,
    find_designation_row,
    _format_date,
)
from src.detector import volume_zscore, price_return_zscore
from src.ml_detector import ML_BASELINE_LOOKBACK, ML_BASELINE_START_OFFSET

SEQ_LEN = 20
N_CHANNELS = 2
# Tried 99/95/90/85 against the real cases: lowering this only raised the
# false-positive rate on the one case it already caught, it never unlocked
# a new detection. Diagnosed why: observation-window reconstruction errors
# came out LOWER than the baseline's own training errors for 3 of 4 cases --
# a sustained multi-month momentum run-up (what these designations actually
# are) reconstructs *more* smoothly than ordinary daily noise, so
# reconstruction-error is structurally a poor fit for this kind of gradual
# anomaly. It's a better fit for a sharp, short discontinuity (what the
# synthetic test below actually is). This is why the ML stage (point-wise
# IsolationForest) outperforms this stage on the real cases.
RECONSTRUCTION_ERROR_PERCENTILE = 99


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {"vol_z": volume_zscore(df["volume"]), "price_z": price_return_zscore(df["close"])}
    )


def build_sequences(features: pd.DataFrame, seq_len: int = SEQ_LEN) -> np.ndarray:
    values = features.to_numpy(dtype=np.float32)
    n = len(values)
    if n < seq_len:
        return np.empty((0, seq_len, values.shape[1]), dtype=np.float32)
    return np.stack([values[i : i + seq_len] for i in range(n - seq_len + 1)])


class LSTMAutoencoder(nn.Module):
    def __init__(self, n_channels: int = N_CHANNELS, encoder_hidden: int = 64, latent: int = 16):
        super().__init__()
        self.encoder1 = nn.LSTM(n_channels, encoder_hidden, batch_first=True)
        self.encoder2 = nn.LSTM(encoder_hidden, latent, batch_first=True)
        self.decoder1 = nn.LSTM(latent, latent, batch_first=True)
        self.decoder2 = nn.LSTM(latent, encoder_hidden, batch_first=True)
        self.output = nn.Linear(encoder_hidden, n_channels)

    def forward(self, x):
        seq_len = x.shape[1]
        h, _ = self.encoder1(x)
        h, (latent_h, _) = self.encoder2(h)
        latent_repeated = latent_h[-1].unsqueeze(1).repeat(1, seq_len, 1)
        h, _ = self.decoder1(latent_repeated)
        h, _ = self.decoder2(h)
        return self.output(h)


def _per_sequence_mse(model: LSTMAutoencoder, sequences: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        reconstructed = model(sequences)
        return ((reconstructed - sequences) ** 2).mean(dim=(1, 2))


def train_autoencoder(sequences: np.ndarray, epochs: int = 100, lr: float = 1e-3, random_state: int = 42) -> tuple:
    torch.manual_seed(random_state)
    model = LSTMAutoencoder()
    x = torch.from_numpy(sequences)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        reconstructed = model(x)
        loss = loss_fn(reconstructed, x)
        loss.backward()
        optimizer.step()

    model.eval()
    training_errors = _per_sequence_mse(model, x).numpy()
    return model, training_errors


def run_case_dl(
    df: pd.DataFrame,
    case: dict,
    seq_len: int = SEQ_LEN,
    epochs: int = 100,
    random_state: int = 42,
    percentile: float = RECONSTRUCTION_ERROR_PERCENTILE,
) -> dict:
    result = {
        "name": case["name"],
        "ticker": case["ticker"],
        "designation_date": case["designation_date"],
        "effective_date": None,
        "status": "ok",
        "lead_time_days": None,
        "false_positive_rate": None,
    }

    d = find_designation_row(df, case["designation_date"])
    result["effective_date"] = _format_date(df["date"].iloc[d])

    baseline_start = d + ML_BASELINE_START_OFFSET
    baseline_end = d + BASELINE_END_OFFSET
    obs_start = d + OBS_START_OFFSET
    obs_end = d + OBS_END_OFFSET

    if baseline_start < 0:
        result["status"] = "insufficient_data"
        return result

    features = build_features(df)
    baseline_features = features.loc[baseline_start:baseline_end]
    if baseline_features.isna().any().any():
        result["status"] = "insufficient_data"
        return result

    baseline_sequences = build_sequences(baseline_features, seq_len)
    if len(baseline_sequences) < seq_len:
        # too few training sequences for a seq_len-length window to mean anything
        result["status"] = "insufficient_data"
        return result

    model, training_errors = train_autoencoder(baseline_sequences, epochs=epochs, random_state=random_state)
    threshold = np.percentile(training_errors, percentile)

    # Observation-window sequences each end on an obs day but may draw
    # their lookback from before obs_start (that history exists in df).
    obs_rows = range(obs_start, obs_end + 1)
    flagged_rows = []
    for row in obs_rows:
        seq_start = row - seq_len + 1
        if seq_start < 0:
            continue
        window = features.loc[seq_start:row]
        if window.isna().any().any():
            continue
        seq = window.to_numpy(dtype=np.float32)[np.newaxis, :, :]
        error = _per_sequence_mse(model, torch.from_numpy(seq)).item()
        if error > threshold:
            flagged_rows.append(row)

    if flagged_rows:
        result["lead_time_days"] = d - flagged_rows[0]

    evaluated = sum(1 for row in obs_rows if row - seq_len + 1 >= 0)
    result["false_positive_rate"] = len(flagged_rows) / evaluated if evaluated else None

    return result
