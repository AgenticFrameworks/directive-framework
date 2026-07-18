---
title: Directive Framework — Execution Directive (ED) system for ag-os
status: DESIGN (packaged from the cm-memory ED system, assessed 2026-07-02)
origin: ~/Projects/cm-memory — ED-AUTHORING-CHECKLIST.md (created 2026-06-28 from the ED-B build),
        BUILD-ORDER.md, ED-A through ED-D, and the cm-tui ED chains (ED-SMOKEFIX et al.)
authored_by: Oracle
created: 2026-07-02 UTC
---

# Directive Framework

A process framework for getting **correct builds out of cheap, unreliable, one-shot executor
agents** by front-loading all intelligence into a rigorously verified directive document, then
gating execution behind adversarial review and explicit human/lead greenlight.

This doc packages the Execution Directive (ED) system as it evolved in cm-memory (and
transferred to the cm-tui coord build), together with an honest assessment of its strengths,
weaknesses, and the design changes ag-os should make when adopting it.

---

## 1. Problem statement

Delegating builds to subagents fails in predictable ways:

- The executor misreads ambiguous specs and guesses (wrongly) at comparisons, enums, defaults.
- The executor mistypes verbatim strings (session IDs, paths, model names) it had to transcribe.
- Wall-clock budgets estimated from API timings blow up 5x when CLI overhead dominates.
- Prose rules ("stop at 180s", "don't iterate past a red test") are honored by humans, not agents.
- Assumed defaults (vector distance metric, tokenizers, ON CONFLICT semantics) silently differ
  from the design's intent and corrupt every downstream calibration.
- Self-audited checklists rot into false ticks — "will do at build time" dressed up as done.

Every one of these is not hypothetical: each occurred in a cm-memory build session and each
produced a specific, named rule in the framework (see §5, "earned provenance").

## 2. Core concept: the Execution Directive

An **ED is a quasi-dry-run of the real code change** — not a reformatted brainstorm, not a
requirements doc. It contains:

- **Traced call sites and real signatures** — external invocations copied verbatim from
  already-battle-tested code, cited by `file:line`, never re-derived.
- **Probes executed against real data at authoring time** — every risky operation (join, API
  call, parse, schema assumption) is *run* while writing the ED, and the actual output recorded
  in the ED body. "Trace-and-defer to open questions" is banned; that is how misses surface only
  at smoke test.
- **Concrete code blocks and diffs** — the ED body contains the implementation, reviewed before
  any executor sees it.
- **A barred smoke plan** — a numbered list of pass/fail bars the executor runs, each with a
  specific expected value and an actionable failure message.
- **Explicit decisions with rejected alternatives recorded** — a call that was analyzed and
  rejected goes in the ED's decision section; it is never re-surfaced as a live choice.

### Depth tiers

- **FULL** — complete dry-run with real data, diffs, test plan. Any non-trivial build.
- **CEREMONY** — a record-only stub documenting what's being done. Trivial/mechanical changes.

The tier exists so the process never collapses to all-or-nothing: *every* change gets an ED,
but a trivial one costs a paragraph. The authoring agent decides and states the tier; the user
never polices it. This single rule is what kept the system alive — mandatory heavyweight
process gets skipped; mandatory lightweight-when-appropriate process gets followed.

## 3. Lifecycle

```
Brainstorm → ED (dry-run) → Checklist self-walk → Cross-vet review → Reconcile (fixes INLINE)
          → Greenlight (explicit GO) → Executor build + smoke → Trust-but-verify → Post-mortem
```

Rules of the chain:

1. **Never skip the ED.** No brainstorm-to-code shortcuts, ever. The brainstorm informs the ED;
   the brainstorm never IS the ED.
2. **Cross-vet is adversarial and independent.** A different model/agent reviews the ED before
   greenlight, with two mandates: (a) re-run at least ONE load-bearing probe against real data —
   replicate a finding, don't just read prose; (b) attack the headline gate — "steelman an
   executor shortcut: what would fail to catch it?"
3. **Reviewer NEEDS-FIX findings are applied INLINE before greenlight**, never deferred to a
   follow-up. (Observed payoff: applying three reviewer-found defects pre-launch saved a full
   build cycle; a later review found 2 CRITICALs — a silent L2-vs-cosine default and an
   empty-`IN ()` SQL crash — that would have shipped.)
4. **Greenlight is explicit.** Design and probe freely; never build without a GO from the user
   or the lead agent holding delegated user-level authority.
