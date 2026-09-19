# FRDM Arm DMA-BUF source audit

This record covers the Android hardware fork pinned for the FRDM i.MX95
LineageOS 23.2 image. The immutable source lock remains the build authority.

| Item | Revision |
| --- | --- |
| Reviewed upstream base | `waydroid/android_hardware_waydroid@9f94eaf967934193724223206f7b421d06f4d891` |
| Locked Active ESL fork | `active-esl/android_hardware_waydroid@b92200ac592ed43acd9f1f1bc41c09bc407b1732` |
| Locked path | `hardware/waydroid` in `locks/lineage-23.2-lock.xml` |
| Comparison | <https://github.com/waydroid/android_hardware_waydroid/compare/9f94eaf967934193724223206f7b421d06f4d891...active-esl:b92200ac592ed43acd9f1f1bc41c09bc407b1732> |

## Reviewed delta

The comparison changes three HWC files with 99 insertions and two deletions:

- `hwcomposer/wayland-hwc.h` adds an explicit Arm gralloc type.
- `hwcomposer/wayland-hwc.cpp` selects that type and binds Wayland
  `linux-dmabuf` version 3 for it.
- `hwcomposer/gralloc_handler.cpp` reads width, height, format, plane stride,
  offset, DRM FourCC, and modifier through Android's public
  `GraphicBufferMapper` metadata API, then imports the first Arm allocation
  plane as a Wayland DMA-BUF.

The delta does not add dependencies, generated binaries, network access, build
scripts, or privileged Android services. Unsupported formats and missing
metadata fail buffer creation with an error rather than aborting the HWC
process or falling back to CPU readback.

## Reproduction

```sh
git clone https://github.com/active-esl/android_hardware_waydroid.git
cd android_hardware_waydroid
git diff --check 9f94eaf967934193724223206f7b421d06f4d891 b92200ac592ed43acd9f1f1bc41c09bc407b1732
git diff --stat 9f94eaf967934193724223206f7b421d06f4d891 b92200ac592ed43acd9f1f1bc41c09bc407b1732
git diff 9f94eaf967934193724223206f7b421d06f4d891 b92200ac592ed43acd9f1f1bc41c09bc407b1732 -- hwcomposer
```

The CI worktree gate verifies every selected project's clean tracked and
untracked state, non-symlinked location beneath the Android worktree, and
locked `HEAD` both before and after source synchronization. This prevents a
persistent runner modification from silently replacing this reviewed delta.
