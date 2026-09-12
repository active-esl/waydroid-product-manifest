#!/usr/bin/env python3
"""Regression tests for the CT101 Android build resource policy."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-lineage-23.2-images.yml"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-images.sh"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def main() -> int:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    build_script = BUILD_SCRIPT.read_text(encoding="utf-8")
    workflow_corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(WORKFLOWS_DIR.glob("*.yml"))
    )

    expected_workflow_lines = (
        "    timeout-minutes: 1440",
        '          JOBS: "6"',
        "          SOONG_GOMEMLIMIT: 28GiB",
        "      - uses: actions/checkout@v7",
        "      - uses: actions/upload-artifact@v7",
    )
    for line in expected_workflow_lines:
        assert workflow.count(line) == 1, f"missing or duplicate workflow policy: {line}"

    assert 'jobs="${JOBS:-6}"' in build_script
    assert '[[ "${jobs}" =~ ^[1-9][0-9]*$ ]]' in build_script
    assert "Target cache before build:" in build_script
    assert "actions/checkout@v4" not in workflow_corpus
    assert "actions/upload-artifact@v4" not in workflow_corpus

    print("Android CI resource-policy regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
