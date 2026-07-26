"""Tests for require_markers.py — the non-fatal generation-contract gate.

Run: uv run pytest (from scripts/)
"""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from require_markers import check, main

COMPLETE = (
    "## Theme: something\nnarration the store step must discard\n"
    "===IDEA START===\nthe idea itself\n===IDEA END===\n\nIDEA_SLUG: some-idea"
)
# What the diverge step actually returned when it stopped after Phase 1.
PHASE_1_ONLY = (
    "Five isolated divergent branches launched (competitor, 3am on-call, "
    "biology). Waiting on them before the critic pass."
)


def test_complete_block_passes():
    assert check(COMPLETE) == (True, "")


def test_phase_1_only_fails():
    ok, reason = check(PHASE_1_ONLY)
    assert ok is False
    assert "IDEA START" in reason


def test_missing_slug_fails():
    ok, reason = check("===IDEA START===\nx\n===IDEA END===")
    assert ok is False
    assert "IDEA_SLUG" in reason


def test_empty_block_fails():
    ok, reason = check("===IDEA START===\n   \n===IDEA END===\nIDEA_SLUG: x")
    assert (ok, reason) == (False, "empty IDEA block")


def test_empty_and_none_input_fail():
    assert check("")[0] is False
    assert check(None)[0] is False


def test_review_kind():
    text = "===REVIEW START===\nfindings\n===REVIEW END===\nREVIEW_SLUG: auth"
    assert check(text, kind="REVIEW") == (True, "")
    assert check(text, kind="IDEA")[0] is False


def _run(monkeypatch, capsys, text):
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    code = main([])
    return code, capsys.readouterr()


def test_main_always_exits_zero_and_reports_ok(monkeypatch, capsys):
    # Exit 0 even on failure: the engine is fail-fast, and a non-zero here would
    # cancel the sibling branches still running.
    code, out = _run(monkeypatch, capsys, COMPLETE)
    assert code == 0
    assert "ok: true" in out.out
    assert "remaining: 0" not in out.out


def test_main_stops_only_this_branch_on_failure(monkeypatch, capsys):
    code, out = _run(monkeypatch, capsys, PHASE_1_ONLY)
    assert code == 0
    assert "ok: false" in out.out
    assert "remaining: 0" in out.out  # parent loop stops this branch
    assert out.err.strip()  # and says so out loud


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
