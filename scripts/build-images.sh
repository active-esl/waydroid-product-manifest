#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
android_dir="${ANDROID_WORKSPACE:-/yocto/android-16-source}"
out_dir="${ANDROID_OUT_DIR:-${android_dir}/out}"
artifact_dir="${OUTPUT_DIR:-/yocto/android-16-artifacts/local}"
lock_file="${SOURCE_LOCK:-${repo_root}/locks/lineage-23.2-lock.xml}"
jobs="${JOBS:-8}"
targets=(
    lineage_waydroid_x86_64-bp4a-userdebug
    lineage_waydroid_aesl_2gb_arm64_only-bp4a-userdebug
)

die() { echo "$*" >&2; exit 1; }

run_repo_sync() {
    local sync_jobs="$1" sync_pid

    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.version GIT_CONFIG_VALUE_0=HTTP/1.1 \
        repo sync -c --no-tags --fail-fast --force-checkout -d -j"${sync_jobs}" &
    sync_pid=$!
    while kill -0 "${sync_pid}" 2>/dev/null; do
        for _ in {1..60}; do
            sleep 5
            kill -0 "${sync_pid}" 2>/dev/null || break
        done
        if kill -0 "${sync_pid}" 2>/dev/null; then
            echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) locked repo sync is still active (${sync_jobs} job(s))"
        fi
    done
    wait "${sync_pid}"
}

for command in repo git python3 sha256sum; do
    command -v "${command}" >/dev/null || die "required command missing: ${command}"
done
[[ "${android_dir}" == /yocto/* ]] || die "ANDROID_WORKSPACE must be under /yocto"
[[ "${out_dir}" == "${android_dir}"/* ]] || die "ANDROID_OUT_DIR must be inside ANDROID_WORKSPACE"
[[ "${artifact_dir}" == /yocto/* ]] || die "OUTPUT_DIR must be under /yocto"
[[ -s "${lock_file}" ]] || die "reviewed source lock missing: ${lock_file}"
python3 "${repo_root}/scripts/validate-lock.py" "${lock_file}"

mkdir -p "${android_dir}" "${out_dir}" "${artifact_dir}"
cd "${android_dir}"

# Reset only repo's manifest metadata so a previous bootstrap checkout can be
# converted into the reviewed standalone lock while retaining downloaded Git
# objects on the persistent /yocto volume.
if [[ -d .repo ]]; then
    rm -rf .repo/local_manifests .repo/manifests .repo/manifests.git
    rm -f .repo/manifest.xml
fi
lock_url="$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve().as_uri())' "${lock_file}")"
echo "Initializing repo from the reviewed standalone lock"
echo "repo may warn that the standalone manifest has no Git HEAD; successful initialization is the gate"
repo init -u "${lock_url}" --standalone-manifest --git-lfs

echo "Synchronizing the exact locked source revisions"
sync_jobs="${jobs}"
for attempt in 1 2 3 4; do
    if run_repo_sync "${sync_jobs}"; then
        break
    fi
    [[ "${attempt}" == 4 ]] && die "repo sync failed after four attempts"
    (( sync_jobs > 1 )) && sync_jobs=$((sync_jobs / 2))
    echo "locked repo sync attempt ${attempt} failed; retrying with ${sync_jobs} job(s)" >&2
done

echo "Running the SELinux production gate"
python3 "${android_dir}/vendor/extra/scripts/check-selinux-runtime-gate.py"
echo "Applying the pinned Waydroid patch series"
"${repo_root}/scripts/apply-waydroid-patches-strict.sh" "${android_dir}"

export OUT_DIR="${out_dir}"
unset OUT_DIR_COMMON_BASE
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git -C "${repo_root}" show -s --format=%ct HEAD)}"
# Android's envsetup is not nounset-safe.
set +u
# shellcheck disable=SC1091
source build/envsetup.sh
set -u

for target in "${targets[@]}"; do
    echo "Configuring Android target ${target}"
    set +u
    lunch "${target}"
    set -u
    echo "Building system, vendor and SPDX outputs for ${target}"
    m -j"${jobs}" systemimage vendorimage sbom

    case "${target}" in
        *x86_64*) target_artifacts="${artifact_dir}/x86_64" ;;
        *aesl_2gb_arm64_only*) target_artifacts="${artifact_dir}/imx8mm" ;;
        *) die "unrecognised target: ${target}" ;;
    esac
    mkdir -p "${target_artifacts}"
    install -m 0644 "${OUT}/system.img" "${target_artifacts}/system.img"
    install -m 0644 "${OUT}/vendor.img" "${target_artifacts}/vendor.img"
    [[ -s "${OUT}/sbom.spdx.json" ]] \
        || die "Android SPDX JSON SBOM was not generated for ${target}"
    python3 -m json.tool "${OUT}/sbom.spdx.json" >/dev/null
    install -m 0644 "${OUT}/sbom.spdx.json" "${target_artifacts}/sbom.spdx.json"
    if [[ -s "${OUT}/sbom.spdx" ]]; then
        install -m 0644 "${OUT}/sbom.spdx" "${target_artifacts}/sbom.spdx"
    fi
    find "${OUT}" -maxdepth 1 -type f -name 'installed-files*.txt' \
        -exec install -m 0644 -t "${target_artifacts}" {} +
done

install -m 0644 "${lock_file}" "${artifact_dir}/source-manifest.xml"
python3 "${repo_root}/scripts/write-build-info.py" \
    --output "${artifact_dir}/build-info.json" \
    --source-lock "${lock_file}" \
    --targets "${targets[@]}"
system_sha=$(sha256sum "${artifact_dir}/imx8mm/system.img" | cut -d' ' -f1)
vendor_sha=$(sha256sum "${artifact_dir}/imx8mm/vendor.img" | cut -d' ' -f1)
sbom_sha=$(sha256sum "${artifact_dir}/imx8mm/sbom.spdx.json" | cut -d' ' -f1)
source_manifest_sha=$(sha256sum "${artifact_dir}/source-manifest.xml" | cut -d' ' -f1)
build_info_sha=$(sha256sum "${artifact_dir}/build-info.json" | cut -d' ' -f1)
printf '%s\n' \
    '# Generated by the reviewed AESL Android 16 image build.' \
    "AESL_WAYDROID_SYSTEM_SHA256 = \"${system_sha}\"" \
    "AESL_WAYDROID_VENDOR_SHA256 = \"${vendor_sha}\"" \
    "AESL_WAYDROID_SBOM_SHA256 = \"${sbom_sha}\"" \
    "AESL_WAYDROID_SOURCE_MANIFEST_SHA256 = \"${source_manifest_sha}\"" \
    "AESL_WAYDROID_BUILD_INFO_SHA256 = \"${build_info_sha}\"" \
    > "${artifact_dir}/waydroid-images.inc"
checksum_tmp="$(mktemp /yocto/android-16-artifacts/.checksums.XXXXXX)"
trap 'rm -f "${checksum_tmp}"' EXIT
(
    cd "${artifact_dir}"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "${checksum_tmp}"
)
install -m 0644 "${checksum_tmp}" "${artifact_dir}/SHA256SUMS"
rm -f "${checksum_tmp}"
trap - EXIT
