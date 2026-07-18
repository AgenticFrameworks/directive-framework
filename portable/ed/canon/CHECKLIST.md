---
title: ED Authoring Checklist — walked after writing an ED, before greenlight
origin: ported 2026-07-02 from cm-memory ED-AUTHORING-CHECKLIST.md (28 items), pruned and
  generalized for ag-os. Earned-by tags kept verbatim as provenance; merged items carry all
  parent tags. Project-specific values are marked "instantiate per project".
authority: process artifact; grows by incident, consolidates every 5 additions (see
  maintenance rules)
---

# ED Authoring Checklist (post-write, pre-greenlight)

> Every item is a HARD STOP: tick with a citation into the ED body that a hostile reader
> could verify, write "N/A because X", or fix the ED. Never greenlight with a red item.
> A tick whose citation says "will do at build time" is a FALSE TICK — re-label
> `[ ] deferred-justified` with the gate reason; cross-vet counts false ticks as red.
> Record `checklist-run: <date>, <result>` in the ED frontmatter.

## A. Load-bearing probes (run against real data while authoring)

- [ ] **A1 — Data probes.** Every schema element the design touches has type/nullness
  verified against the real store, and every fixture-referenced row resolves with expected
  content. *(Earned, origin cm-memory: a timestamp column NULL on 24% of rows needed a COALESCE fallback;
  a probe found typed prose lived under a different event_type than assumed.)*
- [ ] **A2 — Call sites copied verbatim.** External invocation signatures come from
  accepted, battle-tested code, cited `file:line` — never re-derived. *(Earned, origin cm-memory: the one
  subprocess wrapper that survived unchanged was copied wholesale from a proven file with
  one targeted swap.)*
- [ ] **A3 — Worst-case size probed.** For each input class, measure `MAX(...)`, not the
  average. *(Earned, origin cm-memory: a body cap sized for the average truncated the load-bearing claim at
  char 1913.)*
- [ ] **A4 — Wall time MEASURED, never inner-reported time.** Budget = measured invocation
  wall time × call count / workers. CLI/subprocess overhead can dominate API time 5x.
  Instantiate per project: measure the actual invocation with `time` before writing any
  budget. *(Earned twice, origin cm-memory: a budget from call count alone caused a 45-min runaway; a budget
  from `duration_api_ms` (~10s) met a real wall of 72s and blew a smoke run mid-build.)*
- [ ] **A5 — Defaults verified, not assumed.** Distance metrics, tokenizers, ON CONFLICT,
  collation, sort stability: explicitly set in DDL/code, OR probed and the actual default
  recorded in the ED. *(Earned, origin cm-memory: a vector table without `distance_metric=cosine` silently
  calibrated every threshold against L2 — found CRITICAL at review.)*

## B. Spec precision (no ambiguity for a literal reader)

- [ ] **B1 — Every match/comparison/normalization pseudocoded.** Show the canonical-form
  computation; prose like "compare by synonyms" makes the executor guess, and it guesses
  wrong. *(Earned, origin cm-memory: "use the synonym map" without canonicalize-both-sides shown — executor
  compared raw gold against mapped values.)*
- [ ] **B2 — Example coverage, positive and negative.** Worked examples cover the
  non-obvious cases the smoke verifies (not just the headline), and every closed enum
  carries ≥2 negative examples ("do NOT extract X because Y"). *(Earned, origin cm-memory: two gold atoms
  missed until their case-shapes got worked examples; enum FPs like env-var names until an
  explicit negative list existed.)*
- [ ] **B3 — Transcription risk flagged.** Applies only to strings the executor must
  genuinely type — the implementation ships as files (ED §5), so this is CLI args, launch
  constants, IDs. Flag each "this exact string, verbatim". *(Earned, origin cm-memory: an executor mistyped
  a session ID in two files; a hyphenated dir used as a Python module path; a vtab bound a
  list where the on-disk blob was required.)*
- [ ] **B4 — Kill rules enforced in code.** A watchdog/alarm that actually exits after the
  budget, not prose. Prose stop-rules are honored by humans, not executors. *(Earned, origin cm-memory: "expect
  ~90s" with no kill rule -> 45-min runaway; "STOP at 180s" prose with no watchdog would
  have waited indefinitely on a stalled upstream.)*
- [ ] **B5 — Verbatim-required strings grep-verified against the actual artifact.** When
  a spec or smoke bar requires a string verbatim, run that exact grep against the real
  file while writing it — markdown reflow silently splits phrases across line breaks and
  the failure surfaces only at build. *(Earned, origin ag-os: ED-003's required phrase
  "never build without a GO" wrapped mid-phrase in the portable SKILL.md; smoke bar 4
  went RED and cost a build cycle.)*

## C. Smoke isolation + observability

- [ ] **C1 — Actionable failure messages.** Each bar's failure emits "expected Y, got Z,
  hypothesis" — never just "bar X red". *(Earned, origin cm-memory: one specific unmatched-value message was
  the only useful diagnostic in ~30 min of debugging.)*
- [ ] **C2 — Wiring testable before the slow portion.** File writes, temp dirs, fixture
  loading verified on the cheap path first. *(Earned, origin cm-memory: a file-write bug sat invisible behind
  ~10 LLM calls because the smoke bypassed `main()`.)*
