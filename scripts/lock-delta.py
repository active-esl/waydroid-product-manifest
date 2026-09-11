#!/usr/bin/env python3
"""Print project paths whose immutable manifest entries changed."""

from __future__ import annotations

import pathlib
import sys
import xml.etree.ElementTree as ET


def projects(path: pathlib.Path) -> dict[str, bytes]:
    root = ET.parse(path).getroot()
    result: dict[str, bytes] = {}
    for project in root.findall("project"):
        project_path = project.get("path") or project.get("name")
        if not project_path or project_path in result:
            raise ValueError(f"invalid or duplicate project path in {path}: {project_path}")
        result[project_path] = ET.tostring(project, encoding="utf-8")
    return result


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: lock-delta.py PREVIOUS_LOCK CURRENT_LOCK", file=sys.stderr)
        return 2

    previous_path, current_path = map(pathlib.Path, sys.argv[1:])
    try:
        previous = projects(previous_path)
        current = projects(current_path)
    except (OSError, ET.ParseError, ValueError) as error:
        print(f"cannot compare source locks: {error}", file=sys.stderr)
        print("__FULL__")
        return 0

    if previous.keys() != current.keys():
        print("__FULL__")
        return 0

    for project_path in sorted(current):
        if previous[project_path] != current[project_path]:
            print(project_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
