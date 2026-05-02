from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from src import log_utils


def test_validate_run_type_accepts_kebab_case() -> None:
    assert log_utils.validate_run_type("full-rebuild") == "full-rebuild"
    assert log_utils.validate_run_type("Resume-Run") == "resume-run"
    assert log_utils.validate_run_type("v2-benchmark") == "v2-benchmark"


def test_validate_run_type_rejects_invalid_values() -> None:
    for value in ["full_rebuild", "full rebuild", "bad!", "-start", "end-"]:
        with pytest.raises(ValueError):
            log_utils.validate_run_type(value)


def test_build_log_path_uses_date_and_run_type(tmp_path: Path) -> None:
    d = dt.date(2026, 5, 2)
    path = log_utils.build_log_path(tmp_path, "full-rebuild", today=d)
    assert path == tmp_path / "2026-05-02_full-rebuild.md"


def test_create_log_file_is_idempotent(tmp_path: Path) -> None:
    d = dt.date(2026, 5, 2)
    path = log_utils.create_log_file(tmp_path, "cleanup", today=d)
    assert path.exists()
    content1 = path.read_text(encoding="utf-8")
    assert "# Run Log: cleanup" in content1
    assert "Date: 2026-05-02" in content1

    path_again = log_utils.create_log_file(tmp_path, "cleanup", today=d)
    content2 = path_again.read_text(encoding="utf-8")
    assert path_again == path
    assert content2 == content1
