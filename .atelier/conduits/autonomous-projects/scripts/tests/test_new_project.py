"""Tests for new_project.py. Run: uv run pytest"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from new_project import STAGE_FOLDERS, create_project


TEMPLATE = """\
---
test_command: ""
---
# Goal
"""


def _template(tmp_path: Path) -> Path:
    p = tmp_path / "project_template.md"
    p.write_text(TEMPLATE, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# create_project — happy path
# ---------------------------------------------------------------------------

def test_happy_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tmpl = _template(tmp_path)

    result = create_project(repo, tmpl)

    assert result == repo / ".atelier" / "project"
    assert result.is_dir()
    for folder in STAGE_FOLDERS:
        assert (result / folder).is_dir()
        assert (result / folder / ".gitkeep").is_file()

    project_md = result / "project.md"
    assert project_md.is_file()
    # Template copied verbatim — no location rewrite.
    assert project_md.read_text(encoding="utf-8") == TEMPLATE


# ---------------------------------------------------------------------------
# Rejection cases
# ---------------------------------------------------------------------------

def test_already_exists_rejected(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".atelier" / "project").mkdir(parents=True)
    tmpl = _template(tmp_path)
    with pytest.raises(FileExistsError, match="already exists"):
        create_project(repo, tmpl)


def test_missing_repo_rejected(tmp_path):
    tmpl = _template(tmp_path)
    missing = tmp_path / "does-not-exist"
    with pytest.raises(OSError, match="not an existing writable directory"):
        create_project(missing, tmpl)
    assert not (missing / ".atelier").exists()


@pytest.mark.skipif(os.name == "nt", reason="chmod 0 not portable to Windows")
def test_unwritable_repo_rejected(tmp_path):
    tmpl = _template(tmp_path)
    unwritable = tmp_path / "unwritable"
    unwritable.mkdir()
    unwritable.chmod(0o000)
    try:
        with pytest.raises(OSError, match="not an existing writable directory"):
            create_project(unwritable, tmpl)
    finally:
        unwritable.chmod(0o755)  # restore so tmp_path cleanup works


# ---------------------------------------------------------------------------
# Atomicity — failure during build leaves nothing behind
# ---------------------------------------------------------------------------

def test_atomicity_bad_template_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    bad_template = tmp_path / "nonexistent_template.md"

    with pytest.raises(OSError, match="Template not found"):
        create_project(repo, bad_template)

    assert not (repo / ".atelier" / "project").exists()
    # No temp dirs left under .atelier (it may not exist at all).
    atelier = repo / ".atelier"
    leftovers = list(atelier.iterdir()) if atelier.exists() else []
    assert leftovers == [], f"Leftover temp dirs: {leftovers}"
