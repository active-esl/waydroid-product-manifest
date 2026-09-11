#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
android_dir="${ANDROID_WORKSPACE:-/yocto/android-16-source}"
out_dir="${ANDROID_OUT_DIR:-${android_dir}/out}"
imx8mm_out_dir="${ANDROID_IMX8MM_OUT_DIR:-${android_dir}/out-imx8mm}"
artifact_dir="${OUTPUT_DIR:-/yocto/android-16-artifacts/local}"
manifest_cache_dir="${ANDROID_MANIFEST_CACHE_DIR:-/yocto/android-16-manifests}"
lock_file="${SOURCE_LOCK:-${repo_root}/locks/lineage-23.2-lock.xml}"
source_date_epoch_file="${SOURCE_DATE_EPOCH_FILE:-${repo_root}/locks/lineage-23.2-source-date-epoch}"
jobs="${JOBS:-8}"
meson_version="1.7.2"
meson_sha256="82c6818dc81743c96de3a458f06175776ebfde4081195ea31ea6971838f25e38"
meson_url="https://files.pythonhosted.org/packages/e5/2b/46bda4ef5a7ae4135dbfe27fc0368c44e5a349a897a54fdf2cedb8dcb66e/meson-1.7.2-py3-none-any.whl"
meson_tool_dir="/yocto/android-ci-tools/meson-${meson_version}"
imx8mm_build_variant="${IMX8MM_BUILD_VARIANT:-userdebug}"
build_scope="${BUILD_SCOPE:-all}"
force_full_sync="${FORCE_FULL_SYNC:-false}"
case "${imx8mm_build_variant}" in
    user|userdebug) ;;
    *) echo "IMX8MM_BUILD_VARIANT must be user or userdebug" >&2; exit 1 ;;
esac
case "${build_scope}" in
    all)
        targets=(
            lineage_waydroid_x86_64-bp4a-userdebug
            "lineage_waydroid_aesl_2gb_arm64_only-bp4a-${imx8mm_build_variant}"
        )
        ;;
    x86_64)
        targets=(lineage_waydroid_x86_64-bp4a-userdebug)
        ;;
    imx8mm)
        targets=("lineage_waydroid_aesl_2gb_arm64_only-bp4a-${imx8mm_build_variant}")
        ;;
    *) echo "BUILD_SCOPE must be all, x86_64 or imx8mm" >&2; exit 1 ;;
esac

die() { echo "$*" >&2; exit 1; }

prepare_pinned_meson() {
    local cargo_meson module_version pinned_meson_pth resolved_version temporary_dir user_site wheel

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

    # Mesa's Android build rule constructs its own PATH with ~/.cargo/bin
    # before /usr/bin and the inherited job PATH. Put the reviewed wrapper at
    # that first lookup location so nested Meson invocations cannot fall back
    # to the runner's older distro package.
    cargo_meson="${HOME:?HOME is not set}/.cargo/bin/meson"
    mkdir -p "$(dirname "${cargo_meson}")"
    install -m 0755 "${repo_root}/scripts/pinned-tools/meson" "${cargo_meson}"
    resolved_version="$(env -u AESL_MESON_SITE \
        PATH="${HOME}/.cargo/bin:/usr/bin:/usr/local/bin:${PATH}" meson --version)"
    [[ "${resolved_version}" == "${meson_version}" ]] \
        || die "Mesa nested PATH Meson preflight failed: expected ${meson_version}, got ${resolved_version}"

    # Meson's generated build.ninja does not call the wrapper for installation;
    # it records `/usr/bin/python3 -m mesonbuild.mesonmain`. Add the reviewed
    # package directory to Python's user site so that later sanitized command
    # resolves the same Meson version that generated meson-private/install.dat.
    user_site="$(/usr/bin/python3 -m site --user-site)"
    mkdir -p "${user_site}"
    pinned_meson_pth="${user_site}/aesl-pinned-meson.pth"
    printf '%s\n' "${meson_tool_dir}/site" > "${pinned_meson_pth}"
    module_version="$(env -u AESL_MESON_SITE -u PYTHONPATH \
        PATH="/usr/bin:/bin:/sbin:${PATH}" \
        /usr/bin/python3 -m mesonbuild.mesonmain --version)"
    [[ "${module_version}" == "${meson_version}" ]] \
        || die "Mesa install Python-module preflight failed: expected ${meson_version}, got ${module_version}"
    echo "Pinned Meson preflight passed for wrapper and install module: ${resolved_version}"
}

