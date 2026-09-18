#!/usr/bin/env python3
"""Check that locked commits exist before a local-only repo checkout."""

from __future__ import annotations

import argparse
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def missing_objects(lock: Path, workspace: Path, paths: list[str]) -> list[str]:
    projects = {project.attrib["path"]: project.attrib["revision"]
                for project in ET.parse(lock).getroot().iter("project")}
    selected = paths or list(projects)
    unknown = sorted(set(selected) - projects.keys())
    if unknown:
        raise ValueError("paths absent from source lock: " + ", ".join(unknown))

    missing = []
    for path in selected:
        checkout = workspace / path
        if not (checkout / ".git").exists():
            missing.append(path)
            continue
        result = subprocess.run(
            ["git", "-C", str(checkout), "cat-file", "-e", projects[path] + "^{commit}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode:
            missing.append(path)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    missing = missing_objects(args.lock, args.workspace, args.paths)
    if missing:
        print("Locked Git objects absent for {} project(s): {}".format(
            len(missing), ", ".join(missing[:5])))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
