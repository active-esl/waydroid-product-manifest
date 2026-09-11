# AESL Waydroid product manifests

This repository owns the reviewed, immutable source manifests used to build
Active ESL Waydroid product images.

## Android 16 baseline

- Android: 16 QPR2
- LineageOS: 23.2
- Waydroid upstream mirror: `waydroid/dev/lineage-23.2`
- AESL integration branch: `active-esl/lineage-23.2-aesl`
- Initial vendor commit: `d39b2f967d7e54642d674030b1bc1310cdb7b93b`
- Product variants: Vanilla x86_64 validation, then Vanilla ARM64

The files under `overlays/lineage-23.2` are bootstrap inputs only. Branch
names are permitted there because the resolver converts the complete checkout
into a flattened manifest containing commit hashes. Product image builds must
consume a reviewed file under `locks/`; they must never build from the
bootstrap overlays.

## Resolve a candidate lock

Run the **Resolve Android 16 source lock** workflow. It synchronises the
LineageOS and Waydroid source graph, writes `lineage-23.2-lock.xml`, and rejects
the result unless every project revision is a full Git commit hash.

Review the workflow artifact before committing it to
`locks/lineage-23.2-lock.xml`. Updating that file is a controlled source-base
change and should be performed independently of an image release.

The **Build locked Android 16 images** workflow refuses to build without that
reviewed lock. It builds the x86_64 compatibility target first and the AESL
i.MX8MM ARM64-only target second, generates an SPDX SBOM for each, and records
the system and vendor NOTICE licence archives, checksums and immutable build
metadata with the images. Development
`userdebug` output is evidence for integration only; a production release must
also pass the `user` target and the board acceptance procedure.
Select the `user` i.MX8MM variant when manually dispatching the image workflow;
that path invokes the blocking runtime-SELinux exception decision as well as
the normal neverallow build checks. The default `userdebug` path inventories
the exception but cannot produce production-approved release evidence.
`build-info.json` records the selected i.MX8MM variant, release class and
SELinux gate mode so the Yocto host build can reject an integration artifact
when producing a production image.

After the x86_64 lane has already passed, select the `imx8mm` build scope to
resume a failed board-image build without repeating the compatibility lane.
The normal release-validation scope remains `all`.

## Framework x86_64 smoke test

Extract the completed workflow's `x86_64/system.img` and `vendor.img` into a
versioned local directory, then point `/etc/waydroid-extra/images` at that
directory. Waydroid 1.6.x discovers custom preinstalled images at this fixed
path; do not pass the local directory to `waydroid init -i`, because `-i`
selects an OTA channel rather than an image path.

After starting the container and user session, run:

```sh
./scripts/framework-x86-runtime-check.sh
```

Android 16 changed both the service-manager wire protocol and Waydroid's
platform interface descriptor. Waydroid 1.6.2 and libgbinder 1.1.43 cannot
open the UI directly. Prepare the reviewed project-local host runtime once,
then use its compatibility launcher for the session and UI:

```sh
./scripts/prepare-waydroid-a16-host.sh
systemd-run --user --collect "$PWD/scripts/waydroid-a16-host" session start
./scripts/waydroid-a16-host show-full-ui
```

The preparation script pins libgbinder 1.1.52 and libglibutil 1.0.82 by exact
commit, installs nothing system-wide, and requires no elevated privileges.

The check records image hashes and compact host/Android diagnostics, requires
Android 16 to finish boot, verifies the AIDL graphics allocator and
SurfaceFlinger GLES state, and rejects common software-rendering fallbacks.
Its timestamped evidence directory is ignored by Git.

The first proven image/host combination is recorded immutably in
`locks/framework-x86-runtime-2026-09-11.json`. NXP deployment must follow
`docs/nxp-board-bringup.md`; in particular, i.MX8MM and i.MX95 have separate
vendor-image and hardware-acceleration acceptance gates.

Google applications, Widevine, native-translation prebuilts, Android TV
Settings and optional Redroid prebuilts are excluded from the AESL Vanilla
source graph. Licence verification remains a release gate before the first
production image.

## CI storage invariant

On the AESL self-hosted runner, all persistent Android and Yocto source trees,
downloads, caches and build outputs must live on the large `/yocto` volume.
Never place them under `/opt/actions-runner/_work` or the runner root volume;
that filesystem is reserved for the small job checkout, diagnostics and logs.
Workflows must preflight `/yocto` capacity before starting a source sync or
build.

The image workflow preserves incremental state deliberately: a repeated lock
skips `repo sync`, a changed lock synchronizes only changed projects, and each
patched project is restored only when its locked revision or ordered patch
series changes. The existing x86_64 cache remains in `out`; i.MX8MM uses the
separate persistent `out-imx8mm` tree so switching architectures cannot evict
the other target's intermediates. `lineage-23.2-source-date-epoch` is fixed for
the release line to prevent lock bookkeeping changes from invalidating Soong.
