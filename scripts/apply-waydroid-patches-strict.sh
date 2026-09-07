#!/usr/bin/env bash
set -euo pipefail

android_dir="${1:?usage: apply-waydroid-patches-strict.sh ANDROID_SOURCE_DIR}"
patch_root="${android_dir}/vendor/extra/waydroid-patches/base-patches-36"

[[ -d "${android_dir}/.repo" ]] || { echo "not an Android repo checkout: ${android_dir}" >&2; exit 1; }
[[ -d "${patch_root}" ]] || { echo "Waydroid SDK 36 patches missing: ${patch_root}" >&2; exit 1; }

export GIT_COMMITTER_NAME="Active ESL Android CI"
export GIT_COMMITTER_EMAIL="engineering@active-esl.com"

while IFS= read -r -d '' patch_file; do
    relative="${patch_file#"${patch_root}"/}"
    project="${relative%/*}"
    project_dir="${android_dir}/${project}"

    [[ -d "${project_dir}/.git" || -f "${project_dir}/.git" ]] || {
        echo "patch target is not a checked-out project: ${project}" >&2
        exit 1
    }

    if git -C "${project_dir}" apply --check --whitespace=nowarn "${patch_file}"; then
        echo "applying ${relative}"
        git -C "${project_dir}" am --3way --keep-cr "${patch_file}"
    elif git -C "${project_dir}" apply --reverse --check --whitespace=nowarn "${patch_file}"; then
        echo "already applied ${relative}"
    else
        echo "patch is neither cleanly applicable nor already applied: ${relative}" >&2
        exit 1
    fi
done < <(find "${patch_root}" -type f -name '*.patch' -print0 | sort -z)
