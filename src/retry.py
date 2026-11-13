"""Retry transient failures (network blips, timeouts) so they don't need
a human to notice and re-run -- only a genuinely broken call should ever
surface as an error."""

import time


def with_retry(fn, max_attempts: int = 3, backoff_seconds: float = 2, sleep_fn=time.sleep):
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception:
            if attempt == max_attempts:
                raise
            sleep_fn(backoff_seconds * attempt)
