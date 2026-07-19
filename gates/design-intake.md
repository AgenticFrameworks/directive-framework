# Gate — design-intake (planning → design)

Strength: **soft-gate (blocking, recoverable)** — the transition is BLOCKED on failure,
but the bounce-back is cheap: nothing has been coded; fix the planning packets and
re-run. Fail-closed, never `advisory` (fail-open) — see the ladder in `gates/GATES-SPEC.md`:
advisory < soft-gate (blocking, recoverable) < hard-gate < strict-hard.

```gate-spec
{"gate": "design-intake",
 "strength": "soft-gate",
 "boundary": "planning->design",
 "checks": [
   {"id": "pd-dd-pairing",
    "desc": "every DD-NNN in _directives/DD has a shared-serial PD-NNN in _directives/PD",
    "enforce": "soft"},
   {"id": "pd-frontmatter-template",
    "desc": "every PD packet validates against the canon PD-TEMPLATE packet-spec",
    "enforce": "soft"},
   {"id": "dd-frontmatter-template",
    "desc": "every DD packet validates against the canon DD-TEMPLATE packet-spec",
    "enforce": "soft"}
 ]}
```

## Requirements (prose — what the checks assert and why)

1. **PD↔DD pairing (`pd-dd-pairing`, live).** Planning output is PAIRED packets: each
   Decision Directive `DD-NNN` carries the settled decision, its reasoning twin `PD-NNN`
   the reasoning that produced it — shared serial per the RUNTIME-SPEC naming table
   (`DD-012.md` ⇄ `PD-012.md`). A DD with no PD is an unexplained decision; the gate
   bounces it back to planning. A PD without a DD is planning-in-progress and does not
   block. An empty `DD/` passes with a note (a project may enter design with zero
   settled decisions recorded — the validation gate is where substance is enforced).
2. **PD/DD frontmatter shape (`pd-frontmatter-template` / `dd-frontmatter-template`,
   live as of B5).** Every `PD-NNN*.md` / `DD-NNN*.md` packet validates against the
   fenced ```packet-spec contract in the CANON planning templates
   (`planning-directives/PD-TEMPLATE.md` / `DD-TEMPLATE.md`, resolved from the
   runner's own location): required frontmatter keys present and matching their
   declared patterns (`re.fullmatch`), plus the RUNTIME-SPEC shared-serial contract
   in code (`id` agrees with the filename serial, `pair` carries the same serial).
   A packet violation BOUNCES (soft — fix the packet, re-run). A missing or
   malformed canon template BLOCKS (runner error, fail-closed — canon is
   incomplete; see `planning-directives/PLANNING-SPEC.md`). Non-packet files in
   `PD/`/`DD/` are ignored, same conservative posture as `pd-dd-pairing`.

Run: `python3 tools/gate-runner.py gates/design-intake.md [--project DIR]`
Exit 0 PASS / 1 BOUNCE (fix packets, re-run) / 2 BLOCK (runner/template/cursor error).
