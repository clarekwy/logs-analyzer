"""Automated tests for logscope."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

# Ensure package root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parser.log_parser import parse_line, parse_timestamp, stream_entries, LogEntry
from commands import summary as cmd_summary
from commands import timeline as cmd_timeline
from commands.timeline import parse_bucket
from commands import grep as cmd_grep
from commands.grep import parse_since
from formatters import text as fmt_text
from formatters import json_fmt
from formatters import markdown_fmt

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_LOG = FIXTURES / "sample.log"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fh(text: str):
    return io.StringIO(text)


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParseTimestamp(unittest.TestCase):
    def test_valid(self):
        from datetime import datetime
        dt = parse_timestamp("2026-10-01 09:03:14")
        self.assertEqual(dt, datetime(2026, 10, 1, 9, 3, 14))

    def test_invalid_returns_none(self):
        self.assertIsNone(parse_timestamp("not-a-date"))
        self.assertIsNone(parse_timestamp("2026-13-01 09:00:00"))


class TestParseLine(unittest.TestCase):
    def test_valid_info(self):
        entry, ok = parse_line("2026-10-01 09:00:00 INFO Server started\n")
        self.assertTrue(ok)
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.message, "Server started")

    def test_valid_warn(self):
        entry, ok = parse_line("2026-10-01 09:01:00 WARN Disk full")
        self.assertTrue(ok)
        self.assertEqual(entry.level, "WARN")

    def test_valid_error(self):
        entry, ok = parse_line("2026-10-01 09:02:00 ERROR Crash")
        self.assertTrue(ok)
        self.assertEqual(entry.level, "ERROR")

    def test_malformed_no_level(self):
        _, ok = parse_line("2026-10-01 09:00:00 something without level")
        self.assertFalse(ok)

    def test_malformed_unknown_level(self):
        _, ok = parse_line("2026-10-01 09:00:00 DEBUG debug message")
        self.assertFalse(ok)

    def test_malformed_invalid_timestamp(self):
        _, ok = parse_line("not-a-date INFO message")
        self.assertFalse(ok)

    def test_malformed_empty_message(self):
        # Valid line format but message only whitespace — treated as malformed
        _, ok = parse_line("2026-10-01 09:00:00 INFO   ")
        self.assertFalse(ok)

    def test_completely_empty_line(self):
        _, ok = parse_line("")
        self.assertFalse(ok)

    def test_raw_line_preserved(self):
        raw = "2026-10-01 09:00:00 INFO Hello world"
        entry, ok = parse_line(raw)
        self.assertTrue(ok)
        self.assertEqual(entry.raw_line, raw)


class TestStreamEntries(unittest.TestCase):
    def test_mixed_lines(self):
        text = (
            "2026-10-01 09:00:00 INFO Good line\n"
            "this is bad\n"
            "2026-10-01 09:01:00 ERROR Another good\n"
        )
        entries = list(stream_entries(_fh(text)))
        self.assertEqual(len(entries), 3)
        self.assertIsNotNone(entries[0][0])
        self.assertIsNone(entries[1][0])
        self.assertIsNotNone(entries[2][0])


# ---------------------------------------------------------------------------
# Summary tests
# ---------------------------------------------------------------------------

class TestSummary(unittest.TestCase):
    def _run(self, text: str) -> dict:
        return cmd_summary.run(_fh(text))

    def test_severity_counts(self):
        text = (
            "2026-10-01 09:00:00 INFO a\n"
            "2026-10-01 09:01:00 WARN b\n"
            "2026-10-01 09:02:00 ERROR c\n"
            "2026-10-01 09:03:00 ERROR d\n"
        )
        r = self._run(text)
        self.assertEqual(r["counts"]["INFO"], 1)
        self.assertEqual(r["counts"]["WARN"], 1)
        self.assertEqual(r["counts"]["ERROR"], 2)
        self.assertEqual(r["total_valid"], 4)
        self.assertEqual(r["malformed"], 0)

    def test_malformed_counted(self):
        text = (
            "2026-10-01 09:00:00 INFO ok\n"
            "bad line\n"
            "also bad\n"
        )
        r = self._run(text)
        self.assertEqual(r["malformed"], 2)
        self.assertEqual(r["total_valid"], 1)

    def test_first_last_timestamps_not_sorted(self):
        from datetime import datetime
        text = (
            "2026-10-01 09:05:00 INFO later\n"
            "2026-10-01 09:00:00 INFO earlier\n"
        )
        r = self._run(text)
        self.assertEqual(r["first_timestamp"], datetime(2026, 10, 1, 9, 0, 0))
        self.assertEqual(r["last_timestamp"], datetime(2026, 10, 1, 9, 5, 0))

    def test_top_five_errors(self):
        lines = []
        # "alpha" x3, "beta" x2, "gamma" x2, "delta" x1, "epsilon" x1, "zeta" x1
        for _ in range(3):
            lines.append("2026-10-01 09:00:00 ERROR alpha\n")
        for _ in range(2):
            lines.append("2026-10-01 09:01:00 ERROR beta\n")
        for _ in range(2):
            lines.append("2026-10-01 09:02:00 ERROR gamma\n")
        lines.append("2026-10-01 09:03:00 ERROR delta\n")
        lines.append("2026-10-01 09:04:00 ERROR epsilon\n")
        lines.append("2026-10-01 09:05:00 ERROR zeta\n")
        r = self._run("".join(lines))
        top = r["top_errors"]
        self.assertEqual(len(top), 5)
        self.assertEqual(top[0]["message"], "alpha")
        self.assertEqual(top[0]["count"], 3)

    def test_top_errors_tie_alphabetical(self):
        lines = [
            "2026-10-01 09:00:00 ERROR beta\n",
            "2026-10-01 09:01:00 ERROR alpha\n",
        ]
        r = self._run("".join(lines))
        # Both count=1, alpha comes first alphabetically
        self.assertEqual(r["top_errors"][0]["message"], "alpha")

    def test_empty_file(self):
        r = self._run("")
        self.assertIsNone(r["first_timestamp"])
        self.assertIsNone(r["last_timestamp"])
        self.assertEqual(r["total_valid"], 0)

    def test_with_fixture(self):
        with SAMPLE_LOG.open() as fh:
            r = cmd_summary.run(fh)
        self.assertGreater(r["total_valid"], 0)
        self.assertGreater(r["malformed"], 0)


# ---------------------------------------------------------------------------
# Timeline tests
# ---------------------------------------------------------------------------

class TestParseBucket(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(parse_bucket("15m"), timedelta(minutes=15))

    def test_hours(self):
        self.assertEqual(parse_bucket("1h"), timedelta(hours=1))

    def test_invalid_unit(self):
        with self.assertRaises(ValueError):
            parse_bucket("15x")

    def test_invalid_empty(self):
        with self.assertRaises(ValueError):
            parse_bucket("")

    def test_zero_raises(self):
        with self.assertRaises(ValueError):
            parse_bucket("0m")


class TestTimeline(unittest.TestCase):
    def _run(self, text: str, bucket_str: str) -> dict:
        return cmd_timeline.run(_fh(text), parse_bucket(bucket_str))

    def test_no_errors(self):
        text = "2026-10-01 09:00:00 INFO ok\n"
        r = self._run(text, "15m")
        self.assertEqual(r["buckets"], [])

    def test_single_bucket(self):
        text = (
            "2026-10-01 09:00:00 ERROR a\n"
            "2026-10-01 09:05:00 ERROR b\n"
        )
        r = self._run(text, "15m")
        self.assertEqual(len(r["buckets"]), 1)
        self.assertEqual(r["buckets"][0]["count"], 2)

    def test_multiple_buckets_filled(self):
        text = (
            "2026-10-01 09:00:00 ERROR a\n"
            "2026-10-01 09:30:00 ERROR b\n"
        )
        r = self._run(text, "15m")
        # Buckets: :00, :15 (empty), :30
        self.assertEqual(len(r["buckets"]), 3)
        self.assertEqual(r["buckets"][0]["count"], 1)
        self.assertEqual(r["buckets"][1]["count"], 0)
        self.assertEqual(r["buckets"][2]["count"], 1)

    def test_malformed_skipped(self):
        text = (
            "2026-10-01 09:00:00 ERROR a\n"
            "bad line\n"
        )
        r = self._run(text, "15m")
        self.assertEqual(r["malformed"], 1)

    def test_bucket_seconds_stored(self):
        text = "2026-10-01 09:00:00 ERROR a\n"
        r = self._run(text, "1h")
        self.assertEqual(r["bucket_seconds"], 3600)


# ---------------------------------------------------------------------------
# Grep tests
# ---------------------------------------------------------------------------

class TestParseSince(unittest.TestCase):
    def test_with_seconds(self):
        from datetime import datetime
        dt = parse_since("2026-10-01 09:00:00")
        self.assertEqual(dt, datetime(2026, 10, 1, 9, 0, 0))

    def test_without_seconds(self):
        from datetime import datetime
        dt = parse_since("2026-10-01 09:00")
        self.assertEqual(dt, datetime(2026, 10, 1, 9, 0, 0))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_since("not a date")


class TestGrep(unittest.TestCase):
    LOGS = (
        "2026-10-01 09:00:00 INFO startup\n"
        "2026-10-01 09:01:00 WARN disk\n"
        "2026-10-01 09:02:00 ERROR crash\n"
        "2026-10-01 09:03:00 ERROR timeout\n"
        "bad line\n"
        "2026-10-01 09:05:00 INFO shutdown\n"
    )

    def _run(self, level, since=None):
        from datetime import datetime
        since_dt = parse_since(since) if since else None
        return list(cmd_grep.run(_fh(self.LOGS), level, since_dt))

    def test_filter_error(self):
        lines = self._run("ERROR")
        self.assertEqual(len(lines), 2)
        self.assertIn("ERROR crash", lines[0])

    def test_filter_info(self):
        lines = self._run("INFO")
        self.assertEqual(len(lines), 2)

    def test_filter_warn(self):
        lines = self._run("WARN")
        self.assertEqual(len(lines), 1)

    def test_since_filter(self):
        lines = self._run("ERROR", since="2026-10-01 09:03:00")
        self.assertEqual(len(lines), 1)
        self.assertIn("timeout", lines[0])

    def test_malformed_skipped(self):
        lines = self._run("INFO")
        for line in lines:
            self.assertNotIn("bad line", line)

    def test_order_preserved(self):
        lines = self._run("ERROR")
        self.assertTrue(lines[0] < lines[1])  # timestamps in order


# ---------------------------------------------------------------------------
# JSON formatter tests
# ---------------------------------------------------------------------------

class TestJsonFormatter(unittest.TestCase):
    def test_summary_valid_json(self):
        from datetime import datetime
        result = {
            "counts": {"INFO": 1, "WARN": 0, "ERROR": 2},
            "total_valid": 3,
            "malformed": 1,
            "first_timestamp": datetime(2026, 10, 1, 9, 0, 0),
            "last_timestamp": datetime(2026, 10, 1, 9, 5, 0),
            "top_errors": [{"message": "crash", "count": 2}],
        }
        out = json_fmt.summary(result, "app.log")
        parsed = json.loads(out)
        self.assertEqual(parsed["command"], "summary")
        self.assertEqual(parsed["total_valid"], 3)
        self.assertIn("T", parsed["first_timestamp"])  # ISO-8601

    def test_timeline_valid_json(self):
        from datetime import datetime
        result = {
            "bucket_seconds": 900,
            "buckets": [{"bucket_start": datetime(2026, 10, 1, 9, 0), "count": 3}],
            "malformed": 0,
        }
        out = json_fmt.timeline(result, "app.log")
        parsed = json.loads(out)
        self.assertEqual(parsed["command"], "timeline")
        self.assertEqual(parsed["buckets"][0]["count"], 3)

    def test_grep_valid_json(self):
        out = json_fmt.grep(["line1", "line2"], "app.log", "ERROR", None)
        parsed = json.loads(out)
        self.assertEqual(parsed["command"], "grep")
        self.assertEqual(len(parsed["matches"]), 2)


# ---------------------------------------------------------------------------
# Markdown formatter tests
# ---------------------------------------------------------------------------

class TestMarkdownFormatter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
        self.tmp.close()
        self.logfile = self.tmp.name

    def tearDown(self):
        for ext in ("summary", "timeline", "grep"):
            p = Path(self.logfile + f".{ext}.md")
            if p.exists():
                p.unlink()
        os.unlink(self.logfile)

    def test_summary_creates_file(self):
        from datetime import datetime
        result = {
            "counts": {"INFO": 1, "WARN": 0, "ERROR": 1},
            "total_valid": 2,
            "malformed": 0,
            "first_timestamp": datetime(2026, 10, 1, 9, 0, 0),
            "last_timestamp": datetime(2026, 10, 1, 9, 1, 0),
            "top_errors": [{"message": "crash", "count": 1}],
        }
        path_str = markdown_fmt.summary(result, self.logfile)
        path = Path(path_str)
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("# Log Summary Report", content)
        self.assertIn("crash", content)

    def test_timeline_creates_file(self):
        from datetime import datetime
        result = {
            "bucket_seconds": 900,
            "buckets": [{"bucket_start": datetime(2026, 10, 1, 9, 0), "count": 2}],
            "malformed": 0,
        }
        path_str = markdown_fmt.timeline(result, self.logfile, "15m")
        path = Path(path_str)
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("# Log Timeline Report", content)

    def test_grep_creates_file(self):
        path_str = markdown_fmt.grep(["line1", "line2"], self.logfile, "ERROR", None)
        path = Path(path_str)
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("# Log Grep Report", content)
        self.assertIn("line1", content)


# ---------------------------------------------------------------------------
# CLI / error-handling tests
# ---------------------------------------------------------------------------

class TestCLIErrors(unittest.TestCase):
    def _invoke(self, argv):
        """Run main() capturing stdout/stderr and the SystemExit code."""
        import logscope as ls_module
        from io import StringIO
        old_argv = sys.argv
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.argv = ["logscope"] + argv
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        exit_code = 0
        try:
            ls_module.main()
        except SystemExit as exc:
            exit_code = exc.code
        finally:
            stdout_val = sys.stdout.getvalue()
            stderr_val = sys.stderr.getvalue()
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sys.argv = old_argv
        return exit_code, stdout_val, stderr_val

    def test_missing_file(self):
        code, _, err = self._invoke(["summary", "nonexistent_file_xyz.log"])
        self.assertEqual(code, 1)
        self.assertIn("file not found", err)

    def test_invalid_level(self):
        code, _, err = self._invoke(["grep", str(SAMPLE_LOG), "--level", "DEBUG"])
        self.assertEqual(code, 2)
        self.assertIn("invalid --level", err)

    def test_invalid_bucket(self):
        code, _, err = self._invoke(
            ["timeline", str(SAMPLE_LOG), "--bucket", "15x"]
        )
        self.assertEqual(code, 2)
        self.assertIn("invalid --bucket", err)

    def test_invalid_since(self):
        code, _, err = self._invoke(
            ["grep", str(SAMPLE_LOG), "--level", "ERROR", "--since", "not-a-date"]
        )
        self.assertEqual(code, 2)
        self.assertIn("invalid --since", err)

    def test_no_command(self):
        code, _, _ = self._invoke([])
        self.assertEqual(code, 2)

    def test_summary_text_output(self):
        code, out, _ = self._invoke(["summary", str(SAMPLE_LOG)])
        self.assertEqual(code, 0)
        self.assertIn("INFO", out)
        self.assertIn("ERROR", out)

    def test_summary_json_output(self):
        code, out, _ = self._invoke(["summary", str(SAMPLE_LOG), "--format", "json"])
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["command"], "summary")

    def test_timeline_text_output(self):
        code, out, _ = self._invoke(
            ["timeline", str(SAMPLE_LOG), "--bucket", "15m"]
        )
        self.assertEqual(code, 0)
        self.assertIn("Timeline", out)

    def test_grep_text_output(self):
        code, out, _ = self._invoke(
            ["grep", str(SAMPLE_LOG), "--level", "ERROR"]
        )
        self.assertEqual(code, 0)
        self.assertIn("ERROR", out)


# ---------------------------------------------------------------------------
# Streaming / large-file test
# ---------------------------------------------------------------------------

class TestStreaming(unittest.TestCase):
    def test_large_file_streamed(self):
        """Generate a 10 000-line file and ensure summary runs without error."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            for i in range(10_000):
                ts = f"2026-10-01 {(i // 3600) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d}"
                level = ["INFO", "WARN", "ERROR"][i % 3]
                f.write(f"{ts} {level} Message number {i}\n")
            path = f.name

        try:
            with open(path, encoding="utf-8") as fh:
                result = cmd_summary.run(fh)
            self.assertEqual(result["total_valid"], 10_000)
            self.assertEqual(result["malformed"], 0)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
