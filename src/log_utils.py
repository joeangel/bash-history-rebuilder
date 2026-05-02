from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path


_VALID_RUN_TYPE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_run_type(run_type: str) -> str:
    value = run_type.strip().lower()
    if not _VALID_RUN_TYPE.match(value):
        raise ValueError(
            "run_type must be lowercase kebab-case with letters/numbers, e.g. full-rebuild"
        )
    return value


def build_log_path(logs_dir: Path, run_type: str, today: dt.date | None = None) -> Path:
    normalized = validate_run_type(run_type)
    log_date = today or dt.date.today()
    return logs_dir / f"{log_date.isoformat()}_{normalized}.md"


def create_log_file(logs_dir: Path, run_type: str, today: dt.date | None = None) -> Path:
    path = build_log_path(logs_dir, run_type, today=today)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "\n".join(
                [
                    f"# Run Log: {run_type}",
                    "",
                    f"Date: {(today or dt.date.today()).isoformat()}",
                    "",
                    "## Summary",
                    "- ",
                    "",
                    "## Metrics",
                    "- ",
                    "",
                    "## Verification",
                    "- ",
                    "",
                    "## Next Actions",
                    "- ",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new run log file in logs/.")
    parser.add_argument("run_type", help="lowercase kebab-case, e.g. full-rebuild")
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=Path("logs"),
        help="target logs directory",
    )
    args = parser.parse_args()
    path = create_log_file(args.logs_dir, args.run_type)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
