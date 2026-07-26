"""Tests for remove_picked.py — delete the picked inbox file, nothing else.

The first test is the regression that matters: a task dropped into the inbox
while the AI steps were running must survive, even though it sorts ahead of the
file being spec'd. That is the case the old `find | sort | head -n1` at delete
time got wrong.

Run: uv run pytest (from scripts/)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from remove_picked import main, remove_picked  # noqa: E402


def test_late_arrival_survives(tmp_path):
    """A file dropped after the pick sorts first — it must NOT be the one deleted."""
    inbox = tmp_path / "00_tasks"
    inbox.mkdir()
    picked = inbox / "bbb.md"
    picked.write_text("task B", encoding="utf-8")

    # ...three AI steps later, the human drops a task that sorts ahead of it.
    late = inbox / "aaa.md"
    late.write_text("task A", encoding="utf-8")

    removed = remove_picked(str(picked), inbox)

    assert removed == str(picked.resolve())
    assert not picked.exists()
    assert late.exists(), "a task dropped mid-run was deleted without being spec'd"
    assert late.read_text(encoding="utf-8") == "task A"


def test_blank_path_is_a_no_op(tmp_path):
    inbox = tmp_path / "00_tasks"
    inbox.mkdir()
    survivor = inbox / "a.md"
    survivor.write_text("x", encoding="utf-8")

    for blank in ("", "   ", None):
        assert remove_picked(blank, inbox) is None
    assert survivor.exists()


def test_refuses_outside_the_inbox(tmp_path):
    inbox = tmp_path / "00_tasks"
    inbox.mkdir()
    outsider = tmp_path / "elsewhere.md"
    outsider.write_text("not yours", encoding="utf-8")
    nested = inbox / "sub"
    nested.mkdir()
    deeper = nested / "deep.md"
    deeper.write_text("also not yours", encoding="utf-8")

    assert remove_picked(str(outsider), inbox) is None
    assert remove_picked(str(inbox / ".." / "elsewhere.md"), inbox) is None
    assert remove_picked(str(deeper), inbox) is None
    assert outsider.exists()
    assert deeper.exists()


def test_refuses_non_md_and_missing(tmp_path):
    inbox = tmp_path / "00_tasks"
    inbox.mkdir()
    other = inbox / "notes.txt"
    other.write_text("keep", encoding="utf-8")

    assert remove_picked(str(other), inbox) is None
    assert other.exists()
    assert remove_picked(str(inbox / "ghost.md"), inbox) is None
    assert remove_picked(str(inbox), inbox) is None  # a directory is not a file


def test_trailing_newline_is_tolerated(tmp_path):
    """The path arrives via engine interpolation, which may carry a newline."""
    inbox = tmp_path / "00_tasks"
    inbox.mkdir()
    picked = inbox / "a.md"
    picked.write_text("x", encoding="utf-8")

    assert remove_picked(f"{picked}\n", inbox) == str(picked.resolve())
    assert not picked.exists()


def test_main_contract_always_exits_zero(tmp_path, capsys):
    inbox = tmp_path / "00_tasks"
    inbox.mkdir()
    picked = inbox / "a.md"
    picked.write_text("x", encoding="utf-8")

    assert main(["--inbox", str(inbox), str(picked)]) == 0
    assert f"removed: {picked.resolve()}" in capsys.readouterr().out

    # nothing left to remove -> still exit 0, still a parseable line
    assert main(["--inbox", str(inbox), ""]) == 0
    assert "removed: none" in capsys.readouterr().out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
