# Getting started

This repository is the entry point for understanding, building and releasing
the AESL Waydroid platform. It is an orchestration repository: the immutable
manifest selects source from the component repositories, GitHub Actions builds
the Android images, and the Foundries/Yocto repositories build the Linux host
that runs them.

Before triggering an expensive build, select the product lane and follow the
fixed order in the [build and promotion plan](build-plan.md). That document is
the authority for what is built locally, in GitHub Actions, in Foundries and on
the physical machines.

## Validate the repository

The lightweight checks need Git, Python 3 and Bash; they do not download the
Android source tree.

```sh
git clone https://github.com/active-esl/waydroid-product-manifest.git
cd waydroid-product-manifest
python3 scripts/test-validate-lock.py
python3 scripts/test-build-resource-policy.py
python3 scripts/validate-board-support.py config/board-support.json
bash -n scripts/*.sh
```

These checks validate repository policy and source-lock structure. They do not
compile Android or prove that an image boots on hardware.

## Build Android R16 / LineageOS 23.2

Use the
[Build Android R16 / LineageOS 23.2 images](https://github.com/active-esl/waydroid-product-manifest/actions/workflows/build-lineage-23.2-images.yml)
workflow on `main`. It runs on the AESL self-hosted Android runner, so a user
needs write access to dispatch it and the runner must be available.

Choose two inputs:

| Input | Use |
| --- | --- |
| `build_scope=all` | Normal release validation: x86_64 plus both ARM64 profiles |
| `build_scope=arm64_standard` | Rebuild only the standard ARM64 profile |
| `build_scope=arm64_2gb` | Rebuild only the constrained ARM64 profile used by Jaguar Screen integration |
| `build_scope=x86_64` | Framework compatibility test |
| `build_scope=x86_64_2gb` | Host-side check of the shared 2 GB Android policy |
| `arm64_variant=userdebug` | Integration and diagnosis; the default |
| `arm64_variant=user` | Production-gated ARM64 build; still requires release and board acceptance |

The workflow always builds from
[`locks/lineage-23.2-lock.xml`](../locks/lineage-23.2-lock.xml). Do not build a
release directly from the mutable bootstrap files under
`overlays/lineage-23.2/`.

Each selected target emits its images, SPDX SBOM, system/vendor NOTICE
archives and checksums. The artifact root also contains `build-info.json`, the
resolved `source-manifest.xml` and `SHA256SUMS`. Keep the whole artifact; a
loose `system.img` is not sufficient release or board-test evidence.

### Local Android builds

The build script is designed for the controlled runner. It requires a large
persistent `/yocto` filesystem, the Android `repo` tool and the host packages
needed by LineageOS/Soong; it rejects workspaces and output directories outside
`/yocto`. For most contributors, dispatching the workflow is the supported
route. The local repository checks above are the appropriate pre-push test.

## Legacy Android R13 / LineageOS 20

R13 remains in
[`active-esl/android_vendor_waydroid`](https://github.com/active-esl/android_vendor_waydroid/tree/lineage-20)
on the `lineage-20` branch. Its
[ARM64 image workflow](https://github.com/active-esl/android_vendor_waydroid/actions/workflows/build-images.yml?query=branch%3Alineage-20)
is separate from the R16 workflow and its outputs must retain R13/LineageOS 20
identity.

The standard ARM64 lane is the currently published R13 workflow. The 2 GB R13
product is registered as a maintained profile, but its workflow input has not
yet been promoted to `lineage-20`; treat it as **NOT RUN**, not as an available
release build.

## Put an image on hardware

An Android image is only one half of a Waydroid product. The Linux host must
provide a compatible Waydroid/libgbinder stack, Binder, cgroups, image-APEX
mount support, GPU/media devices and the board-specific vendor contract.

For the Jaguar Screen i.MX8MM and FRDM i.MX95 paths, follow
[NXP board bring-up](nxp-board-bringup.md). Keep the Android image run, exact
checksums, Foundries target, machine, distro, image, memory profile and build
variant together as one product tuple. Never use an i.MX8MM vendor image as
i.MX95 acceptance evidence.

The current lanes are intentionally separate:

| Machine | Ready now | Still required |
| --- | --- | --- |
| Jaguar Screen i.MX8MM | Proven R13 standard product; built R16 2 GB Android artifacts | Successful R16 screen-host target and a fresh physical-board test |
| FRDM i.MX95 | Successful development host target 2936; shared R16 ARM64 system-image candidate | Board-specific i.MX95 Mali/Hantro vendor image and full hardware acceptance |

See the README's [machine-specific status tables](../README.md#jaguar-screen--imx8mm)
for the exact built, staged and working states.

## What success means

A green image build proves that the recorded source assembled and produced the
expected evidence bundle. It does not prove Android boot completion, UI,
hardware acceleration, media, OTA/rollback, production signing, board support
or CRA conformity. Use the separate image-build and board-test columns in the
[evidence matrix](../README.md#build-and-board-test-status).
