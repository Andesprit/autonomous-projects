"""Runnable check for promote_reviewed: move 02_in-progress -> 03_to-review.

Lives in the autonomous-projects pytest project (work-one-todo has none of its
own) and reaches sideways for the module, the same way test_pick_next_task.py
does. It used to sit next to the module under work-one-todo/scripts/tests/,
outside any rootdir, so `uv run pytest` never collected it.
ponytail: the de-clobber branch is the non-trivial logic -> one check.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "work-one-todo" / "scripts"))
from promote_reviewed import promote_reviewed  # noqa: E402


def test_promote_reviewed() -> None:
    with tempfile.TemporaryDirectory() as d:
        proj = Path(d)
        in_progress = proj / "02_in-progress"
        in_progress.mkdir()

        # a single in-progress card lands in 03_to-review/
        src = in_progress / "task_x.md"
        src.write_text("# Description\nwork\n", encoding="utf-8")
        dest = promote_reviewed(proj)
        assert dest is not None
        moved = Path(dest)
        assert moved.parent.name == "03_to-review"
        assert moved.name == "task_x.md"
        assert not src.exists()
        assert moved.read_text(encoding="utf-8") == "# Description\nwork\n"

        # de-clobber: a same-named card already awaiting review is not overwritten
        src2 = in_progress / "task_x.md"
        src2.write_text("second", encoding="utf-8")
        dest2 = promote_reviewed(proj)
        assert Path(dest2).name == "task_x.2.md"
        assert (proj / "03_to-review" / "task_x.md").read_text(
            encoding="utf-8"
        ) == "# Description\nwork\n"

        # empty 02_in-progress/ -> no-op, None
        assert promote_reviewed(proj) is None

        # missing 02_in-progress/ -> None, no crash
        assert promote_reviewed(Path(d) / "nope") is None


if __name__ == "__main__":
    test_promote_reviewed()
    print("ok")
