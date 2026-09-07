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
    required_projects = {
        "device/waydroid/waydroid": "active-esl/android_device_waydroid_waydroid",
        "vendor/extra": "active-esl/android_vendor_waydroid",
        "external/v4l2_codec2": "active-esl/android_external_v4l2_codec2",
    }
    resolved_projects = {project.get("path"): project.get("name") for project in projects}
    missing_required = {
        path: name
        for path, name in required_projects.items()
        if resolved_projects.get(path) != name
    }
    invalid = []
    for project in projects:
        revision = project.get("revision", "")
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            invalid.append((project.get("path") or project.get("name"), revision))

    forbidden = [element.tag for element in root if element.tag in {"include", "remove-project", "extend-project"}]
    if not projects or invalid or forbidden or missing_required:
        print(
            f"invalid lock: projects={len(projects)} floating={len(invalid)} "
            f"directives={len(forbidden)} required={len(missing_required)}",
            file=sys.stderr,
        )
        for name, revision in invalid[:10]:
            print(f"floating revision: {name}: {revision}", file=sys.stderr)
        for path, name in missing_required.items():
            print(f"required project missing or replaced: {path}: {name}", file=sys.stderr)
        return 1

    print(f"valid immutable lock: {len(projects)} projects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