5. **Hard stop on red.** The executor does NOT iterate fixes past a failed smoke bar. It writes
   a defects file and exits. Fix-loops by a cheap executor destroy the audit trail and burn
   budget; the fix cycle belongs to the ED author.
6. **Post-mortem feeds the checklist.** Every new failure mode becomes a checklist item that
   would have caught it (see §5).

## 4. Roles

| Role | Function | Notes |
|---|---|---|
| **Lead / Oracle** | Authors all EDs, owns canon, adjudicates reviews and smoke results, holds delegated greenlight authority | The expensive, high-context agent. Intelligence concentrates here. |
| **Executor / Storm** | One-shot subagent that reads the ED + launch prompt, writes the code, runs the smoke | Cheap model, fresh context per build, treated as an unreliable reader (see §6). |
| **Cross-vet reviewer** | Independent model that adversarially reviews the ED pre-greenlight | Must be a *different* model/channel than the author. |
| **User** | Grants greenlight; is never required to police process tiers or checklist compliance | The framework's contract: rigor is the agents' job. |

The asymmetry is the point: the framework converts a ~$0.09/M one-shot coding model into a
viable build channel because correctness lives in the directive, not the executor.

## 5. The authoring checklist — earned provenance

The single most important design property of the framework: **every checklist rule carries an
"earned by" tag naming the exact session failure that justified it.** Rules are grown from
incidents, never invented aspirationally. A tag is removable only when better evidence
supersedes it. This gives the list postmortem-grade authority — any reader can audit *why* each
rule exists — and it is why the list gets followed rather than skimmed.

The checklist is a **hard stop**: walk it top-to-bottom after authoring, before greenlight.
Every item is ticked with a citation, marked "N/A because X", or the ED is fixed. Never
greenlight with a red item. Append `checklist run: <date>, <result>` to the ED frontmatter.

Source of record: `~/Projects/cm-memory/design/planning/ED-AUTHORING-CHECKLIST.md` (28 items as
of 2026-06-30). Categories, with representative items and the failures that earned them:

### A. Load-bearing dry-runs (run against real data while authoring)
- **Schema probe** — verify type/nullness of every column touched. *(Earned: a timestamp column
  was NULL on 24% of rows.)*
- **Source-row resolution** — every fixture-referenced row resolves with expected content.
- **External call-site copied verbatim** from accepted, battle-tested code; cite `file:line`.
- **Worst-case size probe** — measure `MAX(LENGTH(...))`, not the average. *(Earned: a body cap
  sized for the average truncated the load-bearing claim at char 1913.)*
- **Subprocess WALL time × call count, measured** — never API-reported time. *(Earned twice:
  CLI overhead dominates API time 5x; an estimate from `duration_api_ms` caused a 45-minute
  watchdog runaway.)*
- **Defaults verified, not assumed** — distance metrics, tokenizers, ON CONFLICT, collation:
  explicitly set in DDL/code, or probed and the actual default recorded. *(Earned: a vector
  table without `distance_metric=cosine` silently calibrated every threshold against L2.)*

### B. Spec precision (no ambiguity for the executor)
- Every match/comparison/normalization **pseudocoded explicitly** — prose like "compare by
  synonyms" makes the executor guess, and it guesses wrong.
- Every closed enum ships **≥2 negative examples** ("do NOT extract X because Y").
- Worked examples **cover the non-obvious gold cases** the smoke verifies, not just the headline.
- **Transcription-risk flags** on verbatim strings (IDs, hashes, paths, parameter types) —
  "this exact string must appear verbatim." *(Earned: the executor mistyped a session ID in two
  files.)*
- **Kill rules enforced in code** — a watchdog/`signal.alarm` that actually exits, not prose.

### C. Smoke isolation + observability
- Each bar's failure emits a **specific, actionable message** ("expected Y, got Z, hypothesis"),
  never just "bar X red".
