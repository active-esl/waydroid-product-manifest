# AESL Android platform lifecycle

Updated: 2026-09-15

## Product-line model

AESL maintains Android R16/LineageOS 23.2 as the preferred core for new
products and long-support CRA engineering. Its support objective is at least
five years for an admitted product release, extended where the documented
expected product lifetime is longer. Android R13/LineageOS 20 is a separate
legacy lane for potential customer compatibility and qualification needs; it
does not become a long-support commitment merely because CI can rebuild it.

Both release lines expose `standard` and `2gb` ARM64 product profiles. The core
owns framework security fixes, common policy, applications, build
reproducibility and release evidence. Each board owns a separate vendor image,
host BSP contract and hardware acceptance record.

```text
reviewed Android/Lineage core
├── Framework x86_64 compatibility lane (development only)
├── ARM64 standard profile
├── ARM64 2 GB profile
├── i.MX8MM Etnaviv/V4L2 vendor contract
└── i.MX95 NXP Mali/Hantro vendor contract
```

ARM64 is an instruction-set boundary, not a hardware compatibility guarantee.
System content may be shared when its ABI is proven, but `vendor.img` is never
promoted between unproven hardware compatibility classes.

The controlled build identity is the tuple:

```text
(Android release, system profile, vendor compatibility class, board profile, build variant)
```

- **System profile** captures architecture and cross-board policy such as the
  2 GB kiosk constraints. Its `system.img` may be reused across i.MX8 and i.MX9
  only when VINTF and runtime evidence prove the boundary.
- **Vendor compatibility class** captures the SoC GPU/VPU/allocator/HAL stack
  and its exact host-kernel ABI. Start with a separate class for each SoC; merge
  classes only after binary and hardware evidence shows them equivalent.
- **Board profile** captures ODM/carrier-board differences such as display,
  touch, audio, camera, radio, firmware and exposed device nodes. A board gets a
  separate vendor/ODM build whenever those differences change Android content.
- **Build variant** keeps `userdebug` integration evidence distinct from the
  production-gated `user` release.

The initial classes are i.MX8MM/Mesa-Etnaviv/V4L2 for Jaguar Screen and
i.MX95/NXP-Mali/Hantro for FRDM i.MX95. Further i.MX8 and i.MX9 SoCs enter as
separate candidate classes; family membership alone is not evidence that an
existing vendor image is reusable.

## Lifecycle records

`config/board-support.json` is the machine-readable register. A board may move
to `supported` only after it records:

- final CRA product classification and documented expected lifetime;
- support start and end dates, never less than five years and longer where the
  expected use is longer;
- exact Android, Lineage, NXP BSP, host kernel and vendor-library revisions;
- licence disposition for every redistributable binary;
- signed boot, runtime, GPU/VPU, memory, suspend/resume and rollback evidence.

CI validates this register before building. A green compile means only that the
source assembled; it does not change board support status.

## Change lanes

1. **Monthly security lane:** ingest Android/Lineage/NXP advisories, triage the
   SBOM, patch the core and affected vendor targets, then rerun board tests.
2. **Board enablement lane:** introduce a thin product and hardware contract;
   do not modify common policy to hide a board-specific failure.
3. **Release lane:** freeze an immutable source lock, build `user`, sign the
   board bundle, test update and rollback, and retain its evidence.
4. **Emergency lane:** use the vulnerability/incident process in
   `CRA-COMPLIANCE.md`; preserve decision times and affected release inventory.

## i.MX95 baseline decision

The OS for FRDM i.MX95 remains AESL's pinned **LineageOS 23.2 / Android R16**
Waydroid build. NXP `android-16.0.0_2.0.0` is a candidate source of
board-specific GPU/media/HAL components, **not** a replacement Android OS or
manifest. Do not treat its proprietary tarball as a prerequisite for every
LineageOS build: first establish which i.MX95 vendor stack the chosen host
kernel and Waydroid container actually require, then gate only those inputs.
The currently scaffolded i.MX95 product deliberately selects NXP Mali and
fails closed without its matching components; that product choice can be
revisited without changing the LineageOS core.

The current hardware-vendor integration candidate is NXP `android-16.0.0_2.0.0`, which exposes
both proprietary Mali/kbase and Mesa/Panthor configurations. The current LmP
host uses the NXP Mali stack, so the first target is deliberately `nxp-mali`.
Moving to Panthor may reduce proprietary coupling, but it requires a coordinated
host-kernel, firmware, allocator and Android-vendor migration with equivalent
acceptance evidence.

The locally available NXP `android-16.0.0_1.2.0` archive is useful for analysis
only. It must not satisfy the `2.0.0` release gate.
