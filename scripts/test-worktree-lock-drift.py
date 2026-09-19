#!/usr/bin/env python3
"""Regression tests for checked-out HEAD verification before Android builds."""

from __future__ import annotations

import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


CHECKER = Path(__file__).with_name("worktree-lock-drift.py")
CLEANER = Path(__file__).with_name("clean-worktree-residue.py")
AUTHORIZED_ENV = {
    "AESL_ALLOW_LOCKED_SOURCE_CLEANUP": "true",
    "GITHUB_ACTIONS": "true",
    "RUNNER_NAME": "esl-proxmox-runner",
}


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


def check_authorized(lock: Path, project_list: Path, worktree: Path) -> str:
    result = subprocess.run(
        ["python3", str(CHECKER), str(lock), str(project_list), str(worktree)],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **AUTHORIZED_ENV},
    )
    assert result.returncode == 0, result.stderr
    assert "Tracked source changes scheduled for locked resync" in result.stderr
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


def clean(worktree: Path, *projects: str) -> None:
    subprocess.run(
        ["python3", str(CLEANER), str(worktree), *projects],
        check=True,
        env={**os.environ, **AUTHORIZED_ENV},
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        worktree = Path(temp_dir)
        project = worktree / "hardware" / "waydroid"
        project.mkdir(parents=True)
        git("-C", str(project), "init", "-q")
        git("-C", str(project), "config", "commit.gpgsign", "false")
        (project / "tracked.txt").write_text("original\n")
        (project / ".gitignore").write_text("ignored.txt\n")
        git("-C", str(project), "add", "tracked.txt", ".gitignore")
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
        assert "cannot resync project with tracked local changes" in check_failure(
            lock, project_list, worktree
        )
        assert check_authorized(lock, project_list, worktree) == "hardware/waydroid"
        (project / "tracked.txt").write_text("original\n")
        (project / "untracked.txt").write_text("must not enter a locked build\n")
        assert check(lock, project_list, worktree) == "hardware/waydroid"
        (project / "ignored.txt").write_text("must not enter a locked build\n")
        assert check(lock, project_list, worktree) == "hardware/waydroid"
        refused = subprocess.run(
            ["python3", str(CLEANER), str(worktree), "hardware/waydroid"],
            capture_output=True, text=True, check=False,
            env={**os.environ, "AESL_ALLOW_LOCKED_SOURCE_CLEANUP": "true"},
        )
        assert refused.returncode == 2
        assert "refusing cleanup outside the authorized AESL CI runner" in refused.stderr
        assert (project / "untracked.txt").exists()
        assert (project / "ignored.txt").exists()
        clean(worktree, "hardware/waydroid")
        assert not (project / "untracked.txt").exists()
        assert not (project / "ignored.txt").exists()
        assert check(lock, project_list, worktree) == ""
        result = subprocess.run(
            ["python3", str(CLEANER), str(worktree), "."],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 2
        assert "refusing unsafe project path" in result.stderr

        temporarily_missing = worktree / "temporarily-missing-waydroid"
        project.rename(temporarily_missing)
        assert check(lock, project_list, worktree) == "hardware/waydroid"
        clean(worktree, "hardware/waydroid")
        temporarily_missing.rename(project)
        assert check(lock, project_list, worktree) == ""

        (project / "tracked.txt").write_text("replacement content\n")
        git("-C", str(project), "add", "tracked.txt")
        git("-C", str(project), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-q", "-m", "replacement")
        replacement_head = git("-C", str(project), "rev-parse", "HEAD")
        git("-C", str(project), "reset", "-q", "--hard", locked_head)
        git("-C", str(project), "replace", locked_head, replacement_head)
        assert "replacement refs are not allowed" in check_failure(
            lock, project_list, worktree
        )
        git("-C", str(project), "replace", "-d", locked_head)

        git("-C", str(project), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-q", "--allow-empty", "-m", "drifted")
        assert check(lock, project_list, worktree) == "hardware/waydroid"
        (project / "tracked.txt").write_text("local edit\n")
        assert "cannot resync project with tracked local changes" in check_failure(
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
        project.unlink()
        project.mkdir()
        assert "refusing non-Git project path" in check_failure(
            lock, project_list, worktree
        )
        project.rmdir()
        real_project.rename(project)
        project_list.unlink()
        assert check(lock, project_list, worktree) == "__FULL__"

    print("checked-out source lock regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
