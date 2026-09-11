# AESL Android platform lifecycle

Updated: 2026-09-11

## Product-line model

AESL maintains one reviewed Android 16/LineageOS 23.2 core and thin board
products. The core owns framework security fixes, common policy, applications,
build reproducibility and release evidence. Each board owns a separate vendor
image, host BSP contract and hardware acceptance record.

```text
reviewed Android/Lineage core
├── Framework x86_64 compatibility lane (development only)
├── i.MX8MM product + Etnaviv/V4L2 vendor contract
└── i.MX95 product + NXP Mali/Hantro vendor contract
```

ARM64 is an instruction-set boundary, not a hardware compatibility guarantee.
System content may be shared when its ABI is proven, but `vendor.img` is never
promoted between SoC families.

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

The current integration candidate is NXP `android-16.0.0_2.0.0`, which exposes
both proprietary Mali/kbase and Mesa/Panthor configurations. The current LmP
host uses the NXP Mali stack, so the first target is deliberately `nxp-mali`.
Moving to Panthor may reduce proprietary coupling, but it requires a coordinated
host-kernel, firmware, allocator and Android-vendor migration with equivalent
acceptance evidence.

The locally available NXP `android-16.0.0_1.2.0` archive is useful for analysis
only. It must not satisfy the `2.0.0` release gate.
