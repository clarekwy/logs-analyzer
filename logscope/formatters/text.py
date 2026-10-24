"""Text (terminal) formatter for all three commands."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

BAR_WIDTH = 40

# Use ASCII bar on terminals that can't handle Unicode block characters
_BAR_CHAR = "#" if (sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() in ("cp1252", "cp850", "ascii")) else "\u2588"


def _fmt_ts(ts: Optional[datetime]) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "N/A"


def _fmt_bucket_duration(seconds: int) -> str:
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    return f"{seconds // 60}m"


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summary(result: dict) -> str:
    counts = result["counts"]
    lines = [
        "=== Log Summary ===",
        f"  INFO   : {counts['INFO']}",
        f"  WARN   : {counts['WARN']}",
        f"  ERROR  : {counts['ERROR']}",
        f"  Total  : {result['total_valid']}",
        f"  Malformed (skipped): {result['malformed']}",
        f"  First timestamp: {_fmt_ts(result['first_timestamp'])}",
        f"  Last  timestamp: {_fmt_ts(result['last_timestamp'])}",
    ]
    if result["top_errors"]:
        lines.append("\nTop errors:")
        for item in result["top_errors"]:
            lines.append(f"  ({item['count']:>4}x)  {item['message']}")
    else:
        lines.append("\nNo ERROR entries found.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def timeline(result: dict) -> str:
    buckets = result["buckets"]
    duration_label = _fmt_bucket_duration(result["bucket_seconds"])

    if not buckets:
        return f"=== Timeline (bucket={duration_label}) ===\nNo ERROR entries found."

    max_count = max(b["count"] for b in buckets)
    lines = [f"=== Timeline (bucket={duration_label}) ==="]
    for b in buckets:
        ts = b["bucket_start"].strftime("%Y-%m-%d %H:%M")
        count = b["count"]
        bar_len = int(BAR_WIDTH * count / max_count) if max_count > 0 else 0
        bar = _BAR_CHAR * bar_len
        lines.append(f"  {ts}  {bar:<{BAR_WIDTH}} {count:>4}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Grep
# ---------------------------------------------------------------------------

def grep(lines: list[str]) -> str:
    return "\n".join(lines)
