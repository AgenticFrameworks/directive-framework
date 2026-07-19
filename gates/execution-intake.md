# Gate — execution-intake (validation → execution)

Strength: **strict-hard** (DUAL gate). Two layers, both fail-closed:

- **Layer 1 — VD→ED hard-gate, two-layer per ROADMAP Risk 2:** the deterministic
  DD-consumption checks plus the completeness-attestation PRESENCE check. Both arrive
  with B6 (the VD packet type does not exist yet) and print `DEFERRED(B6)` until then.
- **Layer 2 — ED packet strict-hard: fully LIVE now.** The full executor-intake floor,
  mirrored from `tools/executor-run.sh` and tightened with authoring discipline
  (checklist walk recorded, VETTED before GREENLIT, REOPENED re-entry codified).

Ladder context (`gates/GATES-SPEC.md`): advisory < soft-gate (blocking, recoverable) <
hard-gate < strict-hard. A strict-hard gate has no discretionary waiver — the only path
through is satisfying every check.

```gate-spec
{"gate": "execution-intake",
 "strength": "strict-hard",
 "boundary": "validation->execution",
 "checks": [
   {"id": "vd-dd-consumption",
    "desc": "every DD referenced by a VD exists and is settled; every DD consumed or waived",
    "enforce": "hard", "deferred": "B6"},
   {"id": "vd-attestation-present",
    "desc": "dd-set-complete attestation line present in the registry with valid schema",
    "enforce": "hard", "deferred": "B6"},
   {"id": "ed-id-shape",
    "desc": "directive id fullmatches ED-[0-9]{3}",
    "enforce": "hard"},
   {"id": "ed-md-exactly-one",
    "desc": "exactly one _directives/ED/<id>*.md excluding -launch.md/-defects.md",
    "enforce": "hard"},
   {"id": "ed-launch-exists",
    "desc": "launch prompt _directives/ED/<id>-launch.md present",
    "enforce": "hard"},
   {"id": "ed-package-nonempty",
    "desc": "package dir _directives/ED/<id>.files/ exists and is non-empty",
    "enforce": "hard"},
   {"id": "ed-probes-complete",
    "desc": "<id>.files/.probes-complete seam present (probes durable on disk)",
    "enforce": "hard"},
   {"id": "ed-manifest-floor",
    "desc": "manifest.json parses and meets the executor apply[]+smoke floor",
    "enforce": "hard"},
   {"id": "ed-checklist-run",
    "desc": "ED frontmatter records a non-empty checklist-run:",
    "enforce": "hard"},
   {"id": "ed-vetted-before-greenlit",
    "desc": "registry history carries a VETTED line before the latest GREENLIT",
    "enforce": "hard"},
   {"id": "ed-latest-greenlit",
    "desc": "latest registry state is GREENLIT with non-empty go_basis; REOPENED refused with re-greenlight path",
    "enforce": "hard"},
   {"id": "cursor-valid",
    "desc": "cursor.json validates via tools/validate-cursor.py",
    "enforce": "hard"},
   {"id": "cursor-not-mid-build",
    "desc": "cursor is not role=coder with an active directive (no build in flight)",
    "enforce": "hard"},
   {"id": "cursor-phase-match",
    "desc": "cursor phase vs gate boundary (report-only in B4; graduates with B7)",
    "enforce": "report"}
 ]}
```

## Requirements (prose — what the live checks assert and why)

1. **ED packet floor (mirrors the executor's intake, `tools/executor-run.sh:71-115`).**
   Exactly one directive file for the id (discovery mirrors the `:71` call site;
   `-launch.md` excluded there, `-defects.md` additionally excluded here because the glue
   itself writes it on BUILT-RED); launch prompt present (`:73-74`); package dir
   non-empty and `.probes-complete` seam present (`:77`); `manifest.json` parses with a
   non-empty `apply[]` (each entry `from`/`to`/`mode` copy|append, append markers
   source-carried, relative paths, no control chars) and a relative `smoke` path
   (`:78-115`).
2. **Authoring discipline (tightens the floor).** The ED frontmatter records a non-empty
   `checklist-run:` (the CHECKLIST.md walk happened); the registry history carries a
   VETTED line before the latest GREENLIT (cross-vet is not optional); the LATEST state
   is GREENLIT with a non-empty `go_basis` (greenlight is a registry line, nothing else).
3. **REOPENED re-entry (codified from ED-003).** If the latest state is REOPENED the
   gate BLOCKS with the re-entry path in the message: append a FRESH GREENLIT line whose
   `go_basis` cites the reopen, via `append-registry.py`, after the fix is re-vetted.
   The gate never waves a reopened directive through.
4. **Cursor sanity.** `cursor.json` validates via the canonical
   `validate-cursor.py <path/to/cursor.json>` (exit 0/2); and the cursor must not show
   `role=coder` with a non-null `active_directive` (a build in flight owns the cursor).
   Phase-match is `report` in B4 — bootstrap-era cursors legitimately sit mid-pipeline;
   it graduates to enforce when B7 flips the executor onto this runner.

Run: `python3 tools/gate-runner.py gates/execution-intake.md --id ED-NNN [--project DIR]`
Exit 0 PASS / 2 BLOCK (this gate has no soft checks; any error is fail-closed BLOCK).
