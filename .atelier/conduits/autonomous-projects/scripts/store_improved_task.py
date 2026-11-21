"""Pick an inbox task, then publish its completed card before deleting the original."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime
from itertools import count
from pathlib import Path


def fingerprint(path: Path, info: os.stat_result, data: bytes) -> str:
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("picked task is no longer a regular file")
    identity = [str(path), info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns]
    return hashlib.sha256(json.dumps(identity).encode() + data).hexdigest()


def pick(inbox: Path) -> str:
    for path in sorted(inbox.resolve().glob("*.md")):
        if not path.is_symlink() and path.is_file():
            with path.open("rb") as source:
                data = source.read()
                key = fingerprint(path, os.fstat(source.fileno()), data)
            header = json.dumps([path.name, key])
            return f"picked: {header}\n{data.decode('utf-8')}"
    return "task_counter: 0"


def section(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines.pop(0)
    fence = ""
    for i, line in enumerate(lines):
        if fence:
            if re.fullmatch(rf" {{0,3}}{fence}{fence[0]}*[ \t]*", line):
                fence = ""
        elif match := re.match(r" {0,3}(`{3,}|~{3,})", line):
            fence = match[1]
        elif line.startswith("# "):
            lines[i] = "#" + line
    body = "\n".join(lines).strip()
    if not body:
        raise ValueError("empty spec or plan")
    return body


def parse_response(text: str) -> tuple[str, str, str]:
    markers = list(
        re.finditer(r"(?m)^(===(?:TASK|PLAN) (?:START|END)===|TASK_SLUG:.*)$", text)
    )
    expected = [
        "===TASK START===",
        "===TASK END===",
        "===PLAN START===",
        "===PLAN END===",
    ]
    if len(markers) != 5 or [m[0] for m in markers[:4]] != expected:
        raise ValueError("expected one complete spec, plan and slug")
    slug = re.fullmatch(
        r"TASK_SLUG:[ \t]*([a-z0-9]+(?:-[a-z0-9]+)*)[ \t]*", markers[4][0]
    )
    if not slug:
        raise ValueError("invalid task slug")
    spec = section(text[markers[0].end() : markers[1].start()])
    plan = section(text[markers[2].end() : markers[3].start()])
    return slug[1], spec, plan


def render(template: str, description: str, spec: str, plan: str) -> bytes:
    front, separator, body = template.partition("\n---\n")
    if not front.startswith("---\n") or not separator:
        raise ValueError("template needs YAML frontmatter")
    for key, value in (
        ("priority", "1"),
        (
            "creation_datetime",
            datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        ),
    ):
        front, hits = re.subn(rf"(?m)^{key}:.*$", f"{key}: {value}", front)
        if hits != 1:
            raise ValueError(f"template needs one {key} field")
    sections = {"# Description": description, "# Spec": spec, "# Plan": plan}
    headings = re.compile(r"(?m)^# (?:Description|Spec|Plan)$")
    if sorted(headings.findall(body)) != sorted(sections):
        raise ValueError("template needs one Description, Spec and Plan heading")
    return (
        front + separator + headings.sub(lambda m: m[0] + "\n\n" + sections[m[0]], body)
    ).encode()


def publish(backlog: Path, slug: str, key: str, body: bytes) -> tuple[Path, bytes]:
    # A frontmatter comment identifies this exact input even if a retry generates a new slug.
    prefix = f"# inbox-source {key} ".encode()
    for path in backlog.glob("task_*.md"):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as existing:
            if existing.read(4) != b"---\n":
                continue
            receipt = existing.readline(len(prefix) + 65)
            if not receipt.startswith(prefix):
                continue
            saved = b"---\n" + existing.read()
        if receipt != prefix + hashlib.sha256(saved).hexdigest().encode() + b"\n":
            raise ValueError("previously published card has changed")
        return path, b"---\n" + receipt + saved[4:]

    receipt = prefix + hashlib.sha256(body).hexdigest().encode() + b"\n"
    card = b"---\n" + receipt + body[4:]
    with tempfile.NamedTemporaryFile(dir=backlog) as staged:
        staged.write(card)
        staged.flush()
        os.fsync(staged.fileno())
        for number in count(1):
            suffix = "" if number == 1 else f".{number}"
            target = backlog / f"task_{slug}{suffix}.md"
            try:
                os.link(staged.name, target)
            except FileExistsError:
                continue
            return target, card


def store(
    inbox: Path, backlog: Path, template: Path, picked: str, response: str
) -> None:
    name, key = json.loads(picked.split("\n", 1)[0].removeprefix("picked: "))
    if Path(name).name != name or not name.endswith(".md"):
        raise ValueError("invalid inbox filename")
    source = inbox.resolve() / name
    slug, spec, plan = parse_response(response)
    if source.is_symlink() or not source.is_file():
        raise ValueError("picked source has moved")
    with source.open("rb") as original:
        fcntl.flock(original, fcntl.LOCK_EX)
        raw = original.read()
        info = source.lstat()
        if (
            not os.path.samestat(info, os.fstat(original.fileno()))
            or fingerprint(source, info, raw) != key
        ):
            raise ValueError("picked source has changed")
        body = render(
            template.read_text(encoding="utf-8"), raw.decode("utf-8"), spec, plan
        )
        backlog.mkdir(parents=True, exist_ok=True)
        target, expected = publish(backlog, slug, key, body)
        if target.is_symlink() or target.read_bytes() != expected:
            raise ValueError("backlog verification failed")
        directory = os.open(backlog, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        original.seek(0)
        current = original.read()
        if fingerprint(source, source.lstat(), current) != key:
            raise ValueError("picked source changed during publication")
        source.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pick").add_argument("inbox", type=Path)
    writer = commands.add_parser("store")
    for arg in ("inbox", "backlog", "template", "picked"):
        writer.add_argument(arg, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "pick":
            print(pick(args.inbox))
        else:
            store(
                args.inbox,
                args.backlog,
                args.template,
                args.picked.read_text(encoding="utf-8"),
                sys.stdin.read(),
            )
            print("stored: true")
    except (OSError, ValueError) as exc:
        print(f"remaining: 0\nstopped: {exc}")


if __name__ == "__main__":
    main()
