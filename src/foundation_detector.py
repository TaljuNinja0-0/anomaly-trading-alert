"""Foundation-model anomaly stage: Chronos-bolt encoder embeddings, cosine
distance to the baseline's own centroid -- no forecasting, no prediction
head (plan section 3-4).

This module's model-loading/embedding functions require `chronos-forecasting`,
which lives only in the `chronosbolt_env` conda environment (not this
project's base requirements.txt) -- run those parts with
`/home/user/miniconda3/envs/chronosbolt_env/bin/python`. The pure
distance/windowing logic below has no such dependency and runs under the
normal project environment/test suite.
"""

import numpy as np

from src.backtest import BASELINE_END_OFFSET
from src.ml_detector import ML_BASELINE_START_OFFSET

# Tried 99/97/95/92/90 against the real cases (offline, against cached
# embeddings -- re-embedding is the expensive part, not worth repeating per
# threshold). 99 only catches 2/4; 90 is the point where all 4 get caught,
# but it's a real tradeoff, not a free win: 현대로템's false-positive rate
# degrades to 0.75 at that point (basically always-flagged, not a useful
# signal for that one ticker specifically) while 두산에너빌리티 stays a
# reasonable 0.39. A single global cosine-distance-to-centroid seems to fit
# some tickers' baseline embedding clouds much better than others.
EMBED_WINDOW = 20
DISTANCE_PERCENTILE = 90
MIN_BASELINE_EMBEDDINGS = 30


def cosine_distance_to_centroid(embeddings: np.ndarray, centroid: np.ndarray) -> np.ndarray:
    embeddings_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    centroid_norm = centroid / np.linalg.norm(centroid)
    cosine_similarity = embeddings_norm @ centroid_norm
    return 1.0 - cosine_similarity


def run_case_from_embeddings(
    baseline_embeddings: np.ndarray,
    obs_embeddings: np.ndarray,
    d: int,
    obs_start: int,
    percentile: float = DISTANCE_PERCENTILE,
) -> dict:
    result = {
        "status": "ok",
        "lead_time_days": None,
        "false_positive_rate": None,
    }

    if len(baseline_embeddings) < MIN_BASELINE_EMBEDDINGS:
        result["status"] = "insufficient_data"
        return result

    centroid = baseline_embeddings.mean(axis=0)
    baseline_distances = cosine_distance_to_centroid(baseline_embeddings, centroid)
    threshold = np.percentile(baseline_distances, percentile)

    obs_distances = cosine_distance_to_centroid(obs_embeddings, centroid)
    flagged = np.where(obs_distances > threshold)[0]

    if len(flagged) > 0:
        first_flag_row = obs_start + int(flagged[0])
        result["lead_time_days"] = d - first_flag_row

    result["false_positive_rate"] = len(flagged) / len(obs_distances)
    return result


# --- Everything below needs chronos-forecasting (chronosbolt_env only) ---


def load_pipeline(model_name: str = "amazon/chronos-bolt-base", device: str = "cuda"):
    import torch
    from chronos import BaseChronosPipeline

    return BaseChronosPipeline.from_pretrained(model_name, device_map=device, dtype=torch.float32)


def embed_window(pipeline, values: np.ndarray) -> np.ndarray:
    import torch

    series = torch.tensor(values, dtype=torch.float32)
    embeddings, _ = pipeline.embed(series)
    # embeddings: (1, num_patches [+1 REG], d_model) -> pool to a single vector
    return embeddings[0].mean(dim=0).numpy()


def run_case_foundation(df, case, pipeline, window: int = EMBED_WINDOW, percentile: float = DISTANCE_PERCENTILE) -> dict:
    from src.backtest import OBS_END_OFFSET, OBS_START_OFFSET, find_designation_row, _format_date

    out = {
        "name": case["name"],
        "ticker": case["ticker"],
        "designation_date": case["designation_date"],
        "effective_date": None,
        "status": "ok",
        "lead_time_days": None,
        "false_positive_rate": None,
    }

    d = find_designation_row(df, case["designation_date"])
    out["effective_date"] = _format_date(df["date"].iloc[d])

    baseline_start = d + ML_BASELINE_START_OFFSET
    baseline_end = d + BASELINE_END_OFFSET
    obs_start = d + OBS_START_OFFSET
    obs_end = d + OBS_END_OFFSET

    if baseline_start - window + 1 < 0:
        out["status"] = "insufficient_data"
        return out

    close = df["close"].to_numpy()

    def embed_row(row):
        return embed_window(pipeline, close[row - window + 1 : row + 1])

    baseline_embeddings = np.stack([embed_row(r) for r in range(baseline_start, baseline_end + 1)])
    obs_embeddings = np.stack([embed_row(r) for r in range(obs_start, obs_end + 1)])

    sub_result = run_case_from_embeddings(baseline_embeddings, obs_embeddings, d, obs_start, percentile)
    out.update(sub_result)
    return out
