from src.retry import with_retry


def test_with_retry_returns_result_on_first_success():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    result = with_retry(fn, max_attempts=3, sleep_fn=lambda s: None)
    assert result == "ok"
    assert len(calls) == 1


def test_with_retry_retries_transient_failures_then_succeeds():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    result = with_retry(fn, max_attempts=3, sleep_fn=lambda s: None)
    assert result == "ok"
    assert attempts["n"] == 3


def test_with_retry_raises_after_exhausting_attempts():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise ConnectionError("always fails")

    try:
        with_retry(fn, max_attempts=3, sleep_fn=lambda s: None)
        assert False, "expected ConnectionError"
    except ConnectionError:
        pass
    assert attempts["n"] == 3


def test_with_retry_backs_off_between_attempts():
    sleeps = []

    def fn():
        raise ConnectionError("fails")

    try:
        with_retry(fn, max_attempts=3, backoff_seconds=2, sleep_fn=sleeps.append)
    except ConnectionError:
        pass
    assert sleeps == [2, 4]  # slept between attempts 1->2 and 2->3, not after the last failure
