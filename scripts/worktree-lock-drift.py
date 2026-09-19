#!/usr/bin/env python3
"""Print tracked repo projects whose checked-out HEAD differs from the lock.

An unchanged manifest digest does not prove an unchanged source worktree.
``.repo/project.list`` is repo's record of projects selected for this checkout;
the lock can also contain projects excluded by the selected groups.
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: worktree-lock-drift.py LOCK PROJECT_LIST WORKTREE", file=sys.stderr)
        return 2

    lock, project_list, worktree = map(Path, sys.argv[1:])
    if not project_list.is_file():
        print("__FULL__")
        return 0

    try:
        worktree = worktree.resolve(strict=True)
    except OSError as error:
        print(f"cannot inspect Android worktree: {error}", file=sys.stderr)
        return 2

    try:
        projects = {
            project.get("path", project.attrib["name"]): project.attrib["revision"]
            for project in ET.parse(lock).getroot().findall("project")
        }
    except (ET.ParseError, KeyError, OSError) as error:
        print(f"cannot inspect source lock: {error}", file=sys.stderr)
        return 2

    try:
        tracked = [
            line.strip() for line in project_list.read_text().splitlines() if line.strip()
        ]
    except OSError as error:
        print(f"cannot inspect project inventory: {error}", file=sys.stderr)
        return 2
    if not tracked:
        print("__FULL__")
        return 0

    drifted: list[str] = []
    for path in tracked:
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts or path not in projects:
            print("__FULL__")
            return 0
        candidate = worktree / relative
        try:
            project_dir = candidate.resolve(strict=True)
        except FileNotFoundError:
            drifted.append(path)
            continue
        except OSError as error:
            print(f"cannot inspect project path {path}: {error}", file=sys.stderr)
            return 2
        try:
            project_dir.relative_to(worktree)
            beneath_worktree = True
        except ValueError:
            beneath_worktree = False
        if project_dir != candidate or not beneath_worktree:
            print(f"refusing symlinked or escaped project path: {path}", file=sys.stderr)
            return 2
        replacement_refs = subprocess.run(
            [
                "git", "--no-replace-objects", "-C", str(project_dir),
                "for-each-ref", "--format=%(refname)", "refs/replace",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if replacement_refs.returncode or replacement_refs.stdout:
            print(f"replacement refs are not allowed in a locked build: {path}", file=sys.stderr)
            return 2
        result = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(project_dir),
             "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if not result.returncode:
            tracked_status = subprocess.run(
                [
                    "git", "--no-replace-objects", "-C", str(project_dir), "status",
                    "--porcelain=v1", "--untracked-files=no",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if tracked_status.returncode or tracked_status.stdout:
                print(f"cannot resync project with tracked local changes: {path}", file=sys.stderr)
                return 2
            residue_status = subprocess.run(
                [
                    "git", "--no-replace-objects", "-C", str(project_dir), "status",
                    "--porcelain=v1", "--untracked-files=all", "--ignored=matching",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if residue_status.returncode:
                print(f"cannot inspect project residue: {path}", file=sys.stderr)
                return 2
            if residue_status.stdout:
                drifted.append(path)
        if result.returncode or result.stdout.strip() != projects[path]:
            if path not in drifted:
                drifted.append(path)

    print("\n".join(drifted), end="\n" if drifted else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
