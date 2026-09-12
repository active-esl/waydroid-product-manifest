# Contributing

Open changes against `main`. Keep source-lock refreshes separate from build,
policy and documentation changes so provenance remains reviewable.

Every pull request must identify:

- the affected release line, products and boards;
- upstream source and immutable commit for imported changes;
- licence and redistribution impact;
- delivered-artifact SBOM and binary-risk-register impact;
- validation performed and remaining runtime evidence; and
- any use of AI assistance.

Do not introduce mutable source revisions or unregistered binaries. Never put
credentials, customer data or private vulnerability details in a pull request.
Security reports belong in GitHub private vulnerability reporting.

Pull requests are reviewed by the repository owners and the AESL Preloop PR
review flow. Preloop is an additional review plane, not evidence of CRA
conformity. Use `Assisted-by:` for disclosed AI assistance; do not assign AI a
copyright-bearing `Co-authored-by:` trailer.
