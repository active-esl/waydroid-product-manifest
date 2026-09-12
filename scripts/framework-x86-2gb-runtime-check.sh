#!/usr/bin/env bash
set -euo pipefail

evidence_dir="${1:-${PWD}/framework-x86-2gb-evidence/$(date -u +%Y%m%dT%H%M%SZ)}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() {
    echo "$*" >&2
    exit 1
}

"${script_dir}/framework-x86-runtime-check.sh" "${evidence_dir}"

properties="${evidence_dir}/android-2gb-properties.txt"
for property in \
    ro.product.name \
    ro.product.cpu.abi \
    ro.config.low_ram \
    ro.active_esl.memory_profile \
    ro.active_esl.validation_only; do
    printf '%s=%s\n' "${property}" \
        "$("${script_dir}/waydroid-a16-host" prop get "${property}")"
done | tee "${properties}"

memory_max="$(systemctl show waydroid-container.service -p MemoryMax --value)"
printf 'MemoryMax=%s\n' "${memory_max}" \
    | tee "${evidence_dir}/waydroid-container-cgroup.txt"

grep -Fxq 'ro.product.name=lineage_waydroid_aesl_2gb_x86_64' "${properties}" \
    || die "the running product is not the Framework 2 GB validation image"
grep -Fxq 'ro.product.cpu.abi=x86_64' "${properties}" \
    || die "the running product is not native x86_64"
grep -Fxq 'ro.config.low_ram=true' "${properties}" \
    || die "Android low-RAM mode is not enabled"
grep -Fxq 'ro.active_esl.memory_profile=2gb' "${properties}" \
    || die "AESL 2 GB policy marker is missing"
grep -Fxq 'ro.active_esl.validation_only=true' "${properties}" \
    || die "Framework validation-only marker is missing"
[[ "${memory_max}" == 2147483648 ]] \
    || die "Waydroid container MemoryMax is ${memory_max}, expected 2147483648"

printf '%s\n' \
    'Framework x86_64 Waydroid 2 GB runtime evidence: PASS' \
    "evidence_dir=${evidence_dir}" \
    > "${evidence_dir}/RESULT-2GB.txt"
cat "${evidence_dir}/RESULT-2GB.txt"
