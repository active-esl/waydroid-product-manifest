#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
android_dir="${ANDROID_WORKSPACE:-/yocto/android-16-source}"
x86_64_out_dir="${ANDROID_X86_64_OUT_DIR:-${android_dir}/out-x86_64}"
x86_64_2gb_out_dir="${ANDROID_X86_64_2GB_OUT_DIR:-${android_dir}/out-x86_64-2gb}"
arm64_standard_out_dir="${ANDROID_ARM64_STANDARD_OUT_DIR:-${android_dir}/out-arm64-standard}"
arm64_2gb_out_dir="${ANDROID_ARM64_2GB_OUT_DIR:-${ANDROID_IMX8MM_OUT_DIR:-${android_dir}/out-arm64-2gb}}"
imx95_out_dir="${ANDROID_IMX95_OUT_DIR:-${android_dir}/out-imx95-frdm}"
artifact_dir="${OUTPUT_DIR:-/yocto/android-16-artifacts/local}"
manifest_cache_dir="${ANDROID_MANIFEST_CACHE_DIR:-/yocto/android-16-manifests}"
lock_file="${SOURCE_LOCK:-${repo_root}/locks/lineage-23.2-lock.xml}"
source_date_epoch_file="${SOURCE_DATE_EPOCH_FILE:-${repo_root}/locks/lineage-23.2-source-date-epoch}"
jobs="${JOBS:-6}"
meson_version="1.7.2"
meson_sha256="82c6818dc81743c96de3a458f06175776ebfde4081195ea31ea6971838f25e38"
meson_url="https://files.pythonhosted.org/packages/e5/2b/46bda4ef5a7ae4135dbfe27fc0368c44e5a349a897a54fdf2cedb8dcb66e/meson-1.7.2-py3-none-any.whl"
meson_tool_dir="/yocto/android-ci-tools/meson-${meson_version}"
arm64_build_variant="${ARM64_BUILD_VARIANT:-${IMX8MM_BUILD_VARIANT:-userdebug}}"
build_scope="${BUILD_SCOPE:-all}"
force_full_sync="${FORCE_FULL_SYNC:-false}"
[[ "${jobs}" =~ ^[1-9][0-9]*$ ]] \
    || { echo "JOBS must be a positive integer" >&2; exit 1; }
python3 "${repo_root}/scripts/validate-board-support.py" \
    "${repo_root}/config/board-support.json"
case "${arm64_build_variant}" in
    user|userdebug) ;;
    *) echo "ARM64_BUILD_VARIANT must be user or userdebug" >&2; exit 1 ;;
esac
case "${build_scope}" in
    all)
        targets=(
            lineage_waydroid_x86_64-bp4a-userdebug
            "lineage_waydroid_arm64_only-bp4a-${arm64_build_variant}"
            "lineage_waydroid_aesl_2gb_arm64_only-bp4a-${arm64_build_variant}"
        )
        ;;
    arm64_standard)
        targets=("lineage_waydroid_arm64_only-bp4a-${arm64_build_variant}")
        ;;
    arm64_2gb|imx8mm)
        targets=("lineage_waydroid_aesl_2gb_arm64_only-bp4a-${arm64_build_variant}")
        ;;
    imx95_frdm)
        targets=("lineage_waydroid_aesl_imx95_arm64_only-bp4a-${arm64_build_variant}")
        ;;
    x86_64)
        targets=(lineage_waydroid_x86_64-bp4a-userdebug)
        ;;
    x86_64_2gb)
        targets=(lineage_waydroid_aesl_2gb_x86_64-bp4a-userdebug)
        ;;
    *) echo "BUILD_SCOPE must be all, arm64_standard, arm64_2gb, imx95_frdm, x86_64 or x86_64_2gb" >&2; exit 1 ;;
esac

die() { echo "$*" >&2; exit 1; }

