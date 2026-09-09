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
checksums and immutable build metadata with the images. Development
`userdebug` output is evidence for integration only; a production release must
also pass the `user` target and the board acceptance procedure.
Select the `user` i.MX8MM variant when manually dispatching the image workflow;
that path invokes the blocking runtime-SELinux exception decision as well as
the normal neverallow build checks. The default `userdebug` path inventories
the exception but cannot produce production-approved release evidence.
`build-info.json` records the selected i.MX8MM variant, release class and
SELinux gate mode so the Yocto host build can reject an integration artifact
when producing a production image.

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
