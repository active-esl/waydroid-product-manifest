#!/usr/bin/env python3
"""Verify selected immutable lock revisions are reachable from declared refs."""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET


def run(*command: str, cwd: pathlib.Path | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"command failed: {' '.join(command)}: {detail}")
    return result.stdout.strip()


def selected_projects(path: pathlib.Path) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 3 or not all(fields):
            raise ValueError(f"invalid remote lock at {path}:{line_number}")
        project, url, ref = fields
        if project in seen:
            raise ValueError(f"duplicate remote-lock project: {project}")
        if not re.fullmatch(
            r"https://github\.com/active-esl/[A-Za-z0-9_.-]+\.git", url
        ):
            raise ValueError(f"unsupported remote-lock URL: {url}")
        if not re.fullmatch(r"refs/(heads|tags)/[A-Za-z0-9][A-Za-z0-9._/-]*", ref):
            raise ValueError(f"invalid remote-lock ref: {ref}")
        if ".." in ref or "//" in ref or ref.endswith((".", "/")):
            raise ValueError(f"invalid remote-lock ref: {ref}")
        seen.add(project)
        entries.append((project, url, ref))
    if not entries:
        raise ValueError(f"no remote locks selected in {path}")
    return entries


def verify(lock: pathlib.Path, remotes: pathlib.Path) -> None:
    revisions = {
        (project.get("path") or project.get("name")): project.get("revision", "")
        for project in ET.parse(lock).getroot().findall("project")
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        root = pathlib.Path(temp_dir)
        for index, (project, url, ref) in enumerate(selected_projects(remotes)):
            revision = revisions.get(project)
            if revision is None:
                raise ValueError(f"remote-lock project is absent from source lock: {project}")
            if not re.fullmatch(r"[0-9a-f]{40}", revision):
                raise ValueError(
                    f"remote-lock revision is not an immutable commit SHA: "
                    f"{project} {revision or '<empty>'}"
                )
            checkout = root / str(index)
            checkout.mkdir()
            run("git", "init", "-q", cwd=checkout)
            run(
                "git",
                "fetch",
                "-q",
                "--filter=blob:none",
                "--no-tags",
                url,
                ref,
                cwd=checkout,
            )
            resolved = run(
                "git", "rev-parse", "--verify", f"{revision}^{{commit}}", cwd=checkout
            )
            if resolved != revision:
                raise ValueError(
                    f"remote-lock object does not resolve to its exact SHA: "
                    f"{project} {revision} resolved as {resolved}"
                )
            ancestry = subprocess.run(
                ["git", "merge-base", "--is-ancestor", revision, "FETCH_HEAD"],
                cwd=checkout,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if ancestry.returncode != 0:
                raise ValueError(
                    f"remote-lock revision is not reachable from declared ref: "
                    f"{project} {revision} on {ref}"
                )
            print(f"verified {project} {revision} on {ref}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lock", type=pathlib.Path)
    parser.add_argument("remotes", type=pathlib.Path)
    args = parser.parse_args()
    try:
        verify(args.lock, args.remotes)
    except (OSError, ValueError, subprocess.TimeoutExpired, ET.ParseError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
