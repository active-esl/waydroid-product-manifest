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
        projects = {
            project.get("path", project.attrib["name"]): project.attrib["revision"]
            for project in ET.parse(lock).getroot().findall("project")
        }
    except (ET.ParseError, KeyError, OSError) as error:
        print(f"cannot inspect source lock: {error}", file=sys.stderr)
        return 2

    tracked = [line.strip() for line in project_list.read_text().splitlines() if line.strip()]
    if not tracked:
        print("__FULL__")
        return 0

    drifted: list[str] = []
    for path in tracked:
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts or path not in projects:
            print("__FULL__")
            return 0
        result = subprocess.run(
            ["git", "-C", str(worktree / relative), "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode or result.stdout.strip() != projects[path]:
            if not result.returncode:
                status = subprocess.run(
                    ["git", "-C", str(worktree / relative), "status", "--porcelain=v1"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if status.returncode or status.stdout:
                    print(f"cannot resync drifted project with local changes: {path}", file=sys.stderr)
                    return 2
            drifted.append(path)

    print("\n".join(drifted), end="\n" if drifted else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
