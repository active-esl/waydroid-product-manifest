#!/usr/bin/env python3
"""Regression tests for the immutable Android source-lock gate."""

from __future__ import annotations

import copy
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate-lock.py"
LOCK = REPO_ROOT / "locks" / "lineage-23.2-lock.xml"


def validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(VALIDATOR), str(path)],
        check=False,
        capture_output=True,
        text=True,
    )


def main() -> int:
    valid = validate(LOCK)
    assert valid.returncode == 0, valid.stderr

    tree = ET.parse(LOCK)
    root = tree.getroot()
    root.append(copy.deepcopy(root.findall("project")[0]))
    with tempfile.TemporaryDirectory() as temp_dir:
        duplicate_lock = Path(temp_dir) / "duplicate-lock.xml"
        tree.write(duplicate_lock, encoding="utf-8", xml_declaration=True)
        duplicate = validate(duplicate_lock)
    assert duplicate.returncode == 1, duplicate.stdout
    assert "duplicate project path:" in duplicate.stderr, duplicate.stderr
    print("source-lock validation regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
