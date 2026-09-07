#!/usr/bin/env bash
set -euo pipefail

readonly repo_version="2.65"
readonly repo_sha256="1211b57b57e4122a9c546295a59b37d24068f1164d0e87bef096d5323c413e4f"
readonly tools_dir="${AESL_TOOLS_DIR:-${RUNNER_TEMP:-${PWD}/.tools}/android-repo/bin}"
readonly repo_bin="${tools_dir}/repo"

mkdir -p "${tools_dir}"
curl --fail --silent --show-error --location \
    "https://storage.googleapis.com/git-repo-downloads/repo-${repo_version}" \
    --output "${repo_bin}"
echo "${repo_sha256}  ${repo_bin}" | sha256sum --check --strict
chmod 0755 "${repo_bin}"

if [[ -n "${GITHUB_PATH:-}" ]]; then
    echo "${tools_dir}" >> "${GITHUB_PATH}"
else
    printf 'Add %s to PATH\n' "${tools_dir}" >&2
fi
