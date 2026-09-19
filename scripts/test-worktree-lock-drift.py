#!/usr/bin/env python3
"""Regression tests for checked-out HEAD verification before Android builds."""

from __future__ import annotations

import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


CHECKER = Path(__file__).with_name("worktree-lock-drift.py")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def check(lock: Path, project_list: Path, worktree: Path) -> str:
    result = subprocess.run(
        ["python3", str(CHECKER), str(lock), str(project_list), str(worktree)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def check_failure(lock: Path, project_list: Path, worktree: Path) -> str:
    result = subprocess.run(
        ["python3", str(CHECKER), str(lock), str(project_list), str(worktree)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    return result.stderr


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        worktree = Path(temp_dir)
        project = worktree / "hardware" / "waydroid"
        project.mkdir(parents=True)
        git("-C", str(project), "init", "-q")
        (project / "tracked.txt").write_text("original\n")
        git("-C", str(project), "add", "tracked.txt")
        git("-C", str(project), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-q", "--allow-empty", "-m", "locked")
        locked_head = git("-C", str(project), "rev-parse", "HEAD")

        manifest = ET.Element("manifest")
        ET.SubElement(manifest, "project", name="waydroid/android_hardware_waydroid",
                      path="hardware/waydroid", revision=locked_head)
        ET.SubElement(manifest, "project", name="example/missing",
                      path="hardware/missing", revision="0" * 40)
        lock = worktree / "lock.xml"
        ET.ElementTree(manifest).write(lock, encoding="utf-8", xml_declaration=True)
        project_list = worktree / ".repo" / "project.list"
        project_list.parent.mkdir()
        project_list.write_text("hardware/waydroid\n")

        assert check(lock, project_list, worktree) == ""
        (project / "tracked.txt").write_text("local edit at locked head\n")
        assert "cannot resync project with local changes" in check_failure(
            lock, project_list, worktree
        )
        (project / "tracked.txt").write_text("original\n")
        (project / "untracked.txt").write_text("must not enter a locked build\n")
        assert "cannot resync project with local changes" in check_failure(
            lock, project_list, worktree
        )
        (project / "untracked.txt").unlink()
        git("-C", str(project), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-q", "--allow-empty", "-m", "drifted")
        assert check(lock, project_list, worktree) == "hardware/waydroid"
        (project / "tracked.txt").write_text("local edit\n")
        assert "cannot resync project with local changes" in check_failure(
            lock, project_list, worktree
        )
        (project / "tracked.txt").write_text("original\n")

        project_list.write_text("hardware/waydroid\nhardware/missing\n")
        assert check(lock, project_list, worktree).splitlines() == [
            "hardware/waydroid", "hardware/missing"
        ]
        project_list.write_text("hardware/unknown\n")
        assert check(lock, project_list, worktree) == "__FULL__"
        project_list.write_text("hardware/waydroid\n")
        real_project = worktree / "real-waydroid"
        project.rename(real_project)
        project.symlink_to(real_project, target_is_directory=True)
        assert "refusing symlinked or escaped project path" in check_failure(
            lock, project_list, worktree
        )
        project_list.unlink()
        assert check(lock, project_list, worktree) == "__FULL__"

    print("checked-out source lock regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
