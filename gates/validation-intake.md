# Gate — validation-intake (design → validation)

Strength: **soft-gate (blocking, recoverable)** — this is the DD→VD SOFT gate from the
roadmap: it BLOCKS the transition into validation, but the bounce-back is recoverable
and cheap (nothing has been coded yet). Fail-closed, never `advisory` (fail-open) — see
the ladder in `gates/GATES-SPEC.md`: advisory < soft-gate (blocking, recoverable) <
hard-gate < strict-hard.

```gate-spec
{"gate": "validation-intake",
 "strength": "soft-gate",
 "boundary": "design->validation",
 "checks": [
   {"id": "pd-dd-pairing",
    "desc": "every DD-NNN in _directives/DD has a shared-serial PD-NNN in _directives/PD",
    "enforce": "soft"},
   {"id": "dd-status-settled",
    "desc": "every _directives/DD/DD-*.md carries frontmatter 'status: settled'",
    "enforce": "soft"},
   {"id": "dd-ordering-dag",
    "desc": "the declared DD ordering forms a valid DAG",
    "enforce": "soft", "deferred": "B6"},
   {"id": "dd-waived-or-consumed",
    "desc": "every DD is consumed by some VD or carries an explicit waived: <reason>",
    "enforce": "soft", "deferred": "B6"}
 ]}
```

## Requirements (prose — what the checks assert and why)

1. **PD↔DD pairing (`pd-dd-pairing`, live).** Same deterministic existence check as
   design intake (shared serial, RUNTIME-SPEC naming table) — re-asserted here because
   design may have minted new DDs since the last gate.
2. **Every DD settled (`dd-status-settled`, live).** Validation packages settled
   decisions into a build plan; a DD still in `status: draft` (or missing the key) is
   an open decision and bounces the transition back to design. An empty `DD/` passes
   with a note.
3. **DD ordering DAG + waived-or-consumed (deferred to B6).** The VD packet type and the
   completeness attestation arrive with B6 (Design→Validation slice); these checks print
   `DEFERRED(B6)` until then — visibly deferred, never silently passed.

Run: `python3 tools/gate-runner.py gates/validation-intake.md [--project DIR]`
Exit 0 PASS / 1 BOUNCE (fix packets, re-run) / 2 BLOCK (runner/template/cursor error).
