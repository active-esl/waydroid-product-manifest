# Cyber Resilience Act readiness — AESL Android platform

Assessment date: 2026-09-15
Status: engineering readiness plan; not a declaration of conformity  
Owner: Active ESL product security function (named owner to be assigned)

This is engineering guidance, not legal advice. Final classification,
conformity route and legal obligations must be reviewed for each product placed
on the EU market.

## Scope and classification

The Android/Waydroid platform is a component of a product with digital elements,
not the whole product assessment. Each custom board product must be classified
from its intended purpose and functions before release. Do not inherit a CRA
class from the SoC, Android version, another board or this repository.

Current board classifications remain pending in `config/board-support.json`.
The Framework x86_64 lane is a development compatibility fixture and is not a
released AESL product.

## Support-period policy

Every released product records an expected lifetime and a supported-until date.
The engineering floor is five years from placing on the market. Where a custom
or industrial product is reasonably expected to remain in use longer, its
support period is extended to that documented lifetime. Commercial commitments
must not exceed the availability of critical BSP sources, redistribution rights,
signing custody, CI capacity and replacement hardware without an approved
mitigation plan.

The support commitment covers the complete field-update bundle: host Linux and
kernel, Waydroid runtime, Android system and board-specific vendor image,
firmware, boot chain and AESL applications.

Android R16 / LineageOS 23.2 is the preferred maintained baseline for new
AESL products over that 5+ year engineering horizon. Both its `standard` and
`2gb` ARM64 profiles must remain reproducible and security-fixable from the
same reviewed core. Android R13 / LineageOS 20 is retained separately for
potential legacy customer requirements. Any R13 support commitment requires a
specific product feasibility and lifetime decision; availability of a CI
build alone is not such a commitment.

## Annex I engineering gap register

| Area | Required platform evidence | Current state | Gate |
| --- | --- | --- | --- |
| Secure by default / least privilege | production SELinux, minimal services, no debug credentials, threat model | partial | production `user` image and board threat review |
| No known exploitable vulnerabilities | SBOM-linked vulnerability triage and release decision | SBOM generated; operational ownership pending | named PSIRT owner and monthly evidence |
| Protection of confidentiality/integrity | signed images, verified update chain, secret/key handling | architecture incomplete | production key ceremony and verified deployment |
| Attack-surface reduction | disabled unused packages/interfaces and exposed-port inventory | i.MX8MM profile started | per-board interface inventory |
| Security updates | authenticated update, rollback and recovery | host-managed bundle defined | board update and rollback tests |
| Vulnerability handling | intake, assessment, remediation, disclosure and records | process below is draft | exercised tabletop and contact publication |
| Supply-chain transparency | immutable source lock, artifact-derived SPDX, NOTICE, signed provenance and binary-risk decisions | R16 provenance workflow implemented for future runs; historical runs are checksum-only | verify first attested build, add R13 parity, Foundries host export and binary risk register |
| Security logging | actionable logs without unnecessary personal data | not baselined | logging/privacy specification and retention test |

## Vulnerability and incident runbook

1. Record the report time, reporter, affected product/release and possible
   exploitation; acknowledge through the published security contact.
2. Within the first response window, preserve evidence, identify shipped units
   from immutable release manifests and decide whether the issue is an actively
   exploited vulnerability or severe incident under the CRA.
3. Escalate immediately to the named PSIRT and legal/compliance owner. CRA
   Article 14 reporting applies from 11 September 2026. The operational targets
   are an early warning within 24 hours and full notification within 72 hours;
   the Commission guidance states a final report no later than 14 days after a
   corrective measure is available for an actively exploited vulnerability,
   and within one month for a severe incident.
4. Develop and review the smallest supported fix across every affected layer.
   Rebuild from the reviewed lock, issue a new SBOM, sign the complete board
   bundle, test update and rollback, and preserve evidence.
5. Notify affected users through the product's approved channel with impact,
   mitigation and update instructions. Coordinate vulnerability disclosure and
   record any justified delay.
6. Close only after deployment coverage is measured, residual risk is accepted
   by the named owner, and the technical file and support register are updated.

Run a tabletop before the first pilot release and at least annually thereafter.
The runbook must include ENISA/SRP operational access and named out-of-hours
contacts; repository text alone is not proof the reporting path works.

## Release evidence pack

The machine-verifiable pack contract and matrix gaps are maintained in
[`attested-build-evidence.md`](attested-build-evidence.md). Attestation is an
integrity/provenance control within this pack, not a conformity verdict.

Each board release retains, for the required technical-file period:

- immutable source manifest and reviewed change record;
- SPDX SBOM plus system/vendor NOTICE archives and binary licence decisions;
- signed hashes for Android, vendor, host, bootloader and firmware artifacts;
- vulnerability scan/triage with accepted-risk owner and expiry;
- secure-boot/update/rollback results and recovery procedure;
- cold boot, restart, suspend/resume, GPU/VPU and memory acceptance reports;
- CRA classification, risk assessment, support dates and user-facing security
  update instructions.

## Authoritative references

- Regulation (EU) 2024/2847 (official text):
  https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202402847
- European Commission CRA reporting guidance:
  https://digital-strategy.ec.europa.eu/en/policies/cra-reporting
- European Commission implementation timeline:
  https://digital-strategy.ec.europa.eu/en/factpages/cyber-resilience-act-implementation
