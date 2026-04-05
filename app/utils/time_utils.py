from datetime import datetime, timedelta
import pytz


def now_in_tz(timezone: str = "America/Los_Angeles") -> datetime:
    """Get current datetime in the specified timezone."""
    return datetime.now(pytz.timezone(timezone))


def format_time_range(start_iso: str, end_iso: str, timezone: str = "America/Los_Angeles") -> str:
    """Format a time range as human-readable string. E.g., 'Saturday Jan 15, 2:00 PM - 3:30 PM'"""
    tz = pytz.timezone(timezone)
    start = datetime.fromisoformat(start_iso).astimezone(tz)
    end = datetime.fromisoformat(end_iso).astimezone(tz)

    if start.date() == end.date():
        return f"{start.strftime('%A %b %d, %I:%M %p')} - {end.strftime('%I:%M %p')}"
    return f"{start.strftime('%A %b %d, %I:%M %p')} - {end.strftime('%A %b %d, %I:%M %p')}"


def date_range_to_iso(date_start: str, date_end: str, timezone: str = "America/Los_Angeles") -> tuple[str, str]:
    """Convert YYYY-MM-DD date strings to ISO 8601 datetime strings covering the full day range."""
    tz = pytz.timezone(timezone)
    start = tz.localize(datetime.strptime(date_start, "%Y-%m-%d").replace(hour=0, minute=0, second=0))
    end = tz.localize(datetime.strptime(date_end, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
    return start.isoformat(), end.isoformat()


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return len(text) // 4
