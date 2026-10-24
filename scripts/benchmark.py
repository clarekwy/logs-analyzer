#!/usr/bin/env python3
"""
benchmark.py — Generate a 100 MB synthetic log and measure logscope performance.

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --size-mb 100 --keep-log

Reports wall time and peak RSS memory for each logscope command.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import tracemalloc
    _HAS_TRACEMALLOC = True
except ImportError:
    _HAS_TRACEMALLOC = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT   = SCRIPT_DIR.parent
LOGSCOPE    = REPO_ROOT / "logscope" / "logscope.py"
GEN_LOG     = SCRIPT_DIR / "gen_log.py"
LOG_DIR     = REPO_ROOT / "logs"
LOG_PATH    = LOG_DIR / "synthetic.log"

PYTHON = sys.executable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hr(label: str) -> None:
    width = 60
    print(f"\n{'─' * width}" if _can_unicode() else f"\n{'-' * width}")
    print(f"  {label}")
    print(f"{'─' * width}" if _can_unicode() else f"{'-' * width}")


def _can_unicode() -> bool:
    enc = getattr(sys.stdout, 'encoding', '') or ''
    return enc.lower().replace('-', '') not in ('cp1252', 'cp850', 'ascii', 'latin1')


def _run_timed(cmd: list[str], label: str) -> None:
    """Run *cmd*, print wall time; use tracemalloc when running in-process."""
    print(f"\n[{label}]")
    print(f"  cmd : {' '.join(str(c) for c in cmd)}")

    start = time.perf_counter()
    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,   # discard output — we only want perf numbers
        stderr=subprocess.PIPE,
        text=True,
    )
    elapsed = time.perf_counter() - start

    if result.returncode not in (0, 3):   # 3 = md write issues (non-fatal here)
        print(f"  WARN: exit code {result.returncode}")
        if result.stderr.strip():
            print(f"  stderr: {result.stderr.strip()[:200]}")

    print(f"  wall time : {elapsed:.3f}s")


def _peak_rss_mb() -> float | None:
    """Return the current process peak RSS in MB where available."""
    try:
        import resource  # Unix only
        return resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    except ImportError:
        pass
    # Windows: use psutil if present
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / 1_048_576
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark logscope against a large log file.")
    parser.add_argument("--size-mb", type=float, default=100.0,
                        help="Size of synthetic log to generate (default: 100).")
    parser.add_argument("--seed", type=int, default=1,
                        help="Random seed for the generator (default: 1).")
    parser.add_argument("--keep-log", action="store_true",
                        help="Do not delete the synthetic log after benchmarking.")
    args = parser.parse_args()

    _hr("Step 1 — Generate synthetic log")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    gen_cmd = [
        PYTHON, str(GEN_LOG),
        "--size-mb", str(args.size_mb),
        "--out", str(LOG_PATH),
        "--seed", str(args.seed),
    ]
    t0 = time.perf_counter()
    subprocess.run(gen_cmd, check=True)
    gen_time = time.perf_counter() - t0

    actual_mb = LOG_PATH.stat().st_size / 1_048_576
    print(f"  generation time : {gen_time:.2f}s")
    print(f"  file size       : {actual_mb:.1f} MB")

    _hr("Step 2 — Benchmark logscope commands")

    commands = [
        (
            "summary (text)",
            [PYTHON, str(LOGSCOPE), "summary", str(LOG_PATH)],
        ),
        (
            "summary (json)",
            [PYTHON, str(LOGSCOPE), "summary", str(LOG_PATH), "--format", "json"],
        ),
        (
            "timeline --bucket 15m (text)",
            [PYTHON, str(LOGSCOPE), "timeline", str(LOG_PATH), "--bucket", "15m"],
        ),
        (
            "timeline --bucket 1h (json)",
            [PYTHON, str(LOGSCOPE), "timeline", str(LOG_PATH), "--bucket", "1h", "--format", "json"],
        ),
        (
            "grep --level ERROR (text)",
            [PYTHON, str(LOGSCOPE), "grep", str(LOG_PATH), "--level", "ERROR"],
        ),
        (
            "grep --level ERROR --since (text)",
            [PYTHON, str(LOGSCOPE), "grep", str(LOG_PATH),
             "--level", "ERROR", "--since", "2026-10-02 00:00"],
        ),
        (
            "grep --level INFO (json)",
            [PYTHON, str(LOGSCOPE), "grep", str(LOG_PATH), "--level", "INFO",
             "--format", "json"],
        ),
    ]

    for label, cmd in commands:
        _run_timed(cmd, label)

    _hr("Step 3 — Memory profiling (tracemalloc, summary command)")
    _profile_memory(LOG_PATH)

    _hr("Results summary")
    print(f"  Log file : {LOG_PATH}  ({actual_mb:.1f} MB)")
    peak = _peak_rss_mb()
    if peak:
        print(f"  Benchmark process peak RSS : {peak:.1f} MB")
    else:
        print("  Peak RSS : not available on this platform without psutil")

    if not args.keep_log:
        LOG_PATH.unlink(missing_ok=True)
        print(f"\n  Synthetic log deleted. Pass --keep-log to retain it.")
    else:
        print(f"\n  Synthetic log retained at: {LOG_PATH}")


def _profile_memory(log_path: Path) -> None:
    """
    Run the summary command in-process under tracemalloc to report
    how much heap logscope itself allocates (excludes interpreter overhead).
    """
    import io, sys as _sys

    # Patch sys.path so logscope modules are importable
    logscope_dir = str(REPO_ROOT / "logscope")
    if logscope_dir not in _sys.path:
        _sys.path.insert(0, logscope_dir)

    try:
        from parser.log_parser import stream_entries
        from commands.summary import run as summary_run
    except ImportError as exc:
        print(f"  Could not import logscope for in-process profiling: {exc}")
        return

    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        result = summary_run(fh)

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_alloc = sum(s.size_diff for s in stats if s.size_diff > 0)

    print(f"  tracemalloc net heap allocated during summary : {total_alloc / 1024:.1f} KB")
    print(f"  (valid={result['total_valid']:,}  malformed={result['malformed']:,}  errors={result['counts']['ERROR']:,})")
    print()
    print("  Top 5 allocation sites:")
    for stat in stats[:5]:
        if stat.size_diff > 0:
            print(f"    +{stat.size_diff / 1024:>7.1f} KB  {stat.traceback}")


if __name__ == "__main__":
    main()
