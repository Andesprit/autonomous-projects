"""Check a generation step honoured its ===MARKER=== output contract.

The adhd diverge step can end its turn after launching its parallel branches
("waiting on them before the critic pass"), returning a half-finished session
with no idea in it. Storing that produces a document assembled from narration.

This gate is deliberately NOT fatal. The engine is fail-fast: a failed task
cancels every sibling still running, so raising here would let one bad divergent
session cancel an in-flight 10-idea run. Instead it always exits 0 and reports a
verdict the conduit branches on, and on failure emits `remaining: 0` so the
parent loop stops this branch cleanly and leaves the others alone.

Reads the step output on stdin.

Stdout contract (always exit 0):
    ok: true                        markers + slug present
    ok: false
    remaining: 0                    stop this branch, leave siblings running
    stopped: <reason>
"""

from __future__ import annotations

import argparse
import sys


def check(text: str, kind: str = "IDEA") -> tuple[bool, str]:
    """Does *text* carry a complete ``===<kind> START/END===`` + slug block?

    :param text: the generation step's raw output.
    :param kind: marker family, e.g. ``IDEA`` or ``REVIEW``.
    :returns: ``(ok, reason)``; reason is empty when ok.
    """
    text = text or ""
    missing = [
        name
        for name, token in (
            (f"==={kind} START===", f"==={kind} START==="),
            (f"==={kind} END===", f"==={kind} END==="),
            (f"{kind}_SLUG:", f"{kind}_SLUG:"),
        )
        if token not in text
    ]
    if missing:
        return False, f"missing {', '.join(missing)}"
    start = text.index(f"==={kind} START===") + len(f"==={kind} START===")
    end = text.index(f"==={kind} END===")
    if end <= start or not text[start:end].strip():
        return False, f"empty {kind} block"
    return True, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", default="IDEA")
    args = parser.parse_args(argv)

    ok, reason = check(sys.stdin.read(), args.kind)
    if ok:
        print("ok: true")
        return 0
    print("ok: false")
    print("remaining: 0")
    print(f"stopped: {reason}")
    print(
        f"the {args.kind.lower()} step returned no usable block "
        "(it likely ended its turn before finishing); this branch stops here",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
