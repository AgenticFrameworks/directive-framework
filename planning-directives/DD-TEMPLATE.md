# DD Template — Decision Directive packet (`_directives/DD/DD-NNN.md`)

A DD is the ATOMIC UNIT of a settled decision: ONE precise, self-contained,
order-independent action packet that a downstream capacity (VD packaging at B6, ED
authoring at B7) can consume on its own — needing no further research run and no
sibling packet to make sense. This mirrors the vault DD contract (biblio ladder
`50-design-directives/DD-NN.md`); `tools/precipitate.py` re-homes vault DDs into
this shape with 3-digit shared serials per RUNTIME-SPEC.

FORBIDDEN: broad thematic buckets (e.g. "Security Protocols", "Container
Configuration") — those are research topics, not directives. If a packet would need
its own research run to execute, it is too broad: split it into separate DDs.

## Frontmatter contract (machine-enforced)

The `gates/design-intake.md` check `dd-frontmatter-template` validates every
`_directives/DD/DD-NNN*.md` packet against the fenced block below (patterns are
`re.fullmatch`-anchored). A packet violation BOUNCES the planning->design
transition (soft-gate — fix the packet, re-run); a missing or malformed template
file BLOCKS (canon error, fail-closed — see `planning-directives/PLANNING-SPEC.md`).

```packet-spec
{"packet": "DD",
 "required": {
   "id": "DD-[0-9]{3}",
   "pair": "PD-[0-9]{3}",
   "status": "(draft|settled|waived|consumed)",
   "created": "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
 }}
```

Beyond the patterns, the check enforces the RUNTIME-SPEC shared-serial contract in
code: `id` must equal the filename serial (`DD-012*.md` -> `id: DD-012`) and `pair`
must carry the same serial (`pair: PD-012`).

Optional keys (unvalidated unless a pattern is added above): `source` (the vault DD
id — written by precipitate.py; its idempotency key), `derived_from` (vault
provenance chain), `tags`.

Statuses: `draft` (fresh — precipitate.py always writes this), `settled` (an
explicit planning-phase act; `dd-status-settled` requires it at design->validation),
`waived` / `consumed` (B6 validation-phase vocabulary — reserved here so the
pattern does not churn when B6 lands).

## Packet skeleton

    ---
    id: DD-NNN
    pair: PD-NNN
    status: draft
    source: <vault DD id, when precipitated>
    derived_from: <vault provenance, when known>
    created: YYYY-MM-DDTHH:MM:SSZ
    ---

    # <Imperative, atomic title — name the action, not a theme>

    <The concrete action, written for a context-starved consumer: exact paths,
    names, values. Self-contained and order-independent.>

    Rationale: <one line — the decision is settled; the reasoning lives in PD-NNN>

    Done when: <observable, checkable condition — never "when it feels done">
