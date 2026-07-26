"""Per-tick activity counter: rides {{loop.previous}} to stop a loop at N.

The engine's `repeat:` is a static int and `until:` a regex parsed once, so a
runtime per-tick count can't live on either. Instead each activity loops to a
high literal `repeat:` ceiling and this counter trips the static
`until: output.match(remaining:\\s*0)` once `target` activities have run.

`prior` is the previous iteration's sink output (carried by {{loop.previous}},
empty on iteration 1); `target` is the activity's n_* input.

Phases (always exit 0):
    --phase count    (leading, gates the activity)
        done = made-so-far parsed from prior.
        done >= target -> "made: <done>\\nremaining: 0"  (skip + stop signal)
        else           -> "made: <done>"
    --phase advance  (trailing, after the activity ran)
        "made: <done+1>\\nremaining: <max(target-done-1, 0)>"

The count phase also re-reads the harness usage ceiling when --max-usage and
--conduit are given. The parent checks usage once before a branch starts, which
is not enough for a branch that loops 10 times over an hour: it can start under
the ceiling and keep spending long after crossing it. Re-checking here stops the
branch at the first iteration that is at/over the ceiling, and it stays
fail-open (an unreadable usage or unknown harness never blocks work).

The advance task must be the sub-conduit's sink so its `made:` rides forward in
{{loop.previous}}. The count early-skip is a belt-and-suspenders stop if a
round-trip ever drops the counter.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_MADE_RE = re.compile(r"made:\s*(\d+)")


def parse_made(prior: str) -> int:
    """Last 'made: N' in prior (the carried counter), or 0 if absent."""
    matches = _MADE_RE.findall(prior or "")
    return int(matches[-1]) if matches else 0


def count_phase(prior: str, target: int, usage_ok: bool = True) -> str:
    """Leading gate output: emit remaining: 0 once the target is reached.

    :param prior: previous iteration's carried counter output.
    :param target: this activity's n_* count for the tick.
    :param usage_ok: False when the harness is at/over the usage ceiling — the
        branch stops here rather than spending the rest of its iterations.
    """
    done = parse_made(prior)
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


def advance_phase(prior: str, target: int) -> str:
    """Trailing counter output after the activity ran this iteration."""
    done = parse_made(prior)
    return f"made: {done + 1}\nremaining: {max(target - done - 1, 0)}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("count", "advance"), required=True)
    parser.add_argument("--prior", default="")
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
    args = parser.parse_args()

    if args.phase == "count":
        print(count_phase(args.prior, args.target, usage_ok(args.conduit, args.max_usage)))
    else:
        print(advance_phase(args.prior, args.target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
