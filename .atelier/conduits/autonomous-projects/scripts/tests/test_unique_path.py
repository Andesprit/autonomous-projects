"""Tests for unique_path.py. Run: uv run pytest (from scripts/)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unique_path import unique_path


def test_no_collision_returns_name_unchanged(tmp_path):
    dest = unique_path(tmp_path, "idea_x.md")
    assert dest == tmp_path / "idea_x.md"


def test_missing_dir_is_created(tmp_path):
    target = tmp_path / "nested" / "dir"
    dest = unique_path(target, "idea_x.md")
    assert target.is_dir()
    assert dest == target / "idea_x.md"


def test_one_existing_file_appends_2(tmp_path):
    (tmp_path / "idea_x.md").write_text("first", encoding="utf-8")
    dest = unique_path(tmp_path, "idea_x.md")
    assert dest == tmp_path / "idea_x.2.md"
    assert (tmp_path / "idea_x.md").read_text(encoding="utf-8") == "first"


def test_two_existing_files_appends_3(tmp_path):
    (tmp_path / "idea_x.md").write_text("first", encoding="utf-8")
    (tmp_path / "idea_x.2.md").write_text("second", encoding="utf-8")
    dest = unique_path(tmp_path, "idea_x.md")
    assert dest == tmp_path / "idea_x.3.md"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))
