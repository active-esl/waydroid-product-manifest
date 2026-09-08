#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
android_dir="${ANDROID_WORKSPACE:-/yocto/android-16-source}"
out_dir="${ANDROID_OUT_DIR:-${android_dir}/out}"
artifact_dir="${OUTPUT_DIR:-/yocto/android-16-artifacts/local}"
manifest_cache_dir="${ANDROID_MANIFEST_CACHE_DIR:-/yocto/android-16-manifests}"
lock_file="${SOURCE_LOCK:-${repo_root}/locks/lineage-23.2-lock.xml}"
jobs="${JOBS:-8}"
meson_version="1.7.2"
meson_sha256="82c6818dc81743c96de3a458f06175776ebfde4081195ea31ea6971838f25e38"
meson_url="https://files.pythonhosted.org/packages/e5/2b/46bda4ef5a7ae4135dbfe27fc0368c44e5a349a897a54fdf2cedb8dcb66e/meson-1.7.2-py3-none-any.whl"
meson_tool_dir="/yocto/android-ci-tools/meson-${meson_version}"
targets=(
    lineage_waydroid_x86_64-bp4a-userdebug
    lineage_waydroid_aesl_2gb_arm64_only-bp4a-userdebug
)

die() { echo "$*" >&2; exit 1; }

prepare_pinned_meson() {
    local wheel temporary_dir

    if [[ ! -f "${meson_tool_dir}/site/mesonbuild/mesonmain.py" ]]; then
        echo "Installing pinned Meson ${meson_version} in the persistent /yocto tool cache"
        mkdir -p /yocto/android-ci-tools
        temporary_dir="$(mktemp -d /yocto/android-ci-tools/.meson-${meson_version}.XXXXXX)"
        trap 'rm -rf -- "${temporary_dir}"' RETURN
        wheel="${temporary_dir}/meson-${meson_version}-py3-none-any.whl"
        python3 - "${meson_url}" "${wheel}" <<'PY'
import pathlib
import sys
import urllib.request

url, destination = sys.argv[1:]
urllib.request.urlretrieve(url, pathlib.Path(destination))
PY
        echo "${meson_sha256}  ${wheel}" | sha256sum --check --strict
        mkdir -p "${temporary_dir}/site"
        python3 -m zipfile -e "${wheel}" "${temporary_dir}/site"
        rm -f "${wheel}"
        mv -- "${temporary_dir}" "${meson_tool_dir}"
        trap - RETURN
    fi

    export AESL_MESON_SITE="${meson_tool_dir}/site"
    export PATH="${repo_root}/scripts/pinned-tools:${PATH}"
    [[ "$(meson --version)" == "${meson_version}" ]] \
        || die "pinned Meson preflight failed: expected ${meson_version}, got $(meson --version 2>&1)"
    echo "Pinned Meson preflight passed: $(meson --version)"
}

