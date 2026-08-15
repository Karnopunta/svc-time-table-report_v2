"""Backoff helpers for retry scheduling."""
import random
from datetime import datetime, timedelta

def next_retry_at(
    now: datetime,
    attempt_no: int,
    interval_type: str,
    interval_value: int,
    multiplier: float,
    jitter_ratio: float = 0.1,
) -> datetime:
    if interval_type == "EXPONENTIAL":
        base = interval_value * (multiplier ** max(0, attempt_no - 1))
    elif interval_type == "LINEAR":
        base = interval_value * max(1, attempt_no)
    else:
        base = interval_value
    jitter = base * random.uniform(-jitter_ratio, jitter_ratio)
    return now + timedelta(seconds=max(1, int(base + jitter)))
