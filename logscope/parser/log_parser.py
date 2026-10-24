"""Streaming log parser and LogEntry data model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Generator, IO, Optional, Tuple

VALID_LEVELS = frozenset({"INFO", "WARN", "ERROR"})

# Regex: YYYY-MM-DD HH:MM:SS LEVEL message
_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(INFO|WARN|ERROR)\s+(.+)$"
)


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    level: str
    message: str
    raw_line: str


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse 'YYYY-MM-DD HH:MM:SS'. Returns None on failure."""
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def parse_line(raw: str) -> Tuple[Optional[LogEntry], bool]:
    """
    Parse a single raw log line.

    Returns (LogEntry, True) on success, (None, False) on malformed input.
    """
    line = raw.rstrip("\n\r")
    m = _LINE_RE.match(line)
    if not m:
        return None, False

    ts = parse_timestamp(m.group(1))
    if ts is None:
        return None, False

    level = m.group(2)
    message = m.group(3).strip()
    if not message:
        return None, False

    return LogEntry(timestamp=ts, level=level, message=message, raw_line=line), True


def stream_entries(file_handle: IO[str]) -> Generator[Tuple[Optional[LogEntry], str], None, None]:
    """
    Yield (LogEntry | None, raw_line) for every line in *file_handle*.

    LogEntry is None for malformed lines; raw_line is always the original text.
    Reads one line at a time — safe for large files.
    """
    for raw in file_handle:
        entry, ok = parse_line(raw)
        yield entry, raw.rstrip("\n\r")
