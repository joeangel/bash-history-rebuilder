from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

TIMESTAMP_PATTERN = re.compile(r"^#(\d+)$")


@dataclass
class Metrics:
    count: int
    min_ts: int | None
    max_ts: int | None


def collect_source_metrics(input_dir: Path, glob_pattern: str) -> Metrics:
    count = 0
    min_ts: int | None = None
    max_ts: int | None = None
    for file_path in sorted(input_dir.glob(glob_pattern)):
        if not file_path.is_file():
            continue
        with file_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                match = TIMESTAMP_PATTERN.match(line.rstrip("\n"))
                if not match:
                    continue
                ts = int(match.group(1))
                count += 1
                if min_ts is None or ts < min_ts:
                    min_ts = ts
                if max_ts is None or ts > max_ts:
                    max_ts = ts
    return Metrics(count=count, min_ts=min_ts, max_ts=max_ts)


def collect_db_metrics(db_path: Path) -> Metrics:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT COUNT(*), MIN(ts), MAX(ts) FROM dedup_entries"
    ).fetchone()
    conn.close()
    return Metrics(count=int(row[0]), min_ts=row[1], max_ts=row[2])


def collect_output_metrics(output_file: Path) -> tuple[Metrics, int]:
    line_count = 0
    entry_count = 0
    min_ts: int | None = None
    max_ts: int | None = None
    current_ts: int | None = None
    with output_file.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_count += 1
            stripped = line.rstrip("\n")
            match = TIMESTAMP_PATTERN.match(stripped)
            if match:
                current_ts = int(match.group(1))
                if min_ts is None or current_ts < min_ts:
                    min_ts = current_ts
                if max_ts is None or current_ts > max_ts:
                    max_ts = current_ts
                entry_count += 1
            elif current_ts is not None:
                # command line
                continue
    return Metrics(count=entry_count, min_ts=min_ts, max_ts=max_ts), line_count


def fmt_ts(ts: int | None) -> str:
    if ts is None:
        return "None"
    return f"{ts} ({dt.datetime.fromtimestamp(ts).isoformat()})"


def run_validation(input_dir: Path, glob_pattern: str, db_path: Path, output_file: Path) -> int:
    source = collect_source_metrics(input_dir, glob_pattern)
    db = collect_db_metrics(db_path)
    output, output_lines = collect_output_metrics(output_file)

    errors: list[str] = []
    if db.count != output.count:
        errors.append(f"db entry count ({db.count}) != output entry count ({output.count})")
    if db.min_ts != output.min_ts or db.max_ts != output.max_ts:
        errors.append(
            f"db/output timestamp range mismatch: "
            f"db[{fmt_ts(db.min_ts)} .. {fmt_ts(db.max_ts)}] "
            f"vs output[{fmt_ts(output.min_ts)} .. {fmt_ts(output.max_ts)}]"
        )
    if source.max_ts != db.max_ts:
        errors.append(
            f"source max_ts ({fmt_ts(source.max_ts)}) != db max_ts ({fmt_ts(db.max_ts)})"
        )

    print("Validation Summary")
    print(f"- source timestamps: {source.count}")
    print(f"- source range: {fmt_ts(source.min_ts)} .. {fmt_ts(source.max_ts)}")
    print(f"- db dedup entries: {db.count}")
    print(f"- db range: {fmt_ts(db.min_ts)} .. {fmt_ts(db.max_ts)}")
    print(f"- output entries: {output.count}")
    print(f"- output lines: {output_lines}")
    print(f"- output range: {fmt_ts(output.min_ts)} .. {fmt_ts(output.max_ts)}")

    if errors:
        print("Validation Result: FAILED")
        for err in errors:
            print(f"- {err}")
        return 1
    print("Validation Result: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate source/db/output consistency.")
    parser.add_argument("--input-dir", type=Path, default=Path("bash_history"))
    parser.add_argument("--glob", default=".bashrc-*")
    parser.add_argument("--db-path", type=Path, default=Path("output/rebuild_history.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("output/bash_history_recovered"))
    args = parser.parse_args()
    return run_validation(args.input_dir, args.glob, args.db_path, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
