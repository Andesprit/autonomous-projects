"""Runnable check for pick_next_task: priority asc, filename tie-break, blank=last.

ponytail: parse + sort + missing-value branch is non-trivial -> one check.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "work-one-todo" / "scripts"))
from pick_next_task import pick_next_task  # noqa: E402


def _write(to_do: Path, name: str, priority: str | None) -> None:
    body = "---\n"
    if priority is not None:
        body += f"priority: {priority}\n"
    body += "---\n# Description\n"
    (to_do / name).write_text(body, encoding="utf-8")


def test_pick_next_task() -> None:
    with tempfile.TemporaryDirectory() as d:
        to_do = Path(d) / "01_to-do"
        to_do.mkdir()

        # priorities 3,1,2 -> the 1 wins
        _write(to_do, "a.md", "3")
        _write(to_do, "b.md", "1")
        _write(to_do, "c.md", "2")
        assert pick_next_task(d) == "b.md"

        # tie on priority 1 -> lexicographically-first filename wins
        _write(to_do, "aa.md", "1")
        assert pick_next_task(d) == "aa.md"

        # blank priority loses to an explicit 5
        for p in to_do.glob("*.md"):
            p.unlink()
        _write(to_do, "blank.md", None)
        _write(to_do, "five.md", "5")
        assert pick_next_task(d) == "five.md"

        # the template ships `priority:  # note` (commented but unfilled) -> the
        # trailing comment fails int() -> sorts last, same as a blank line
        for p in to_do.glob("*.md"):
            p.unlink()
        _write(to_do, "commented.md", " # lower number = worked sooner")
        _write(to_do, "five.md", "5")
        assert pick_next_task(d) == "five.md"

        # empty 01_to-do/ -> empty output
        for p in to_do.glob("*.md"):
            p.unlink()
        assert pick_next_task(d) == ""

        # missing 01_to-do/ -> empty output, no crash
        assert pick_next_task(Path(d) / "nope") == ""


if __name__ == "__main__":
    test_pick_next_task()
    print("ok")
