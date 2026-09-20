#!/usr/bin/env python3
"""Regression tests for the CT101 Android build resource policy."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


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
        '          AESL_ALLOW_LOCKED_SOURCE_CLEANUP: "true"',
        "          SOONG_GOMEMLIMIT: 28GiB",
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7",
        "      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7",
        "  id-token: write",
        "  attestations: write",
        "        uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4",
        "          subject-checksums: /yocto/android-16-artifacts/${{ github.run_id }}-${{ github.run_attempt }}/SHA256SUMS",
        '          ATTESTATION_BUNDLE: ${{ steps.attest-provenance.outputs.bundle-path }}',
        '"${OUTPUT_DIR}/provenance.sigstore.json"',
    )
    for line in expected_workflow_lines:
        assert workflow.count(line) == 1, f"missing or duplicate workflow policy: {line}"

    assert "name: Build Android R16 / LineageOS 23.2 images" in workflow
    run_name = next(line for line in workflow.splitlines() if line.startswith("run-name: "))
    job_name = next(
        line for line in workflow.splitlines()
        if line.startswith("    name: Android R16 / LineageOS 23.2 - ")
    )
    artifact_name = next(
        line for line in workflow.splitlines()
        if line.startswith("          name: aesl-android-r16-")
    )
    for label in (run_name, job_name):
        for target_name in (
            "Jaguar Screen i.MX8MM 2 GB",
            "Generic ARM64 standard baseline",
            "FRDM i.MX95 standard vendor",
            "Framework x86_64",
            "Framework x86_64 2 GB",
            "multiple targets (x86_64 + ARM64 standard + ARM64 2 GB)",
        ):
            assert target_name in label, f"missing Android R16 target identity: {target_name}"
    for target_slug in (
        "imx8mm-jaguar-screen-2gb",
        "generic-arm64-standard-baseline",
        "frdm-imx95-standard-vendor",
        "framework-x86_64",
        "framework-x86_64-2gb",
        "multiple-targets-x86_64-arm64-standard-2gb",
    ):
        assert target_slug in artifact_name, f"missing artifact target identity: {target_slug}"
    for label in (run_name, job_name, artifact_name):
        assert "inputs.build_scope == 'imx95_frdm'" in label, (
            "i.MX95 identity must be selected by its own build scope"
        )

    assert 'jobs="${JOBS:-6}"' in build_script
    assert '[[ "${jobs}" =~ ^[1-9][0-9]*$ ]]' in build_script
    # The expensive build must stop at the first failed command/target, while
    # the following failure-only advisory step remains able to reduce evidence.
    assert build_script.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert "--fail-fast" in build_script
    assert "          set -o pipefail" in workflow
    assert "steps.build-images.outcome == 'failure'" in workflow
    registration_step = "      - name: Register exact FRDM run continuation before long work"
    regression_step = "      - name: Regression-test source lock validation"
    assert workflow.count(registration_step) == 1
    assert workflow.index(registration_step) < workflow.index(regression_step), (
        "FRDM continuation registration must fail closed before long build work"
    )
    assert "        if: ${{ inputs.build_scope == 'imx95_frdm' }}" in workflow
    assert "inputs.continuation_thread_id != ''" not in workflow
    assert '            --thread-id "${{ inputs.continuation_thread_id }}"' in workflow
    assert 'if [[ "${arm64_build_variant}" == user ]]; then' in build_script
    assert "imx8mm_build_variant" not in build_script
    assert "Target cache before build:" in build_script
    assert 'if [[ "${build_scope}" == imx95_frdm && -d "${artifact_dir}/imx95_frdm" ]]; then' in build_script
    assert 'board_profile=generic_arm64' in build_script
    assert 'board_profile=imx8mm' in build_script
    assert 'board_profile=imx95_frdm' in build_script
    assert '"AESL_WAYDROID_BOARD_PROFILE = \\"${board_profile}\\""' in build_script
    for source_integrity_gate in (
        'cached_project_list_sha="$(cat .repo/aesl-project-list.sha256',
        '"${cached_project_list_sha}" == "${project_list_sha}"',
        'clean_project_residue "${full_sync_projects[@]}"',
        'sha256sum .repo/project.list',
        'remaining_drift="$(python3 "${repo_root}/scripts/worktree-lock-drift.py"',
    ):
        assert source_integrity_gate in build_script, (
            f"missing persistent-worktree integrity gate: {source_integrity_gate}"
        )
    for image_gate in (
        'validate_raw_android_image "${target_artifacts}/system.img"',
        'validate_raw_android_image "${target_artifacts}/vendor.img"',
        'e2fsck -fn "${image}"',
        'image is Android sparse; raw ext4 is required',
        '[[ "${logical_size}" -eq "${required_size}" ]]',
    ):
        assert image_gate in build_script, f"missing Android image integrity gate: {image_gate}"
    profile_corpus = build_script + (REPO_ROOT / "scripts/write-build-info.py").read_text(
        encoding="utf-8"
    )
    assert '"generic_arm64"' in profile_corpus
    assert "imx8mm-standard-candidate" not in workflow
    assert "i.MX8MM standard vendor candidate" not in workflow
    for profile_contract in (
        "arm64_standard)",
        "arm64_2gb|imx8mm)",
        "imx95_frdm)",
        "lineage_waydroid_aesl_imx95_arm64_only-bp4a-",
        'target_artifacts="${artifact_dir}/imx95_frdm"',
        "ANDROID_IMX95_OUT_DIR",
        "lineage_waydroid_arm64_only-bp4a-",
        "lineage_waydroid_aesl_2gb_arm64_only-bp4a-",
        "ANDROID_ARM64_STANDARD_OUT_DIR",
        "ANDROID_ARM64_2GB_OUT_DIR",
        '\"android_release\": \"r16\"',
        '\"maintenance_class\": \"maintained-5-plus-years\"',
    ):
        assert profile_contract in profile_corpus, (
            f"missing Android R16 product-profile contract: {profile_contract}"
        )
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "build-info.json"
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/write-build-info.py"),
                "--output", str(output),
                "--source-lock", str(REPO_ROOT / "locks/lineage-23.2-lock.xml"),
                "--arm64-variant", "userdebug",
                "--targets",
                "lineage_waydroid_arm64_only-bp4a-userdebug",
                "lineage_waydroid_aesl_2gb_arm64_only-bp4a-userdebug",
                "lineage_waydroid_aesl_imx95_arm64_only-bp4a-userdebug",
            ],
            check=True,
            env={**os.environ, "SOURCE_DATE_EPOCH": "1234567890"},
        )
        profiles = json.loads(output.read_text(encoding="utf-8"))["product_profiles"]
        assert [(profile["memory_profile"], profile["board_profile"]) for profile in profiles] == [
            ("standard", "generic_arm64"),
            ("2gb", "imx8mm"),
            ("standard", "imx95_frdm"),
        ]
    assert "actions/checkout@v4" not in workflow_corpus
    assert "actions/upload-artifact@v4" not in workflow_corpus
    assert "actions/attest@v4" not in workflow_corpus
    assert "actions/checkout@v7" not in workflow_corpus
    assert "actions/upload-artifact@v7" not in workflow_corpus

    print("Android CI resource-policy regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
