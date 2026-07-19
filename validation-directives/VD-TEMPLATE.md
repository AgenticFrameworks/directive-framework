# VD Template — Validation Directive packet (`_directives/VD/VD-NNN.md`)

A VD is the VALIDATION phase's output: it packages a set of SETTLED DDs into ONE
validated build plan that the execution capacity (ED authoring at B7) consumes.
Where a DD is one atomic decision, a VD is the deliberate act of grouping those
decisions into a buildable unit — declaring what it consumes, how VDs order among
themselves, and how much parallelism the plan tolerates.

A VD has NO pair twin (there is no reasoning-twin dir for VDs — the reasoning
lives in the consumed DDs and their PDs). Cross-references are carried by
`consumes:` (the DD ids being packaged), never by a `pair:` key — a `pair:` key
on a VD is refused in code.

## Frontmatter contract (machine-enforced)

The `gates/execution-intake.md` check `vd-dd-consumption` validates every
`_directives/VD/VD-NNN*.md` packet against the fenced block below (patterns are
`re.fullmatch`-anchored). The CANON template loads FIRST: a missing or malformed
template file BLOCKS (GateError, fail-closed — even on a packet-empty project); a
packet violation is a CheckFail (enforce=hard at execution-intake -> BLOCK exit 2).
`gates/validation-intake.md` (`dd-waived-or-consumed`) also reads VD `consumes:`
lists — a malformed list fails there too (soft), never silently swallowed. See
`validation-directives/VALIDATION-SPEC.md`.

```packet-spec
{"packet": "VD",
 "required": {
   "id": "VD-[0-9]{3}",
   "status": "(draft|settled|consumed)",
   "created": "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
   "author": "\\S+",
   "consumes": "DD-[0-9]{3}(,\\s*DD-[0-9]{3})*",
   "parallelism": "(sequential|partial|full)"
 }}
```

Beyond the patterns, the check enforces in code: `id` must equal the filename
serial (`VD-001*.md` -> `id: VD-001`); a `pair:` key is refused (VDs have no
twin); every DD listed in `consumes:` must exist on disk with status
settled/consumed (consuming a waived DD is a contradiction); and `status: draft`
BLOCKS at execution-intake — an unfinished build plan cannot enter execution.

Optional keys (unvalidated unless a pattern is added above): `after:` (single-line
comma list of VD ids, e.g. `after: VD-001, VD-002` — declares VD ordering; every
ref must exist as a VD packet, self-references are refused, the declared ordering
must form a DAG), `tags`.

Statuses: `draft` (fresh — packaging in progress; blocks execution-intake),
`settled` (the build plan is final — required to pass validation->execution),
`consumed` (B7 executor vocabulary — reserved here so the pattern does not churn
when B7 lands).

Parallelism: how the plan tolerates concurrent build — `sequential` (one unit at
a time), `partial` (independent subsets may interleave), `full` (all units
independent). Declared now, CONSUMED by the B7 executor; the B6 gate validates
only the vocabulary.

Author independence: `author:` records who packaged the plan. When any VD exists,
the consuming ED's directive frontmatter MUST carry `author:` and every VD
`author:` must DIFFER from it (exact string compare) — packager and ED author are
different capacities. The cursor is the operational fresh-context mechanism; the
gate checks the recorded authors.

## Packet skeleton

    ---
    id: VD-NNN
    status: draft
    created: YYYY-MM-DDTHH:MM:SSZ
    author: <who packaged this plan — MUST differ from the consuming ED's author>
    consumes: DD-NNN, DD-NNN
    parallelism: sequential
    ---

    # <Imperative title — name the build plan, not a theme>

    <What this plan builds, written for the ED author: which settled decisions it
    packages, the shape of the build, what "validated" means here.>

    Done when: <observable, checkable condition — never "when it feels done">
