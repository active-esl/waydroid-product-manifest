# NXP board bring-up

The first board target is the 2 GB i.MX8MM. The i.MX95 is a separate hardware
target: it may eventually share the architecture-independent Android system
image, but it must have its own reviewed vendor image, GPU/VPU contract and
board acceptance evidence. Do not deploy the i.MX8MM vendor image on i.MX95.

## Current state

The Android product `lineage_waydroid_aesl_2gb_arm64_only` is already defined.
It is ARM64-only, Vanilla, low-RAM, PSI/lmkd tuned, Mesa Etnaviv/minigbm based,
Vulkan-free and limited to one V4L2 Codec2 AVC decoder stream.

The released Jaguar host (Foundries target 2892) is not yet suitable for this
image. It ships Waydroid 1.4.2, libgbinder 1.1.35, libglibutil 1.0.75 and the
legacy platform-interface descriptor. Android 16 host compatibility requires
the reviewed Waydroid 1.6.3, libgbinder 1.1.52, libglibutil 1.0.82 and AIDL6
platform-interface changes, plus loop-control and device-mapper mounts for
image APEX. Those changes exist in the product integration source but have not
been delivered in the Jaguar Foundries image. This is a host-build blocker,
not a reason to rebuild the already checksum-proven Android image.

## Jaguar Screen evidence log

Evidence reviewed: 2026-09-15.

The candidate is the explicit product tuple
`imx8mm-jaguar-screen-r16-waydroid-2gb-userdebug`: machine
`imx8mm-jaguar-screen`, distro `lmp-dynamicdevices`, image
`lmp-factory-image`, product features `display android-container`, and the R16
/ LineageOS 23.2 2 GB `userdebug` image pair. The initial Foundries attempts
used the historical branch name `r16-jaguar-host`; attempts 2935 and 2937 must
retain that identifier in evidence. New attempts use `r16-jaguar-screen`,
reported by Foundries as `platform-r16-jaguar-screen`, because the build is
specific to the Jaguar Screen hardware and display path. The branch remains
separate from `main-jaguar-screen`, so publication alone cannot move the lab
board. A published target remains pending.

Foundries attempt 2938 is also blocked by competing native U-Boot tool
providers: OE-Core `u-boot-tools_2024.01.bb` and partner
`u-boot-imx-tools_2025.04.bb` are both scheduled and both provide
`u-boot-tools-native` plus the related mkimage, mkenvimage and mkeficapsule
capabilities. Treat the complete provider error as build evidence even if
BitBake proceeds afterward. It must be fixed by establishing one coherent
provider contract for all dependees; never hide it with log filtering, QA
suppression, exception handling or an arbitrary mask that drops required
functionality.
Partner commit `3d33e23` establishes OE-Core as the sole native U-Boot tools
owner and uses the effective recipe-specific AppArmor clang override.
Attempt 2939 had not published a Foundries target at this evidence review, so
it is not a successful host build or board-test result. Retain its complete CI
result before changing that verdict; never infer success from the absence of a
target or from a later BitBake task running.

The 2026-09-14 manual test of R16 2 GB run 34856380503 on the physical Jaguar
screen machine confirmed that Binder appears but `waydroidplatform` never
registers on target 2892. A reversible live transplant of the FRDM 1.6.3/AIDL6
runtime did not produce a qualifying boot, so it is not release evidence. Do
not repeat that transplant: build the complete host integration and retest the
paired host and Android artifacts.

The preserved R13 image link is restored, but the current target 2892 is not a
qualified fallback. A bounded check after reboot showed Android release 13 and
RUNNING container/session states, while `sys.boot_completed` stayed empty and
`waydroid-jaguar-ui.service` failed waiting for `waydroidplatform`. Do not use
that state to replace the earlier target 2887 R13 PASS evidence, and do not
perform another runtime transplant while the complete host build is pending.

## Implementation sequence

1. Dispatch **Build Android R16 / LineageOS 23.2 images** with
   `build_scope=arm64_2gb` and `arm64_variant=userdebug`. Preserve
   `build-info.json`, `SHA256SUMS`, SPDX,
   NOTICE archives and `source-manifest.xml` with the two images.
2. Update the Yocto Waydroid runtime to the reviewed Android 16-compatible
   host implementation. Package pinned libgbinder 1.1.52 and libglibutil
   1.0.82 revisions, AIDL6 service-manager selection and the
   `id.waydro.waydroid.IPlatform` interface descriptor. Do not compile this
   compatibility stack on the 2 GB target at first boot.
3. Replace the Lineage 18.1 network downloads in `waydroid-data` with the
   exact CI-produced `system.img` and i.MX8MM `vendor.img` checksums. Consume
   `waydroid-images.inc`/`build-info.json`, and reject an integration artifact
   when building a production host image.
4. Remove the unconditional Vulkan requirement for the i.MX8MM product. The
   host kernel and image must instead provide binderfs, cgroup v2, MEMCG, PSI,
   zram, the selected DMA heaps, the Etnaviv DRM render node and the VSI V4L2
   decoder node.
5. Build the LmP/Yocto image with the `waydroid` distro feature on persistent
   `/yocto` CI storage. Flash the i.MX8MM using its board-specific UUU family;
   do not reuse i.MX95 layout, WKS, FIT or flash scripts.
6. On the board, prove Android boot and UI first, then run
   `/usr/libexec/waydroid-acceleration-check` after cold boot, container restart
   and suspend/resume. Run `/usr/libexec/waydroid-memory-headroom` for idle,
   steady-state and peak kiosk workloads and retain all reports.
7. After integration passes, rebuild Android with `arm64_variant=user` and
   repeat the board evidence as the production/SELinux release gate. Deliver
   subsequent host updates through the LmP OSTree/OTA path; reserve UUU for
   recovery or storage-layout changes.

## i.MX95 follow-on

Create an explicit i.MX95 Android product/vendor target only after identifying
the shipping kernel DRM renderer, allocator handle layout, DMA heaps and VPU
nodes. Reuse the pinned Lineage source lock and common ARM64 system content
where the evidence permits, but keep the i.MX95 vendor image and acceleration
acceptance record separate from i.MX8MM.
