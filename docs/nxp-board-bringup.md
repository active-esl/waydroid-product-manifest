# NXP board bring-up

The first board target is the 2 GB i.MX8MM. The i.MX95 is a separate hardware
target: it may eventually share the architecture-independent Android system
image, but it must have its own reviewed vendor image, GPU/VPU contract and
board acceptance evidence. Do not deploy the i.MX8MM vendor image on i.MX95.

This is the first slice of a wider i.MX8/i.MX9 matrix, not a two-family binary
split. NXP publishes distinct Android products for individual SoCs and boards,
and their GPU, VPU, ISP, audio, radio and firmware capabilities differ. Admit a
new board using the controlled tuple from `android-platform-lifecycle.md`:

```text
(Android release, system profile, vendor compatibility class, board profile, build variant)
```

Begin with a vendor compatibility class per SoC (for example i.MX8MM, i.MX8MP
and i.MX95). Keep a further board/ODM variant when its peripherals or Android
HAL content differ. Consolidate two classes only after VINTF, host-kernel ABI,
GPU/VPU and board acceptance evidence proves the same vendor image works on
both; do not infer compatibility from the i.MX8 or i.MX9 family name.

## Board lanes at a glance

| Machine | Working build | Staged candidate | Current boundary |
| --- | --- | --- | --- |
| Jaguar Screen i.MX8MM | R13 standard: Android run 34838947265 with Foundries target 2887 | Foundries target 2943 is installed from isolated tag `r16-jaguar-screen` | The released R16 `system.img` is truncated and must be replaced before runtime acceptance |
| FRDM i.MX95 | Foundries development host target 2936 | The R16 pair from run 34856380503 reached partial startup evidence on FRDM | Replace the corrupt shared `system.img`; the i.MX8MM `vendor.img` is also not an FRDM product image, so build the i.MX95 Mali/Hantro vendor class |

“Working build” in this table identifies the highest component gate that has
passed. Only Jaguar R13 has passed the complete Android UI and acceleration
board gate. FRDM target 2936 is a working host-build baseline, not a completed
Android product.

## Jaguar Screen current state

The Android product `lineage_waydroid_aesl_2gb_arm64_only` is already defined.
It is ARM64-only, Vanilla, low-RAM, PSI/lmkd tuned, Mesa Etnaviv/minigbm based,
Vulkan-free and limited to one V4L2 Codec2 AVC decoder stream.

Foundries target 2943 delivers the reviewed Waydroid 1.6.3/AIDL6 and image-APEX
host integration. It is installed on the Jaguar Screen machine with boot
firmware `2026090703`; both U-Boot upgrade flags are clear. Two defects were
found during staging: the Jaguar session must point Waydroid at the system
PulseAudio socket `/run/pulse`, and immutable release provisioning must not
accept an arbitrary older image pair before comparing the release marker.

The pinned R16 `system.img` from run 34856380503 is not deployable. Its ext4
superblock declares 1,981,640,704 bytes while the released file contains only
1,233,031,168 bytes. The missing tail includes extended attributes for
`/system/bin/run-as` and `/system/bin/simpleperf_app_runner`; do not clear those
security attributes as a repair. Replace the shared artifact and repin its
checksum before testing any i.MX8 or i.MX9 board.

The R16 source lock now pins device commit
[`e9d3eda`](https://github.com/active-esl/android_device_waydroid_waydroid/commit/e9d3eda4e658e37c9c116ae3dccb55e7728c18a5).
Relative to `d00473a`, it changes only
`BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE` from `erofs` to `ext4` in `BoardConfig.mk`;
the vendor image was already ext4. The replacement build's installed system
and vendor images both match their declared ext4 geometry exactly.

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
separate from `main-jaguar-screen`. Target 2943 was published and deliberately
staged only on the Jaguar Screen device through tag `r16-jaguar-screen`.

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

## Next Jaguar Screen action

Follow the canonical [build and promotion plan](build-plan.md). Run 34856380503
is preserved as failed integration evidence; its truncated `system.img` must
not be reused.

1. Rebuild the shared R16 2 GB `system.img` with the raw-ext4 geometry and
   read-only filesystem integrity gates enabled; build the i.MX8MM vendor image
   in the same controlled tuple.
2. Publish a new immutable Android integration release, update the partner
   checksums, and build a successor to Foundries target 2943 containing the
   provisioning and Jaguar PulseAudio fixes.
3. Stage only on the Jaguar Screen machine, retaining the working R13 rollback,
   then prove Android boot, UI, Etnaviv/V4L2, memory and lifecycle behaviour.
4. Apply the shared-image gate to every i.MX8/i.MX9 target. Only after
   `userdebug` integration passes, build the Android `user` variant and repeat
   the release gates.

## FRDM i.MX95 lane

[Foundries target 2936](https://app.foundries.io/factories/dynamic-devices/targets/2936)
from `main-imx95-frdm-devel` built successfully and supplied the updated
Waydroid 1.6.3/AIDL6 host used for the FRDM integration test. The R16 image
pair was staged far enough to start Android 16 userspace. That is useful host
and image-APEX evidence, but it is not a complete FRDM Android build: the
paired `vendor.img` from run 34856380503 targets i.MX8MM Etnaviv, while FRDM
uses the i.MX95 DPU/Mali path. EGL therefore failed to create a configuration.

The next Android artifact is an explicit i.MX95 Mali/Hantro vendor image,
paired with the reviewed shared ARM64 system image and tested again on target
2936 or its exact successor.

Create an explicit i.MX95 Android product/vendor target only after identifying
the shipping kernel DRM renderer, allocator handle layout, DMA heaps and VPU
nodes. Reuse the pinned Lineage source lock and common ARM64 system content
where the evidence permits, but keep the i.MX95 vendor image and acceleration
acceptance record separate from i.MX8MM.
