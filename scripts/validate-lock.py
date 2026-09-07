#!/usr/bin/env python3
"""Reject Android source locks containing floating project revisions."""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate-lock.py MANIFEST", file=sys.stderr)
        return 2

    manifest = Path(sys.argv[1])
    root = ET.parse(manifest).getroot()
    projects = root.findall("project")
    invalid = []
    for project in projects:
        revision = project.get("revision", "")
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            invalid.append((project.get("path") or project.get("name"), revision))

    forbidden = [element.tag for element in root if element.tag in {"include", "remove-project", "extend-project"}]
    if not projects or invalid or forbidden:
        print(f"invalid lock: projects={len(projects)} floating={len(invalid)} directives={len(forbidden)}", file=sys.stderr)
        for name, revision in invalid[:10]:
            print(f"floating revision: {name}: {revision}", file=sys.stderr)
        return 1

    print(f"valid immutable lock: {len(projects)} projects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
