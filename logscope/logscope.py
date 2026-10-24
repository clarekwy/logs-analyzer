#!/usr/bin/env python3
"""logscope — lightweight command-line log analyser."""

from __future__ import annotations

import sys
import os

# Ensure the package root is on the path when run as a script
sys.path.insert(0, os.path.dirname(__file__))

from cli.args import build_parser, validate_level
from commands import summary as cmd_summary
from commands import timeline as cmd_timeline
from commands.timeline import parse_bucket
from commands import grep as cmd_grep
from commands.grep import parse_since
from formatters import text as fmt_text
from formatters import json_fmt
from formatters import markdown_fmt


def _open_file(path: str):
    """Open a log file for reading, exiting cleanly on errors."""
    if not os.path.exists(path):
        print(f"Error: file not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    try:
        return open(path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"Error: cannot read file: {path}: {exc}", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help(sys.stderr)
        raise SystemExit(2)

    # ------------------------------------------------------------------
    # summary
    # ------------------------------------------------------------------
    if args.command == "summary":
        with _open_file(args.logfile) as fh:
            result = cmd_summary.run(fh)

        if args.fmt == "json":
            print(json_fmt.summary(result, args.logfile))
        elif args.fmt == "md":
            path = markdown_fmt.summary(result, args.logfile)
            print(f"Report written to: {path}")
        else:
            print(fmt_text.summary(result))

    # ------------------------------------------------------------------
    # timeline
    # ------------------------------------------------------------------
    elif args.command == "timeline":
        try:
            bucket = parse_bucket(args.bucket)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(2)

        with _open_file(args.logfile) as fh:
            result = cmd_timeline.run(fh, bucket)

        if args.fmt == "json":
            print(json_fmt.timeline(result, args.logfile))
        elif args.fmt == "md":
            bucket_label = args.bucket
            path = markdown_fmt.timeline(result, args.logfile, bucket_label)
            print(f"Report written to: {path}")
        else:
            print(fmt_text.timeline(result))

    # ------------------------------------------------------------------
    # grep
    # ------------------------------------------------------------------
    elif args.command == "grep":
        validate_level(args.level)

        since_dt = None
        if args.since:
            try:
                since_dt = parse_since(args.since)
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                raise SystemExit(2)

        if args.fmt in ("json", "md"):
            # Collect into a list only when needed for structured output
            with _open_file(args.logfile) as fh:
                matched = list(cmd_grep.run(fh, args.level, since_dt))

            if args.fmt == "json":
                print(json_fmt.grep(matched, args.logfile, args.level, args.since))
            else:
                path = markdown_fmt.grep(matched, args.logfile, args.level, args.since)
                print(f"Report written to: {path}")
        else:
            # Stream lines directly to stdout — no retention
            with _open_file(args.logfile) as fh:
                for line in cmd_grep.run(fh, args.level, since_dt):
                    print(line)

    else:
        print(f"Error: unknown command: {args.command!r}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
