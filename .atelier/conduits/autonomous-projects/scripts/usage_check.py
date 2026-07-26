"""Single usage gate: is the harness behind activity X under --max-usage?

One per-activity usage gate. Resolves the activity sub-conduit's hardcoded
harness (text-scan for `harness:<name>`, following a tool:conduit delegate
one hop so work-one-todo -> task-with-review resolves), reads that harness's
live 5h usage via usage.mjs, and prints a single ok flag.

Stdout contract (always exit 0):
    ok: true|false

Fail-open (ok: true) when the harness is unknown, usage is unreadable, or the
ceiling is unparseable, so a broken read never blocks the tick.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# harness:<name> from a sub-conduit's `tool:` -> the label usage.mjs prints.
#
# Both spellings of each agent are listed. flow-atelier resolves harness names
# through the ACP registry now, so the same agent can legally be written with
# its registry id (`harness:claude-acp`) as well as the legacy name the
# conduits use (`harness:claude-code`). A name that is missing here is not an
# error -- is_ok fails open -- which means the max_usage ceiling would quietly
# stop throttling, so keep this in sync when a conduit's `tool:` is renamed.
USAGE_LABEL = {
    "claude-code": "claudecode",
    "claude-acp": "claudecode",
    "codex": "codex",
    "codex-acp": "codex",
    "opencode": "opencode",
}

_HARNESS_RE = re.compile(r"harness:([a-z][a-z0-9-]*)")
_DELEGATE_RE = re.compile(r'^\s*task:\s*"?([a-z][a-z0-9-]+)"?\s*$', re.MULTILINE)


def resolve_harness(conduit: str, conduits_dir: Path, _seen: set[str] | None = None) -> str | None:
    """Harness short name a conduit runs on, following tool:conduit delegates.

    Scans <conduits_dir>/<conduit>/conduit.yaml for `harness:<name>`. If none,
    follows each `task: <sibling>` reference (a tool:conduit delegate) one hop,
    so a conduit that only delegates (work-one-todo) resolves to where the
    harness is actually declared (task-with-review). Returns None if unresolved.
    """
    _seen = _seen or set()
    if conduit in _seen:
        return None
    _seen.add(conduit)
    try:
        text = (conduits_dir / conduit / "conduit.yaml").read_text(encoding="utf-8")
    except OSError:
        return None
    m = _HARNESS_RE.search(text)
    if m:
        return m.group(1)
    for child in _DELEGATE_RE.findall(text):
        if (conduits_dir / child).is_dir():
            found = resolve_harness(child, conduits_dir, _seen)
            if found:
                return found
    return None


def _parse_usage(text: str) -> dict[str, int]:
    """Turn usage.mjs output ('<label>: <pct>%' lines) into {label: int}.

    Lines whose value is 'n/a' or otherwise non-numeric are skipped (left
    unset, which is_ok treats as under-ceiling).
    """
    usage: dict[str, int] = {}
    for line in text.splitlines():
        label, _, val = line.partition(":")
        try:
            usage[label.strip()] = int(val.strip().rstrip("%"))
        except ValueError:
            pass  # "n/a" or junk -> unset (treated as under-ceiling)
    return usage


def read_usage() -> dict[str, int]:
    """Live 5h usage % per usage.mjs label. Fail open: empty on any error."""
    script = Path(__file__).resolve().parent / "usage.mjs"
    try:
        out = subprocess.run(
            ["node", str(script)], capture_output=True, text=True, timeout=120
        ).stdout
    except Exception:
        return {}
    return _parse_usage(out)


def is_ok(harness: str | None, usage: dict[str, int], max_usage: int | None) -> bool:
    """True unless the activity's harness is at/over the ceiling. Fail-open."""
    if max_usage is None:
        return True  # unparseable ceiling -> no limit
    label = USAGE_LABEL.get(harness or "")
    if label is None:
        return True  # unknown harness -> don't throttle on it
    pct = usage.get(label)
    if pct is None:
        return True  # unreadable usage -> fail open
    return pct < max_usage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conduit", required=True)
    parser.add_argument("--max-usage", required=True)
    args = parser.parse_args()

    conduits_dir = Path(__file__).resolve().parents[2]
    harness = resolve_harness(args.conduit, conduits_dir)
    try:
        ceiling: int | None = int(args.max_usage)
    except (TypeError, ValueError):
        ceiling = None
    if harness and harness not in USAGE_LABEL:
        # Fail-open is deliberate, but silence is not: without this the tick
        # runs unthrottled and nothing says why.
        print(
            f"warning: no usage label for harness {harness!r}; "
            f"max_usage will not throttle this activity "
            f"(known: {', '.join(sorted(USAGE_LABEL))})",
            file=sys.stderr,
        )
    ok = is_ok(harness, read_usage(), ceiling)
    print(f"ok: {str(ok).lower()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
