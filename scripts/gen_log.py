#!/usr/bin/env python3
"""
gen_log.py — Generate a synthetic application log file.

Usage:
    python scripts/gen_log.py                          # 100 MB -> logs/synthetic.log
    python scripts/gen_log.py --size-mb 50             # 50 MB
    python scripts/gen_log.py --out /tmp/big.log       # custom output path
    python scripts/gen_log.py --size-mb 100 --seed 42  # deterministic output

The generator writes one line at a time and never holds more than a single
line in memory, so it is safe to run for any target size.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

_INFO_MESSAGES = [
    "Server started on port {port}",
    "Health check passed",
    "User {uid} logged in",
    "Request {req} completed in {ms}ms",
    "Cache warmed for key {key}",
    "Configuration reloaded",
    "Worker {wid} started",
    "Scheduled job {job} finished",
    "Database connection pool resized to {n}",
    "Session {sid} created",
    "Feature flag {flag} enabled",
    "Deployment {deploy} succeeded",
    "Backup completed in {ms}ms",
    "Metrics flushed to collector",
    "SSL certificate renewed",
]

_WARN_MESSAGES = [
    "Cache miss for user {uid}",
    "Disk usage above {pct}%",
    "Slow query detected: {ms}ms",
    "Retry {n} for request {req}",
    "Memory usage at {pct}%",
    "Connection pool nearing capacity ({n}/{max})",
    "Rate limit approaching for client {uid}",
    "Deprecated API endpoint called: {endpoint}",
    "Config value {key} is missing, using default",
    "Response time degraded: {ms}ms",
]

_ERROR_MESSAGES = [
    "Database connection timed out",
    "Null pointer exception in handler",
    "Out of memory",
    "Failed to write to disk: {path}",
    "Authentication failed for user {uid}",
    "Service {svc} unavailable",
    "Request {req} exceeded timeout of {ms}ms",
    "Unhandled exception in worker {wid}",
    "Circuit breaker opened for {svc}",
    "Failed to acquire lock for resource {key}",
]

_MALFORMED = [
    "this is a malformed line",
    "no timestamp here ERROR something",
    "DEBUG secret level not in spec",
    "",
    "   ",
    "WARN missing timestamp",
]

_LEVELS = ["INFO", "INFO", "INFO", "WARN", "WARN", "ERROR"]  # weighted


def _render(template: str, rng: random.Random) -> str:
    return template.format(
        port=rng.choice([8080, 8443, 3000, 5432]),
        uid=rng.randint(100, 99999),
        req=f"req-{rng.randint(1000, 9999)}",
        ms=rng.randint(1, 9999),
        key=f"key:{rng.randint(1, 500)}",
        wid=rng.randint(1, 32),
        job=f"job-{rng.randint(1, 20)}",
        n=rng.randint(1, 64),
        sid=f"sess-{rng.randint(10000, 99999)}",
        flag=f"feature-{rng.randint(1, 10)}",
        deploy=f"v{rng.randint(1,9)}.{rng.randint(0,9)}.{rng.randint(0,9)}",
        pct=rng.randint(70, 99),
        max=rng.randint(50, 200),
        endpoint=f"/api/v{rng.randint(1,3)}/deprecated",
        path=f"/var/data/file{rng.randint(1,100)}.db",
        svc=rng.choice(["auth", "db", "cache", "queue", "search"]),
    )


def _next_timestamp(current: datetime, rng: random.Random) -> datetime:
    return current + timedelta(seconds=rng.randint(0, 5))


def generate(out_path: Path, target_bytes: int, seed: int | None) -> None:
    rng = random.Random(seed)
    malformed_every = 47  # inject one malformed line roughly every 47 valid lines

    ts = datetime(2026, 10, 1, 0, 0, 0)
    written = 0
    line_count = 0

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", buffering=1 << 16) as fh:
        while written < target_bytes:
            ts = _next_timestamp(ts, rng)

            # Occasionally inject a malformed line
            if line_count % malformed_every == 0 and line_count > 0:
                raw = rng.choice(_MALFORMED)
                line = raw + "\n"
            else:
                level = rng.choice(_LEVELS)
                if level == "INFO":
                    msg = _render(rng.choice(_INFO_MESSAGES), rng)
                elif level == "WARN":
                    msg = _render(rng.choice(_WARN_MESSAGES), rng)
                else:
                    msg = _render(rng.choice(_ERROR_MESSAGES), rng)
                line = f"{ts.strftime('%Y-%m-%d %H:%M:%S')} {level} {msg}\n"

            fh.write(line)
            written += len(line.encode("utf-8"))
            line_count += 1

    print(f"Generated {written / 1_048_576:.1f} MB  ({line_count:,} lines)  -> {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic log file.")
    parser.add_argument(
        "--size-mb", type=float, default=100.0,
        help="Target size in megabytes (default: 100).",
    )
    parser.add_argument(
        "--out", default=None,
        help="Output path (default: logs/synthetic.log next to this script).",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for deterministic output.",
    )
    args = parser.parse_args()

    if args.size_mb <= 0:
        print("Error: --size-mb must be positive.", file=sys.stderr)
        raise SystemExit(2)

    if args.out:
        out_path = Path(args.out)
    else:
        script_dir = Path(__file__).parent
        out_path = script_dir.parent / "logs" / "synthetic.log"

    target_bytes = int(args.size_mb * 1_048_576)
    generate(out_path, target_bytes, args.seed)


if __name__ == "__main__":
    main()
