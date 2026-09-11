#!/usr/bin/env bash
set -euo pipefail

workspace_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runtime_root="${WAYDROID_A16_RUNTIME_ROOT:-${workspace_dir}/waydroid-host-runtime}"
gbinder_dir="${runtime_root}/libgbinder-src"
glibutil_dir="${runtime_root}/libglibutil-src"

gbinder_revision=e906afcffbfa51b7fbefe042a13b933d9e8dfdd9
glibutil_revision=cccc4aa8f1745096f6feb66da7883b35055d9423

checkout() {
    local url=$1 tag=$2 revision=$3 directory=$4
    if [[ ! -d "${directory}/.git" ]]; then
        git clone --depth 1 --branch "${tag}" "${url}" "${directory}"
    fi
    [[ "$(git -C "${directory}" rev-parse HEAD)" == "${revision}" ]] || {
        echo "${directory} is not at reviewed revision ${revision}" >&2
        exit 1
    }
}

mkdir -p "${runtime_root}"
checkout https://github.com/sailfishos/libglibutil.git 1.0.82 \
    "${glibutil_revision}" "${glibutil_dir}"
checkout https://github.com/mer-hybris/libgbinder.git 1.1.52 \
    "${gbinder_revision}" "${gbinder_dir}"

make -C "${gbinder_dir}" release LIBGLIBUTIL_PATH="${glibutil_dir}" \
    -j"${WAYDROID_HOST_BUILD_JOBS:-4}"

echo "Android 16 host Binder runtime ready at ${runtime_root}"
