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
    "desc": "every DD-NNN packet carries frontmatter status settled/waived/consumed (no open drafts)",
    "enforce": "soft"},
   {"id": "dd-ordering-dag",
    "desc": "optional DD 'after:' ordering references existing DDs, no self-refs, forms a DAG",
    "enforce": "soft"},
   {"id": "dd-waived-or-consumed",
    "desc": "waived DDs carry a reason; consumed DDs are listed by a VD; every DD consumed-or-waived once VDs exist",
    "enforce": "soft"}
 ]}
```

## Requirements (prose — what the checks assert and why)

1. **PD↔DD pairing (`pd-dd-pairing`, live).** Same deterministic existence check as
   design intake (shared serial, RUNTIME-SPEC naming table) — re-asserted here because
   design may have minted new DDs since the last gate.
2. **Every DD closed (`dd-status-settled`, live).** Validation packages settled
   decisions into a build plan; a DD still in `status: draft` (or missing the key) is
   an open decision and bounces the transition back to design. Since B6 the accepted
   statuses are `settled`, `waived`, and `consumed` — the validation-phase vocabulary
   `planning-directives/DD-TEMPLATE.md` reserved. Only `DD-NNN` packets are scanned;
   an empty `DD/` passes with a note.
3. **DD ordering DAG (`dd-ordering-dag`, live since B6).** A DD may declare
   `after: DD-NNN[, DD-NNN…]` (single-line comma list — frontmatter is line-scoped).
   Every reference must exist as a DD packet on disk, self-references are refused,
   and the declared ordering must form a DAG (Kahn-style resolve). No `after:` keys
   anywhere passes with a note.
4. **Waived-or-consumed discipline (`dd-waived-or-consumed`, live since B6).**
   `status: waived` requires a non-empty `waived: <reason>` key; `status: consumed`
   requires some VD to list the DD in its `consumes:`. Full coverage — every DD
   consumed by a VD or explicitly waived — is enforced only once ≥1 VD packet exists
   (the first design→validation entry must be passable before any VD is authored);
   the hard coverage backstop lives at `gates/execution-intake.md`. A malformed VD
   `consumes:` list fails here too — never silently swallowed as "nothing consumed".
   Contract detail: `validation-directives/VALIDATION-SPEC.md`.

Run: `python3 tools/gate-runner.py gates/validation-intake.md [--project DIR]`
Exit 0 PASS / 1 BOUNCE (fix packets, re-run) / 2 BLOCK (runner/template/cursor error).
