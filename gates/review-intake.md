# Gate — review-intake (execution → review)

Strength: **strict-hard** — review begins only when execution is fully closed. Ladder
context (`gates/GATES-SPEC.md`): advisory < soft-gate (blocking, recoverable) <
hard-gate < strict-hard. A strict-hard gate has no discretionary waiver.

```gate-spec
{"gate": "review-intake",
 "strength": "strict-hard",
 "boundary": "execution->review",
 "checks": [
   {"id": "no-open-execution",
    "desc": "no ED latest registry state in {GREENLIT, BUILT-GREEN, BUILT-RED, REOPENED}",
    "enforce": "hard"},
   {"id": "rd-packet-shape",
    "desc": "RD packet validates against the RD template",
    "enforce": "hard", "deferred": "B9"}
 ]}
```

## Requirements (prose — what the checks assert and why)

1. **Execution fully closed (`no-open-execution`, live).** For every ED id in the
   registry, the latest state must be OUTSIDE {GREENLIT, BUILT-GREEN, BUILT-RED,
   REOPENED}: everything either reached VERIFIED or never left the paper states
   (DESIGN/VETTED). A GREENLIT ED is an unfired build; BUILT-GREEN is an unverified
   build; BUILT-RED is an unresolved defect; REOPENED is an open fix cycle — none of
   them may be swept under a review phase.
2. **RD packet shape (deferred to B9).** The Review Directive packet shape is settled at
   B9 by design (FABLE-1 sanctioned deferral); until then the check prints
   `DEFERRED(B9)` — visibly deferred, never silently passed.

Run: `python3 tools/gate-runner.py gates/review-intake.md [--project DIR]`
Exit 0 PASS / 2 BLOCK (this gate has no soft checks; any error is fail-closed BLOCK).