validate_raw_android_image() {
    local block_count block_size filesystem image logical_size partition required_size
    image="$1"
    partition="$2"
    filesystem="$(blkid -p -s TYPE -o value "${image}" 2>/dev/null || true)"
    case "${filesystem}" in
        ext4)
            block_count="$(LC_ALL=C dumpe2fs -h "${image}" 2>/dev/null | awk -F: '/^Block count:/ {gsub(/ /, "", $2); print $2}' || true)"
            block_size="$(LC_ALL=C dumpe2fs -h "${image}" 2>/dev/null | awk -F: '/^Block size:/ {gsub(/ /, "", $2); print $2}' || true)"
            [[ "${block_count}" =~ ^[0-9]+$ && "${block_size}" =~ ^[0-9]+$ ]] \
                || die "could not read ${partition} ext4 geometry: ${image}"
            logical_size="$(stat -c '%s' "${image}")"
            required_size="$((block_count * block_size))"
            [[ "${logical_size}" -ge "${required_size}" ]] \
                || die "${partition} image is truncated: file=${logical_size} bytes ext4=${required_size} bytes"
            [[ "${logical_size}" -eq "${required_size}" ]] \
                || die "${partition} image has trailing data: file=${logical_size} bytes ext4=${required_size} bytes"
            e2fsck -fn "${image}" \
                || die "${partition} image failed read-only ext4 integrity validation: ${image}"
            ;;
        *)
            [[ "$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).open("rb").read(4).hex())' "${image}")" != 3aff26ed ]] \
                || die "${partition} image is Android sparse; raw ext4 is required: ${image}"
            # blkid may report "unknown" for ext4 with appended bytes. Check
            # its superblock before falling back to the generic diagnostic.
            block_count="$(LC_ALL=C dumpe2fs -h "${image}" 2>/dev/null | awk -F: '/^Block count:/ {gsub(/ /, "", $2); print $2}' || true)"
            block_size="$(LC_ALL=C dumpe2fs -h "${image}" 2>/dev/null | awk -F: '/^Block size:/ {gsub(/ /, "", $2); print $2}' || true)"
            if [[ "${block_count}" =~ ^[0-9]+$ && "${block_size}" =~ ^[0-9]+$ ]]; then
                logical_size="$(stat -c '%s' "${image}")"
                required_size="$((block_count * block_size))"
                [[ "${logical_size}" -le "${required_size}" ]] \
                    || die "${partition} image has trailing data: file=${logical_size} bytes ext4=${required_size} bytes"
            fi
            die "${partition} image has unsupported filesystem: ${image} (${filesystem:-unknown})"
            ;;
    esac
}

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

for command in repo git python3 sha256sum timeout ps blkid dumpe2fs e2fsck; do
    command -v "${command}" >/dev/null || die "required command missing: ${command}"
done
# The locked R16 ext4 images passed e2fsck 1.47.0 on CT101. Older host
# e2fsprogs may not understand features emitted by Android's image tools.
e2fsck_version="$(e2fsck -V 2>&1 | awk 'NR == 1 {print $2}')"
[[ "${e2fsck_version}" =~ ^([0-9]+)\.([0-9]+)(\.[0-9]+)? ]] \
    || die "cannot determine host e2fsck version: ${e2fsck_version:-unknown}"
(( BASH_REMATCH[1] > 1 || (BASH_REMATCH[1] == 1 && BASH_REMATCH[2] >= 47) )) \
    || die "host e2fsck ${e2fsck_version} is too old; R16 images require e2fsprogs 1.47 or newer"
