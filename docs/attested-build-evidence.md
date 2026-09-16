# Attested build evidence programme

Updated: 2026-09-15
Status: engineering evidence plan; not a CRA conformity assessment or
Declaration of Conformity

This programme turns each active or maintained product tuple into a
cryptographically attributable evidence pack suitable for review during a
Cyber Resilience Act process. An attestation proves the origin and integrity
of named artifacts; it does not prove that those artifacts are secure or that
the product complies with the CRA.

## Evidence pack contract

Every candidate pack must contain or link all of the following for one exact
product tuple:

| Evidence | Required content | Gate |
| --- | --- | --- |
| Product identity | Machine, distro, host image, Android release/profile/variant, source lock and host manifest revision | Exact tuple; no generic ARM64 substitution |
| Android provenance | GitHub OIDC/Sigstore build-provenance attestation covering every subject in `SHA256SUMS` | Verify against `active-esl/waydroid-product-manifest` or the R13 producer repository |
| Android inventory | Artifact-derived SPDX JSON, installed-file lists, system/vendor NOTICE archives and source manifest | Generated from delivered images, not inferred from recipes alone |
| Binary risk | Every prebuilt/closed-source SBOM item linked to origin, hash, licence, function, exposure, maintenance, risk and treatment | No unknown or unaccepted changed binary |
| Vulnerability decision | Scanner results plus reviewed VEX/exploitability, disposition, owner and expiry | No unresolved release-blocking known exploitable vulnerability |
| Host provenance | Foundries target, manifest and layer commits, TUF/OSTree identity, package/image manifest, SBOM and signed checksums | Must describe the host actually paired with Android |
| Pairing record | Android and host hashes, target identity and compatibility metadata | Both halves match the same product tuple |
| Hardware evidence | Boot completion, platform service, UI, renderer, media, memory, restart, update, rollback and recovery | Passed on the named physical machine |
| Product review | Classification, risk assessment, Annex I gap decisions, support period, secure defaults, CVD/Article 14 readiness and approver | Human-controlled CRA engineering evidence gate |

The pack is retained for the product support/technical-documentation period,
not merely the CI artifact's 30-day convenience window.

## Implemented R16 provenance

The R16 image workflow now grants only the additional GitHub permissions
needed to mint an OIDC identity and persist attestations. After a successful
build it passes the generated `SHA256SUMS` to the commit-pinned
`actions/attest` action. The attestation therefore names the images, SPDX and
NOTICE files, installed-file reports, immutable source manifest and build
metadata by digest. Its Sigstore bundle is copied into the uploaded evidence
directory as `provenance.sigstore.json`.

The attestation step is blocking. If it fails, the job fails; the subsequent
`if: always()` upload may preserve diagnostics but must never turn that failure
into a successful verdict.

After downloading the replacement artifact, verify its files and provenance:

```sh
sha256sum --check SHA256SUMS
gh attestation verify arm64_2gb/system.img \
  --repo active-esl/waydroid-product-manifest
```

Repeat `gh attestation verify` for the paired `vendor.img` and inspect the
workflow repository, commit, ref and triggering event in the verification
result. Verification policy must eventually restrict release candidates to
the reviewed workflow on `main`.

## Matrix readiness

| Product lane | Current useful evidence | Missing before CRA process intake |
| --- | --- | --- |
| Jaguar Screen R13 standard | Image run 34838947265 and working target 2887 board evidence | Rebuild release candidate with R13 provenance parity; binary register; vulnerability/VEX review; production signing and OTA/rollback pack |
| Jaguar Screen R16 2 GB | Old run 34856380503 is rejected: its `system.img` is truncated. Prior-pin `userdebug` [run 35076252596](https://github.com/active-esl/waydroid-product-manifest/actions/runs/35076252596) passed checksums and both image attestations were verified | Rebuild the current `93b91e5` device pin, verify and retain its evidence, publish the immutable pair, complete paired host and HIL integration; then rebuild `user` and complete security evidence |
| FRDM i.MX95 R16 | Foundries development host target 2936 and partial Android userspace evidence | Board-specific i.MX95 Android vendor product; Android attestation; exact host export; binary/licence review; full HIL acceptance |
| R13 2 GB | Product definition only | Published workflow lane, full build and all evidence gates |
| R16 standard | Product definition and workflow scope | Full build tied to a named product need, then all evidence gates |

Historical successful runs are not retroactively described as attested. They
remain useful integration evidence. The attestation workflow applies to new
runs after its introduction.

## Remaining implementation order

1. Rebuild the current R16 source lock, verify its checksums and attested
   subjects, and retain the evidence beyond the workflow's convenience
   retention period. Run 35076252596 already passed this gate for the prior pin.
2. Measure each generated SPDX JSON file. GitHub's SBOM predicate input is
   limited to 16 MB; add SPDX-specific attestations only after every selected
   lane is proven to fit or a reviewed smaller delivered-artifact SBOM is
   generated. Never silently skip an oversized SBOM.
3. Add equivalent commit-pinned provenance generation to the R13 producer
   workflow before rebuilding a release candidate.
4. Define and validate the binary-risk register linked to delivered SBOM
   identifiers, starting with the i.MX95 proprietary GPU/media/firmware set.
5. Export a stable Foundries host evidence pack and verify its TUF/OSTree and
   manifest identities. Do not relabel an AESL signature as Foundries builder
   provenance.
6. Add vulnerability scan plus reviewed VEX/exception data with owners and
   expiries; untriaged scanner counts are not a release decision.
7. Add pairing and HIL evidence schemas, then make the complete CRA engineering
   evidence gate blocking for production `user` candidates.

The non-automatable work remains explicit: product classification and scope,
whole-product risk assessment, applicable Annex I decisions, conformity route,
support-period approval, Annex II user information, Annex VII technical file
and any Declaration of Conformity/CE decision.
