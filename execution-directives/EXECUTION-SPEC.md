# Execution Spec — intent-separated chunk synthesis + chain walk-back (boundary B7)

Canon artifact, shipped by ED-008 (Execution rails slice). This is the contract for
the EXECUTION phase's *synthesis* input: how a directive whose implementation must be
**written** (not merely applied) is decomposed into ordered, intent-separated chunks,
each carrying its own coding instruction, and how every such directive opens with a
traced chain walk-back from the VD it consumes back through the DD/PD lineage.
Companion to `RUNTIME-SPEC.md` (layout + naming, settled by ED-001),
`planning-directives/PLANNING-SPEC.md` (the PD/DD contract, shipped by ED-005),
`validation-directives/VALIDATION-SPEC.md` (the VD contract, shipped by ED-007),
`EXECUTOR-SPEC.md` (the glue's apply/synthesis mechanics), and `gates/GATES-SPEC.md`
(the intake-gate ladder, shipped by ED-004).

This document is the definition `EXECUTOR-SPEC.md` (§"Synthesis EDs (aider)") defers
"until B7 defines intent-chunk synthesis". Two kinds of ED reach the executor:

- **Apply EDs** — the implementation already exists as reviewed FILES; the glue copies
  them byte-identically (`mode: copy`/`append`). No coder is in the loop. Most rails
  EDs (ED-004…ED-008 themselves) are apply EDs. This spec does not govern their body.
- **Synthesis EDs** — the implementation must be *written* by the coder (the aider/GPT
  executor, `openrouter/openai/gpt-5.6-sol`). The ED body is decomposed into the
  intent-separated chunks defined below, and the coder is handed one chunk at a time.

## Format version (`format: v2`)

A directive that ships the chunk-synthesis contract declares `format: v2` in its
frontmatter. The gate check `ed-chain-walkback` (`gates/execution-intake.md`, hard,
live since B7) is **format-gated**: a `format: v2` ED must carry a non-empty
`chain-walkback:` frontmatter key; a v1 or absent-format ED predates the contract and
passes with a note. The version is a forward gate, never retro-applied — shipped v1 EDs
(ED-001…ED-008, ED-008 itself authored v1) remain valid unchanged.

The `format:` value is checked **exactly and fail-closed**: the only recognized values
are *absent* / `v1` (predates the contract, chain-walkback not required) and `v2`
(chain-walkback required). Any other non-empty value — a `V2` casing typo, `format: 2`,
a future `v3` this gate has not yet learned — is a hard CheckFail, never a silent
downgrade to v1. A directive that *means* v2 but mistypes the version must not skip the
hard gate on the strength of the typo.

## Chain walk-back (mandatory opener)

Every `format: v2` directive opens — before objective, before context — with a
**chain walk-back**: a traced line from the VD it consumes back through the DDs that VD
packaged and the PDs those DDs decided. It appears in two places, which must agree:

- **Frontmatter** `chain-walkback:` — the trace, conventionally a single line of ids:
  `VD-NNN -> DD-NNN[,DD-NNN…] -> PD-NNN[,PD-NNN…]`. Both its **presence** (a non-empty
  value on a `format: v2` ED) and its **shape** are enforced at execution-intake
  (`ed-chain-walkback`, hard). The shape grammar (machine-checked since ED-011): the
  value is `->`-separated **segments**, each a comma-list of well-formed `(VD|DD|PD)-NNN`
  refs (three digits); at least one segment, at least one ref per segment, no empty
  segment (a leading/trailing/double `->` is a malformed chain, not a trace). The
  trace's *truth* — that those ids exist, that those DDs are the ones the VD actually
  consumes, those PDs their real pairs, and the segments run in pipeline order — is still
  audited at B10 (review phase), exactly like the completeness attestation is
  presence-checked at B7 and truth-audited at B10. The gate asserts the chain is
  *well-formed*, never that it is *true*; a syntactically valid but factually wrong chain
  passes intake and is caught at B10.
- **Section `# 0. Chain walk-back`** — the same chain in prose: which VD, which DDs it
  packaged, which PDs decided them, and one line on why this ED is the faithful
  execution of that validated plan. This is the human-readable half of the same fact.

The walk-back exists so a fresh-context executor can verify, from the directive alone,
that the work it is about to synthesize descends from a settled, validated lineage — not
from an unpackaged idea. A `format: v2` ED with no `chain-walkback:` is refused
fail-closed: an execution with no traced plan is exactly what the VD→ED hard-gate exists
to stop.

## Intent-separated chunks

A synthesis ED's implementation is split into ordered **chunks split BY INTENT** — one
coherent purpose per chunk (a schema, a parser, a check, a wiring seam) — never by
arbitrary line count, file boundary, or token budget. Each chunk is the unit handed to
the coder. The rules:

- **One intent per chunk.** A chunk does one thing a reviewer can name in a sentence
  ("add the `after:` DAG resolver", "wire the new check into the CHECKS registry"). If a
  chunk needs the word "and" to describe, it is two chunks.
- **Ordered, dependency-respecting.** Chunks are a sequence; a later chunk may rely on an
  earlier chunk's output, never the reverse. The order is the build order.
- **Explicit coding instruction per chunk.** Each chunk carries an instruction naming
  both its **architecture** (where the code lives, what it calls, what contract it must
  satisfy — cited `file:line` from §2 Traced context) and its **formatting** (idiom,
  naming, comment density to match the surrounding canon). The coder retypes nothing it
  is not told to; ambiguity is an authoring defect, not a coder decision.
- **Per-chunk dry-run smoke is OPTIONAL and author-specified.** A chunk MAY declare a
  dry-run assertion the coder runs before proceeding (e.g. `py_compile`, a single
  gate-runner invocation). When declared it is a hard local gate; when absent the chunk
  is verified only by the ED's whole-package smoke (§6). The author decides per chunk;
  there is no implicit per-chunk smoke.

## Author ≠ coder doctrine

The capacity that *authors* the directive is never the capacity that *codes* it. In this
system the coder is the glue / the GPT executor (`gpt-5.6-sol` via OpenRouter), driven by
the launch prompt; the author is the orchestrator (Fable). The separation is not advisory:

- The **GREENLIT registry line IS the sign-off.** The coder acts only on a directive whose
  latest registry state is `GREENLIT` with a non-empty `go_basis` (`ed-latest-greenlit`,
  hard). No greenlit line, no synthesis. Authority is checkable from the registry alone
  (`EXECUTOR-SPEC.md` §Authority audit).
- The coder **retypes only the transcription-risk strings** the ED flags (§5) and writes
  only what the chunk instructions specify. It never re-derives design, never invents
  structure the ED did not decompose.
- Author-independence at the validation boundary (VD `author:` ≠ ED `author:`, enforced by
  `vd-dd-consumption`) and coder-independence here are the same principle at two seams: the
  capacity that decided must not be the capacity that rubber-stamps its own decision.

## Check ↔ gate mapping

| Check | Gate | Enforce | Asserts |
|---|---|---|---|
| `cursor-phase-match` | `gates/execution-intake.md` | hard | cursor phase sits at this boundary's source (`validation`) or destination (`execution`); an off-pipeline phase BLOCKs (graduated report→hard at B7) |
| `ed-chain-walkback` | `gates/execution-intake.md` | hard | if the ED md is `format: v2`, frontmatter carries a non-empty `chain-walkback:` that parses as `->`-separated segments of `(VD|DD|PD)-NNN` comma-lists; a v1/absent-format ED passes with a note — presence + **shape** (ED-011), truth audited at B10 |

Both checks are format- and phase-gated presence checks, deterministic and fail-closed.
The synthesis mechanics they front (intent-chunk hand-off, per-chunk coding instructions)
are executed by the orchestrator + coder, not the gate; the gate guarantees a `format: v2`
directive cannot reach the coder without its traced chain, and cannot be intaked from an
off-pipeline cursor phase.

## Out-of-band cutover (B7a)

Flipping `tools/executor-run.sh` to actually CALL `gate-runner.py gates/execution-intake.md`
at its intake step is **B7a/ED-009**, an out-of-band atomic-rename cutover (the executor is
bootstrap-class and self-overwrites via `cp`, a hazard an in-band manifest apply cannot
safely carry). ED-008 ships the rails — the graduated `cursor-phase-match` and the new
`ed-chain-walkback` — but is itself built by the un-flipped glue, which never invokes
execution-intake, so graduating these checks is bootstrap-safe.

## Packet-scan integrity (per-run content snapshot, ED-011)

The intake gates read VD/DD packets many times in one run — one check tallies the
authors, another walks the `consumes:` edges, a third resolves the `after:` ordering.
`_scan_packets` memoizes the packet **list** per `(kind, dir)` so every check in one gate
run shares a single file-set snapshot (the list-TOCTOU close, ED-007). ED-011 closes the
matching **content** TOCTOU: at first scan each packet's `sha256` is snapshotted into an
in-memory sidecar; every later (memoized) read of that packet set re-hashes the same files
and **fails closed** if any packet's bytes drifted — an author flipped, a `consumes:`
rewritten, or a packet deleted — between the first check that read it and a later check
that re-parses it. One gate run therefore sees exactly one immutable packet set, in name
*and* in content.

The snapshot is purely in-memory (no artifact is written — canon purity is untouched) and
rides a sidecar dict, not the `_scan_packets` return value, so the `(name, serial)` tuple
contract every consumer unpacks is unchanged. Like the list-TOCTOU close it fronts, this is
a defense against mid-run mutation, not a cross-run guarantee: what changes *between*
distinct gate invocations is out of scope (that is the registry/cursor's job).

## Exit codes

Gate exit codes are the GATES-SPEC contract: 0 PASS / 1 BOUNCE (soft CheckFail) / 2 BLOCK
(hard CheckFail or GateError, fail-closed). `gates/execution-intake.md` is strict-hard — it
has no soft checks, so any failure is a fail-closed BLOCK (exit 2); a runner/template/canon
error can never masquerade as a pass.
