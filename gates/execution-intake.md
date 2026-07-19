# Gate — execution-intake (validation → execution)

Strength: **strict-hard** (DUAL gate). Two layers, both fail-closed, both fully LIVE
since B6:

- **Layer 1 — VD→ED hard-gate, two-layer per ROADMAP Risk 2 (live since B6).** The
  deterministic DD-consumption check (`vd-dd-consumption`: VD packets validate against
  the canon `validation-directives/VD-TEMPLATE.md` packet-spec; consumed DDs exist with
  status settled/consumed; every DD consumed-or-waived, "DD set is unpackaged" when DDs
  exist with zero VDs; VD `after:` ordering is a DAG; VD authors independent of the ED
  author) plus the completeness-attestation PRESENCE check (`vd-attestation-present`:
  a `dd-set-complete` attest line with non-empty `basis` and `risk_accepted` rides a
  valid registry line for the ED — schema only, never truth; B10 audits).
- **Layer 2 — ED packet strict-hard.** The full executor-intake floor, mirrored from
  `tools/executor-run.sh` and tightened with authoring discipline (checklist walk
  recorded, VETTED before GREENLIT, REOPENED re-entry codified).

Ladder context (`gates/GATES-SPEC.md`): advisory < soft-gate (blocking, recoverable) <
hard-gate < strict-hard. A strict-hard gate has no discretionary waiver — the only path
through is satisfying every check.

> **Note (B7/B7a boundary).** B7 (ED-008) ships these execution rails — the graduated
> `cursor-phase-match` (hard) and the new format-gated `ed-chain-walkback`. Flipping
> `tools/executor-run.sh` to actually CALL this runner at execution intake is **B7a/ED-009**
> (an out-of-band atomic-rename cutover, self-overwrite hazard), NOT this ED. ED-008 is
> built by the un-flipped glue, which never invokes execution-intake — so graduating these
> checks is bootstrap-safe (ED-008's own build never runs this gate against itself).

```gate-spec
{"gate": "execution-intake",
 "strength": "strict-hard",
 "boundary": "validation->execution",
 "checks": [
   {"id": "vd-dd-consumption",
    "desc": "VD packets validate against canon VD-TEMPLATE; consumed DDs exist settled/consumed; every DD consumed-or-waived; VD after: DAG; VD authors != ED author",
    "enforce": "hard"},
   {"id": "vd-attestation-present",
    "desc": "dd-set-complete attestation (non-empty basis + risk_accepted) rides a valid registry line for the ED — presence+schema only, never truth",
    "enforce": "hard"},
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
    "desc": "cursor phase must sit at the source (validation) or destination (execution) of this boundary — graduated report->hard at B7",
    "enforce": "hard"},
   {"id": "ed-chain-walkback",
    "desc": "if the ED md is format: v2, frontmatter carries a non-empty chain-walkback: (v1/absent passes) — presence+schema only, truth audited at B10",
    "enforce": "hard"}
 ]}
```

## Requirements (prose — what the live checks assert and why)

1. **VD→ED consumption (`vd-dd-consumption`, live since B6).** The canon
   `validation-directives/VD-TEMPLATE.md` packet-spec loads FIRST (missing/malformed
   canon template = BLOCK, fail-closed, even on a packet-empty project). Every
   `_directives/VD/VD-NNN*.md` packet must satisfy the required keys/patterns, `id`
   equal to the filename serial, no `pair:` key (VDs have no twin), and a non-draft
   status. Every consumed DD must exist on disk with status settled/consumed
   (consuming a waived DD is a contradiction); every DD must be consumed-or-waived —
   DDs with zero VDs anywhere is "the DD set is unpackaged"; a waived DD without a
   non-empty `waived: <reason>` fails here too. VD `after:` ordering must be a DAG.
   Author independence: when VDs exist, the ED directive frontmatter must carry
   `author:` (missing = independence unverifiable, fail-closed) and every VD
   `author:` must differ from it (exact string compare) — the cursor is the
   operational fresh-context mechanism; the gate checks the recorded authors.
   No DD and no VD packets passes with a note. See
   `validation-directives/VALIDATION-SPEC.md`.
2. **Completeness attestation (`vd-attestation-present`, live since B6).** Some
   registry line in the ED's history must carry `attest: "dd-set-complete"` with
   non-empty string `basis` and `risk_accepted` — the keys ride on a VALID state
   line (the append-registry line contract is not evolved). One valid line
   satisfies; malformed attest lines are noted in the detail. PRESENCE + schema
   only, deterministic — the gate never asserts the attestation is TRUE
   (completeness truth is audited at B10). With zero DD packets there is no DD set
   to attest and the check passes with a note.
3. **ED packet floor (mirrors the executor's intake, `tools/executor-run.sh:71-115`).**
   Exactly one directive file for the id (discovery mirrors the `:71` call site;
   `-launch.md` excluded there, `-defects.md` additionally excluded here because the glue
   itself writes it on BUILT-RED); launch prompt present (`:73-74`); package dir
   non-empty and `.probes-complete` seam present (`:77`); `manifest.json` parses with a
   non-empty `apply[]` (each entry `from`/`to`/`mode` copy|append, append markers
   source-carried, relative paths, no control chars) and a relative `smoke` path
   (`:78-115`).
4. **Authoring discipline (tightens the floor).** The ED frontmatter records a non-empty
   `checklist-run:` (the CHECKLIST.md walk happened); the registry history carries a
   VETTED line before the latest GREENLIT (cross-vet is not optional); the LATEST state
   is GREENLIT with a non-empty `go_basis` (greenlight is a registry line, nothing else).
5. **REOPENED re-entry (codified from ED-003).** If the latest state is REOPENED the
   gate BLOCKS with the re-entry path in the message: append a FRESH GREENLIT line whose
   `go_basis` cites the reopen, via `append-registry.py`, after the fix is re-vetted.
   The gate never waves a reopened directive through.
6. **Cursor sanity.** `cursor.json` validates via the canonical
   `validate-cursor.py <path/to/cursor.json>` (exit 0/2); and the cursor must not show
   `role=coder` with a non-null `active_directive` (a build in flight owns the cursor).
   Phase-match is now **hard** (graduated report->hard at B7): the cursor phase must sit
   at `validation` (this boundary's source) or `execution` (its destination); an
   off-pipeline phase BLOCKs.
7. **Chain walk-back (`ed-chain-walkback`, format-gated).** If the ED's directive md
   carries `format: v2` frontmatter, it must also carry a non-empty `chain-walkback:`
   key tracing the VD->DD->PD chain (presence + schema only; the traced chain's TRUTH is
   audited at B10, like the completeness attestation). A v1/absent-format ED predates the
   contract and passes with a note — ED-008 itself is authored v1 and passes here. See
   `execution-directives/EXECUTION-SPEC.md`.

Run: `python3 tools/gate-runner.py gates/execution-intake.md --id ED-NNN [--project DIR]`
Exit 0 PASS / 2 BLOCK (this gate has no soft checks; any error is fail-closed BLOCK).
