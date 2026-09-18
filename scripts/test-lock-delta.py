#!/usr/bin/env python3
"""Check source-lock project additions without a full Android resync."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def delta(previous: str, current: str) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        old = Path(directory) / "old.xml"
        new = Path(directory) / "new.xml"
        old.write_text(previous)
        new.write_text(current)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("lock-delta.py")), str(old), str(new)],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.splitlines()


base = '<manifest><project name="a" path="a" revision="1"/></manifest>'
added = '<manifest><project name="a" path="a" revision="1"/><project name="b" path="b" revision="2"/></manifest>'
changed = '<manifest><project name="a" path="a" revision="2"/><project name="b" path="b" revision="2"/></manifest>'
assert delta(base, added) == ["b"]
assert delta(base, changed) == ["a", "b"]
assert delta(added, base) == ["__FULL__"]
print("source-lock delta regression tests passed")