run_repo_sync() {
    local sync_jobs="$1" sync_pid sync_status
    shift

    setsid env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.version GIT_CONFIG_VALUE_0=HTTP/1.1 \
        repo sync -c --no-tags --fail-fast --force-checkout --force-sync -d -j"${sync_jobs}" "$@" &
    sync_pid=$!
    trap 'kill -TERM -- "-${sync_pid}" 2>/dev/null || true' INT TERM
    while kill -0 "${sync_pid}" 2>/dev/null; do
        for _ in {1..60}; do
            sleep 5
            kill -0 "${sync_pid}" 2>/dev/null || break
        done
        if kill -0 "${sync_pid}" 2>/dev/null; then
            echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) locked repo sync is still active (${sync_jobs} job(s))"
        fi
    done
    if wait "${sync_pid}"; then sync_status=0; else sync_status=$?; fi
    trap - INT TERM
    return "${sync_status}"
}

run_with_heartbeat() {
    local stage="$1" build_pid build_status started_at
    shift

    started_at="${SECONDS}"
    setsid "$@" &
    build_pid=$!
    trap 'kill -TERM -- "-${build_pid}" 2>/dev/null || true' INT TERM
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
    if wait "${build_pid}"; then build_status=0; else build_status=$?; fi
    trap - INT TERM
    return "${build_status}"
}

sync_locked_sources() {
    local attempt sync_jobs="${jobs}"
    local -a projects=("$@")

    if run_repo_sync "${sync_jobs}" --local-only "${projects[@]}"; then
        return 0
    fi
    echo "Local object cache is incomplete; fetching only missing locked revisions"
    for attempt in 1 2 3 4; do
        if run_repo_sync "${sync_jobs}" "${projects[@]}"; then
            return 0
        fi
        [[ "${attempt}" == 4 ]] && die "repo sync failed after four attempts"
        (( sync_jobs > 1 )) && sync_jobs=$((sync_jobs / 2))
        echo "locked repo sync attempt ${attempt} failed; retrying with ${sync_jobs} job(s)" >&2
    done
}

for command in repo git python3 sha256sum timeout ps; do
    command -v "${command}" >/dev/null || die "required command missing: ${command}"
