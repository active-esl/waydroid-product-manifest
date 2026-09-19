#!/usr/bin/env python3
"""Fingerprint each project's ordered patch series and locked base revision."""

from __future__ import annotations

import hashlib
import pathlib
import sys
import xml.etree.ElementTree as ET


def validate_required_revisions(
    requirements: pathlib.Path, revisions: dict[str, str]
) -> None:
    if not requirements.is_file():
        raise ValueError(f"required revisions file is missing: {requirements}")
    for line_number, raw_line in enumerate(requirements.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 2 or not all(fields):
            raise ValueError(
                f"invalid required revision at {requirements}:{line_number}"
            )
        project, required_revision = fields
        locked_revision = revisions.get(project)
        if locked_revision is None:
            raise ValueError(f"required patch dependency is absent from source lock: {project}")
        if locked_revision != required_revision:
            raise ValueError(
                "required patch dependency revision mismatch: "
                f"{project} is {locked_revision}, expected {required_revision}"
            )


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(
            "usage: patch-state.py SOURCE_LOCK PATCH_ROOT [REQUIRED_REVISIONS]",
            file=sys.stderr,
        )
        return 2

    lock_path = pathlib.Path(sys.argv[1])
    patch_root = pathlib.Path(sys.argv[2])
    requirements = (
        pathlib.Path(sys.argv[3])
        if len(sys.argv) == 4
        else pathlib.Path(__file__).resolve().parent.parent
        / "locks"
        / "lineage-23.2-required-revisions.tsv"
    )
    revisions: dict[str, str] = {}
    for project in ET.parse(lock_path).getroot().findall("project"):
        path = project.get("path") or project.get("name")
        if path in revisions:
            raise ValueError(f"duplicate project path in source lock: {path}")
        revisions[path] = project.get("revision", "")
    validate_required_revisions(requirements, revisions)
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
