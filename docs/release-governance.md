# AESL Waydroid release governance

The manifest repository is the authoritative release ledger. Device and vendor
repositories provide inputs; their branches or tags cannot independently
declare a supported product release.

## Release identity

Platform releases use annotated, cryptographically signed tags of the form
`aesl-waydroid-platform-16.<minor>.<patch>`. A release record must identify the
exact device, vendor, BSP and Yocto commits even when matching component tags
are also created for navigation.

- `minor` advances for a compatible platform capability or supported-board
  addition.
- `patch` advances for compatible security, reliability or compliance fixes.
- release candidates use a suffix such as `-rc.1` and carry no market-support
  claim.

The current `lineage-23.2-aesl` work is an integration line. Do not create a
production release tag until every blocking gate below is satisfied.

## Blocking release evidence

An approved release record contains or links:

1. the reviewed commit-pinned source lock and reproducible build metadata;
2. production `user` image checksums and retained build provenance;
3. delivered-artifact SPDX or CycloneDX SBOM and NOTICE archives;
4. the binary risk register, licence conclusions and redistribution evidence;
5. board-specific GPU, media, memory, update and rollback acceptance results;
6. vulnerability triage with no unresolved release-blocking findings;
7. CRA classification and Annex I gap status for the complete product; and
8. declared support start/end dates and product-security ownership.

The release approver verifies the tag signature and the immutable evidence
links. A CI success, Preloop review, SBOM generation or tag alone is never a
Declaration of Conformity.

## Maintenance

Security updates are released from the maintained line with traceability to
the affected product releases. Feature support and security support are tracked
separately. Superseded locks, source commits, SBOMs, risk decisions and signed
release records are retained for the full declared support period plus the
applicable technical-documentation retention period.
