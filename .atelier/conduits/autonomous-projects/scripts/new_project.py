"""One-command project scaffolder.

Usage:
    uv run python new_project.py --repo <path>

Creates <repo>/.atelier/project/ with project.md (from the template) and all
stage folders. Atomic: builds in a temp dir, renames on success.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path


STAGE_FOLDERS = [
    "00_abandoned",
    "00_backlog",
    "00_tasks",
    "01_to-do",
    "02_in-progress",
    "03_to-review",
    "04_done",
]


def create_project(repo: Path, template_path: Path) -> Path:
    """Create <repo>/.atelier/project/ with stage folders and a project.md.

    Validates inputs first, then builds atomically in a temp dir.

    Returns the created .atelier/project path.

    Raises:
        FileExistsError: <repo>/.atelier/project already exists.
        OSError: *repo* is not a writable directory, or the template is missing.
    """
    if not repo.is_dir() or not os.access(str(repo), os.W_OK):
        raise OSError(f"--repo {str(repo)!r} is not an existing writable directory.")

    if not template_path.exists():
        raise OSError(f"Template not found at {template_path}.")

    target = repo / ".atelier" / "project"
    if target.exists():
        raise FileExistsError(f"Project already exists at {target}.")

    target.parent.mkdir(parents=True, exist_ok=True)  # <repo>/.atelier

    tmp_dir = Path(tempfile.mkdtemp(dir=target.parent))
    try:
        for folder in STAGE_FOLDERS:
            d = tmp_dir / folder
            d.mkdir(parents=True)
            # ponytail: .gitkeep so git tracks the empty lane; survives commit/clone
            (d / ".gitkeep").write_text("", encoding="utf-8")
        (tmp_dir / "project.md").write_text(
            template_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        os.rename(str(tmp_dir), str(target))
    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold .atelier/project/ inside a target repo."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Path to the target repo (must exist, writable); .atelier/project/ goes here",
    )
    args = parser.parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    template_path = script_dir.parent / "references" / "project_template.md"

    try:
        path = create_project(Path(args.repo), template_path)
    except (FileExistsError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created project at {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
