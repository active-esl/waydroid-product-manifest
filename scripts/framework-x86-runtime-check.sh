#!/usr/bin/env bash
set -euo pipefail

evidence_dir="${1:-${PWD}/framework-x86-evidence/$(date -u +%Y%m%dT%H%M%SZ)}"
image_dir=/etc/waydroid-extra/images

die() {
    echo "$*" >&2
    exit 1
}

command -v waydroid >/dev/null || die "waydroid is not installed"
[[ "$(uname -m)" == x86_64 ]] || die "Framework compatibility check requires an x86_64 host"
[[ -s "${image_dir}/system.img" ]] || die "missing ${image_dir}/system.img"
[[ -s "${image_dir}/vendor.img" ]] || die "missing ${image_dir}/vendor.img"

status="$(waydroid status)"
grep -Fq $'Session:\tRUNNING' <<<"${status}" || die "Waydroid session is not running"
grep -Fq $'Container:\tRUNNING' <<<"${status}" || die "Waydroid container is not running"

mkdir -p "${evidence_dir}"
printf '%s\n' "${status}" > "${evidence_dir}/waydroid-status.txt"
waydroid --version > "${evidence_dir}/waydroid-version.txt"
uname -a > "${evidence_dir}/host-kernel.txt"
sha256sum "${image_dir}/system.img" "${image_dir}/vendor.img" \
    > "${evidence_dir}/image-sha256.txt"

if command -v glxinfo >/dev/null; then
    glxinfo -B > "${evidence_dir}/host-glxinfo.txt" 2>&1 || true
fi

runtime_dump="${evidence_dir}/android-runtime.txt"
pkexec /bin/sh -c '
    printf "__PROPERTIES__\n"
    waydroid shell getprop
    printf "__SERVICES__\n"
    waydroid shell service list
    printf "__SURFACEFLINGER__\n"
    waydroid shell dumpsys SurfaceFlinger
    printf "__ACONFIG_METADATA__\n"
    waydroid shell -- ls -l \
        /metadata/aconfig/maps/system.package.map \
        /metadata/aconfig/maps/system.flag.map
' > "${runtime_dump}"

awk '
    /^__PROPERTIES__$/ { section="properties"; next }
    /^__SERVICES__$/ { section="services"; next }
    /^__SURFACEFLINGER__$/ { section="surfaceflinger"; next }
    /^__ACONFIG_METADATA__$/ { section="aconfig"; next }
    section == "properties" { print > properties }
    section == "services" { print > services }
    section == "surfaceflinger" { print > surfaceflinger }
    section == "aconfig" { print > aconfig }
' properties="${evidence_dir}/android-properties.txt" \
  services="${evidence_dir}/android-services.txt" \
  surfaceflinger="${evidence_dir}/surfaceflinger.txt" \
  aconfig="${evidence_dir}/aconfig-metadata.txt" \
  "${runtime_dump}"

properties="${evidence_dir}/android-properties.txt"
services="${evidence_dir}/android-services.txt"
surfaceflinger="${evidence_dir}/surfaceflinger.txt"
aconfig="${evidence_dir}/aconfig-metadata.txt"

grep -Fq '[sys.boot_completed]: [1]' "${properties}" \
    || die "Android did not complete boot"
grep -Fq '[ro.build.version.release]: [16]' "${properties}" \
    || die "running image is not Android 16"
grep -Fq '[init.svc.vendor.graphics.allocator]: [running]' "${properties}" \
    || die "AIDL graphics allocator service is not running"
grep -Fq 'android.hardware.graphics.allocator.IAllocator/default' "${services}" \
    || die "AIDL graphics allocator is not registered"
grep -Fq '/metadata/aconfig/maps/system.package.map' "${aconfig}" \
    || die "Android 16 aconfig metadata was not initialized"
grep -Fq '/metadata/aconfig/maps/system.flag.map' "${aconfig}" \
    || die "Android 16 aconfig metadata was not initialized"
grep -Eiq 'GLES|OpenGL ES' "${surfaceflinger}" \
    || die "SurfaceFlinger did not report a GLES renderer"

if grep -Eiq 'swiftshader|llvmpipe|softpipe' "${surfaceflinger}"; then
    die "software rendering fallback detected"
fi

printf '%s\n' \
    'Framework x86_64 Waydroid runtime evidence: PASS' \
    "evidence_dir=${evidence_dir}" \
    > "${evidence_dir}/RESULT.txt"
cat "${evidence_dir}/RESULT.txt"
