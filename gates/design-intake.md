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
    "desc": "every PD packet validates against the PD template frontmatter",
    "enforce": "soft", "deferred": "B5"},
   {"id": "dd-frontmatter-template",
    "desc": "every DD packet validates against the DD template frontmatter",
    "enforce": "soft", "deferred": "B5"}
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
2. **PD/DD frontmatter shape (deferred to B5).** The PD/DD templates ship with B5
   (planning slice); until then these checks print `DEFERRED(B5)` — visibly deferred,
   never silently passed.

Run: `python3 tools/gate-runner.py gates/design-intake.md [--project DIR]`
Exit 0 PASS / 1 BOUNCE (fix packets, re-run) / 2 BLOCK (runner/template/cursor error).
