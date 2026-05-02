from __future__ import annotations

import argparse
import json
import re
import resource
import signal
import sqlite3
import time
from pathlib import Path

TIMESTAMP_PATTERN = re.compile(r"^#(\d+)$")
BYTES_IN_MB = 1024 * 1024


class StopController:
    def __init__(self) -> None:
        self.stop_requested = False
        self.reason = ""

    def request_stop(self, reason: str) -> None:
        self.stop_requested = True
        self.reason = reason


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dedup_entries (
            ts INTEGER NOT NULL,
            cmd TEXT NOT NULL,
            PRIMARY KEY (ts, cmd)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_files (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            processed_at REAL NOT NULL
        );
        """
    )
    return conn


def iter_history_entries_stream(file_path: Path):
    current_ts: int | None = None
    current_cmd_lines: list[str] = []
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.rstrip("\n")
            match = TIMESTAMP_PATTERN.match(stripped)
            if match:
                if current_ts is not None:
                    yield (current_ts, "\n".join(current_cmd_lines))
                current_ts = int(match.group(1))
                current_cmd_lines = []
            elif current_ts is not None:
                current_cmd_lines.append(stripped)
    if current_ts is not None:
        yield (current_ts, "\n".join(current_cmd_lines))


def format_eta(seconds: float) -> str:
    if seconds < 0:
        return "unknown"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def print_progress(
    start_time: float,
    processed_bytes: int,
    total_bytes: int,
    processed_files: int,
    total_files: int,
    raw_entries: int,
    inserted_entries: int,
    cpu_pct: float,
    throttle_ms: float,
) -> None:
    elapsed = max(time.time() - start_time, 0.001)
    mbps = (processed_bytes / BYTES_IN_MB) / elapsed
    pct = (processed_bytes / total_bytes * 100.0) if total_bytes else 100.0
    remaining_seconds = ((total_bytes - processed_bytes) / processed_bytes) * elapsed if processed_bytes else -1
    print(
        "progress "
        f"{pct:6.2f}% | files {processed_files}/{total_files} | "
        f"raw {raw_entries} | dedup {inserted_entries} | "
        f"speed {mbps:6.2f} MB/s | cpu {cpu_pct:5.1f}% | "
        f"throttle {throttle_ms:5.1f}ms | eta {format_eta(remaining_seconds)}"
    )


def build_status_payload(
    start_time: float,
    processed_bytes: int,
    total_bytes: int,
    processed_files: int,
    total_files: int,
    raw_entries: int,
    inserted_entries: int,
    cpu_pct: float,
    throttle_ms: float,
    state: str,
    reason: str,
) -> dict:
    elapsed = max(time.time() - start_time, 0.001)
    pct = (processed_bytes / total_bytes * 100.0) if total_bytes else 100.0
    mbps = (processed_bytes / BYTES_IN_MB) / elapsed
    remaining_seconds = ((total_bytes - processed_bytes) / processed_bytes) * elapsed if processed_bytes else -1
    return {
        "state": state,
        "reason": reason,
        "progress_percent": round(pct, 4),
        "processed_files": processed_files,
        "total_files": total_files,
        "processed_bytes": processed_bytes,
        "total_bytes": total_bytes,
        "raw_entries": raw_entries,
        "new_dedup_entries": inserted_entries,
        "speed_mb_per_sec": round(mbps, 4),
        "cpu_percent": round(cpu_pct, 2),
        "throttle_ms": round(throttle_ms, 2),
        "eta_seconds": round(remaining_seconds, 3) if remaining_seconds >= 0 else None,
        "updated_at": time.time(),
    }


def write_status_file(status_file: Path, payload: dict) -> None:
    status_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = status_file.with_suffix(status_file.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(status_file)


def process_cpu_percent(prev_cpu: float, prev_time: float) -> tuple[float, float, float]:
    now = time.time()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    cpu_now = usage.ru_utime + usage.ru_stime
    cpu_delta = max(cpu_now - prev_cpu, 0.0)
    wall_delta = max(now - prev_time, 0.001)
    return ((cpu_delta / wall_delta) * 100.0, cpu_now, now)


def adjust_throttle(
    throttle_ms: float,
    cpu_pct: float,
    target_cpu: float,
    auto_throttle: bool,
) -> float:
    if not auto_throttle:
        return throttle_ms
    if cpu_pct > target_cpu + 5:
        return min(throttle_ms + 1.0, 200.0)
    if cpu_pct < target_cpu - 10:
        return max(throttle_ms - 0.5, 0.0)
    return throttle_ms


def export_history(conn: sqlite3.Connection, output_file: Path) -> int:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    cur = conn.execute("SELECT ts, cmd FROM dedup_entries ORDER BY ts, cmd")
    with output_file.open("w", encoding="utf-8") as f:
        for ts, cmd in cur:
            f.write(f"#{ts}\n")
            f.write(f"{cmd}\n")
            count += 1
    return count


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rebuild bash history from fragmented backup files."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("bash_history"),
        help="Directory containing history fragment files.",
    )
    parser.add_argument(
        "--glob",
        default=".bashrc-*",
        help="Glob pattern for fragment files inside input-dir.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/bash_history_recovered"),
        help="Output path for rebuilt history file.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("output/rebuild_history.sqlite3"),
        help="SQLite database path for incremental rebuild.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Rows per DB commit batch.",
    )
    parser.add_argument(
        "--report-every",
        type=float,
        default=2.0,
        help="Progress report interval in seconds.",
    )
    parser.add_argument(
        "--throttle-ms",
        type=float,
        default=0.0,
        help="Sleep milliseconds after each commit batch to reduce CPU pressure.",
    )
    parser.add_argument(
        "--target-cpu",
        type=float,
        default=70.0,
        help="Target process CPU percentage for auto-throttle mode.",
    )
    parser.add_argument(
        "--auto-throttle",
        action="store_true",
        help="Adjust throttle automatically to stay near target CPU.",
    )
    parser.add_argument(
        "--stop-flag-file",
        type=Path,
        default=Path("output/STOP_REBUILD"),
        help="If this file exists, the process stops gracefully after the current batch.",
    )
    parser.add_argument(
        "--export-on-stop",
        action="store_true",
        help="Export output file even if the run is interrupted.",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=Path("output/rebuild_status.json"),
        help="Path to JSON status file for external monitoring.",
    )
    parser.add_argument(
        "--status-every",
        type=float,
        default=2.0,
        help="Status JSON refresh interval in seconds.",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Drop old DB state and rebuild from scratch.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    controller = StopController()

    def _signal_handler(signum: int, _frame) -> None:
        controller.request_stop(f"signal {signum}")

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    files = [p for p in sorted(args.input_dir.glob(args.glob)) if p.is_file()]
    total_files = len(files)
    total_bytes = sum(p.stat().st_size for p in files)
    conn = init_db(args.db_path)

    if args.reset_db:
        conn.execute("DELETE FROM dedup_entries")
        conn.execute("DELETE FROM processed_files")
        conn.commit()

    raw_entries = 0
    inserted_entries = 0
    processed_bytes = 0
    processed_files_count = 0
    start_time = time.time()
    last_report = start_time
    last_status = start_time
    usage = resource.getrusage(resource.RUSAGE_SELF)
    last_cpu = usage.ru_utime + usage.ru_stime
    last_cpu_time = start_time
    cpu_pct = 0.0
    throttle_ms = args.throttle_ms
    buffer: list[tuple[int, str]] = []

    for file_path in files:
        if controller.stop_requested or args.stop_flag_file.exists():
            controller.request_stop(controller.reason or "stop requested")
            break

        st = file_path.stat()
        row = conn.execute(
            "SELECT 1 FROM processed_files WHERE path=? AND size=? AND mtime=?",
            (str(file_path), st.st_size, st.st_mtime),
        ).fetchone()
        if row:
            processed_bytes += st.st_size
            processed_files_count += 1
            if time.time() - last_report >= args.report_every:
                last_report = time.time()
                print_progress(
                    start_time,
                    processed_bytes,
                    total_bytes,
                    processed_files_count,
                    total_files,
                    raw_entries,
                    inserted_entries,
                    cpu_pct,
                    throttle_ms,
                )
            if time.time() - last_status >= args.status_every:
                last_status = time.time()
                write_status_file(
                    args.status_file,
                    build_status_payload(
                        start_time,
                        processed_bytes,
                        total_bytes,
                        processed_files_count,
                        total_files,
                        raw_entries,
                        inserted_entries,
                        cpu_pct,
                        throttle_ms,
                        "running",
                        "",
                    ),
                )
            continue

        for ts, cmd in iter_history_entries_stream(file_path):
            if controller.stop_requested or args.stop_flag_file.exists():
                controller.request_stop(controller.reason or "stop requested")
                break
            raw_entries += 1
            buffer.append((ts, cmd))
            if len(buffer) >= args.batch_size:
                before = conn.total_changes
                conn.executemany(
                    "INSERT OR IGNORE INTO dedup_entries(ts, cmd) VALUES (?, ?)",
                    buffer,
                )
                conn.commit()
                inserted_entries += conn.total_changes - before
                buffer.clear()
                if throttle_ms > 0:
                    time.sleep(throttle_ms / 1000.0)
                cpu_pct, last_cpu, last_cpu_time = process_cpu_percent(last_cpu, last_cpu_time)
                throttle_ms = adjust_throttle(
                    throttle_ms,
                    cpu_pct,
                    args.target_cpu,
                    args.auto_throttle,
                )

        if controller.stop_requested:
            break

        if buffer:
            before = conn.total_changes
            conn.executemany(
                "INSERT OR IGNORE INTO dedup_entries(ts, cmd) VALUES (?, ?)",
                buffer,
            )
            conn.commit()
            inserted_entries += conn.total_changes - before
            buffer.clear()
            if throttle_ms > 0:
                time.sleep(throttle_ms / 1000.0)
            cpu_pct, last_cpu, last_cpu_time = process_cpu_percent(last_cpu, last_cpu_time)
            throttle_ms = adjust_throttle(
                throttle_ms,
                cpu_pct,
                args.target_cpu,
                args.auto_throttle,
            )

        conn.execute(
            "INSERT OR REPLACE INTO processed_files(path, size, mtime, processed_at) VALUES (?, ?, ?, ?)",
            (str(file_path), st.st_size, st.st_mtime, time.time()),
        )
        conn.commit()

        processed_bytes += st.st_size
        processed_files_count += 1
        if time.time() - last_report >= args.report_every:
            last_report = time.time()
            print_progress(
                start_time,
                processed_bytes,
                total_bytes,
                processed_files_count,
                total_files,
                raw_entries,
                inserted_entries,
                cpu_pct,
                throttle_ms,
            )
        if time.time() - last_status >= args.status_every:
            last_status = time.time()
            write_status_file(
                args.status_file,
                build_status_payload(
                    start_time,
                    processed_bytes,
                    total_bytes,
                    processed_files_count,
                    total_files,
                    raw_entries,
                    inserted_entries,
                    cpu_pct,
                    throttle_ms,
                    "running",
                    "",
                ),
            )

    output_rows = 0
    if not controller.stop_requested or args.export_on_stop:
        output_rows = export_history(conn, args.output)

    elapsed = time.time() - start_time
    print_progress(
        start_time,
        processed_bytes,
        total_bytes,
        processed_files_count,
        total_files,
        raw_entries,
        inserted_entries,
        cpu_pct,
        throttle_ms,
    )
    print(f"elapsed_seconds: {elapsed:.2f}")
    print(f"input_files: {total_files}")
    print(f"raw_entries: {raw_entries}")
    print(f"new_dedup_entries: {inserted_entries}")
    print(f"output_entries: {output_rows}")
    print(f"db_path: {args.db_path}")
    print(f"output_file: {args.output}")
    if controller.stop_requested:
        write_status_file(
            args.status_file,
            build_status_payload(
                start_time,
                processed_bytes,
                total_bytes,
                processed_files_count,
                total_files,
                raw_entries,
                inserted_entries,
                cpu_pct,
                throttle_ms,
                "stopped",
                controller.reason or "external request",
            ),
        )
    else:
        write_status_file(
            args.status_file,
            build_status_payload(
                start_time,
                processed_bytes,
                total_bytes,
                processed_files_count,
                total_files,
                raw_entries,
                inserted_entries,
                cpu_pct,
                throttle_ms,
                "completed",
                "",
            ),
        )
    if controller.stop_requested:
        print(f"stopped: {controller.reason or 'external request'}")
        print("resume_hint: rerun the same command to continue from processed files")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
