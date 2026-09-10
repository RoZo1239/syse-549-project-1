"""One UTC timestamp helper, used by every service.

Sub-second precision is mandatory: the cross-service ordering check
(conformance check H-ORD) sorts transcript events from four independent
processes by `ts`, and whole-second timestamps collide.
"""

from datetime import datetime, timezone


def now_iso() -> str:
    """Current UTC time as ISO 8601 with millisecond precision and a Z suffix.

    >>> now_iso()  # doctest: +SKIP
    '2026-09-14T18:22:03.114Z'
    """
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def iso_from_epoch(epoch_seconds: float) -> str:
    """Format an epoch timestamp the same way `now_iso` formats the clock."""
    return (
        datetime.fromtimestamp(epoch_seconds, timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
