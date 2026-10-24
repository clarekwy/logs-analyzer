"""Markdown formatter — writes report files, returns the path."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _fmt_ts(ts: Optional[datetime]) -> str:
    return ts.isoformat() if ts else "N/A"


def _report_path(input_file: str, command: str) -> Path:
    return Path(input_file).with_suffix("").parent / (Path(input_file).name + f".{command}.md")


def _write(path: Path, content: str) -> None:
    """Write *content* to *path*, raising SystemExit(3) on failure."""
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"Error: could not write report {path}: {exc}", file=sys.stderr)
        raise SystemExit(3) from exc


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summary(result: dict, input_file: str) -> str:
    counts = result["counts"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Log Summary Report",
        f"",
        f"| Field | Value |",
        f"|---|---|",
        f"| Input file | `{input_file}` |",
        f"| Generated | {now} |",
        f"",
        f"## Severity Counts",
        f"",
        f"| Level | Count |",
        f"|---|---|",
        f"| INFO | {counts['INFO']} |",
        f"| WARN | {counts['WARN']} |",
        f"| ERROR | {counts['ERROR']} |",
        f"| **Total valid** | **{result['total_valid']}** |",
        f"| Malformed (skipped) | {result['malformed']} |",
        f"",
        f"## Timestamps",
        f"",
        f"- **First:** {_fmt_ts(result['first_timestamp'])}",
        f"- **Last:** {_fmt_ts(result['last_timestamp'])}",
        f"",
        f"## Top Errors",
        f"",
    ]
    if result["top_errors"]:
        lines += [
            "| Count | Message |",
            "|---|---|",
        ]
        for item in result["top_errors"]:
            lines.append(f"| {item['count']} | {item['message']} |")
    else:
        lines.append("_No ERROR entries found._")

    content = "\n".join(lines) + "\n"
    path = _report_path(input_file, "summary")
    _write(path, content)
    return str(path)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def timeline(result: dict, input_file: str, bucket_label: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Log Timeline Report",
        f"",
        f"| Field | Value |",
        f"|---|---|",
        f"| Input file | `{input_file}` |",
        f"| Bucket | {bucket_label} |",
        f"| Generated | {now} |",
        f"| Malformed (skipped) | {result['malformed']} |",
        f"",
        f"## Error Buckets",
        f"",
    ]
    buckets = result["buckets"]
    if buckets:
        lines += [
            "| Bucket Start | Error Count |",
            "|---|---|",
        ]
        for b in buckets:
            lines.append(f"| {b['bucket_start'].isoformat()} | {b['count']} |")
    else:
        lines.append("_No ERROR entries found._")

    content = "\n".join(lines) + "\n"
    path = _report_path(input_file, "timeline")
    _write(path, content)
    return str(path)


# ---------------------------------------------------------------------------
# Grep
# ---------------------------------------------------------------------------

def grep(
    matched_lines: list[str],
    input_file: str,
    level: str,
    since: Optional[str],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    meta_since = since if since else "—"
    lines = [
        f"# Log Grep Report",
        f"",
        f"| Field | Value |",
        f"|---|---|",
        f"| Input file | `{input_file}` |",
        f"| Level | {level} |",
        f"| Since | {meta_since} |",
        f"| Generated | {now} |",
        f"| Matches | {len(matched_lines)} |",
        f"",
        f"## Matching Lines",
        f"",
    ]
    if matched_lines:
        lines.append("```")
        lines.extend(matched_lines)
        lines.append("```")
    else:
        lines.append("_No matching lines found._")

    content = "\n".join(lines) + "\n"
    path = _report_path(input_file, "grep")
    _write(path, content)
    return str(path)
