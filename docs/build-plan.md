# Build and promotion plan

This is the canonical plan for deciding what AESL builds, where it builds it
and when it may move to hardware. Build history and failure evidence belong in
the board bring-up documents; they do not change this sequence.

## Product lanes

| Lane | Purpose | Android product | Linux host source | State |
| --- | --- | --- | --- | --- |
| Jaguar Screen R13 standard | Proven legacy screen baseline | `lineage_waydroid_arm64` from the R13 `lineage-20` lane | Foundries `main-jaguar-screen` | Maintain; rebuild only for an approved R13 fix or customer qualification |
| Jaguar Screen R16 2 GB | Active replacement for the screen product | `lineage_waydroid_aesl_2gb_arm64_only`; i.MX8MM/Etnaviv vendor contract | Foundries `r16-jaguar-screen` → `platform-r16-jaguar-screen` | Active integration |
| FRDM i.MX95 R16 | Active i.MX95 product lane | Proposed explicit `lineage_waydroid_aesl_imx95_arm64_only`; i.MX95 Mali/Hantro vendor contract | Foundries `main-imx95-frdm-devel` during integration | Host baseline built; Android vendor product not yet built |

The R13 2 GB and R16 standard ARM64 profiles remain registered capabilities,
but they are not current board-delivery priorities. Do not spend a full build
on either without a customer, product or regression reason.

## Where each build runs

| Work | Location | Output |
| --- | --- | --- |
| Repository policy, manifest and script checks | Developer checkout and GitHub-hosted governance CI | Fast validation only |
| R16 Android/LineageOS images | This repository's GitHub Actions workflow on the CT101 self-hosted runner | `system.img`, board-specific `vendor.img`, lock, build metadata, SBOM, NOTICE and checksums |
| Legacy R13 Android images | `android_vendor_waydroid`'s `lineage-20` GitHub Actions workflow on the self-hosted runner | R13 images and their source/build evidence |
| LmP/Yocto host image | Foundries CI from the machine's manifest branch | Signed/OTA-capable host target and factory artifacts |
| Installation and runtime acceptance | The named physical Jaguar Screen or FRDM machine | Serial/runtime evidence, UI, GPU/media, memory, restart, update and rollback results |

Do not run a full local Android or Yocto image build merely to reproduce the
CI result. Before expensive CI, run the fast repository checks and, for a
Yocto recipe/DT/provider change, the smallest exact-component preflight that
can expose the error. Foundries CI remains the authority for the shipped host
image.

## Fixed build order

1. **Select one product tuple.** Record machine, distro, image, Android
   release, profile, variant, source lock and host manifest branch.
2. **Run fast validation.** Validate manifests, scripts and policy. For host
   changes, compile or parse only the smallest affected Yocto component.
3. **Build Android only when its inputs changed.** Reuse an already verified
   image artifact when the change is host-only.
4. **Build the matching host in Foundries.** Do not substitute a host target
   from the other machine or SoC family.
5. **Pair the artifacts before staging.** Verify the Android artifact identity
   and checksums against the host's expected release metadata. A shared ARM64
   `system.img` does not make a vendor image portable.
6. **Stage on exactly one named machine.** Preserve the currently working
   baseline and a rollback path.
7. **Run integration acceptance.** Require Android boot completion, platform
   service, UI, correct hardware renderer, media path and bounded memory proof.
8. **Promote only after integration passes.** Rebuild the Android ARM64 lane as
   `user`, build the release host, and add OTA/rollback, signing, SBOM, licence
   and vulnerability evidence.

Every `ERROR:` block from Android, BitBake or Foundries CI is part of the build
verdict. Never hide, filter, downgrade or infer success past an error.

## When to trigger each lane

### Jaguar Screen R13 standard

Build only for an approved R13 security/compatibility fix, a customer
qualification request, or a regression check required by a shared change.
Keep the proven target 2887 evidence as the baseline until a complete successor
passes the same screen, Etnaviv and UI checks.

### Jaguar Screen R16 2 GB

The Android `userdebug` pair from run 34856380503 is already built and
checksum-proven. The next build is therefore the Foundries
`r16-jaguar-screen` host, not another Android build. When that target succeeds,
pair it with the existing image artifact and perform the screen acceptance
test. Build the Android `user` variant only after `userdebug` integration
passes.

### FRDM i.MX95 R16

Foundries target 2936 is the current development-host baseline. The next build
is an explicit i.MX95 Android vendor product using the Mali/Hantro contract,
not another generic host and not the i.MX8MM Etnaviv `vendor.img`. The shared
R16 ARM64 system content may be reused only where its ABI is proven. Pair the
new i.MX95 Android artifact with target 2936 or an exact successor, then run
FRDM graphics, media and lifecycle acceptance.

## Promotion vocabulary

| State | Meaning |
| --- | --- |
| **BUILT** | The named CI system produced and retained the expected artifacts |
| **PAIRED** | Android and host metadata/checksums match one product tuple |
| **STAGED** | That pair was installed or selected on the named machine |
| **WORKING** | The required integration checks passed on that machine |
| **RELEASED** | Production variant, signing, OTA/rollback and release evidence were approved |
| **BLOCKED** | A recorded error or failed gate prevents promotion |

Never use **working** for a component that merely built, or **released** for a
development target that merely booted.
