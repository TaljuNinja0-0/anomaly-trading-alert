from src.kis_client import _chunk_date_ranges


def test_chunk_date_ranges_single_chunk_when_within_max_days():
    chunks = _chunk_date_ranges("20260101", "20260110", max_days=90)
    assert chunks == [("20260101", "20260110")]


def test_chunk_date_ranges_splits_long_range():
    # 200 days with max_days=90 must split into 3 non-overlapping,
    # contiguous chunks covering the whole range exactly once.
    chunks = _chunk_date_ranges("20260101", "20260719", max_days=90)
    assert len(chunks) == 3
    assert chunks[0][0] == "20260101"
    assert chunks[-1][1] == "20260719"
    for (prev_start, prev_end), (next_start, next_end) in zip(chunks, chunks[1:]):
        assert next_start > prev_end  # contiguous, no overlap, no gap bigger than 1 day
