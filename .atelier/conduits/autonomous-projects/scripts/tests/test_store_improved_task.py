"""Regression coverage for the improve-task inbox → backlog handoff."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import store_improved_task as tasks  # noqa: E402

TEMPLATE = SCRIPTS.parent / "references/task_template.md"
RESPONSE = """===TASK START===
# Spec
Cover the original request.
# Examples
```sh
# preserve this comment
```
===TASK END===
===PLAN START===
# Plan
Implement and test.
===PLAN END===
TASK_SLUG: sample-task"""


@pytest.fixture
def files(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    source = inbox / "z.md"
    source.write_bytes(b"# Description\r\n\r\nKeep $(date) and trailing spaces.  \r\n")
    return source, tmp_path / "backlog"


def test_cli_publishes_then_removes_only_the_picked_input(files, tmp_path):
    source, backlog = files
    raw = source.read_bytes()
    script = [sys.executable, str(SCRIPTS / "store_improved_task.py")]
    snapshot = tmp_path / "picked"
    snapshot.write_bytes(subprocess.check_output([*script, "pick", source.parent]))
    earlier = source.with_name("a.md")
    earlier.write_text("new arrival")
    template = tmp_path / "template"
    template.write_text(TEMPLATE.read_text() + "\n# Custom section\n")
    args = [*script, "store", source.parent, backlog, template, snapshot]
    result = subprocess.run(
        args, input=RESPONSE, text=True, capture_output=True, check=True
    )
    assert result.stdout == "stored: true\n"
    card = (backlog / "task_sample-task.md").read_bytes()
    assert b"# Description\n\n" + raw in card
    assert b"priority: 1\n" in card and b"creation_datetime:  #" not in card
    assert (
        b"# Spec\n\nCover the original request.\n## Examples\n```sh\n# preserve" in card
    )
    assert b"# Plan\n\nImplement and test." in card and b"# Custom section" in card
    assert not source.exists()
    assert earlier.read_text() == "new arrival"


@pytest.mark.parametrize(
    "response",
    [
        RESPONSE.split("===PLAN END===")[0],
        RESPONSE.replace("Implement and test.", ""),
        RESPONSE.replace(
            "# Spec\nCover the original request.\n# Examples\n```sh\n# preserve this comment\n```",
            "",
        ),
        RESPONSE.replace("sample-task", "../escape"),
        RESPONSE + "\nTASK_SLUG: another",
    ],
)
def test_rejects_malformed_response(files, response):
    source, backlog = files
    with pytest.raises(ValueError):
        tasks.store(
            source.parent, backlog, TEMPLATE, tasks.pick(source.parent), response
        )
    assert source.exists() and not backlog.exists()


@pytest.mark.parametrize("mode", ["failed", "missing", "incomplete"])
def test_unverified_publication_keeps_source(files, monkeypatch, mode):
    source, backlog = files
    raw = source.read_bytes()

    def bad_link(staged, destination):
        if mode == "failed":
            raise OSError("disk full")
        if mode == "incomplete":
            destination.write_bytes(b"# Description\n")

    monkeypatch.setattr(os, "link", bad_link)
    with pytest.raises((OSError, ValueError)):
        tasks.store(
            source.parent, backlog, TEMPLATE, tasks.pick(source.parent), RESPONSE
        )
    assert source.read_bytes() == raw


def test_duplicate_slug_from_different_inputs(files):
    source, backlog = files
    second = source.with_name("zz.md")
    second.write_bytes(source.read_bytes())
    for _ in range(2):
        tasks.store(
            source.parent, backlog, TEMPLATE, tasks.pick(source.parent), RESPONSE
        )
    assert sorted(p.name for p in backlog.iterdir()) == [
        "task_sample-task.2.md",
        "task_sample-task.md",
    ]
    assert tasks.pick(source.parent) == "task_counter: 0"


def test_retry_after_publication_reuses_verified_card(files, monkeypatch):
    source, backlog = files
    picked = tasks.pick(source.parent)
    with monkeypatch.context() as m:

        def interrupted(path):
            raise PermissionError("source removal interrupted")

        m.setattr(Path, "unlink", interrupted)
        with pytest.raises(PermissionError):
            tasks.store(source.parent, backlog, TEMPLATE, picked, RESPONSE)
    (card,) = backlog.iterdir()
    published = card.read_bytes()
    assert source.exists()
    tasks.store(
        source.parent,
        backlog,
        TEMPLATE,
        tasks.pick(source.parent),
        RESPONSE.replace("sample-task", "new-name"),
    )
    assert list(backlog.iterdir()) == [card]
    assert card.read_bytes() == published and not source.exists()


def test_changed_source_survives(files):
    source, backlog = files
    picked = tasks.pick(source.parent)
    source.write_text("new instructions")
    with pytest.raises(ValueError, match="changed"):
        tasks.store(source.parent, backlog, TEMPLATE, picked, RESPONSE)
    assert source.read_text() == "new instructions" and not backlog.exists()


def test_edit_during_publication_keeps_replacement(files, monkeypatch):
    source, backlog = files
    picked = tasks.pick(source.parent)
    publish = tasks.publish

    def publish_then_replace(*args):
        result = publish(*args)
        replacement = source.with_suffix(".tmp")
        replacement.write_text("edited while publishing")
        replacement.replace(source)
        return result

    monkeypatch.setattr(tasks, "publish", publish_then_replace)
    with pytest.raises(ValueError, match="changed during publication"):
        tasks.store(source.parent, backlog, TEMPLATE, picked, RESPONSE)
    assert source.read_text() == "edited while publishing"
