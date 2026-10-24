"""CLI argument parsing and exit-code handling."""

from __future__ import annotations

import argparse
import sys

VALID_LEVELS = ("INFO", "WARN", "ERROR")
VALID_FORMATS = ("text", "json", "md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logscope",
        description="Analyse application log files after an incident.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ------------------------------------------------------------------
    # summary
    # ------------------------------------------------------------------
    p_summary = sub.add_parser("summary", help="Summarise a log file.")
    p_summary.add_argument("logfile", help="Path to the log file.")
    p_summary.add_argument(
        "--format",
        choices=VALID_FORMATS,
        default="text",
        dest="fmt",
        help="Output format: text (default), json, or md.",
    )

    # ------------------------------------------------------------------
    # timeline
    # ------------------------------------------------------------------
    p_timeline = sub.add_parser(
        "timeline", help="Show ERROR counts in time buckets."
    )
    p_timeline.add_argument("logfile", help="Path to the log file.")
    p_timeline.add_argument(
        "--bucket",
        required=True,
        help="Time bucket size, e.g. 5m, 15m, 1h, 2h.",
    )
    p_timeline.add_argument(
        "--format",
        choices=VALID_FORMATS,
        default="text",
        dest="fmt",
        help="Output format: text (default), json, or md.",
    )

    # ------------------------------------------------------------------
    # grep
    # ------------------------------------------------------------------
    p_grep = sub.add_parser("grep", help="Filter log lines by level and time.")
    p_grep.add_argument("logfile", help="Path to the log file.")
    p_grep.add_argument(
        "--level",
        required=True,
        help="Log level to filter: INFO, WARN, or ERROR.",
    )
    p_grep.add_argument(
        "--since",
        default=None,
        help='Only show lines at or after this timestamp, e.g. "2026-10-01 09:00".',
    )
    p_grep.add_argument(
        "--format",
        choices=VALID_FORMATS,
        default="text",
        dest="fmt",
        help="Output format: text (default), json, or md.",
    )

    return parser


def validate_level(value: str) -> str:
    if value not in VALID_LEVELS:
        print(
            f'Error: invalid --level value "{value}". Use INFO, WARN, or ERROR.',
            file=sys.stderr,
        )
        raise SystemExit(2)
    return value


def validate_format(value: str) -> str:
    if value not in VALID_FORMATS:
        print(
            f'Error: invalid --format value "{value}". Use text, json, or md.',
            file=sys.stderr,
        )
        raise SystemExit(2)
    return value
