# Review Spec

Review starts only after `gates/review-intake.md` strict-hard passes: no execution directive
may be open. Review emits settled RD packets. `kind: code-review` records security, logic,
reuse/shared-library, unreferenced-archive, and simplification findings. `kind: intent-drift`
is reserved for B10's PD→DD→VD→ED audit. `verdict: changes-requested` never authorizes a direct
patch; it must name a new directive lifecycle in its evidence.

## Intent-drift walk (B10)

For `kind: intent-drift`, the reviewer walks each claimed `PD -> DD -> VD -> ED` chain,
checks the VD's recorded `dd-set-complete` attestation against the actual DD set, and records
in the RD body: the exact packet ids/paths examined, observed implementation evidence, an
`honored` or `drifted` conclusion for each decision, and residual uncertainty. A `drifted`
conclusion or false/unsupported attestation requires `verdict: changes-requested` and a named
new PD/DD/VD/ED remediation route. Review never directly edits the implementation.
