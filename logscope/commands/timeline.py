"""Timeline command: bucket ERROR events into time windows."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import IO

from parser.log_parser import stream_entries

_BUCKET_RE = re.compile(r"^(\d+)(m|h)$")


def parse_bucket(value: str) -> timedelta:
    """
    Parse a bucket duration string such as '5m', '15m', '1h', '2h'.

    Raises ValueError with a clear message on failure.
    """
    m = _BUCKET_RE.match(value.strip())
    if not m:
        raise ValueError(
            f"invalid --bucket value {value!r}. Use a duration such as 15m or 1h."
        )
    n = int(m.group(1))
    unit = m.group(2)
    if n <= 0:
        raise ValueError(
            f"invalid --bucket value {value!r}. Duration must be positive."
        )
    if unit == "m":
        return timedelta(minutes=n)
    return timedelta(hours=n)


def _bucket_floor(ts: datetime, bucket: timedelta) -> datetime:
    """Return the start of the bucket containing *ts*."""
    epoch = datetime(1970, 1, 1)
    delta = ts - epoch
    bucket_secs = int(bucket.total_seconds())
    floored_secs = (int(delta.total_seconds()) // bucket_secs) * bucket_secs
    return epoch + timedelta(seconds=floored_secs)


def run(file_handle: IO[str], bucket: timedelta) -> dict:
    """
    Single-pass timeline aggregation.

    Returns a dict with keys:
      bucket_seconds  int
      buckets         list[dict]  — {bucket_start: datetime, count: int}
      malformed       int
    """
    malformed = 0
    raw_buckets: dict[datetime, int] = {}

    for entry, _raw in stream_entries(file_handle):
        if entry is None:
            malformed += 1
            continue
        if entry.level != "ERROR":
            continue
        floor = _bucket_floor(entry.timestamp, bucket)
        raw_buckets[floor] = raw_buckets.get(floor, 0) + 1

    if not raw_buckets:
        return {
            "bucket_seconds": int(bucket.total_seconds()),
            "buckets": [],
            "malformed": malformed,
        }

    # Fill empty buckets between first and last
    first = min(raw_buckets)
    last = max(raw_buckets)
    buckets = []
    current = first
    while current <= last:
        buckets.append({"bucket_start": current, "count": raw_buckets.get(current, 0)})
        current += bucket

    return {
        "bucket_seconds": int(bucket.total_seconds()),
        "buckets": buckets,
        "malformed": malformed,
    }