- [ ] **C3 — Bars re-runnable in isolation**, or the dependency chain documented.
  *(Earned, origin cm-memory: a bar crashed reopening a temp dir a prior bar had rmtree'd.)*
- [ ] **C4 — Nondeterminism-tolerant bars are one-directional.** "Every run-1 tuple still
  in run-2" beats set-equality with an LLM in the loop. *(Earned, origin cm-memory: a set-equality bar failed
  on +7 new triples that were mere nondeterminism.)*
- [ ] **C5 — Output-shape + IO-boundary invariants explicit.** Line-per-input vs
  only-on-match stated; every INSERT's conflict semantics explicit; mkdir before open.
  *(Earned, origin cm-memory: one review found three HIGHs in this cluster — ambiguous empty-result lines,
  "UPSERT" prose over plain-INSERT code, an output default under a nonexistent dir.)*
- [ ] **C6 — Result lifecycle: one atomic write; abnormal exits leave evidence.** Full
  result computed in memory, written once via tmp + atomic replace at end of run; any
  watchdog/kill path persists a partial-RED result BEFORE exiting. *(Earned, origin cm-memory: a stale RED
  verdict sat on disk 13 min after the smoke actually passed elsewhere; a watchdog
  `os._exit` left zero on-disk evidence of what state the run reached.)*
- [ ] **C7 — Concurrency lock.** The smoke holds a lockfile (`flock`) and refuses to start
  if another instance is in flight, with an actionable message. *(Earned, origin cm-memory: two concurrent
  smokes raced the atomic write AND doubled subprocess concurrency, self-inflicting the
  rate-limit failures being debugged.)*

## D. Cross-vet (see CROSS-VET.md for the full protocol)

- [ ] **D1 — Independent review completed**: reviewer replicated ≥1 load-bearing probe
  against real data, attacked the headline gate adversarially, and audited ticks for false
  ticks (count reported). *(Earned, origin cm-memory: a reviewer replicated two probes and found three real
  defects self-review missed; another counted five false ticks and forced the watchdog,
  atomic-write, and lockfile code into existence.)*
- [ ] **D2 — Every NEEDS-FIX applied INLINE before greenlight**, never deferred to a
  follow-up. *(Earned, origin cm-memory: three reviewer-found defects fixed pre-launch saved a full build
  cycle; a later review caught 2 CRITICALs that would have shipped.)*

## E. Canon + status

- [ ] **E1 — Canon drift checked; supersessions narrow.** If the project keeps a settled
  ledger, run its drift check against every ED assertion touching it BEFORE launch; a
  contradiction gets its SUPERSEDES entry appended FIRST, scoped to this call site only.
  N/A if no canon exists — say so. Instantiate per project: the drift tool. *(Earned, origin cm-memory: a
  drift flag fired mid-launch and blocked tools; the narrow carve-out that followed kept
  three sibling components on the settled default.)*
- [ ] **E2 — directives.jsonl appended** to reflect this ED's current state before any
  executor launch. It is the only status authority; derived views are never hand-edited.
  *(Earned, origin cm-memory: origin system carried contradictory states within a single hand-edited doc.)*

## F. Executor-proof launch prompt (see LAUNCH-TEMPLATE.md)

- [ ] **F1 — Every file to read named; every file to build/apply listed.** No "read
  whatever's relevant". *(Earned, origin cm-memory: an explicit 4-file read list was fully consumed in the
  executor's first 90 seconds.)*
- [ ] **F2 — "Hard stop on red — do NOT iterate fixes past a red bar" appears verbatim.**
  *(Earned, origin cm-memory: with the rule present, the executor wrote defects.md and exited instead of
  fix-looping; without it, executors iterate past red.)*
- [ ] **F3 — Critical constants duplicated verbatim in the prompt body** (model, timeouts,
  caps, IDs) including the wall-clock kill threshold in explicit minutes — the prompt is
  read FIRST; a misread of the ED must not cascade. *(Earned, origin cm-memory: a launcher that repeated
  every key constant produced a clean one-shot build.)*
- [ ] **F4 — Explicit out-of-scope list.** What later directives do; what the executor
  MUST NOT touch, with paths. *(Earned, origin cm-memory: present in every origin launcher; zero
  sacred-invariant violations across the whole run.)*

---

## Maintenance

1. When a NEW failure mode emerges during a build, add the item that would have caught it,
   tagged `*(Earned, origin ag-os: <incident>)*`. No rule without an incident. The origin
   prefix distinguishes locally-earned evidence from the inherited cm-memory provenance;
   inherited items are first in line for retirement at consolidation passes.
2. Every 5 additions, consolidate: merge overlaps, demote items whose failure mode is now
   enforced by code/tooling/design (keep their tags in a retired appendix below). The walk
   list stays under ~20 items.
3. Remove an earned tag only when better evidence supersedes it.

## Retired items

*(none yet — B-transcription was SCOPED (not retired) by the ship-files-not-prose rule,
ED template §5)*

> **Anti-pattern this list exists to kill:** "the design was right, the build just had
> bugs." Origin post-mortems showed most build bugs were ED-side. Catching them at
> authoring costs a paragraph instead of a build cycle.