run_repo_sync() {
    local sync_jobs="$1" sync_pid
    shift

    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.version GIT_CONFIG_VALUE_0=HTTP/1.1 \
        repo sync -c --no-tags --fail-fast --force-checkout -d -j"${sync_jobs}" "$@" &
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

run_with_heartbeat() {
    local stage="$1" build_pid started_at
    shift

    started_at="${SECONDS}"
    "$@" &
    build_pid=$!
    while kill -0 "${build_pid}" 2>/dev/null; do
        for _ in {1..60}; do
            sleep 5
            kill -0 "${build_pid}" 2>/dev/null || break
        done
        if kill -0 "${build_pid}" 2>/dev/null; then
            echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Android CI stage is active: ${stage}; elapsed $(((SECONDS - started_at) / 60)) minute(s)"
            ps -o pid=,etime=,%cpu=,%mem= -p "${build_pid}" || true
        fi
    done
    wait "${build_pid}"
}

for command in repo git python3 sha256sum timeout ps; do
    command -v "${command}" >/dev/null || die "required command missing: ${command}"
done
[[ "${android_dir}" == /yocto/* ]] || die "ANDROID_WORKSPACE must be under /yocto"
[[ "${out_dir}" == "${android_dir}"/* ]] || die "ANDROID_OUT_DIR must be inside ANDROID_WORKSPACE"
out_dir_relative="${out_dir#"${android_dir}/"}"
[[ "${artifact_dir}" == /yocto/* ]] || die "OUTPUT_DIR must be under /yocto"
[[ "${manifest_cache_dir}" == /yocto/* ]] || die "ANDROID_MANIFEST_CACHE_DIR must be under /yocto"
[[ -s "${lock_file}" ]] || die "reviewed source lock missing: ${lock_file}"
python3 "${repo_root}/scripts/validate-lock.py" "${lock_file}"

mkdir -p "${android_dir}" "${out_dir}" "${artifact_dir}" "${manifest_cache_dir}"
prepare_pinned_meson
lock_sha="$(sha256sum "${lock_file}" | cut -d' ' -f1)"
manifest_repo="${manifest_cache_dir}/${lock_sha}"
if ! git -C "${manifest_repo}" rev-parse --verify HEAD >/dev/null 2>&1; then
    if [[ -e "${manifest_repo}" ]]; then
        quarantine="${manifest_repo}.invalid.$(date -u +%s)"
        echo "Quarantining incomplete cached manifest repository: ${quarantine}" >&2
        mv -- "${manifest_repo}" "${quarantine}"
    fi
    mkdir -p "${manifest_repo}"
    git -C "${manifest_repo}" init -q -b locked
    install -m 0644 "${lock_file}" "${manifest_repo}/default.xml"
    git -C "${manifest_repo}" add default.xml
    git -C "${manifest_repo}" \
        -c user.name='AESL Android CI' -c user.email='ci@active-esl.invalid' \
        commit -q -m "Android source lock ${lock_sha}"
fi
echo "${lock_sha}  ${manifest_repo}/default.xml" | sha256sum --check --strict
manifest_url="$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve().as_uri())' "${manifest_repo}")"

cd "${android_dir}"

cached_lock="$(cat .repo/aesl-source-lock.sha256 2>/dev/null || true)"
cached_manifest_url="$(git --git-dir=.repo/manifests.git config --get remote.origin.url 2>/dev/null || true)"
if [[ "${cached_lock}" == "${lock_sha}" && "${cached_manifest_url}" == "${manifest_url}" ]]; then
    echo "Reusing cached repo initialization for source lock ${lock_sha}"
else
    echo "Activating Git-backed source lock ${lock_sha}"
    repo init -u "${manifest_url}" -b locked -m default.xml --git-lfs
fi

echo "Restoring exact locked revisions from the local /yocto object cache"
if ! run_repo_sync "${jobs}" --local-only; then
    echo "Local object cache is incomplete; fetching only missing locked revisions"
    sync_jobs="${jobs}"
    for attempt in 1 2 3 4; do
        if run_repo_sync "${sync_jobs}"; then
            break
        fi
        [[ "${attempt}" == 4 ]] && die "repo sync failed after four attempts"
        (( sync_jobs > 1 )) && sync_jobs=$((sync_jobs / 2))
        echo "locked repo sync attempt ${attempt} failed; retrying with ${sync_jobs} job(s)" >&2
    done
fi
printf '%s\n' "${lock_sha}" > .repo/aesl-source-lock.sha256

echo "Running the SELinux production gate"
python3 "${android_dir}/vendor/extra/scripts/check-selinux-runtime-gate.py"
echo "Applying the pinned Waydroid patch series"
run_with_heartbeat "Waydroid patch application" \
    timeout --foreground --kill-after=60s 30m \
    "${repo_root}/scripts/apply-waydroid-patches-strict.sh" "${android_dir}"

# Some Android 16 Soong modules identify host outputs by their leading
# "out/" component. Keep this path relative to TOP while its validated
# physical location remains under /yocto/android-16-source.
export OUT_DIR="${out_dir_relative}"
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
    run_with_heartbeat "Android image build ${target}" \
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
