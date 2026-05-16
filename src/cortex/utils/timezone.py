"""Timezone helpers — Cortex displays everything in America/Los_Angeles (PT).

DB columns intentionally store UTC via SYSUTCDATETIME (best practice). All
*human-facing* timestamps — vault frontmatter, alert emails, webhook
response payloads, log lines — go through these helpers to render in PT
with DST handled automatically by the IANA zone.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


def now_pacific() -> datetime:
    """Current time in America/Los_Angeles (PDT or PST depending on DST)."""
    return datetime.now(PACIFIC)


def to_pacific(dt: datetime) -> datetime:
    """Convert any aware/naive datetime to America/Los_Angeles."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(PACIFIC)


def fmt_pacific(dt: datetime | None = None, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """Format a datetime in Pacific time. Default fmt includes PDT/PST suffix."""
    if dt is None:
        dt = now_pacific()
    else:
        dt = to_pacific(dt)
    return dt.strftime(fmt)
