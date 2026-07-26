"""Delete exactly the inbox file that was picked — never a re-globbed guess.

improve-task used to re-run `find | sort | head -n1` to delete the raw task it
had just spec'd. The pick and the delete are separated by three AI steps (up to
the conduit's 2h timeout), so a file dropped into the inbox in between could
sort ahead of the picked one and be deleted in its place: the user's new task
was destroyed unread, and the spec'd one stayed to be spec'd again next
iteration. The conduit now passes the path chosen up front; this deletes that
file and nothing else.

Refuses anything that is not a regular *.md file sitting directly in --inbox, so
a stale, empty or malformed path degrades to a no-op instead of deleting
somewhere else.

Stdout contract (always exit 0):
    removed: <path>     the picked file was deleted
    removed: none       no path given, or it no longer qualifies
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def remove_picked(picked: str | None, inbox: str | Path) -> str | None:
    """Delete *picked* if it is a *.md file directly inside *inbox*.

    :param picked: absolute path chosen by the pick step; blank when the inbox
        was already drained.
    :param inbox: the task-inbox folder the file must live in.
    :returns: the deleted path as a string, or None if nothing was removed.
    """
    if not picked or not picked.strip():
        return None
    try:
        target = Path(picked.strip()).resolve()
        parent = Path(inbox).resolve()
    except OSError:
        return None
    if target.suffix.lower() != ".md":
        return None
    if target.parent != parent:  # only ever delete inside the declared inbox
        return None
    if not target.is_file():
        return None
    try:
        target.unlink()
    except OSError:
        return None
    return str(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", required=True, help="Folder the file must live in.")
    parser.add_argument("picked", nargs="?", default="", help="Path chosen by the pick step.")
    args = parser.parse_args(argv)

    removed = remove_picked(args.picked, args.inbox)
    print(f"removed: {removed if removed else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
