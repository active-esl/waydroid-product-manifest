#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
android_dir="${ANDROID_WORKSPACE:-${repo_root}/.android-workspace}"
lock_output="${LOCK_OUTPUT:-${repo_root}/lineage-23.2-lock.xml}"
sync_jobs="${JOBS:-4}"

command -v repo >/dev/null || { echo "repo tool is required" >&2; exit 1; }
command -v git >/dev/null || { echo "git is required" >&2; exit 1; }

quarantine_invalid_repo_gitdirs() {
    local kind root gitdir relative quarantine_root quarantine_path

    for kind in project-objects projects; do
        root="${android_dir}/.repo/${kind}"
        [[ -d "${root}" ]] || continue

        while IFS= read -r -d '' gitdir; do
            if git --git-dir="${gitdir}" rev-parse --git-dir >/dev/null 2>&1; then
                continue
            fi

            relative="${kind}/${gitdir#"${root}/"}"
            quarantine_root="${android_dir}/.repo/corrupt-projects"
            quarantine_path="${quarantine_root}/${relative//\//__}.$(date -u +%s)"
            mkdir -p "${quarantine_root}"
            echo "Quarantining invalid repo Git metadata: ${relative}" >&2
            mv -- "${gitdir}" "${quarantine_path}"
        done < <(find "${root}" -type d -name '*.git' -prune -print0)
    done
}

run_repo_sync() {
    local jobs="$1" sync_pid
    shift
    quarantine_invalid_repo_gitdirs
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.version GIT_CONFIG_VALUE_0=HTTP/1.1 \
        repo sync -c --no-tags --force-checkout -j"${jobs}" "$@" &
    sync_pid=$!
    while kill -0 "${sync_pid}" 2>/dev/null; do
        for _ in {1..60}; do
            sleep 5
            kill -0 "${sync_pid}" 2>/dev/null || break
        done
        if kill -0 "${sync_pid}" 2>/dev/null; then
            echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) repo sync is still active (${jobs} job(s))"
        fi
    done
    wait "${sync_pid}"
}

sync_with_retries() {
    local attempt delay=15 jobs="${sync_jobs}"
    for attempt in 1 2 3 4 5 6; do
        if run_repo_sync "${jobs}" "$@"; then
            return 0
        fi
        [[ "${attempt}" == 6 ]] && return 1
        echo "repo sync attempt ${attempt} failed; retrying in ${delay}s with ${jobs} job(s)" >&2
        sleep "${delay}"
        (( jobs > 1 )) && jobs=$((jobs / 2))
        (( delay < 120 )) && delay=$((delay * 2))
    done
}

init_with_retries() {
    local attempt delay=15
    for attempt in 1 2 3 4 5 6; do
        if GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.version GIT_CONFIG_VALUE_0=HTTP/1.1 \
            repo init -u https://github.com/LineageOS/android.git \
                -b lineage-23.2 --git-lfs; then
            return 0
        fi
        [[ "${attempt}" == 6 ]] && return 1
        echo "repo init attempt ${attempt} failed; retrying in ${delay}s" >&2
        sleep "${delay}"
        (( delay < 120 )) && delay=$((delay * 2))
    done
}

mkdir -p "${android_dir}"
cd "${android_dir}"

if [[ -d .repo ]]; then
    rm -rf .repo/manifests .repo/manifests.git .repo/local_manifests
    rm -f .repo/manifest.xml
fi

init_with_retries
echo "Syncing the minimal build/make project before applying local manifests"
sync_with_retries build/make

mkdir -p .repo/local_manifests
cp "${repo_root}"/overlays/lineage-23.2/*.xml .repo/local_manifests/
echo "Syncing the complete LineageOS 23.2 source tree; progress heartbeat is every five minutes"
sync_with_retries

repo manifest -r -o "${lock_output}"
python3 "${repo_root}/scripts/validate-lock.py" "${lock_output}"
