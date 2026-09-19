#!/usr/bin/env python3
"""Regression tests for patch-series dependency revision checks."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PATCH_STATE = REPO_ROOT / "scripts" / "patch-state.py"
REQUIRED_HWC = "b92200ac592ed43acd9f1f1bc41c09bc407b1732"


def run(lock: Path, patch_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(PATCH_STATE), str(lock), str(patch_root)],
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
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        patch_root = root / "patches"
        patch_root.mkdir()
        requirements = patch_root / "required-revisions.tsv"
        requirements.write_text(f"hardware/waydroid\t{REQUIRED_HWC}\n")
        lock = root / "lock.xml"

        write_lock(lock, REQUIRED_HWC)
        exact = run(lock, patch_root)
        assert exact.returncode == 0, exact.stderr

        write_lock(lock, "0" * 40)
        mismatch = run(lock, patch_root)
        assert mismatch.returncode != 0, mismatch.stdout
        assert "required patch dependency revision mismatch" in mismatch.stderr

        write_lock(lock, REQUIRED_HWC, include_hwc=False)
        missing = run(lock, patch_root)
        assert missing.returncode != 0, missing.stdout
        assert "required patch dependency is absent" in missing.stderr

        requirements.write_text("hardware/waydroid b92200ac\n")
        malformed = run(lock, patch_root)
        assert malformed.returncode != 0, malformed.stdout
        assert "invalid required revision" in malformed.stderr

    print("patch-state dependency regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
