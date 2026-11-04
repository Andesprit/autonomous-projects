"""Per-tick activity counter: rides {{loop.history}} to stop a loop at N.

The engine's `repeat:` is a static int and `until:` a regex parsed once, so a
runtime per-tick count can't live on either. Instead each activity loops to a
high literal `repeat:` ceiling and this counter trips the static
`until: output.match(remaining:\\s*0)` once `target` activities have run.

`history` is the parent loop's {{loop.history}} (empty on iteration 1), read
from the file at "$INPUT_HISTORY_FILE"; `target` is the activity's n_* input.
It is the history, not {{loop.previous}}, because a try that fails counts as a
try: its {{loop.previous}} is the raw error text, with no `made:` in it, and
the count would restart from 0. So the count is the last `made: N` of a try
that did not fail.

Phases (always exit 0):
    --phase count    (leading, gates the activity)
        done = made-so-far parsed from history.
        done >= target -> "made: <done>\\nremaining: 0"  (skip + stop signal)
        else           -> "made: <done>"
        unknown        -> "remaining: 0\\nstopped: ..."  (see made_so_far)
    --phase advance  (trailing, after the activity ran)
        "made: <done+1>\\nremaining: <max(target-done-1, 0)>"

The count phase also re-reads the harness usage ceiling when --max-usage and
--conduit are given. The parent checks usage once before a branch starts, which
is not enough for a branch that loops 10 times over an hour: it can start under
the ceiling and keep spending long after crossing it. Re-checking here stops the
branch at the first iteration that is at/over the ceiling, and it stays
fail-open (an unreadable usage or unknown harness never blocks work).

The advance task must be the sub-conduit's sink so its `made:` rides forward in
{{loop.history}}. The count early-skip is a belt-and-suspenders stop if a
round-trip ever drops the counter.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_MADE_RE = re.compile(r"made:\s*(\d+)")
# How the engine renders {{loop.history}}: one "--- iteration K ---" block per
# try, after an "--- N earlier iterations omitted ---" line once it keeps only
# the newest tries (10 by default). A failed try's block starts with the line
# "[this try failed with exit code N]".
_ITERATION_RE = re.compile(r"^--- iteration \d+ ---$", re.MULTILINE)
_OMITTED_RE = re.compile(r"^--- \d+ earlier iterations omitted ---$", re.MULTILINE)
_FAILED_TRY = "[this try failed with exit code"


def parse_made(prior: str) -> int:
    """Last 'made: N' in prior (the carried counter), or 0 if absent."""
    matches = _MADE_RE.findall(prior or "")
    return int(matches[-1]) if matches else 0


def made_so_far(history: str) -> int | None:
    """The count carried by the newest try in *history* that did not fail.

    A failed try is skipped: its text is whatever the command or agent printed,
    so it has no counter, and a `made:` inside it is not one. Text with no
    iteration blocks is read as a single try.

    :param history: the rendered {{loop.history}}; empty before the first try.
    :returns: the count, or None when the engine left older tries out and none
        of the tries it kept carries a count. The count is then unknown, and
        guessing 0 would make the activity run up to `target` more times.
    """
    parts = _ITERATION_RE.split(history or "")
    head, tries = (parts[0], parts[1:]) if len(parts) > 1 else ("", parts)
    good = "\n".join(t for t in tries if not t.lstrip().startswith(_FAILED_TRY))
    if not _MADE_RE.search(good) and _OMITTED_RE.search(head):
        return None
    return parse_made(good)


def count_phase(history: str, target: int, usage_ok: bool = True) -> str:
    """Leading gate output: emit remaining: 0 once the target is reached.

    :param history: the parent loop's {{loop.history}}.
    :param target: this activity's n_* count for the tick.
    :param usage_ok: False when the harness is at/over the usage ceiling — the
        branch stops here rather than spending the rest of its iterations.
    """
    done = made_so_far(history)
    if done is None:
        return "remaining: 0\nstopped: no count in the loop history, its last tries all failed"
    if not usage_ok:
        return f"made: {done}\nremaining: 0\nstopped: usage ceiling reached"
    if done >= target:
        return f"made: {done}\nremaining: 0"
    return f"made: {done}"


def usage_ok(conduit: str | None, max_usage: str | None) -> bool:
    """Is *conduit*'s harness still under *max_usage*? Fail-open on anything odd.

    Returns True when the check isn't requested (no --conduit/--max-usage), when
    the harness or its usage can't be read, or when the ceiling won't parse — a
    broken reading must never stall the queue.
    """
    if not conduit or max_usage is None:
        return True
    try:
        from usage_check import is_ok, read_usage, resolve_harness
    except ImportError:
        return True
    try:
        ceiling: int | None = int(max_usage)
    except (TypeError, ValueError):
        return True
    conduits_dir = Path(__file__).resolve().parents[2]
    return is_ok(resolve_harness(conduit, conduits_dir), read_usage(), ceiling)


def advance_phase(history: str, target: int) -> str:
    """Trailing counter output after the activity ran this iteration."""
    done = made_so_far(history) or 0
    return f"made: {done + 1}\nremaining: {max(target - done - 1, 0)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("count", "advance"), required=True)
    parser.add_argument(
        "--history-file",
        required=True,
        help='File holding the loop history: "$INPUT_HISTORY_FILE".',
    )
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument(
        "--conduit",
        default=None,
        help="This activity's sub-conduit name; enables the per-iteration usage re-check.",
    )
    parser.add_argument(
        "--max-usage",
        default=None,
        help="Usage ceiling %% for the re-check; omit to skip it.",
    )
    args = parser.parse_args(argv)
    if not args.history_file:
        # flow-atelier 0.12 and older set no $INPUT_* variable in shell steps.
        parser.error(
            "--history-file is empty: this package needs a flow-atelier newer "
            "than 0.12.0, which gives shell steps their values as $INPUT_* variables"
        )
    history = Path(args.history_file).read_text(encoding="utf-8", errors="replace")

    if args.phase == "count":
        print(count_phase(history, args.target, usage_ok(args.conduit, args.max_usage)))
    else:
        print(advance_phase(history, args.target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
