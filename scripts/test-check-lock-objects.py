#!/usr/bin/env python3
"""Regression test for fetching missing lock objects before checkout."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path


script = Path(__file__).with_name("check-lock-objects.py")
spec = importlib.util.spec_from_file_location("check_lock_objects", script)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    checkout = root / "src" / "project"
    checkout.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    subprocess.run(["git", "-C", str(checkout), "-c", "commit.gpgsign=false",
                    "-c", "user.name=Test",
                    "-c", "user.email=test@example.invalid", "commit", "-q",
                    "--allow-empty", "-m", "first"], check=True)
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    lock = root / "lock.xml"
    lock.write_text('<manifest><project path="project" revision="{}"/></manifest>'.format(revision))
    assert module.missing_objects(lock, root / "src", ["project"]) == []
    assert module.missing_objects(lock, root / "empty", ["project"]) == ["project"]
    lock.write_text('<manifest><project path="project" revision="{}"/></manifest>'.format("0" * 40))
    assert module.missing_objects(lock, root / "src", ["project"]) == ["project"]
    lock.write_text('<manifest><project name="project" revision="{}"/></manifest>'.format(revision))
    assert module.missing_objects(lock, root / "src", ["project"]) == []
    invalid = subprocess.run(
        [sys.executable, str(script), "--lock", str(lock), "--workspace", str(root / "src"), "unknown"],
        capture_output=True, text=True, check=False,
    )
    assert invalid.returncode == 2

print("locked-object preflight regression tests passed")
