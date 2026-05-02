from __future__ import annotations

import json
from pathlib import Path

from src import history_rebuilder as hr


def test_iter_history_entries_stream_supports_multiline(tmp_path: Path) -> None:
    history_file = tmp_path / ".bashrc-1"
    history_file.write_text(
        "#100\n"
        "echo one\n"
        "echo two\n"
        "#101\n"
        "ls -la\n"
        "#102\n"
        "printf 'a\\n'\n"
        "printf 'b\\n'\n",
        encoding="utf-8",
    )

    entries = list(hr.iter_history_entries_stream(history_file))
    assert entries == [
        (100, "echo one\necho two"),
        (101, "ls -la"),
        (102, "printf 'a\\n'\nprintf 'b\\n'"),
    ]


def test_iter_history_entries_stream_ignores_preamble_and_handles_empty_command(
    tmp_path: Path,
) -> None:
    history_file = tmp_path / ".bashrc-2"
    history_file.write_text(
        "not-a-timestamp\n"
        "still-ignore\n"
        "#200\n"
        "#201\n"
        "echo ok\n",
        encoding="utf-8",
    )
    entries = list(hr.iter_history_entries_stream(history_file))
    assert entries == [
        (200, ""),
        (201, "echo ok"),
    ]


def test_adjust_throttle_behaviors() -> None:
    assert hr.adjust_throttle(1.0, cpu_pct=90, target_cpu=65, auto_throttle=True) > 1.0
    assert hr.adjust_throttle(5.0, cpu_pct=40, target_cpu=65, auto_throttle=True) < 5.0
    assert hr.adjust_throttle(0.0, cpu_pct=30, target_cpu=65, auto_throttle=True) == 0.0
    assert hr.adjust_throttle(200.0, cpu_pct=99, target_cpu=65, auto_throttle=True) == 200.0
    assert hr.adjust_throttle(7.0, cpu_pct=95, target_cpu=65, auto_throttle=False) == 7.0


def test_format_eta() -> None:
    assert hr.format_eta(-1) == "unknown"
    assert hr.format_eta(0) == "00:00:00"
    assert hr.format_eta(3661) == "01:01:01"


def test_build_status_payload_shape() -> None:
    payload = hr.build_status_payload(
        start_time=hr.time.time() - 10,
        processed_bytes=1024 * 1024,
        total_bytes=2 * 1024 * 1024,
        processed_files=5,
        total_files=10,
        raw_entries=100,
        inserted_entries=90,
        cpu_pct=55.5,
        throttle_ms=3.0,
        state="running",
        reason="",
    )
    assert payload["state"] == "running"
    assert payload["processed_files"] == 5
    assert payload["total_files"] == 10
    assert payload["progress_percent"] == 50.0
    assert payload["cpu_percent"] == 55.5
    assert payload["throttle_ms"] == 3.0
    assert isinstance(payload["updated_at"], float)


def test_main_dedup_and_resume(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / ".bashrc-a").write_text(
        "#100\n"
        "echo hi\n"
        "#101\n"
        "ls\n",
        encoding="utf-8",
    )
    (input_dir / ".bashrc-b").write_text(
        "#100\n"
        "echo hi\n"
        "#102\n"
        "pwd\n",
        encoding="utf-8",
    )

    db_path = output_dir / "db.sqlite3"
    out_file = output_dir / "history"
    status_file = output_dir / "status.json"
    stop_flag = output_dir / "stop.flag"

    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--input-dir",
            str(input_dir),
            "--glob",
            ".bashrc-*",
            "--db-path",
            str(db_path),
            "--output",
            str(out_file),
            "--status-file",
            str(status_file),
            "--status-every",
            "0.01",
            "--report-every",
            "999",
            "--reset-db",
        ],
    )
    rc1 = hr.main()
    assert rc1 == 0

    lines1 = out_file.read_text(encoding="utf-8").splitlines()
    assert lines1 == ["#100", "echo hi", "#101", "ls", "#102", "pwd"]

    status1 = json.loads(status_file.read_text(encoding="utf-8"))
    assert status1["state"] == "completed"
    assert status1["new_dedup_entries"] == 3

    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--input-dir",
            str(input_dir),
            "--glob",
            ".bashrc-*",
            "--db-path",
            str(db_path),
            "--output",
            str(out_file),
            "--status-file",
            str(status_file),
            "--status-every",
            "0.01",
            "--report-every",
            "999",
        ],
    )
    rc2 = hr.main()
    assert rc2 == 0
    lines2 = out_file.read_text(encoding="utf-8").splitlines()
    assert lines2 == lines1

    assert not stop_flag.exists()


def test_resume_when_file_changes_reprocesses(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    fragment = input_dir / ".bashrc-a"
    fragment.write_text(
        "#100\n"
        "echo first\n",
        encoding="utf-8",
    )
    db_path = output_dir / "db.sqlite3"
    out_file = output_dir / "history"
    status_file = output_dir / "status.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--input-dir",
            str(input_dir),
            "--glob",
            ".bashrc-*",
            "--db-path",
            str(db_path),
            "--output",
            str(out_file),
            "--status-file",
            str(status_file),
            "--report-every",
            "999",
            "--reset-db",
        ],
    )
    assert hr.main() == 0
    first = out_file.read_text(encoding="utf-8")
    assert "echo first" in first

    fragment.write_text(
        "#100\n"
        "echo first\n"
        "#101\n"
        "echo second\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--input-dir",
            str(input_dir),
            "--glob",
            ".bashrc-*",
            "--db-path",
            str(db_path),
            "--output",
            str(out_file),
            "--status-file",
            str(status_file),
            "--report-every",
            "999",
        ],
    )
    assert hr.main() == 0
    second = out_file.read_text(encoding="utf-8")
    assert "echo first" in second
    assert "echo second" in second


def test_main_stop_flag_graceful_stop(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / ".bashrc-a").write_text(
        "#100\n"
        "echo hi\n"
        "#101\n"
        "ls\n",
        encoding="utf-8",
    )
    stop_flag = output_dir / "stop.flag"
    stop_flag.write_text("stop", encoding="utf-8")

    db_path = output_dir / "db.sqlite3"
    out_file = output_dir / "history"
    status_file = output_dir / "status.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--input-dir",
            str(input_dir),
            "--glob",
            ".bashrc-*",
            "--db-path",
            str(db_path),
            "--output",
            str(out_file),
            "--stop-flag-file",
            str(stop_flag),
            "--status-file",
            str(status_file),
            "--status-every",
            "0.01",
            "--report-every",
            "999",
            "--reset-db",
        ],
    )
    rc = hr.main()
    assert rc == 130
    status = json.loads(status_file.read_text(encoding="utf-8"))
    assert status["state"] == "stopped"
    assert status["reason"]


def test_main_stop_flag_with_export_on_stop(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / ".bashrc-a").write_text(
        "#100\n"
        "echo hi\n",
        encoding="utf-8",
    )
    stop_flag = output_dir / "stop.flag"
    stop_flag.write_text("stop", encoding="utf-8")

    db_path = output_dir / "db.sqlite3"
    out_file = output_dir / "history"
    status_file = output_dir / "status.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--input-dir",
            str(input_dir),
            "--glob",
            ".bashrc-*",
            "--db-path",
            str(db_path),
            "--output",
            str(out_file),
            "--stop-flag-file",
            str(stop_flag),
            "--status-file",
            str(status_file),
            "--report-every",
            "999",
            "--reset-db",
            "--export-on-stop",
        ],
    )
    rc = hr.main()
    assert rc == 130
    assert out_file.exists()
