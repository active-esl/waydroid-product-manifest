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

    release_identity = (
        "name: Build Android R16 / LineageOS 23.2 images",
        "run-name: Android R16 / LineageOS 23.2 - ${{ inputs.build_scope }}",
        "name: Android R16 / LineageOS 23.2 - ${{ inputs.build_scope }}",
        "name: aesl-android-r16-lineage-23.2-${{ github.run_id }}",
    )
    for label in release_identity:
        assert label in workflow, f"missing Android R16 CI identity: {label}"

    assert 'jobs="${JOBS:-6}"' in build_script
    assert '[[ "${jobs}" =~ ^[1-9][0-9]*$ ]]' in build_script
    assert 'if [[ "${arm64_build_variant}" == user ]]; then' in build_script
    assert "imx8mm_build_variant" not in build_script
    assert "Target cache before build:" in build_script
    profile_corpus = build_script + (REPO_ROOT / "scripts/write-build-info.py").read_text(
        encoding="utf-8"
    )
    for profile_contract in (
        "arm64_standard)",
        "arm64_2gb|imx8mm)",
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
    assert "actions/checkout@v4" not in workflow_corpus
    assert "actions/upload-artifact@v4" not in workflow_corpus
    assert "actions/attest@v4" not in workflow_corpus
    assert "actions/checkout@v7" not in workflow_corpus
    assert "actions/upload-artifact@v7" not in workflow_corpus

    print("Android CI resource-policy regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
