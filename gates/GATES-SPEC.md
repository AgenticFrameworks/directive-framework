# Gates Spec — phase-boundary intake gates (canon `gates/`)

Canon artifact, shipped by ED-004 (Intake-gate framework, boundary B4). This file is the
CONTRACT for the graduated gate ladder and the machine-readable template format consumed
by `tools/gate-runner.py`. B4 ships the FRAMEWORK (this spec + four intake templates +
the runner); the gates go LIVE at later boundaries — B6 instantiates the design/validation
flow (DD→VD checks + completeness attestation), B7 flips the executor to call the runner
(the "VD→ED hard + ED-dual strict gates live" roadmap row). Until then nothing in
`tools/executor-run.sh` invokes the runner.

## The ladder (Terminology guard — two different "soft"s exist; never conflate them)

Ordered weakest → strongest. `advisory` is listed to define what a phase gate is NEVER.

| Rung | Blocks the transition? | Failure exit | Recovery |
|---|---|---|---|
| **advisory** | **NO — this is the `~/.claude` policy vocab (fail-open). A phase gate is NEVER advisory.** | n/a | n/a |
| **soft-gate (blocking, recoverable)** | YES — fail-closed | 1 (BOUNCE) | bounce-back is recoverable and cheap: nothing has been coded yet; fix the packet, re-run the gate |
| **hard-gate** | YES — fail-closed | 2 (BLOCK) | requires the upstream phase to re-deliver (e.g. a missing/unsettled DD, an absent attestation) |
| **strict-hard** | YES — fail-closed | 2 (BLOCK) | full-packet contract; no discretionary waiver exists — the only path through is satisfying every check |

Templates MUST use the phrase `soft-gate (blocking, recoverable)` verbatim when naming
the soft rung, and MUST reserve `advisory` for the explicitly fail-open, never-a-phase-gate
sense.

## Gate map (one template per phase boundary)

| Boundary | Template | Strength | Notes |
|---|---|---|---|
| (entry into planning) | — none — | — | **planning-start is the sanctioned exception**: entering planning has no intake gate; planning is where packets begin to exist |
| planning → design | `gates/design-intake.md` | soft-gate (blocking, recoverable) | PD↔DD pairing live; PD/DD frontmatter-template checks deferred to B5 |
| design → validation | `gates/validation-intake.md` | soft-gate (blocking, recoverable) | the DD→VD SOFT gate: pairing + every DD `status: settled`; DAG + waived-or-consumed deferred to B6 |
| validation → execution | `gates/execution-intake.md` | strict-hard (dual) | layer 1: VD→ED hard-gate two-layer (deterministic DD-consumption + attestation-PRESENCE — both deferred to B6); layer 2: ED packet strict-hard — fully live NOW |
| execution → review | `gates/review-intake.md` | strict-hard | execution fully closed (no ED latest state in {GREENLIT, BUILT-GREEN, BUILT-RED, REOPENED}); RD packet-shape checks deferred to B9 (FABLE-1 sanctioned) |

The VD→ED two-layer split encodes the deterministic-first axiom (ROADMAP Risk 2):
everything hard-checkable is HARD in code; the un-mechanizable completeness-of-intent
judgment is a **recorded inference** — a registry attestation line whose PRESENCE and
schema the gate checks deterministically, never its truth. Review-phase drift walks
(B10) audit attestations against outcomes.

## Machine-readable template contract

Each gate template carries, as its **first fenced code block tagged `gate-spec`**, a JSON
object (stdlib `json.loads` — no yaml anywhere in the loop):

```
{"gate": "<template filename stem>",
 "strength": "soft-gate | hard-gate | strict-hard",
 "boundary": "<phase>-><phase>",
 "checks": [
   {"id": "<check-id>", "desc": "<human summary>",
    "enforce": "hard | soft | report",
    "deferred": "B5 | B6 | B9"        // optional — sanctioned deferrals only
   }, ...]}
```

Runner semantics (`tools/gate-runner.py`, exit codes below):

- **Unknown check id → BLOCK exit 2** (fail-closed). The runner ships a fixed check
  registry; a template cannot invent checks.
- **`deferred` checks print `DEFERRED(<boundary>)`** — never pass/fail silently. Only
  ids in the runner's sanctioned-deferral registry may carry `deferred`, and the named
  boundary must match; deferring a live check id is itself a BLOCK (a template must not
  be able to silently disable a shipped check).
- **`report` checks print, never affect exit.** The graduation path
  report → soft → hard happens by later EDs editing the template — directive-governed,
  never an ad-hoc edit.
- `gate` must equal the template's filename stem; `strength` must be a ladder rung
  (`advisory` is rejected); `boundary` must be `phase->phase` over the five pipeline
  phases.

## Runner invocation and exit codes

```
python3 tools/gate-runner.py <gates/TEMPLATE.md> [--project DIR] [--id ED-NNN]
python3 tools/gate-runner.py --validate-templates <gates-dir>
```

| Exit | Meaning |
|---|---|
| 0 | PASS — every live blocking check passed |
| 1 | BOUNCE — a soft check failed: transition blocked, recoverable bounce-back |
| 2 | BLOCK — a hard/strict check failed, OR any runner/template/cursor error (fail-closed) |

The runner is READ-ONLY: it writes nothing, takes no lock (smokes that exercise it hold
their own `flock`), and reads project state from `<project>/_directives/` (`registry.jsonl`,
`cursor.json`, `ED/`, `DD/`, `PD/`). Cursor validation shells out to the canonical
validator — `validate-cursor.py <path/to/cursor.json>`, single positional, exit 0/2
(`tools/validate-cursor.py:86-92`) — never a re-derived schema.

## Live vs deferred (as shipped by B4)

Live now: the full ED-packet strict layer of `execution-intake` (id shape, exactly-one
directive file, launch prompt, non-empty package + probes seam, manifest floor mirroring
`tools/executor-run.sh:78-115`, `checklist-run:` recorded, VETTED-before-GREENLIT,
latest==GREENLIT with non-empty `go_basis`, REOPENED-latest refused with the re-greenlight
message, cursor valid + not mid-build), plus `pd-dd-pairing` and `dd-status-settled` on
the soft gates, plus `no-open-execution` on review intake. `cursor-phase-match` ships as
`report` (bootstrap-era cursors legitimately sit mid-pipeline; graduates with B7).

Deferred (printed, never silent): PD/DD frontmatter-template checks → B5;
`vd-dd-consumption`, `vd-attestation-present`, `dd-ordering-dag`,
`dd-waived-or-consumed` → B6; `rd-packet-shape` → B9.

## REOPENED re-entry (codified from ED-003)

A directive whose latest registry state is REOPENED is never waved through execution
intake. Re-entry = a FRESH GREENLIT line whose `go_basis` cites the reopen, appended via
`execution-directives/append-registry.py` after the fix is re-vetted. This codifies the
ED-003-proven cycle and closes B4's inherited item (ED-002 post-mortem d: "decide the
REOPENED→EXECUTE transition explicitly").
