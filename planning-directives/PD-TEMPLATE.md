# PD Template — Planning Directive packet (`_directives/PD/PD-NNN.md`)

A PD is the REASONING TWIN of a DD (RUNTIME-SPEC naming table: shared serial
`PD-012` ⇄ `DD-012`, frontmatter `pair:` cross-link). It records WHY the paired
decision was settled — it is never consumed downstream (non-consumable; VD/ED
capacities read DDs only). A DD with no PD is an unexplained decision and bounces
at design-intake (`pd-dd-pairing`); a PD with no DD is planning-in-progress and
does not block.

For precipitated packets, `tools/precipitate.py` writes the PD as a provenance
POINTER into the source vault notebook — the reasoning ladder already exists there
(10-sections -> 20-findings -> 30-actionables -> 50-design-directives) and is not
duplicated into the runtime. For hand-authored planning, write the reasoning
inline.

## Frontmatter contract (machine-enforced)

The `gates/design-intake.md` check `pd-frontmatter-template` validates every
`_directives/PD/PD-NNN*.md` packet against the fenced block below (patterns are
`re.fullmatch`-anchored). A packet violation BOUNCES the planning->design
transition (soft-gate — fix the packet, re-run); a missing or malformed template
file BLOCKS (canon error, fail-closed — see `planning-directives/PLANNING-SPEC.md`).

```packet-spec
{"packet": "PD",
 "required": {
   "id": "PD-[0-9]{3}",
   "pair": "DD-[0-9]{3}",
   "status": "(draft|settled)",
   "created": "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
 }}
```

Beyond the patterns, the check enforces the RUNTIME-SPEC shared-serial contract in
code: `id` must equal the filename serial (`PD-012*.md` -> `id: PD-012`) and `pair`
must carry the same serial (`pair: DD-012`).

Optional keys (unvalidated unless a pattern is added above): `source` (the vault DD
id — written by precipitate.py), `derived_from` (vault provenance chain), `tags`.

Statuses: `draft` (fresh — precipitate.py always writes this), `settled` (the
paired decision is settled and the reasoning is final). PDs carry no
`waived`/`consumed` states — those are DD validation-phase vocabulary (B6).

## Packet skeleton

    ---
    id: PD-NNN
    pair: DD-NNN
    status: draft
    source: <vault DD id, when precipitated>
    created: YYYY-MM-DDTHH:MM:SSZ
    ---

    # PD-NNN — reasoning for DD-NNN

    <Why this decision was settled: alternatives weighed, constraints that decided
    it, evidence consulted. For precipitated packets this is a pointer to the vault
    notebook ladder; for hand-authored planning, write it here.>
