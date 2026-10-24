"""Grep command: filter log lines by level and optional --since timestamp."""

from __future__ import annotations

from datetime import datetime
from typing import IO, Generator, Optional

from parser.log_parser import stream_entries, VALID_LEVELS


def parse_since(value: str) -> datetime:
    """
    Parse a --since timestamp.

    Accepts 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD HH:MM'.
    Raises ValueError with a clear message on failure.
    """
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"invalid --since timestamp. Use YYYY-MM-DD HH:MM:SS or YYYY-MM-DD HH:MM."
    )


def run(
    file_handle: IO[str],
    level: str,
    since: Optional[datetime] = None,
) -> Generator[str, None, None]:
    """
    Yield matching raw log lines in source-file order.

    Lines are yielded immediately (no retention) to keep memory bounded.
    Malformed lines are silently skipped.
    """
    for entry, raw in stream_entries(file_handle):
        if entry is None:
            continue
        if entry.level != level:
            continue
        if since is not None and entry.timestamp < since:
            continue
        yield raw
