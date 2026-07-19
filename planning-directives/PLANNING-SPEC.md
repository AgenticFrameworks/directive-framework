# Planning Spec — PD/DD packets, pairing, and vault precipitation (boundary B5)

Canon artifact, shipped by ED-005 (Planning slice). This is the contract for the
PLANNING phase's output: paired PD/DD packets in the consuming project's
`_directives/` runtime, and the deterministic adapter that precipitates them from a
biblio research vault. Companion to `RUNTIME-SPEC.md` (layout + naming, settled by
ED-001) and `gates/GATES-SPEC.md` (the intake-gate ladder, shipped by ED-004).

## Packet types and pairing

| Packet | Dir | Role |
|---|---|---|
| `PD-NNN.md` | `_directives/PD/` | Planning Directive — the REASONING TWIN: why the decision was settled. Non-consumable (VD/ED capacities read DDs only). |
| `DD-NNN.md` | `_directives/DD/` | Decision Directive — the settled decision: ONE atomic, self-contained, order-independent action packet. |

Pairing is the RUNTIME-SPEC shared-serial contract: `PD-012` ⇄ `DD-012`, plus a
frontmatter `pair:` cross-link in each. `gates/design-intake.md` enforces the
asymmetry deterministically: a DD without its PD BOUNCES (unexplained decision); a
PD without its DD is planning-in-progress and passes.

## Templates and enforcement (live at design-intake as of B5)

The canon templates `planning-directives/PD-TEMPLATE.md` and
`planning-directives/DD-TEMPLATE.md` each carry a fenced ```packet-spec JSON block:
`{"packet": "PD"|"DD", "required": {<frontmatter key>: <regex>}}`. The gate-runner
checks `pd-frontmatter-template` / `dd-frontmatter-template` (live in
`gates/design-intake.md` since B5; the B5 entries left the sanctioned deferral
registry with this ED) read the CANON template — resolved from the runner's own
location, never the consuming project — and validate every `PD-NNN*.md` /
`DD-NNN*.md` packet:

- required key missing/empty, or value failing `re.fullmatch` against its declared
  pattern -> **CheckFail** (enforce=soft at design-intake -> BOUNCE exit 1: fix the
  packet, re-run; nothing downstream has been built);
- canon template missing, unreadable, without a packet-spec block, with invalid
  JSON, with a wrong `packet` value, or with an uncompilable regex ->
  **GateError** (BLOCK exit 2: the canon is incomplete/malformed — fail-closed,
  never waved through as a packet problem);
- `id` != filename serial, or `pair` != shared serial -> **CheckFail** (the
  RUNTIME-SPEC contract, enforced in code, not per-template patterns);
- non-packet files in `PD/`/`DD/` (names not matching `(PD|DD)-NNN…`) are ignored
  by these checks — deliberately conservative, same posture as `pd-dd-pairing`.

## Precipitation protocol (vault -> runtime)

`tools/precipitate.py` is the deterministic adapter from a biblio research vault
notebook to runtime planning packets:

    python3 tools/precipitate.py <vault-notebook-dir> [--project DIR]

`<vault-notebook-dir>` is the notebook directory containing
`50-design-directives/DD-NN.md` (2-digit per-notebook serials — the vault ladder
contract). Protocol, in order:

1. **Vault is read-only.** The adapter never writes into the vault — "retarget,
   don't rebuild". (Rejected alternative: retargeting biblio itself via
   `BIBLIO_DIR` — the ladder layout and 2-digit ids are baked into the vault's
   own prompts and would violate the 3-digit `(PD|DD)-NNN` runtime contract.)
2. **Serial allocation:** next shared serial = max existing serial across
   `_directives/PD/` + `_directives/DD/` + 1 — allocation can never collide with
   hand-authored packets. 3-digit space; >999 is a hard error.
3. **PD first, then DD**, both via exclusive create (`open 'x'`, ED-003 init
   precedent — precipitation can never clobber runtime state). An orphan PD from a
   mid-pair failure is benign and visible; an orphan DD would bounce at
   `pd-dd-pairing`, which is why the PD leads.
4. **Idempotency:** each precipitated packet records `source:` = the vault DD's
   own `id:` (its vault-relative path). Re-runs skip sources already present in
   `_directives/DD/` — `0 new pair(s)` is the expected steady state.
5. **Packets land `status: draft`.** Settling to `settled` is an explicit
   planning-phase act by the orchestrator/author — `dd-status-settled`
   (`gates/validation-intake.md`) enforces it at design->validation.
6. Vault files not matching `DD-NN.md` are skipped VISIBLY (printed), never
   silently — real vaults contain stray non-contract files.

The DD body is re-homed verbatim (the vault packet already satisfies the atomicity
contract: imperative title, concrete action, one-line rationale, `Done when:`).
The PD is written as a provenance pointer to the vault reasoning ladder.

## Hand-authoring path

Planning that does not come from a vault writes both packets by hand: allocate the
next free shared serial (same max+1 rule), write `PD-NNN.md` (reasoning inline) and
`DD-NNN.md` conforming to the templates. The design-intake checks apply equally to
precipitated and hand-authored packets.

## Exit codes

`precipitate.py`: 0 OK (including an all-skipped idempotent re-run), 2 any error
(fail-closed; a crash can never masquerade as success — `__main__` catch-all).
Gate exit codes are the GATES-SPEC contract: 0 PASS / 1 BOUNCE / 2 BLOCK.