done
[[ "${android_dir}" == /yocto/* ]] || die "ANDROID_WORKSPACE must be under /yocto"
[[ "${out_dir}" == "${android_dir}"/* ]] || die "ANDROID_OUT_DIR must be inside ANDROID_WORKSPACE"
[[ "${imx8mm_out_dir}" == "${android_dir}"/* ]] \
    || die "ANDROID_IMX8MM_OUT_DIR must be inside ANDROID_WORKSPACE"
[[ "${artifact_dir}" == /yocto/* ]] || die "OUTPUT_DIR must be under /yocto"
[[ "${manifest_cache_dir}" == /yocto/* ]] || die "ANDROID_MANIFEST_CACHE_DIR must be under /yocto"
[[ -s "${lock_file}" ]] || die "reviewed source lock missing: ${lock_file}"
[[ -s "${source_date_epoch_file}" ]] || die "stable source-date epoch missing: ${source_date_epoch_file}"
python3 "${repo_root}/scripts/validate-lock.py" "${lock_file}"

mkdir -p "${android_dir}" "${out_dir}" "${imx8mm_out_dir}" "${artifact_dir}" "${manifest_cache_dir}"
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

previous_lock="${android_dir}/.repo/aesl-source-lock.xml"
full_sync=false
changed_projects=()
if [[ "${force_full_sync}" == true || "${force_full_sync}" == 1 ]]; then
    echo "A complete source resynchronization was explicitly requested"
    full_sync=true
elif [[ "${cached_lock}" == "${lock_sha}" ]]; then
    echo "Source worktree already matches the immutable lock; skipping repo sync"
elif [[ -s "${previous_lock}" ]]; then
    mapfile -t changed_projects \
        < <(python3 "${repo_root}/scripts/lock-delta.py" "${previous_lock}" "${lock_file}")
    if [[ "${changed_projects[0]:-}" == __FULL__ ]]; then
        full_sync=true
        changed_projects=()
    fi
else
    full_sync=true
fi

if [[ "${full_sync}" == true ]]; then
    echo "Restoring the complete locked source tree from the /yocto object cache"
    sync_locked_sources
elif (( ${#changed_projects[@]} > 0 )); then
    echo "Synchronizing ${#changed_projects[@]} project(s) changed by the immutable lock"
    printf '  %s\n' "${changed_projects[@]}"
    sync_locked_sources "${changed_projects[@]}"
else
    echo "No project revisions changed; preserving the incremental source worktree"
fi
printf '%s\n' "${lock_sha}" > .repo/aesl-source-lock.sha256
install -m 0644 "${lock_file}" "${previous_lock}"

if [[ "${imx8mm_build_variant}" == user ]]; then
    echo "Running the SELinux production gate"
    python3 "${android_dir}/vendor/extra/scripts/check-selinux-runtime-gate.py" --production
else
    echo "Inventorying the open SELinux runtime exception for integration output"
    python3 "${android_dir}/vendor/extra/scripts/check-selinux-runtime-gate.py"
fi
echo "Applying the pinned Waydroid patch series"
patch_root="${android_dir}/vendor/extra/waydroid-patches/base-patches-36"
patch_state_dir="${android_dir}/.repo/aesl-patch-state"
patch_projects_file="${android_dir}/.repo/aesl-patch-projects"
mkdir -p "${patch_state_dir}"
mapfile -t patch_states \
    < <(python3 "${repo_root}/scripts/patch-state.py" "${lock_file}" "${patch_root}")
declare -A desired_patch_projects=()
declare -A synchronized_projects=()
for changed_project in "${changed_projects[@]}"; do
    synchronized_projects["${changed_project}"]=1
done
for patch_state in "${patch_states[@]}"; do
    IFS=$'\t' read -r patch_project patch_digest <<< "${patch_state}"
    desired_patch_projects["${patch_project}"]=1
    patch_marker="${patch_state_dir}/${patch_project}.sha256"
    applied_digest="$(cat "${patch_marker}" 2>/dev/null || true)"
    if [[ -n "${applied_digest}" && "${applied_digest}" != "${patch_digest}" ]]; then
        if [[ "${full_sync}" != true && -z "${synchronized_projects[$patch_project]:-}" ]]; then
            echo "Patch state changed for ${patch_project}; restoring its exact locked base"
            sync_locked_sources "${patch_project}"
        fi
    fi
done
if [[ -s "${patch_projects_file}" ]]; then
    while IFS= read -r previous_patch_project; do
        [[ -n "${previous_patch_project}" ]] || continue
        if [[ -z "${desired_patch_projects[$previous_patch_project]:-}" ]]; then
            echo "Patch series was removed for ${previous_patch_project}; restoring its locked base"
            sync_locked_sources "${previous_patch_project}"
        fi
    done < "${patch_projects_file}"
fi
run_with_heartbeat "Waydroid patch application" \
    timeout --foreground --kill-after=60s 30m \
    "${repo_root}/scripts/apply-waydroid-patches-strict.sh" "${android_dir}"
for patch_state in "${patch_states[@]}"; do
    IFS=$'\t' read -r patch_project patch_digest <<< "${patch_state}"
    patch_marker="${patch_state_dir}/${patch_project}.sha256"
    mkdir -p "$(dirname "${patch_marker}")"
    printf '%s\n' "${patch_digest}" > "${patch_marker}"
done
printf '%s\n' "${!desired_patch_projects[@]}" | sort > "${patch_projects_file}"

unset OUT_DIR_COMMON_BASE
if [[ -z "${SOURCE_DATE_EPOCH:-}" ]]; then
    source_epoch="$(tr -d '[:space:]' < "${source_date_epoch_file}")"
    [[ "${source_epoch}" =~ ^[0-9]+$ ]] \
        || die "invalid stable SOURCE_DATE_EPOCH: ${source_date_epoch_file}"
    export SOURCE_DATE_EPOCH="${source_epoch}"
else
    export SOURCE_DATE_EPOCH
fi
# Android's envsetup is not nounset-safe.
set +u
# shellcheck disable=SC1091
source build/envsetup.sh
set -u

for target in "${targets[@]}"; do
    case "${target}" in
        *x86_64*)
            target_out_dir="${out_dir}"
            target_artifacts="${artifact_dir}/x86_64"
            ;;
        *aesl_2gb_arm64_only*)
            target_out_dir="${imx8mm_out_dir}"
            target_artifacts="${artifact_dir}/imx8mm"
            ;;
        *) die "unrecognised target: ${target}" ;;
    esac
    # Soong identifies host outputs by their leading out/ component. Keep the
    # target-specific path relative to TOP while its physical location remains
    # under /yocto/android-16-source.
    export OUT_DIR="${target_out_dir#"${android_dir}/"}"
    echo "Configuring Android target ${target}"
    set +u
    lunch "${target}"
    set -u
    echo "Building system, vendor and SPDX outputs for ${target}"
    run_with_heartbeat "Android image build ${target}" \
        m -j"${jobs}" systemimage vendorimage sbom

    mkdir -p "${target_artifacts}"
    install -m 0644 "${OUT}/system.img" "${target_artifacts}/system.img"
    install -m 0644 "${OUT}/vendor.img" "${target_artifacts}/vendor.img"
    sbom_dir="${target_out_dir}/soong/sbom/${TARGET_PRODUCT:?TARGET_PRODUCT is not set}"
    [[ -s "${sbom_dir}/sbom.spdx.json" ]] \
        || die "Android SPDX JSON SBOM was not generated for ${target}"
    python3 -m json.tool "${sbom_dir}/sbom.spdx.json" >/dev/null
    install -m 0644 "${sbom_dir}/sbom.spdx.json" "${target_artifacts}/sbom.spdx.json"
    if [[ -s "${sbom_dir}/sbom.spdx" ]]; then
        install -m 0644 "${sbom_dir}/sbom.spdx" "${target_artifacts}/sbom.spdx"
    fi
    if [[ -s "${sbom_dir}/sbom-gen-report.txt" ]]; then
        install -m 0644 "${sbom_dir}/sbom-gen-report.txt" "${target_artifacts}/sbom-gen-report.txt"
    fi
    for partition in system vendor; do
        notice="${OUT}/${partition}/etc/NOTICE.xml.gz"
        [[ -s "${notice}" ]] \
            || die "Android ${partition} NOTICE archive was not generated for ${target}"
        install -m 0644 "${notice}" "${target_artifacts}/NOTICE-${partition}.xml.gz"
    done
    find "${OUT}" -maxdepth 1 -type f -name 'installed-files*.txt' \
        -exec install -m 0644 -t "${target_artifacts}" {} +
done

install -m 0644 "${lock_file}" "${artifact_dir}/source-manifest.xml"
python3 "${repo_root}/scripts/write-build-info.py" \
    --output "${artifact_dir}/build-info.json" \
    --source-lock "${lock_file}" \
    --imx8mm-variant "${imx8mm_build_variant}" \
    --targets "${targets[@]}"
if [[ -d "${artifact_dir}/imx8mm" ]]; then
    system_sha=$(sha256sum "${artifact_dir}/imx8mm/system.img" | cut -d' ' -f1)
    vendor_sha=$(sha256sum "${artifact_dir}/imx8mm/vendor.img" | cut -d' ' -f1)
    sbom_sha=$(sha256sum "${artifact_dir}/imx8mm/sbom.spdx.json" | cut -d' ' -f1)
    system_notice_sha=$(sha256sum "${artifact_dir}/imx8mm/NOTICE-system.xml.gz" | cut -d' ' -f1)
    vendor_notice_sha=$(sha256sum "${artifact_dir}/imx8mm/NOTICE-vendor.xml.gz" | cut -d' ' -f1)
    source_manifest_sha=$(sha256sum "${artifact_dir}/source-manifest.xml" | cut -d' ' -f1)
    build_info_sha=$(sha256sum "${artifact_dir}/build-info.json" | cut -d' ' -f1)
    printf '%s\n' \
        '# Generated by the reviewed AESL Android 16 image build.' \
        "AESL_WAYDROID_SYSTEM_SHA256 = \"${system_sha}\"" \
        "AESL_WAYDROID_VENDOR_SHA256 = \"${vendor_sha}\"" \
        "AESL_WAYDROID_SBOM_SHA256 = \"${sbom_sha}\"" \
        "AESL_WAYDROID_SYSTEM_NOTICE_SHA256 = \"${system_notice_sha}\"" \
        "AESL_WAYDROID_VENDOR_NOTICE_SHA256 = \"${vendor_notice_sha}\"" \
        "AESL_WAYDROID_SOURCE_MANIFEST_SHA256 = \"${source_manifest_sha}\"" \
        "AESL_WAYDROID_BUILD_INFO_SHA256 = \"${build_info_sha}\"" \
        > "${artifact_dir}/waydroid-images.inc"
fi
checksum_tmp="$(mktemp /yocto/android-16-artifacts/.checksums.XXXXXX)"
trap 'rm -f "${checksum_tmp}"' EXIT
(
    cd "${artifact_dir}"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "${checksum_tmp}"
)
install -m 0644 "${checksum_tmp}" "${artifact_dir}/SHA256SUMS"
rm -f "${checksum_tmp}"
trap - EXIT
