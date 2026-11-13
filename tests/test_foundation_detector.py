import numpy as np

from src.foundation_detector import cosine_distance_to_centroid, run_case_from_embeddings


def test_cosine_distance_to_centroid_is_zero_for_identical_vectors():
    centroid = np.array([1.0, 0.0, 0.0])
    embeddings = np.array([[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])  # same direction, different scale
    distances = cosine_distance_to_centroid(embeddings, centroid)
    assert np.allclose(distances, 0.0, atol=1e-6)


def test_cosine_distance_to_centroid_is_large_for_orthogonal_vector():
    centroid = np.array([1.0, 0.0])
    embeddings = np.array([[0.0, 1.0]])
    distances = cosine_distance_to_centroid(embeddings, centroid)
    assert np.allclose(distances, 1.0)


def test_run_case_from_embeddings_flags_the_known_outlier():
    rng = np.random.RandomState(0)
    baseline_embeddings = rng.normal(0, 0.01, size=(70, 16)) + np.array([1.0] + [0.0] * 15)
    obs_embeddings = rng.normal(0, 0.01, size=(36, 16)) + np.array([1.0] + [0.0] * 15)
    outlier_row_in_obs = 10
    obs_embeddings[outlier_row_in_obs] = np.array([0.0, 1.0] + [0.0] * 14)  # orthogonal direction

    d = 100
    obs_start = d - 30
    result = run_case_from_embeddings(baseline_embeddings, obs_embeddings, d, obs_start, percentile=99)

    assert result["status"] == "ok"
    expected_lead_time = d - (obs_start + outlier_row_in_obs)
    assert abs(result["lead_time_days"] - expected_lead_time) <= 2


def test_run_case_from_embeddings_insufficient_data_when_baseline_too_small():
    baseline_embeddings = np.zeros((5, 16))
    obs_embeddings = np.zeros((36, 16))
    result = run_case_from_embeddings(baseline_embeddings, obs_embeddings, 100, 70, percentile=99)
    assert result["status"] == "insufficient_data"
    assert result["lead_time_days"] is None
