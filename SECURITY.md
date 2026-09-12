# Security policy

## Reporting a vulnerability

Use GitHub's **Report a vulnerability** action for this repository. Do not open
a public issue for an uncoordinated vulnerability and do not include secrets,
customer data or exploit material in ordinary issues or pull requests.

Include the affected revision or release, reproducible impact, relevant target
and any suggested mitigation. We aim to acknowledge reports within two working
days and will coordinate disclosure after affected releases and customers have
a remediation path.

## Supported scope

`main` controls the maintained AESL Android 16 source lock and release process.
An individual product's security-support period is defined by its signed
release record; repository activity or a successful CI run is not itself a
support declaration. Superseded development locks are retained for provenance
but do not create a separate support commitment.

Reports are triaged into the AESL product-security process. Potentially
exploited vulnerabilities are escalated immediately for CRA Article 14 and
other applicable reporting assessment. This engineering policy is not a
Declaration of Conformity or legal advice.

## Automated review

Pull requests and the scheduled repository security review are assessed by the
AESL Preloop Cloud flows. Preloop findings support human triage; they do not
replace SBOM vulnerability management, binary-risk assessment or product
release acceptance.
