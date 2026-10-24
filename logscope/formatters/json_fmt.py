"""JSON formatter for all three commands."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional


def _serialise(obj: Any) -> Any:
    """Custom serialiser for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def _dumps(data: Any) -> str:
    return json.dumps(data, default=_serialise, indent=2)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summary(result: dict, input_file: str) -> str:
    payload = {
        "command": "summary",
        "input_file": input_file,
        "counts": result["counts"],
        "total_valid": result["total_valid"],
        "malformed": result["malformed"],
        "first_timestamp": result["first_timestamp"],
        "last_timestamp": result["last_timestamp"],
        "top_errors": result["top_errors"],
    }
    return _dumps(payload)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def timeline(result: dict, input_file: str) -> str:
    buckets_out = [
        {
            "bucket_start": b["bucket_start"],
            "count": b["count"],
        }
        for b in result["buckets"]
    ]
    payload = {
        "command": "timeline",
        "input_file": input_file,
        "bucket_seconds": result["bucket_seconds"],
        "malformed": result["malformed"],
        "buckets": buckets_out,
    }
    return _dumps(payload)


# ---------------------------------------------------------------------------
# Grep
# ---------------------------------------------------------------------------

def grep(lines: list[str], input_file: str, level: str, since: Optional[str]) -> str:
    payload = {
        "command": "grep",
        "input_file": input_file,
        "level": level,
        "since": since,
        "matches": lines,
    }
    return _dumps(payload)
