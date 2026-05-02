from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
from pathlib import Path


_VALID_LABEL = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_label(label: str) -> str:
    value = label.strip().lower()
    if not _VALID_LABEL.match(value):
        raise ValueError("label must be lowercase kebab-case, e.g. nightly or post-merge")
    return value


def build_snapshot_dir(
    root: Path, label: str, now: dt.datetime | None = None
) -> Path:
    ts = now or dt.datetime.now()
    clean_label = validate_label(label)
    return root / f"{ts.strftime('%Y-%m-%d_%H%M%S')}_{clean_label}"


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def create_snapshot(
    snapshots_dir: Path,
    label: str,
    db_path: Path,
    output_file: Path,
    status_file: Path,
    logs_dir: Path,
    now: dt.datetime | None = None,
) -> tuple[Path, list[str], list[str]]:
    snap_dir = build_snapshot_dir(snapshots_dir, label, now=now)
    snap_dir.mkdir(parents=True, exist_ok=False)

    copied: list[str] = []
    missing: list[str] = []

    targets = [
        (db_path, snap_dir / db_path.name),
        (output_file, snap_dir / output_file.name),
        (status_file, snap_dir / status_file.name),
    ]
    for src, dst in targets:
        if copy_if_exists(src, dst):
            copied.append(src.as_posix())
        else:
            missing.append(src.as_posix())

    for log_file in sorted(logs_dir.glob("*.md")):
        if log_file.name.lower() == "readme.md":
            continue
        if copy_if_exists(log_file, snap_dir / "logs" / log_file.name):
            copied.append(log_file.as_posix())

    return snap_dir, copied, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Create snapshot of DB/output/logs.")
    parser.add_argument("label", help="lowercase kebab-case label, e.g. post-run")
    parser.add_argument("--snapshots-dir", type=Path, default=Path("snapshots"))
    parser.add_argument("--db-path", type=Path, default=Path("output/rebuild_history.sqlite3"))
    parser.add_argument("--output-file", type=Path, default=Path("output/bash_history_recovered"))
    parser.add_argument("--status-file", type=Path, default=Path("output/rebuild_status.json"))
    parser.add_argument("--logs-dir", type=Path, default=Path("logs"))
    args = parser.parse_args()

    snap_dir, copied, missing = create_snapshot(
        snapshots_dir=args.snapshots_dir,
        label=args.label,
        db_path=args.db_path,
        output_file=args.output_file,
        status_file=args.status_file,
        logs_dir=args.logs_dir,
    )
    print(f"snapshot_dir: {snap_dir}")
    print(f"copied_count: {len(copied)}")
    for item in copied:
        print(f"copied: {item}")
    if missing:
        print(f"missing_count: {len(missing)}")
        for item in missing:
            print(f"missing: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
