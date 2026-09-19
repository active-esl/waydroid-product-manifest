#!/usr/bin/env python3
"""Regression tests for patch-series dependency revision checks."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PATCH_STATE = REPO_ROOT / "scripts" / "patch-state.py"
REAL_LOCK = REPO_ROOT / "locks" / "lineage-23.2-lock.xml"
REAL_REQUIREMENTS = REPO_ROOT / "locks" / "lineage-23.2-required-revisions.tsv"


def run(
    lock: Path, patch_root: Path, requirements: Path | None = None
) -> subprocess.CompletedProcess[str]:
    command = ["python3", str(PATCH_STATE), str(lock), str(patch_root)]
    if requirements is not None:
        command.append(str(requirements))
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )


def write_lock(path: Path, revision: str, include_hwc: bool = True) -> None:
    project = (
        f'<project path="hardware/waydroid" revision="{revision}" />'
        if include_hwc
        else ""
    )
    path.write_text(f"<manifest>{project}</manifest>\n")


def main() -> int:
    entries = [
        line.split("\t")
        for raw_line in REAL_REQUIREMENTS.read_text().splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    ]
    assert len(entries) == 1, entries
    project, required_revision = entries[0]
    assert project == "hardware/waydroid"

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        patch_root = root / "patches"
        patch_root.mkdir()
        requirements = root / "required-revisions.tsv"
        requirements.write_text(f"{project}\t{required_revision}\n")
        lock = root / "lock.xml"

        real = run(REAL_LOCK, patch_root, REAL_REQUIREMENTS)
        assert real.returncode == 0, real.stderr
        compatible = run(REAL_LOCK, patch_root)
        assert compatible.returncode == 0, compatible.stderr

        write_lock(lock, required_revision)
        exact = run(lock, patch_root, requirements)
        assert exact.returncode == 0, exact.stderr

        write_lock(lock, "0" * 40)
        mismatch = run(lock, patch_root, requirements)
        assert mismatch.returncode != 0, mismatch.stdout
        assert "required patch dependency revision mismatch" in mismatch.stderr

        write_lock(lock, required_revision, include_hwc=False)
        missing = run(lock, patch_root, requirements)
        assert missing.returncode != 0, missing.stdout
        assert "required patch dependency is absent" in missing.stderr

        requirements.write_text("hardware/waydroid b92200ac\n")
        malformed = run(lock, patch_root, requirements)
        assert malformed.returncode != 0, malformed.stdout
        assert "invalid required revision" in malformed.stderr

        absent = run(lock, patch_root, root / "absent.tsv")
        assert absent.returncode != 0, absent.stdout
        assert "required revisions file is missing" in absent.stderr

        lock.write_text(
            "<manifest>"
            f'<project path="{project}" revision="{required_revision}" />'
            f'<project path="{project}" revision="{required_revision}" />'
            "</manifest>\n"
        )
        duplicate = run(lock, patch_root, requirements)
        assert duplicate.returncode != 0, duplicate.stdout
        assert "duplicate project path in source lock" in duplicate.stderr

    print("patch-state dependency regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
