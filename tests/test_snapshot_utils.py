from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from src import snapshot_utils


def test_validate_label() -> None:
    assert snapshot_utils.validate_label("post-run") == "post-run"
    assert snapshot_utils.validate_label("Nightly") == "nightly"
    with pytest.raises(ValueError):
        snapshot_utils.validate_label("post_run")


def test_build_snapshot_dir() -> None:
    p = snapshot_utils.build_snapshot_dir(
        Path("snapshots"), "post-run", now=dt.datetime(2026, 5, 2, 17, 10, 5)
    )
    assert p.as_posix() == "snapshots/2026-05-02_171005_post-run"


def test_create_snapshot_copies_files_and_logs(tmp_path: Path) -> None:
    output = tmp_path / "output"
    logs = tmp_path / "logs"
    snaps = tmp_path / "snapshots"
    output.mkdir()
    logs.mkdir()

    db = output / "rebuild_history.sqlite3"
    history = output / "bash_history_recovered"
    status = output / "rebuild_status.json"
    log_file = logs / "2026-05-02_full-rebuild.md"
    readme = logs / "README.md"

    db.write_text("db", encoding="utf-8")
    history.write_text("history", encoding="utf-8")
    status.write_text("status", encoding="utf-8")
    log_file.write_text("log", encoding="utf-8")
    readme.write_text("rules", encoding="utf-8")

    snap_dir, copied, missing = snapshot_utils.create_snapshot(
        snapshots_dir=snaps,
        label="post-run",
        db_path=db,
        output_file=history,
        status_file=status,
        logs_dir=logs,
        now=dt.datetime(2026, 5, 2, 17, 20, 30),
    )

    assert snap_dir.name == "2026-05-02_172030_post-run"
    assert (snap_dir / db.name).exists()
    assert (snap_dir / history.name).exists()
    assert (snap_dir / status.name).exists()
    assert (snap_dir / "logs" / log_file.name).exists()
    assert not (snap_dir / "logs" / "README.md").exists()
    assert len(copied) == 4
    assert missing == []


def test_create_snapshot_tracks_missing_files(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    snaps = tmp_path / "snapshots"
    logs.mkdir()

    snap_dir, copied, missing = snapshot_utils.create_snapshot(
        snapshots_dir=snaps,
        label="post-run",
        db_path=tmp_path / "missing-db.sqlite3",
        output_file=tmp_path / "missing-output",
        status_file=tmp_path / "missing-status",
        logs_dir=logs,
        now=dt.datetime(2026, 5, 2, 17, 40, 0),
    )

    assert snap_dir.exists()
    assert copied == []
    assert len(missing) == 3
