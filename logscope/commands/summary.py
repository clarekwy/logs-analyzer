"""Summary command: single-pass aggregation over a log file."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import IO, Optional

from parser.log_parser import stream_entries


def run(file_handle: IO[str]) -> dict:
    """
    Single-pass summary over *file_handle*.

    Returns a dict with keys:
      counts          dict[str, int]  — INFO/WARN/ERROR counts
      total_valid     int
      malformed       int
      first_timestamp datetime | None
      last_timestamp  datetime | None
      top_errors      list[dict]      — up to 5 {message, count}
    """
    counts: dict[str, int] = {"INFO": 0, "WARN": 0, "ERROR": 0}
    total_valid = 0
    malformed = 0
    first_ts: Optional[datetime] = None
    last_ts: Optional[datetime] = None
    error_counter: Counter = Counter()

    for entry, _raw in stream_entries(file_handle):
        if entry is None:
            malformed += 1
            continue

        counts[entry.level] += 1
        total_valid += 1

        if first_ts is None or entry.timestamp < first_ts:
            first_ts = entry.timestamp
        if last_ts is None or entry.timestamp > last_ts:
            last_ts = entry.timestamp

        if entry.level == "ERROR":
            error_counter[entry.message] += 1

    # Top-5: descending count, alphabetical on ties
    top_errors = [
        {"message": msg, "count": cnt}
        for msg, cnt in sorted(error_counter.items(), key=lambda x: (-x[1], x[0]))[:5]
    ]

    return {
        "counts": counts,
        "total_valid": total_valid,
        "malformed": malformed,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "top_errors": top_errors,
    }
