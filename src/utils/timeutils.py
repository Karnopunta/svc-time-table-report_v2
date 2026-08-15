"""Time helpers for consistent timestamps."""
from datetime import datetime, timezone

def now_tz() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)
