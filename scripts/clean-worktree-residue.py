#!/usr/bin/env python3
"""Remove disposable untracked and ignored files from selected repo projects."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


GIT_ENV_KEYS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


def clean_git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in GIT_ENV_KEYS:
        environment.pop(key, None)
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: clean-worktree-residue.py WORKTREE PROJECT...", file=sys.stderr)
        return 2

    try:
        worktree = Path(sys.argv[1]).resolve(strict=True)
    except OSError as error:
        print(f"cannot inspect Android worktree: {error}", file=sys.stderr)
        return 2

    cleanup_authorized = os.environ.get("ALLOW_LOCKED_SOURCE_CLEANUP") in {"1", "true"}

    for path in sys.argv[2:]:
        relative = Path(path)
        if not path or relative == Path(".") or relative.is_absolute() or ".." in relative.parts:
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
        if (project_dir == worktree or project_dir != candidate
                or not (project_dir / ".git").exists()):
            print(f"refusing symlinked or non-Git project path: {path}", file=sys.stderr)
            return 2
        try:
            if candidate.resolve(strict=True) != project_dir:
                raise OSError("project path changed during validation")
        except OSError as error:
            print(f"cannot revalidate project path {path}: {error}", file=sys.stderr)
            return 2
        environment = clean_git_environment()
        preview = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(project_dir), "clean", "-ndx"],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        if preview.returncode:
            print(f"cannot inventory untracked source residue: {path}", file=sys.stderr)
            return 2
        if preview.stdout:
            print(f"Disposable source residue scheduled for removal from {path}:")
            for line in preview.stdout.splitlines():
                print(f"  {line}")
            if not cleanup_authorized:
                print(
                    "refusing cleanup without ALLOW_LOCKED_SOURCE_CLEANUP=true",
                    file=sys.stderr,
                )
                return 2
        result = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(project_dir), "clean", "-fdqx"],
            check=False,
            env=environment,
        )
        if result.returncode:
            print(f"cannot remove untracked source residue: {path}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
