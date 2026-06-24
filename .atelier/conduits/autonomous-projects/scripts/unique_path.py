"""Print a collision-free path under <dir> for <filename>, creating <dir>.

The store steps (idea_<slug>.md, review_<slug>.md, task_<slug>.md) each write
a slug-named file; the slug is invented per run, so over many ticks two runs
can pick the same name and a plain write clobbers the earlier proposal
silently. Mirrors the suffix guard in block_stranded.py: name taken -> append
.2, .3, ... instead of overwriting.

Usage:  python3 unique_path.py <dir> <filename>   # prints chosen abs path
"""

from __future__ import annotations

import sys
from pathlib import Path


def unique_path(directory: str | Path, filename: str) -> Path:
    """Collision-free path for <filename> under <directory>, creating it.

    :param directory: target folder; created (parents too) if missing.
    :param filename: desired name; if taken, .2/.3/... is appended to the stem.
    :returns: a path that does not currently exist.
    """
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    dest = d / filename
    if dest.exists():  # ponytail: TOCTOU ok under serialized ticks; revisit if stores ever run concurrently
        stem, suffix = dest.stem, dest.suffix
        i = 2
        while (d / f"{stem}.{i}{suffix}").exists():
            i += 1
        dest = d / f"{stem}.{i}{suffix}"
    return dest


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: unique_path.py <dir> <filename>", file=sys.stderr)
        sys.exit(2)
    print(unique_path(sys.argv[1], sys.argv[2]).resolve())


if __name__ == "__main__":
    main()
