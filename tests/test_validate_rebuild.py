from __future__ import annotations

import sqlite3
from pathlib import Path

from src.validate_rebuild import run_validation


def _init_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE dedup_entries (ts INTEGER NOT NULL, cmd TEXT NOT NULL, PRIMARY KEY (ts, cmd));"
    )
    conn.commit()
    conn.close()


def test_validate_ok(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / ".bashrc-a").write_text("#100\ncmd1\n#200\ncmd2\n", encoding="utf-8")
    db_path = output_dir / "db.sqlite3"
    _init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.executemany(
        "INSERT INTO dedup_entries(ts, cmd) VALUES (?, ?)",
        [(100, "cmd1"), (200, "cmd2")],
    )
    conn.commit()
    conn.close()

    out_file = output_dir / "history"
    out_file.write_text("#100\ncmd1\n#200\ncmd2\n", encoding="utf-8")

    rc = run_validation(input_dir, ".bashrc-*", db_path, out_file)
    assert rc == 0


def test_validate_fails_on_mismatch(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / ".bashrc-a").write_text("#100\ncmd1\n#300\ncmd3\n", encoding="utf-8")
    db_path = output_dir / "db.sqlite3"
    _init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO dedup_entries(ts, cmd) VALUES (?, ?)", (100, "cmd1"))
    conn.commit()
    conn.close()

    out_file = output_dir / "history"
    out_file.write_text("#100\ncmd1\n", encoding="utf-8")

    rc = run_validation(input_dir, ".bashrc-*", db_path, out_file)
    assert rc == 1
