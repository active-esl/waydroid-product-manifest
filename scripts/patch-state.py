#!/usr/bin/env python3
"""Fingerprint each project's ordered patch series and locked base revision."""

from __future__ import annotations

import hashlib
import pathlib
import sys
import xml.etree.ElementTree as ET


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: patch-state.py SOURCE_LOCK PATCH_ROOT", file=sys.stderr)
        return 2

    lock_path = pathlib.Path(sys.argv[1])
    patch_root = pathlib.Path(sys.argv[2])
    revisions = {
        (project.get("path") or project.get("name")): project.get("revision", "")
        for project in ET.parse(lock_path).getroot().findall("project")
    }
    grouped: dict[str, list[pathlib.Path]] = {}
    for patch in sorted(patch_root.rglob("*.patch")):
        project = patch.parent.relative_to(patch_root).as_posix()
        grouped.setdefault(project, []).append(patch)

    for project, patches in sorted(grouped.items()):
        if project not in revisions:
            raise ValueError(f"patch target is absent from source lock: {project}")
        digest = hashlib.sha256()
        digest.update(revisions[project].encode())
        digest.update(b"\0")
        for patch in patches:
            digest.update(patch.name.encode())
            digest.update(b"\0")
            digest.update(patch.read_bytes())
            digest.update(b"\0")
        print(f"{project}\t{digest.hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
