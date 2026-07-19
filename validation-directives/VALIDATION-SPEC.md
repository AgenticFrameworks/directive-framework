# Validation Spec — VD packets, consumption, and attestation (boundary B6)

Canon artifact, shipped by ED-007 (Design→Validation slice). This is the contract
for the VALIDATION phase's output: VD packets in the consuming project's
`_directives/` runtime that package settled DDs into validated build plans, plus
the completeness attestation that rides the registry. Companion to
`RUNTIME-SPEC.md` (layout + naming, settled by ED-001),
`planning-directives/PLANNING-SPEC.md` (the PD/DD contract, shipped by ED-005),
and `gates/GATES-SPEC.md` (the intake-gate ladder, shipped by ED-004).

## Packet type

| Packet | Dir | Role |
|---|---|---|
| `VD-NNN.md` | `_directives/VD/` | Validation Directive — packages a set of SETTLED DDs into ONE validated build plan for the execution capacity (ED authoring at B7). No pair twin: cross-references are `consumes:` DD ids, never `pair:` (refused in code). |

## Template and enforcement (live at execution-intake as of B6)

The canon template `validation-directives/VD-TEMPLATE.md` carries a fenced
```packet-spec JSON block: `{"packet": "VD", "required": {<frontmatter key>:
<regex>}}` — required keys `id`, `status`, `created`, `author`, `consumes`,
`parallelism`. The gate-runner check `vd-dd-consumption` (live in
`gates/execution-intake.md` since B6) loads the CANON template FIRST — resolved
from the runner's own location, never the consuming project — and validates every
`VD-NNN*.md` packet:

- canon template missing, unreadable, without a packet-spec block, with invalid
  JSON, with a wrong `packet` value, or with an uncompilable regex ->
  **GateError** (BLOCK exit 2: the canon is incomplete/malformed — fail-closed,
  even on a packet-empty project, never waved through as a packet problem);
- required key missing/empty, or value failing `re.fullmatch` against its
  declared pattern -> **CheckFail** (enforce=hard at execution-intake -> BLOCK
  exit 2);
- `id` != filename serial, or a `pair:` key present -> **CheckFail** (the
  RUNTIME-SPEC contract plus the no-twin rule, enforced in code);
- non-packet files in `VD/` (names not matching `VD-NNN…`) are ignored —
  deliberately conservative, same posture as the PD/DD checks.

## Consumption vocabulary (`consumes:` / `waived:` / `consumed`)

A VD's `consumes:` is a single-line comma list of DD ids (≥1 — frontmatter is
line-scoped). A DD leaves the open set exactly one of two ways:

- **consumed** — some VD lists it in `consumes:`. The consumed DD must exist on
  disk with status `settled` or `consumed`; consuming a `waived` DD is a
  contradiction and fails.
- **waived** — `status: waived` with a non-empty `waived: <reason>` key; a
  waived DD without a reason fails (soft at validation-intake, hard at
  execution-intake).

Deliberate asymmetry: a DD that is still `status: settled` but IS listed by a
VD's `consumes:` PASSES — flipping the DD to `consumed` is bookkeeping, not a
gate condition. The reverse is a violation: `status: consumed` with no VD listing
it claims a packaging that never happened.

## Coverage (every DD consumed-or-waived)

- `dd-waived-or-consumed` (`gates/validation-intake.md`, soft): full coverage is
  enforced only once ≥1 VD packet exists — the first design→validation entry must
  be passable before any VD is authored. Zero VDs passes with a note.
- `vd-dd-consumption` (`gates/execution-intake.md`, hard): the backstop. DDs
  existing with zero VDs anywhere is "the DD set is unpackaged" — a build plan
  was never packaged, BLOCK. No DDs and no VDs passes with a note (empty
  project). A malformed VD `consumes:` list propagates as a CheckFail at both
  gates — never silently swallowed as "nothing consumed".

## Ordering (`after:` DAG — on DD and on VD)

Both packet kinds may declare optional `after:` — a single-line comma list of
same-kind ids. Every reference must exist as a packet on disk, self-references
are refused, and the declared ordering must form a DAG (Kahn-style resolve). DD
ordering is checked by `dd-ordering-dag` (validation-intake, soft); VD ordering
inside `vd-dd-consumption` (execution-intake, hard). No `after:` keys anywhere
passes with a note. `after:` stays an OPTIONAL key — unvalidated by the
packet-spec patterns, enforced in code only when present.

## Parallelism

Required VD key, vocabulary `sequential | partial | full` — how the plan
tolerates concurrent build (one unit at a time / independent subsets interleave /
all independent). Declared at B6, CONSUMED by the B7 executor; the B6 gate
validates only the vocabulary.

## Completeness attestation (registry protocol)

The second layer of the VD→ED hard-gate (ROADMAP Risk 2). The VALIDATION phase
closes with the VD author attesting that the DD set is completely packaged:

- The attestation RIDES an otherwise-valid registry state line for the ED as
  extra keys — `append-registry.py` / `validate-registry.py` are NOT evolved (a
  bare attest-only line is impossible: the line contract requires id+state+ts).
  Append it by piggybacking on the next legitimate state append (e.g. GREENLIT).
- Schema: `attest: "dd-set-complete"` plus non-empty string `basis` (what was
  reviewed to conclude completeness) and `risk_accepted` (the residual risk being
  accepted). One valid line in the ED's history satisfies; malformed attest lines
  are noted in the check detail, never crash the gate.
- `vd-attestation-present` (`gates/execution-intake.md`, hard) checks PRESENCE +
  schema ONLY — deterministically checkable. It never asserts the attestation is
  TRUE; completeness truth is audited at B10 (review phase). With zero DD packets
  there is no DD set to attest and the check passes with a note.

## Author independence

When any VD exists, the consuming ED's directive frontmatter MUST carry
`author:` — missing means independence is unverifiable and the gate fails
closed. Every VD `author:` must differ from the ED author (exact string
compare): the capacity that packaged the plan must not be the capacity that
authored the ED consuming it. The cursor is the operational fresh-context
mechanism for that separation; the gate checks the recorded authors.

## Check ↔ gate mapping

| Check | Gate | Enforce | Asserts |
|---|---|---|---|
| `dd-status-settled` | `gates/validation-intake.md` | soft | every DD packet status is settled/waived/consumed (B6 extended the accepted set; scan is `DD-NNN` packets only) |
| `dd-ordering-dag` | `gates/validation-intake.md` | soft | DD `after:` refs exist, no self-refs, DAG |
| `dd-waived-or-consumed` | `gates/validation-intake.md` | soft | waived ⇒ reason; consumed ⇒ listed by a VD; full coverage once ≥1 VD |
| `vd-dd-consumption` | `gates/execution-intake.md` | hard | VD packets valid vs canon template; consumed DDs settled/consumed; coverage backstop ("the DD set is unpackaged"); VD `after:` DAG; author independence |
| `vd-attestation-present` | `gates/execution-intake.md` | hard | dd-set-complete attestation present with non-empty basis + risk_accepted |

## Exit codes

Gate exit codes are the GATES-SPEC contract: 0 PASS / 1 BOUNCE (soft CheckFail —
fix packets, re-run) / 2 BLOCK (hard CheckFail or GateError, fail-closed — a
runner/template/canon error can never masquerade as a packet pass).
