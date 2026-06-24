"""Move every task stranded in 02_in-progress/ to 05_blocked/ with a note.

Success in work-one-todo moves a task to 03_to-review/, so any *.md still
sitting in 02_in-progress/ after the advance loop means the loop gave up: the
reviewer never returned DONE within the retry cap, or a crash/timeout/usage
throttle cut the run off. Left there, the task is silently retried every tick,
burning quota with no note for the human. This moves it out, out loud.

Stdout contract (always exit 0): one line per file moved to 05_blocked/, or a
single "blocked: none" when nothing was stranded:
    blocked: <path>
    blocked: <path>
    blocked: none
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
from pathlib import Path


def _extract_reason(text: str | None) -> str | None:
    """Pull the reviewer's last `REASON:` line from a verdict blob (None if absent)."""
    matches = re.findall(r"^\s*REASON:\s*(.+?)\s*$", text or "", re.MULTILINE)
    return matches[-1].strip() if matches and matches[-1].strip() else None


def block_stranded(project_dir: str | Path, reason: str | None = None) -> list[str]:
    """Move every *.md left in 02_in-progress/ to 05_blocked/, each with a note.

    :param project_dir: project folder holding the numbered stage subfolders.
    :param reason: the reviewer's last one-line reason, appended to the note when
        present; falls back to the plain note when None (crash/timeout, no verdict).
    :returns: destination paths as strings; empty list if nothing was stranded.
    """
    project = Path(project_dir)
    in_progress = project / "02_in-progress"
    try:
        stranded = sorted(p for p in in_progress.glob("*.md") if p.is_file())
    except OSError:
        return []
    if not stranded:
        return []

    blocked = project / "05_blocked"
    blocked.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note = (
        f"\n\n# Blocked\n\n"
        f"Auto-blocked {stamp}: the work-and-review loop ended without a DONE "
        f"verdict (retry cap hit, or the run was cut off). Needs a human.\n"
    )
    if reason:
        note += f"\nLast reviewer feedback: {reason}\n"

    moved: list[str] = []
    for src in stranded:
        dest = blocked / src.name
        if dest.exists():  # don't clobber a task blocked on an earlier run
            i = 2
            while (blocked / f"{src.stem}.{i}{src.suffix}").exists():
                i += 1
            dest = blocked / f"{src.stem}.{i}{src.suffix}"
        try:
            with src.open("a", encoding="utf-8") as fh:
                fh.write(note)
        except OSError:
            pass  # note is best-effort; still move it out of the retry path
        src.replace(dest)
        moved.append(str(dest))
    return moved


def main() -> None:
    project_dir = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = "" if sys.stdin.isatty() else sys.stdin.read()
    moved = block_stranded(project_dir, _extract_reason(raw))
    for dest in moved:
        print(f"blocked: {dest}")
    if not moved:
        print("blocked: none")


if __name__ == "__main__":
    main()
