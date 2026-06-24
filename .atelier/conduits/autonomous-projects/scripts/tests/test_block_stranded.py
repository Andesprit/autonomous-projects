"""Tests for block_stranded.py. Run: uv run pytest (from scripts/)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from block_stranded import _extract_reason, block_stranded


def _project(tmp_path):
    proj = tmp_path / "proj"
    (proj / "02_in-progress").mkdir(parents=True)
    return proj


def test_moves_stranded_file_with_note(tmp_path):
    proj = _project(tmp_path)
    src = proj / "02_in-progress" / "task_x.md"
    src.write_text("# Description\nwork\n", encoding="utf-8")
    moved = block_stranded(proj)
    assert len(moved) == 1
    dest = Path(moved[0])
    assert dest.parent.name == "05_blocked"
    assert dest.name == "task_x.md"
    assert not src.exists()
    body = dest.read_text(encoding="utf-8")
    assert body.startswith("# Description")  # original content preserved
    assert "# Blocked" in body


def test_moves_all_stranded_files(tmp_path):
    proj = _project(tmp_path)
    (proj / "02_in-progress" / "task_a.md").write_text("a", encoding="utf-8")
    (proj / "02_in-progress" / "task_b.md").write_text("b", encoding="utf-8")
    moved = block_stranded(proj)
    assert len(moved) == 2
    assert {Path(m).name for m in moved} == {"task_a.md", "task_b.md"}
    assert not list((proj / "02_in-progress").glob("*.md"))
    assert (proj / "05_blocked" / "task_a.md").exists()
    assert (proj / "05_blocked" / "task_b.md").exists()


def test_empty_in_progress_is_noop(tmp_path):
    proj = _project(tmp_path)
    assert block_stranded(proj) == []
    assert not (proj / "05_blocked").exists()


def test_non_md_left_alone(tmp_path):
    proj = _project(tmp_path)
    (proj / "02_in-progress" / "notes.txt").write_text("x", encoding="utf-8")
    assert block_stranded(proj) == []
    assert not (proj / "05_blocked").exists()
    assert (proj / "02_in-progress" / "notes.txt").exists()


def test_name_collision_does_not_clobber(tmp_path):
    proj = _project(tmp_path)
    (proj / "05_blocked").mkdir()
    (proj / "05_blocked" / "task_x.md").write_text("first", encoding="utf-8")
    src = proj / "02_in-progress" / "task_x.md"
    src.write_text("second", encoding="utf-8")
    moved = block_stranded(proj)
    assert len(moved) == 1
    assert Path(moved[0]).name == "task_x.2.md"
    assert (proj / "05_blocked" / "task_x.md").read_text(encoding="utf-8") == "first"


def test_missing_in_progress_dir_no_crash(tmp_path):
    proj = tmp_path / "bare"
    proj.mkdir()
    assert block_stranded(proj) == []


def test_reason_appended_to_note(tmp_path):
    proj = _project(tmp_path)
    src = proj / "02_in-progress" / "task_x.md"
    src.write_text("# Description\nwork\n", encoding="utf-8")
    moved = block_stranded(proj, "tests still red on the new parser")
    body = Path(moved[0]).read_text(encoding="utf-8")
    assert "# Blocked" in body
    assert "Last reviewer feedback: tests still red on the new parser" in body


def test_extract_reason(tmp_path):
    assert (
        _extract_reason("VERDICT: NOT_DONE\nREASON: didn't address the X constraint")
        == "didn't address the X constraint"
    )
    assert _extract_reason("no verdict here") is None
    assert _extract_reason("") is None
    assert _extract_reason("REASON:   \n") is None  # blank reason -> generic note
    multi = "REASON: first try failed\nVERDICT: NOT_DONE\nREASON: last try failed"
    assert _extract_reason(multi) == "last try failed"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))
