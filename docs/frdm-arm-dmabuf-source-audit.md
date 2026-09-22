# FRDM Arm DMA-BUF source audit

This record covers the Android hardware fork pinned for the FRDM i.MX95
LineageOS 23.2 image. The immutable source lock remains the build authority.

| Item | Revision |
| --- | --- |
| Reviewed upstream base | `waydroid/android_hardware_waydroid@9f94eaf967934193724223206f7b421d06f4d891` |
| Locked Active ESL fork | `active-esl/android_hardware_waydroid@d481be79d7d96f790e3ec257bcb7c57e8fe26816` |
| Maintained integration branch | `refs/heads/lineage-23.2-aesl` |
| Commit signature | Verified GitHub merge signature; reviewed source commit `3745e7cd2807539e5f88f758d0e860f13a6a8bd6` has a verified software-key SSH signature |
| Locked path | `hardware/waydroid` in `locks/lineage-23.2-lock.xml` |
| Comparison | <https://github.com/waydroid/android_hardware_waydroid/compare/9f94eaf967934193724223206f7b421d06f4d891...active-esl:d481be79d7d96f790e3ec257bcb7c57e8fe26816> |

## Reviewed delta

The comparison changes four HWC files with 162 insertions and 21 deletions:

- `hwcomposer/wayland-hwc.h` adds an explicit Arm gralloc type.
- `hwcomposer/wayland-hwc.cpp` selects that type and binds Wayland
  `linux-dmabuf` version 3 for it.
- `hwcomposer/gralloc_handler.cpp` reads width, height, format, plane stride,
  offset, DRM FourCC, and modifier through Android's public
  `GraphicBufferMapper` metadata API, then imports the first Arm allocation
  plane as a Wayland DMA-BUF.
- `hwcomposer/hwcomposer.cpp` records the DMA-BUF device and inode beside each
  cached Wayland buffer. If SurfaceFlinger recycles a native handle address,
  the composer now imports the replacement allocation instead of continuing
  to present the stale buffer.
  It also waits for the producer acquire fence before importing a replacement
  DMA-BUF, preventing the i.MX95 Mali/GBM path from retaining the boot frame
  when Android presents its first application surface.

The delta does not add dependencies, generated binaries, network access, build
scripts, or privileged Android services. Unsupported formats and missing
metadata fail buffer creation with an error rather than aborting the HWC
process or falling back to CPU readback.

## Reproduction

```sh
git clone https://github.com/active-esl/android_hardware_waydroid.git
cd android_hardware_waydroid
git verify-commit d481be79d7d96f790e3ec257bcb7c57e8fe26816
git diff --check 9f94eaf967934193724223206f7b421d06f4d891 d481be79d7d96f790e3ec257bcb7c57e8fe26816
git diff --stat 9f94eaf967934193724223206f7b421d06f4d891 d481be79d7d96f790e3ec257bcb7c57e8fe26816
git diff 9f94eaf967934193724223206f7b421d06f4d891 d481be79d7d96f790e3ec257bcb7c57e8fe26816 -- hwcomposer
```

At the source-sync boundaries, the CI worktree gate verifies every selected
project's clean tracked state, non-symlinked location beneath the Android
worktree, and locked `HEAD`. It removes untracked and ignored residue from the
affected locked projects before resyncing them, then repeats the verification.
Tracked local edits remain a hard failure for local and developer builds. On
the dedicated CI runner, the same explicit cleanup authorization inventories
their status, resets the affected project to its current `HEAD`, then schedules
it for `repo sync --force-checkout -d` at the locked revision. This detects persistent runner
source changes before the Android build starts; the immutable lock remains the
authority for every selected project revision.

The CI checkout treats untracked and ignored files inside locked source
projects as disposable residue. Android build products and compiler caches are
configured under the workspace-level `out-*` directories, outside those
project trees. Before removing residue, CI prints `git clean -ndx` output with
the owning project path to the retained build log. Nested untracked Git
repositories are not force-deleted; they remain visible to the final drift gate
and stop the build for manual inspection.
Deletion also requires `AESL_ALLOW_LOCKED_SOURCE_CLEANUP=true` while GitHub
Actions identifies the runner as `esl-proxmox-runner`. The dedicated Android CI
build step sets the switch; local and developer invocations cannot activate it
accidentally and fail closed after printing the same inventory.
