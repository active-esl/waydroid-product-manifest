#!/usr/bin/env python3
"""Remove disposable untracked and ignored files from selected repo projects."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: clean-worktree-residue.py WORKTREE PROJECT...", file=sys.stderr)
        return 2

    try:
        worktree = Path(sys.argv[1]).resolve(strict=True)
    except OSError as error:
        print(f"cannot inspect Android worktree: {error}", file=sys.stderr)
        return 2

    for path in sys.argv[2:]:
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            print(f"refusing unsafe project path: {path}", file=sys.stderr)
            return 2
        candidate = worktree / relative
        if not candidate.exists():
            # repo sync will recreate a selected project whose checkout was
            # removed; there is no local residue to clean first.
            continue
        try:
            project_dir = candidate.resolve(strict=True)
            project_dir.relative_to(worktree)
        except (OSError, ValueError) as error:
            print(f"cannot clean project path {path}: {error}", file=sys.stderr)
            return 2
        if project_dir != candidate or not (project_dir / ".git").exists():
            print(f"refusing symlinked or non-Git project path: {path}", file=sys.stderr)
            return 2
        result = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(project_dir), "clean", "-fdqx"],
            check=False,
        )
        if result.returncode:
            print(f"cannot remove untracked source residue: {path}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
