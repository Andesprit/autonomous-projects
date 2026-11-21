"""Tests for loop_count.py — proves the counter stops a loop at the target.

Run: uv run pytest (from scripts/)
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from loop_count import advance_phase, count_phase, made_so_far, main, parse_made, usage_ok

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


def _render(tries: list[str], limit: int = 10) -> str:
    """Render tries the way flow-atelier renders {{loop.history}}.

    A copy of the engine's format, kept here because the package tests do not
    install flow-atelier: newest `limit` tries kept, one block per try.
    """
    omitted = max(len(tries) - limit, 0) if limit > 0 else 0
    blocks = [
        f"--- iteration {i} ---\n{out}"
        for i, out in enumerate(tries[omitted:], omitted + 1)
    ]
    if omitted:
        blocks.insert(0, f"--- {omitted} earlier iterations omitted ---")
    return "\n\n".join(blocks)


def _failed(text: str) -> str:
    """What the engine keeps for a try that failed: a marker line, then raw text."""
    return f"[this try failed with exit code 1]\n{text}"


# Raw agent/command text from a failed try: a stray counter and shell syntax.
_FAILURE_TEXT = "made: 99 $(touch pwned) `id`\ntask 'generate_idea' failed: exit=1"


def test_made_so_far_reads_the_last_good_try():
    history = _render(["made: 1\nremaining: 4", "made: 2\nremaining: 3"])
    assert made_so_far(history) == 2


def test_made_so_far_skips_a_failed_newest_try():
    # loop.previous would be the failure text here, which has no counter of
    # its own: the count must come from the try before it.
    history = _render(["made: 1\nremaining: 4", "made: 2\nremaining: 3", _failed(_FAILURE_TEXT)])
    assert made_so_far(history) == 2
    assert count_phase(history, 5) == "made: 2"
    assert advance_phase(history, 5) == "made: 3\nremaining: 2"


def test_made_so_far_ignores_a_counter_inside_failure_text():
    assert made_so_far(_render([_failed(_FAILURE_TEXT)])) == 0


def test_made_so_far_reads_text_without_iteration_blocks_as_one_try():
    assert made_so_far("") == 0
    assert made_so_far(None) == 0
    assert made_so_far("made: 3\nremaining: 1") == 3
    assert made_so_far(_failed(_FAILURE_TEXT)) == 0


def test_count_is_unknown_when_kept_tries_all_failed_and_older_ones_were_dropped():
    # 3 good tries, then 10 failures: the engine keeps only the failures, so
    # the count is unknown. Guessing 0 would run the activity `target` more times.
    tries = ["made: 1", "made: 2", "made: 3"] + [_failed(_FAILURE_TEXT)] * 10
    history = _render(tries)
    assert "earlier iterations omitted" in history
    assert made_so_far(history) is None
    out = count_phase(history, 15)
    assert _REMAINING_ZERO.search(out)
    assert "stopped:" in out


def test_main_reads_the_history_file(tmp_path, capsys):
    f = tmp_path / "INPUT_HISTORY"
    f.write_text(_render(["made: 2\nremaining: 1", _failed(_FAILURE_TEXT)]))
    assert main(["--phase", "advance", "--target", "3", "--history-file", str(f)]) == 0
    assert capsys.readouterr().out == "made: 3\nremaining: 0\n"


def test_main_says_which_flow_atelier_it_needs_when_the_file_is_missing(capsys):
    # flow-atelier 0.12 sets no $INPUT_HISTORY_FILE, so the step passes "".
    with pytest.raises(SystemExit) as exc:
        main(["--phase", "count", "--target", "3", "--history-file", ""])
    assert exc.value.code == 2
    assert "newer than 0.12.0" in capsys.readouterr().err


def _simulate(
    target: int, repeat_ceiling: int = 50, fails: set[int] | None = None, limit: int = 10
) -> tuple[int, int]:
    """Mirror the engine loop and return (activities run, tries run).

    Each try: run count (gate) on the rendered {{loop.history}}, run the
    activity only if count didn't emit remaining: 0, then run advance, whose
    output is what the history keeps for that try (it is the sub-conduit's
    sink). A try in `fails` fails after count: the engine keeps its failure
    text, does not check `until:` on it, and starts the next try. Stop when
    ANY output of a good try matches remaining:\\s*0, the any-match semantics
    the engine uses for a tool:conduit `until:`.
    """
    fails = fails or set()
    tries: list[str] = []
    activities = 0
    for i in range(1, repeat_ceiling + 1):
        history = _render(tries, limit)
        c = count_phase(history, target)
        if _REMAINING_ZERO.search(c):
            return activities, i
        if i in fails:
            tries.append(_failed(_FAILURE_TEXT))
            continue
        activities += 1  # the real activity task runs this try
        a = advance_phase(history, target)
        tries.append(a)
        if _REMAINING_ZERO.search(a):
            return activities, i
    return activities, repeat_ceiling


def test_loop_stops_exactly_at_target():
    for target in (1, 2, 5, 15):
        assert _simulate(target)[0] == target, f"target={target}"


def test_loop_does_not_exceed_repeat_ceiling():
    # A pathological target above the ceiling stops at the ceiling, never spins.
    assert _simulate(1000, repeat_ceiling=10)[0] == 10


def test_failed_tries_do_not_reset_the_count():
    # The bug: after a failed try the count restarted from 0, so the tick made
    # more than n_* items. Failed tries now leave the count where it was.
    for fails in ({2}, {1, 3}, {2, 3, 4, 7}):
        activities, _ = _simulate(5, fails=fails)
        assert activities == 5, f"fails={fails}"


def test_a_branch_whose_tries_keep_failing_stops_once_the_history_window_fills():
    # Every try fails: the count stays 0 while the engine still shows every
    # try, then stops once older tries drop out of {{loop.history}}.
    activities, tries = _simulate(5, fails=set(range(1, 51)))
    assert activities == 0
    assert tries == 12  # 11 failed tries, then the 12th count stops the branch
    # Good tries, then a run of failures longer than the window: stop, never
    # restart the count from 0.
    activities, _ = _simulate(15, fails=set(range(4, 51)))
    assert activities == 3


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
