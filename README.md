# logs-analyzer

A lightweight command-line tool for analysing application log files after an incident.
Works entirely offline — no dashboard, database, or network connection required.

## Requirements

- Python 3.9+
- No third-party dependencies (standard library only)

## Installation

```bash
git clone <repo>
cd logs-summariser/logscope
```

Run directly:

```bash
python logscope.py <command> <logfile> [options]
```

Or make it executable:

```bash
chmod +x logscope.py
./logscope.py summary app.log
```

## Log format

Each log line must follow this pattern:

```
YYYY-MM-DD HH:MM:SS LEVEL message
```

Example:

```
2026-10-01 09:03:14 INFO  Server started on port 8080
2026-10-01 09:04:02 WARN  Cache miss for user 182
2026-10-01 09:05:48 ERROR Database connection timed out
```

Valid levels: `INFO`, `WARN`, `ERROR`. Malformed lines are skipped and counted.

---

## Commands

### `summary`

Print a summary of log activity.

```bash
python logscope.py summary app.log
python logscope.py summary app.log --format json
python logscope.py summary app.log --format md
```

**Output includes:**
- Count of INFO / WARN / ERROR lines
- Total valid lines and malformed lines skipped
- First and last valid timestamps
- Top 5 most frequent error messages

### `timeline`

Show ERROR counts grouped into time buckets with a bar chart.

```bash
python logscope.py timeline app.log --bucket 15m
python logscope.py timeline app.log --bucket 1h
python logscope.py timeline app.log --bucket 5m --format json
python logscope.py timeline app.log --bucket 2h --format md
```

Supported bucket units: `m` (minutes), `h` (hours). Examples: `5m`, `15m`, `1h`, `2h`.

Empty buckets between the first and last error bucket are preserved.

### `grep`

Filter log lines by level, with an optional time filter.

```bash
python logscope.py grep app.log --level ERROR
python logscope.py grep app.log --level WARN
python logscope.py grep app.log --level ERROR --since "2026-10-01 09:00"
python logscope.py grep app.log --level INFO  --since "2026-10-01 09:00:00"
python logscope.py grep app.log --level ERROR --format json
python logscope.py grep app.log --level ERROR --format md
```

`--level` is required. `--since` accepts `YYYY-MM-DD HH:MM:SS` or `YYYY-MM-DD HH:MM`.

---

## Output formats

| Flag | Behaviour |
|---|---|
| *(none)* | Human-readable terminal text (default) |
| `--format json` | Valid JSON to stdout; diagnostics to stderr |
| `--format md` | Writes `<input>.<command>.md` and prints the path |

Markdown report filenames:

```
app.log.summary.md
app.log.timeline.md
app.log.grep.md
```

---

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Success |
| 1 | Runtime or file error |
| 2 | Invalid arguments |
| 3 | Markdown report write failure |

---

## Running tests

```bash
cd logs-summariser/logscope
python -m pytest tests/ -v
```

---

## Project structure

```
logscope/
├── logscope.py          # Entry point
├── cli/
│   └── args.py          # argparse wiring and exit-code handling
├── parser/
│   └── log_parser.py    # Streaming parser and LogEntry model
├── commands/
│   ├── summary.py
│   ├── timeline.py
│   └── grep.py
├── formatters/
│   ├── text.py
│   ├── json_fmt.py
│   └── markdown_fmt.py
└── tests/
    ├── fixtures/
    │   └── sample.log
    └── test_logscope.py
```