[[ "${android_dir}" == /yocto/* ]] || die "ANDROID_WORKSPACE must be under /yocto"
[[ "${x86_64_out_dir}" == "${android_dir}"/* ]] \
    || die "ANDROID_X86_64_OUT_DIR must be inside ANDROID_WORKSPACE"
[[ "${x86_64_2gb_out_dir}" == "${android_dir}"/* ]] \
    || die "ANDROID_X86_64_2GB_OUT_DIR must be inside ANDROID_WORKSPACE"
[[ "${arm64_standard_out_dir}" == "${android_dir}"/* ]] \
    || die "ANDROID_ARM64_STANDARD_OUT_DIR must be inside ANDROID_WORKSPACE"
[[ "${arm64_2gb_out_dir}" == "${android_dir}"/* ]] \
    || die "ANDROID_ARM64_2GB_OUT_DIR must be inside ANDROID_WORKSPACE"
[[ "${imx95_out_dir}" == "${android_dir}"/* ]] \
    || die "ANDROID_IMX95_OUT_DIR must be inside ANDROID_WORKSPACE"
[[ "${artifact_dir}" == /yocto/* ]] || die "OUTPUT_DIR must be under /yocto"
[[ "${manifest_cache_dir}" == /yocto/* ]] || die "ANDROID_MANIFEST_CACHE_DIR must be under /yocto"
[[ -s "${lock_file}" ]] || die "reviewed source lock missing: ${lock_file}"
[[ -s "${source_date_epoch_file}" ]] || die "stable source-date epoch missing: ${source_date_epoch_file}"
python3 "${repo_root}/scripts/validate-lock.py" "${lock_file}"

mkdir -p "${android_dir}" "${x86_64_out_dir}" "${x86_64_2gb_out_dir}" \
    "${arm64_standard_out_dir}" "${arm64_2gb_out_dir}" "${imx95_out_dir}" "${artifact_dir}" \
    "${manifest_cache_dir}"
source_cache_evidence="${artifact_dir}/source-cache-evidence.txt"
target_cache_evidence="${artifact_dir}/target-cache-evidence.tsv"
printf 'phase\ttarget\tcache_present_before\tbytes_before\tmtime_before\tbytes_after\tmtime_after\telapsed_seconds\n' \
    > "${target_cache_evidence}"
prepare_pinned_meson
lock_sha="$(sha256sum "${lock_file}" | cut -d' ' -f1)"
lock_project_count="$(python3 -c 'import sys,xml.etree.ElementTree as ET; print(len(ET.parse(sys.argv[1]).getroot().findall("project")))' "${lock_file}")"
manifest_repo="${manifest_cache_dir}/${lock_sha}"
manifest_cache_mode=reused
if ! git -C "${manifest_repo}" rev-parse --verify HEAD >/dev/null 2>&1; then
    manifest_cache_mode=created
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
    repo_init_mode=reused
    echo "Reusing cached repo initialization for source lock ${lock_sha}"
else
    repo_init_mode=activated
    echo "Activating Git-backed source lock ${lock_sha}"
    repo init -u "${manifest_url}" -b locked -m default.xml --git-lfs
fi

previous_lock="${android_dir}/.repo/aesl-source-lock.xml"
comparison_lock="${previous_lock}"
# Older revisions recorded only the lock digest.  Their Git-backed manifest
# cache still contains the exact XML, so use it to calculate a project delta
# instead of needlessly resetting all 1,181 projects during migration.
if [[ ! -s "${comparison_lock}" \
    && "${cached_lock}" =~ ^[0-9a-f]{64}$ \
    && -s "${manifest_cache_dir}/${cached_lock}/default.xml" ]]; then
    comparison_lock="${manifest_cache_dir}/${cached_lock}/default.xml"
    echo "Recovering the previous immutable lock from the /yocto manifest cache"
fi
full_sync=false
changed_projects=()
if [[ "${force_full_sync}" == true || "${force_full_sync}" == 1 ]]; then
    echo "A complete source resynchronization was explicitly requested"
    full_sync=true
elif [[ "${cached_lock}" == "${lock_sha}" ]]; then
    echo "Source worktree already matches the immutable lock; skipping repo sync"
elif [[ -s "${comparison_lock}" ]]; then
    mapfile -t changed_projects \
        < <(python3 "${repo_root}/scripts/lock-delta.py" "${comparison_lock}" "${lock_file}")
    if [[ "${changed_projects[0]:-}" == __FULL__ ]]; then
        full_sync=true
        changed_projects=()
    fi
else
    full_sync=true
fi

if [[ "${full_sync}" == true ]]; then
    echo "Restoring the complete locked source tree from the /yocto object cache"
    source_sync_mode="full"
    sync_locked_sources
elif (( ${#changed_projects[@]} > 0 )); then
    echo "Synchronizing ${#changed_projects[@]} project(s) changed by the immutable lock"
    source_sync_mode="delta"
    printf '  %s\n' "${changed_projects[@]}"
    sync_locked_sources "${changed_projects[@]}"
else
    echo "No project revisions changed; preserving the incremental source worktree"
    source_sync_mode="reused"
fi
printf '%s\n' "${lock_sha}" > .repo/aesl-source-lock.sha256
install -m 0644 "${lock_file}" "${previous_lock}"

if [[ "${arm64_build_variant}" == user ]]; then
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
patch_projects_to_apply=()
for changed_project in "${changed_projects[@]}"; do
    synchronized_projects["${changed_project}"]=1
done
for patch_state in "${patch_states[@]}"; do
    IFS=$'\t' read -r patch_project patch_digest <<< "${patch_state}"
    desired_patch_projects["${patch_project}"]=1
    patch_marker="${patch_state_dir}/${patch_project}.sha256"
    applied_digest="$(cat "${patch_marker}" 2>/dev/null || true)"
    if [[ "${full_sync}" == true || "${applied_digest}" != "${patch_digest}" ]]; then
        if [[ "${full_sync}" != true && -z "${synchronized_projects[$patch_project]:-}" ]]; then
            echo "Patch state changed for ${patch_project}; restoring its exact locked base"
            sync_locked_sources "${patch_project}"
            synchronized_projects["${patch_project}"]=1
        fi
        patch_projects_to_apply+=("${patch_project}")
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
if (( ${#patch_projects_to_apply[@]} > 0 )); then
    echo "Applying patches for ${#patch_projects_to_apply[@]} changed project(s)"
    run_with_heartbeat "Waydroid patch application" \
        timeout --foreground --kill-after=60s 30m \
        "${repo_root}/scripts/apply-waydroid-patches-strict.sh" \
        "${android_dir}" "${patch_projects_to_apply[@]}"
else
    echo "Patch state already matches; preserving patched source projects"
fi
printf '%s\n' \
    "lock_sha256=${lock_sha}" \
    "previous_lock_sha256=${cached_lock:-none}" \
    "lock_validation=passed" \
    "lock_project_count=${lock_project_count}" \
    "duplicate_project_paths=0" \
    "manifest_cache_mode=${manifest_cache_mode}" \
    "repo_init_mode=${repo_init_mode}" \
    "source_sync_mode=${source_sync_mode}" \
    "changed_projects=${#changed_projects[@]}" \
    "patch_projects_applied=${#patch_projects_to_apply[@]}" \
    "android_workspace=${android_dir}" \
    > "${source_cache_evidence}"
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
        *aesl_2gb_x86_64*)
            target_out_dir="${x86_64_2gb_out_dir}"
            target_artifacts="${artifact_dir}/x86_64_2gb"
            ;;
        *x86_64*)
            target_out_dir="${x86_64_out_dir}"
            target_artifacts="${artifact_dir}/x86_64"
            ;;
        *aesl_2gb_arm64_only*)
            target_out_dir="${arm64_2gb_out_dir}"
            target_artifacts="${artifact_dir}/arm64_2gb"
            ;;
        *aesl_imx95_arm64_only*)
            target_out_dir="${imx95_out_dir}"
            target_artifacts="${artifact_dir}/imx95_frdm"
            ;;
        *arm64_only*)
            target_out_dir="${arm64_standard_out_dir}"
            target_artifacts="${artifact_dir}/arm64_standard"
            ;;
        *) die "unrecognised target: ${target}" ;;
    esac
    # Soong identifies host outputs by their leading out/ component. Keep the
    # target-specific path relative to TOP while its physical location remains
    # under /yocto/android-16-source.
    export OUT_DIR="${target_out_dir#"${android_dir}/"}"
    target_ninja_log="${target_out_dir}/.ninja_log"
    cache_present_before=false
    bytes_before=0
    mtime_before=0
    if [[ -f "${target_ninja_log}" ]]; then
        cache_present_before=true
        read -r bytes_before mtime_before < <(stat -c '%s %Y' "${target_ninja_log}")
    fi
    echo "Target cache before build: target=${target} present=${cache_present_before} ninja_log_bytes=${bytes_before}"
    target_started_at="$(date +%s)"
    printf 'start\t%s\t%s\t%s\t%s\t-\t-\t0\n' \
        "${target}" "${cache_present_before}" "${bytes_before}" "${mtime_before}" \
        >> "${target_cache_evidence}"
    echo "Configuring Android target ${target}"
    set +u
    lunch "${target}"
    set -u
    echo "Building system, vendor and SPDX outputs for ${target}"
    run_with_heartbeat "Android image build ${target}" \
        m -j"${jobs}" systemimage vendorimage sbom
    target_finished_at="$(date +%s)"
    read -r bytes_after mtime_after < <(stat -c '%s %Y' "${target_ninja_log}")
    printf 'complete\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "${target}" "${cache_present_before}" "${bytes_before}" "${mtime_before}" \
        "${bytes_after}" "${mtime_after}" "$((target_finished_at - target_started_at))" \
        >> "${target_cache_evidence}"

    mkdir -p "${target_artifacts}"
    install -m 0644 "${OUT}/system.img" "${target_artifacts}/system.img"
    install -m 0644 "${OUT}/vendor.img" "${target_artifacts}/vendor.img"
    validate_raw_android_image "${target_artifacts}/system.img" "${target} system"
    validate_raw_android_image "${target_artifacts}/vendor.img" "${target} vendor"
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
    --arm64-variant "${arm64_build_variant}" \
    --targets "${targets[@]}"
arm64_profile_dir=
if [[ "${build_scope}" == imx95_frdm && -d "${artifact_dir}/imx95_frdm" ]]; then
    arm64_profile_dir=imx95_frdm
elif [[ -d "${artifact_dir}/arm64_2gb" && ! -d "${artifact_dir}/arm64_standard" ]]; then
    arm64_profile_dir=arm64_2gb
elif [[ -d "${artifact_dir}/arm64_standard" && ! -d "${artifact_dir}/arm64_2gb" ]]; then
    arm64_profile_dir=arm64_standard
fi
if [[ -n "${arm64_profile_dir}" ]]; then
    memory_profile="${arm64_profile_dir#arm64_}"
    case "${arm64_profile_dir}" in
        arm64_standard) board_profile=generic_arm64 ;;
        arm64_2gb) board_profile=imx8mm ;;
        imx95_frdm)
            memory_profile=standard
            board_profile=imx95_frdm
            ;;
    esac
    system_sha=$(sha256sum "${artifact_dir}/${arm64_profile_dir}/system.img" | cut -d' ' -f1)
    vendor_sha=$(sha256sum "${artifact_dir}/${arm64_profile_dir}/vendor.img" | cut -d' ' -f1)
    sbom_sha=$(sha256sum "${artifact_dir}/${arm64_profile_dir}/sbom.spdx.json" | cut -d' ' -f1)
    system_notice_sha=$(sha256sum "${artifact_dir}/${arm64_profile_dir}/NOTICE-system.xml.gz" | cut -d' ' -f1)
    vendor_notice_sha=$(sha256sum "${artifact_dir}/${arm64_profile_dir}/NOTICE-vendor.xml.gz" | cut -d' ' -f1)
    source_manifest_sha=$(sha256sum "${artifact_dir}/source-manifest.xml" | cut -d' ' -f1)
    build_info_sha=$(sha256sum "${artifact_dir}/build-info.json" | cut -d' ' -f1)
    printf '%s\n' \
        '# Generated by the reviewed AESL Android 16 image build.' \
        "AESL_WAYDROID_MEMORY_PROFILE = \"${memory_profile}\"" \
        "AESL_WAYDROID_BOARD_PROFILE = \"${board_profile}\"" \
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
