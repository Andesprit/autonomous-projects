"""Tests for loop_count.py — proves the counter stops a loop at the target.

Run: uv run pytest (from scripts/)
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from loop_count import advance_phase, count_phase, parse_made, usage_ok

_REMAINING_ZERO = re.compile(r"remaining:\s*0")


def test_parse_made_absent():
    assert parse_made("") == 0
    assert parse_made("remaining: 3") == 0
    assert parse_made(None) == 0


def test_parse_made_reads_last():
    assert parse_made("made: 4\nremaining: 0") == 4
    assert parse_made("made: 1\n\nmade: 2") == 2  # last wins


def test_parse_made_ignores_other_sentinels():
    # work-one-todo / improve-task carry a second sink (task_counter) alongside
    # advance's made: — the extra line must not corrupt the parse.
    assert parse_made("made: 2\nremaining: 1\n\ntask_counter: 7") == 2


def test_count_phase_emits_skip_at_target():
    assert count_phase("made: 5\nremaining: 0", 5) == "made: 5\nremaining: 0"
    assert count_phase("made: 6", 5) == "made: 6\nremaining: 0"  # over-shoot still stops


def test_count_phase_passes_through_under_target():
    assert count_phase("", 3) == "made: 0"
    assert count_phase("made: 1\nremaining: 2", 3) == "made: 1"


def test_advance_phase_advances_and_computes_remaining():
    assert advance_phase("", 3) == "made: 1\nremaining: 2"
    assert advance_phase("made: 2\nremaining: 1", 3) == "made: 3\nremaining: 0"


def test_count_phase_stops_the_loop_when_over_the_usage_ceiling():
    # The parent checks usage once before the branch; a 10-iteration branch can
    # cross the ceiling halfway through, so the count phase re-checks and stops.
    out = count_phase("made: 2\nremaining: 8", 10, usage_ok=False)
    assert _REMAINING_ZERO.search(out)
    assert "made: 2" in out
    assert "stopped: usage" in out


def test_count_phase_under_ceiling_is_unchanged():
    assert count_phase("made: 2", 10, usage_ok=True) == count_phase("made: 2", 10)


def test_usage_ok_skipped_when_not_requested():
    assert usage_ok(None, None) is True
    assert usage_ok("generate-idea", None) is True
    assert usage_ok(None, "80") is True


def test_usage_ok_unparseable_ceiling_fails_open():
    assert usage_ok("generate-idea", "not-a-number") is True


def test_usage_ok_unknown_conduit_fails_open():
    # No such sub-conduit -> harness unresolved -> never throttle on it.
    assert usage_ok("no-such-conduit", "80") is True


def _simulate(target: int, repeat_ceiling: int = 50) -> int:
    """Mirror the engine loop and return how many activities actually ran.

    Each iteration: run count (gate), run the activity only if count didn't
    emit remaining: 0, then run advance. advance's output becomes the next
    iteration's `prior` (it is the sub-conduit's sink -> {{loop.previous}}).
    Stop when ANY emitted output this iteration matches remaining:\\s*0 — the
    any-match semantics the engine uses for a tool:conduit `until:`.
    """
    prior = ""
    activities = 0
    for _ in range(repeat_ceiling):
        c = count_phase(prior, target)
        outputs = [c]
        if not _REMAINING_ZERO.search(c):
            activities += 1  # the real activity task runs this iteration
            a = advance_phase(prior, target)
            outputs.append(a)
            prior = a
        if any(_REMAINING_ZERO.search(o) for o in outputs):
            break
    return activities


def test_loop_stops_exactly_at_target():
    for target in (1, 2, 5, 15):
        assert _simulate(target) == target, f"target={target}"


def test_loop_does_not_exceed_repeat_ceiling():
    # A pathological target above the ceiling stops at the ceiling, never spins.
    assert _simulate(1000, repeat_ceiling=10) == 10


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