- **Wiring testable before the slow/LLM portion** — cheap path first.
- Each bar **re-runnable in isolation**, or the dependency chain documented.
- Bars with nondeterminism in the loop are **one-directional** ("every run-1 tuple still in
  run-2" beats set-equality when an LLM is involved).
- **Output-shape and IO-boundary invariants explicit** (line-per-input vs only-on-match; every
  INSERT's conflict semantics; mkdir-before-open).
- **Result written ONCE, atomically, at end of run** (tmp + fsync + `os.replace`). *(Earned: a
  stale RED verdict sat on disk 13 minutes after the smoke actually passed elsewhere — an audit
  hazard a less rigorous verify would have shipped.)*
- **Watchdog persists a partial-RED result BEFORE exiting** — a kill that leaves zero evidence
  forces the next cycle to guess what state the run reached.
- **Lockfile (`flock`) — refuse to start if another smoke is in flight.** *(Earned: two
  concurrent smokes raced the atomic write AND doubled subprocess concurrency, self-inflicting
  the rate-limit failures being debugged.)*

### D. Cross-vet
- Reviewer **re-runs ≥1 load-bearing probe** against real data.
- Reviewer **attacks the headline gate adversarially**.
- NEEDS-FIX defects **applied inline before greenlight**.
- **False-tick detection**: a `[x]` MUST cite a body artifact a hostile reader can verify. A
  tick whose body says "will run at greenlight" is a FALSE TICK — re-labeled
  `[ ] deferred-justified` with the gate reason. The reviewer counts false ticks as red.
  *(Observed: one review caught 5 false ticks and forced real implementations — the watchdog,
  atomic-write, and lockfile code exist because a reviewer refused the sketch.)*

### E. Reconciliation with canon
- Run the drift check against any assertion the ED makes about a settled decision — before the
  build, not when the enforcement hook fires mid-launch.
- If the ED contradicts settled canon, append the SUPERSEDES entry FIRST, **scoped narrowly**
  (this call site only). Wide supersessions blow up the canon.
- Status trackers updated to reflect ED state before executor launch.

### F. Executor-proof launch prompt
The launch prompt is what the executor reads FIRST; assume it may misread the ED.
- **Name every file to read; list every file to build.** No "read whatever's relevant."
- **"Hard stop on red — do NOT iterate fixes past a red bar" appears verbatim.**
- **Critical constants duplicated verbatim in the prompt body** (model name, timeouts, caps,
  IDs) so a misread of the ED can't cascade.
- **Wall-clock kill threshold restated with explicit minutes.**
- **Explicit out-of-scope list** — what later directives do, what the executor MUST NOT touch
  (protected stores, sibling modules, canon files).

### Checklist maintenance
1. When a NEW failure mode emerges during a build, add an item that would have caught it.
2. **ag-os amendment (see §8.3):** growth must be paired with consolidation — the origin
   system's "grows monotonically" rule is a decay path.

> **Anti-pattern the checklist exists to kill:** "the design was right, the build just had
> bugs." Post-mortems showed most build bugs were ED-side — a missing probe, an ambiguous spec,
> a missing kill rule. Catching them at authoring time costs a paragraph instead of a
> 45-minute build cycle.

## 6. Design principles (extracted)

1. **Prose is not enforcement.** Every rule that matters migrates into code or hooks: watchdogs
   are `signal.alarm`, results are atomic writes, concurrency is `flock`, canon drift is a
   PreToolUse deny. The origin system learned each of these *after* prose was demonstrably
   ignored. ag-os should start there.
2. **Front-load intelligence; treat the executor as a hostile reader.** The directive plus
   launch prompt must survive a lazy, literal, transcription-error-prone reading.
3. **Run the risky operation while authoring.** A probe deferred is a defect scheduled.
4. **Earned provenance over invented policy.** No rule without a named incident; no incident
   without a rule.
5. **Adversarial, independent verification with false-tick policing.** Self-audit is
   structurally untrustworthy; the reviewer's job is to refuse the dressing.
6. **Tier the ceremony, never skip it.** FULL vs CEREMONY keeps the chain unbroken at near-zero
   cost for trivial changes.
7. **Explicit greenlight; scoped gates.** Probing is always free; building never is.

## 7. Assessment of the origin system (2026-07-02)

### What works

- **Provenance-driven evolution** — the checklist is grown from incidents like a good
  postmortem culture, giving it auditability and authority most process docs never have.
- **False-tick detection (D4)** is the standout innovation; it attacks the exact failure mode
  that kills self-audited checklists, and it demonstrably forced sketches into implementations.
- **Enforcement migrated from prose to code** — the system's clearest learning arc.
- **Cheap executors became viable** — repeated all-bars-green one-shot builds (8/8, 10/10)
  from a bargain-tier model, because correctness lives in the directive.
- **It transferred** — born in the cm-memory slice build, it ran the cm-tui coord chains
  unchanged (same v2 cross-vet-reconcile cycle, green smokes) and is codified as standing
  user-level process. Evidence of a general method, not a one-project ritual.

### What doesn't (the weaknesses ag-os must design against)

1. **Authoring cost approaches build cost, with a lossy copy step.** FULL EDs run 600–1,250
   lines and contain complete, reviewed implementations — which the executor then *re-types*
   into files, reintroducing the very transcription risk the checklist mitigates. When the ED
   already contains the code, prose-to-transcribe instead of files-to-apply is a self-inflicted
   defect channel.
2. **Status drift across parallel trackers.** With status duplicated across README, build-order
   doc, live tracker, and the EDs themselves, contradictions appear *within a single file*
   (observed: a chunk marked both "DESIGN-PENDING / NEXT BUILDABLE" and "shipped" in the same
   doc). The origin system copes with an authority-window rule; the fix is structural (§8.2).
3. **Monotone checklist growth** — 21 → 28 hard-stop items in roughly two days, with growth
   specified and pruning not. A list that only grows eventually gets skimmed, and skimming
   under false-tick pressure produces exactly the false ticks the system polices.
4. **Value asserted, not measured.** Each earned tag evidences its *rule*; nothing measures the
   *system* (defect-escape rate, build cycles per chunk, authoring wall-clock). Deliberately
   deferred in the origin project; ag-os should not inherit the deferral (§8.4).
5. **Reviewer variance unmanaged.** Cross-vet strength floats with whichever model reviews;
   the CRITICAL-finding reviews came from a specific strong channel, not from the process.

## 8. ag-os adaptations (changes from the origin system)

### 8.1 Ship artifacts, not transcription
The ED's code blocks are the reviewed source of truth. The directive package hands the executor
**files/patches to apply** (scaffold dir or unified diffs), and the executor's job narrows to:
apply, wire, run smoke, report. Eliminates the retype channel entirely; checklist item B4
(transcription risk) shrinks to the few strings that genuinely must be typed.

### 8.2 Single source of status, derived views
Directive state (DESIGN / VETTED / GREENLIT / BUILT-GREEN / BUILT-RED / VERIFIED) lives in
**exactly one machine-readable place** (one status file or a directive-registry). README
dashboards and build-order views are *generated* from it, never hand-edited. An
authority-window rule is a coping mechanism, not a fix — don't port it; port generation.

### 8.3 Checklist lifecycle policy
Growth stays incident-driven, but every N additions (suggest N=5) triggers a consolidation
pass: merge overlapping items, demote items whose failure mode is now enforced in code/tooling
(an item enforced by a hook or by §8.1 no longer needs a manual tick), keep the earned tags in
a retired-items appendix. Target: the manual-walk list stays under ~20 items indefinitely.

### 8.4 Measure from day one
Log per directive: tier, authoring wall-clock, review findings by severity, smoke
first-run result, build cycles to green, post-ship defects traced to ED-side vs executor-side.
Cheap to capture at greenlight/verify time; converts §7's "value asserted" gap into a
dashboard. No new tooling required beyond a JSONL append.

### 8.5 Pin the review channel
Cross-vet is a named, versioned channel with a minimum-capability bar, recorded in the
directive frontmatter. If the strong reviewer is unavailable, the directive waits or the lead
explicitly accepts (and records) the downgrade. Review quality must be a property of the
process, not of routing luck.

### 8.6 Keep unchanged
Depth tiers, explicit greenlight, hard-stop-on-red, inline-fix-before-greenlight, executor-proof
launch prompts (F1–F5), load-bearing probes at authoring time (A-category), false-tick policing
(D4), narrow supersessions against canon (E2), post-mortem-feeds-checklist. These are the load-
bearing walls; they carry the origin system's entire track record.

---

## Appendix: source artifacts (cm-memory)

| Artifact | Path |
|---|---|
| Authoring checklist (28 items, earned tags) | `~/Projects/cm-memory/design/planning/ED-AUTHORING-CHECKLIST.md` |
| Ordered build path + per-chunk protocol | `~/Projects/cm-memory/design/planning/BUILD-ORDER.md` |
| Exemplar FULL ED (v2, post-cross-vet, 13 findings inline) | `~/Projects/cm-memory/design/planning/ED-D-supersession.md` |
| Cross-vet defect application log | `~/Projects/cm-memory/design/planning/ED-D-supersession-defects-v2.md` |
| Machine-readable review output | `~/Projects/cm-memory/design/planning/ED-*-review-openrouter.json` |
| Executor launch prompts | `~/Projects/cm-memory/design/planning/ED-C1-launcher.md`, `ED-C2-wiring-launcher.md` |
| Transfer evidence (second repo, same process) | `~/Projects/cm-memory/meta-plan/tui/eds/ED-*/` |
| Process rules as project canon | `~/Projects/cm-memory/CLAUDE.md` (Step 4), `design/planning/SETTLED-LEDGER.md` |
