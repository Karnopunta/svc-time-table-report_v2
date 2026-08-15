"""Date utilities for ETL report jobs - handle daily/weekly/monthly scheduling."""
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

JAKARTA_TZ = timezone(timedelta(hours=7))


def now_jakarta() -> datetime:
    """Return an aware timestamp in Asia/Jakarta timezone."""
    return datetime.now(JAKARTA_TZ)


def calculate_date_range(
    schedule_type: str,
    reference_date: str = None,
) -> Tuple[str, str]:
    """
    Calculate STARTDATE and ENDDATE based on schedule type.

    Args:
        schedule_type: 'daily', 'weekly', or 'monthly'
        reference_date: YYYY-MM-DD format (default: today Jakarta time)

    Returns:
        Tuple of (STARTDATE, ENDDATE) in 'YYYY-MM-DD' format.

    Examples:
        daily   -> (yesterday, today)            e.g. ('2026-03-24', '2026-03-25')
        weekly  -> (Mon prev week, Mon this week) e.g. ('2026-03-16', '2026-03-23')
        monthly -> (1st prev month, 1st this month) e.g. ('2026-02-01', '2026-03-01')
    """
    if reference_date:
        current_date = datetime.strptime(reference_date, "%Y-%m-%d").date()
    else:
        current_date = now_jakarta().date()

    schedule_type = schedule_type.lower().strip()

    if schedule_type == "daily":
        start_date = current_date - timedelta(days=1)
        end_date = current_date

    elif schedule_type == "weekly":
        days_since_monday = current_date.weekday()
        monday_this_week = current_date - timedelta(days=days_since_monday)
        start_date = monday_this_week - timedelta(days=7)
        end_date = monday_this_week

    elif schedule_type == "monthly":
        first_this_month = current_date.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        start_date = last_prev_month.replace(day=1)
        end_date = first_this_month

    else:
        raise ValueError(f"Invalid schedule_type: {schedule_type}. Use daily/weekly/monthly")

    logger.info(f"[{schedule_type.upper()}] date range: {start_date} -> {end_date}")
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def generate_looping_dates(
    start_date: str,
    end_date: str,
) -> List[Tuple[str, str]]:
    """
    Generate list of day-by-day (start, end) tuples for looping queries.

    Weekly/monthly jobs loop through each day individually so each DB hit
    covers exactly one day.

    Args:
        start_date: YYYY-MM-DD
        end_date:   YYYY-MM-DD

    Returns:
        List of ('YYYY-MM-DD', 'YYYY-MM-DD') tuples, one per day.

    Example (weekly):
        [('2026-03-16','2026-03-17'), ('2026-03-17','2026-03-18'), ...]
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    dates: List[Tuple[str, str]] = []
    current = start
    while current < end:
        next_day = current + timedelta(days=1)
        dates.append((current.strftime("%Y-%m-%d"), next_day.strftime("%Y-%m-%d")))
        current = next_day

    logger.info(f"Generated {len(dates)} looping date range(s)")
    return dates


def format_date(date_input, fmt: str = "%Y-%m-%d") -> str:
    """
    Format a date value to the given strftime pattern.

    Accepts datetime, date, or 'YYYY-MM-DD' / 'YYYY-MM-DD HH:MM:SS' strings.
    """
    if isinstance(date_input, str):
        for parse_fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                date_input = datetime.strptime(date_input, parse_fmt)
                break
            except ValueError:
                continue
        else:
            return date_input  # return as-is if unparseable
    return date_input.strftime(fmt)


def date_for_filename(reference_date: str = None) -> str:
    """Return YYYYMMDD string suitable for embedding in filenames."""
    if reference_date:
        return reference_date.replace("-", "")
    return now_jakarta().strftime("%Y%m%d")
