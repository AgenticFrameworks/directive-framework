---
title: ED Roadmap to Parallel Building — is the directive framework robust enough for headless, near-zero-HITL, parallel autonomous builds?
status: ASSESSMENT
authored_by: Claude (Opus 4.8), at Marsh's request
created: 2026-07-12 UTC
scope: fitness evaluation of the ag-os ED framework as the governance spine for TECHNE's
       headless coding team and its planned parallel-building evolution
related:
  - dev/directive-framework/execution-directives/DESIGN.md            # the framework's own design + self-assessment
  - dev/directive-framework/case-study-odo-bootstrap.md  # the authorization envelope, demonstrated live
  - dev/directive-framework/execution-directives/validate-registry.py # go_basis (ED-063) enforcement today
  - techne: coordshim.py / bridge.py / entrypoint.sh     # the runtime that consumes this framework
---

# ED Roadmap to Parallel Building

**Question posed (Marsh, 2026-07-12):** Is the ED system robust enough *in its design* for
TECHNE to run as an autonomous, headless coding team with little-to-zero human-in-the-loop
(HITL), including the future plan of turning TECHNE into a *parallel* building system?

**One-line verdict:** By design — yes; it is arguably the best-fit framework available, because
it was purpose-built for exactly this problem. As currently *implemented in TECHNE* — not yet:
the design is sound but TECHNE isn't actually running on it, and the specific parts that make
zero-HITL and parallelism *real* (machine-checkable envelope scope, exercised escalation,
cross-directive conflict detection) are the least-built parts. This document records the
evaluation and the concrete roadmap to close the gap.

> Direction decision recorded 2026-07-12: **import-model wins.** ag-os `dev/directive-framework/`
> is the single source of truth; TECHNE consumes it and retires its stale forked copy rather than
> maintaining a divergent one. This doc is written under that decision.

---

## 1. Why the *design* fits headless, near-zero-HITL autonomy

The ED framework's stated reason to exist (`DESIGN.md` §1, opening line) is *"getting correct
builds out of cheap, unreliable, one-shot executor agents … gating execution behind adversarial
review and explicit greenlight."* That **is** the headless-delegation problem. It is not a system
that merely tolerates autonomy; it is one engineered for safe delegation to unreliable executors.
Three load-bearing properties map directly onto "little-to-zero HITL, safely":

### 1.1 The authorization envelope is the correct answer to "zero HITL"
Nobody actually wants *literally* zero human — they want the human touched **only at genuine
authority boundaries**. That is precisely what the envelope model encodes: one explicit GO covers
the "planned interior," and the gate fires only when the system reaches a real boundary (a new
outward surface, a canon contradiction, a red smoke bar).

This is not theoretical. The **odo bootstrap case study** (`case-study-odo-bootstrap.md` §2) is a
live, unplanned demonstration:

1. The agent attempted to create a new remote repo and push — a **new outward surface**, not
   covered by the GO (which authorized executing *planned* changes).
2. The gate caught it, did not route around it, and surfaced the exact command to Marsh.
3. Marsh granted with one word: `push`.
4. *"Every subsequent push to that same remote proceeded without asking — the envelope had
   widened by exactly one surface, on explicit human authority, and the widening is
   attributable."*

That ladder — GO covers the interior, the envelope boundary catches the exterior, a cited human
grant widens it by exactly one surface, and the gate mechanism is never deleted to make progress
— is exactly the headless-but-governed shape TECHNE needs. `go_basis` (ED-063) is the on-ramp: it
makes that authority machine-recorded (`human:<name>` / `delegated:<basis>` / `envelope:<version>`;
see `validate-registry.py:33-40`).

### 1.2 Prose → code enforcement
`DESIGN.md` §6 principle 1: *"Prose is not enforcement."* Watchdogs are `signal.alarm`, results
are atomic writes (`tmp + fsync + os.replace`), concurrency is `flock`, canon drift is a
PreToolUse deny. An unreliable executor honors code, not paragraphs. This is what makes autonomy
*safe* rather than reckless — every rule that matters has migrated (or must migrate) into a
mechanism the executor cannot skim past.

### 1.3 Adversarial cross-vet, false-tick policing, hard-stop-on-red
These are the anti-hallucination / anti-self-deception machinery (`DESIGN.md` §3 rules 2–5, §5.D):
- Cross-vet is **independent and adversarial** — a *different* model re-runs ≥1 load-bearing
  probe against real data and attacks the headline gate.
- **False-tick detection (D4)** — a `[x]` that cites no verifiable body artifact is counted red.
  This is the standout innovation; it attacks the exact failure mode that kills self-audited
  checklists, and it demonstrably forced sketches into implementations.
- **Hard stop on red** — the cheap executor does *not* iterate fixes past a failed smoke bar; it
  writes a defects file and exits. The fix cycle belongs to the ED author.

Together these let you trust a cheap executor's output without a human reading every diff — the
precondition for headless operation.

---

## 2. Where it is *not* robust enough yet (the honest gaps)

1. **The envelope is proven at N=1 and is still an accountability *record*, not an enforcement
   *boundary*.** `validate-registry.py` checks only that `go_basis` is *present as a non-empty
   string* on GREENLIT lines after the cutoff — not that the action falls *within* a declared
   envelope. The canon itself flags this (`case-study-odo-bootstrap.md` §2 design note): *"envelope
   scope must be machine-checkable, which is precisely the envelope-version idea."* Designed, not
   built. For true zero-HITL you need the machine to **auto-approve in-scope and auto-escalate
   out-of-scope**. Today it records *who* authorized, not *whether this specific action was
   authorized*.

2. **TECHNE isn't actually running its autonomy through ED.** `deep_thought` ran the
   PM-autonomous author path (`grantor=pm`, `go_basis=delegated:pm-autonomous`), *outside* ED
   governance (confirmed 2026-07-12: 404 on the ED marker, no `ed:*` labels). `go_basis` is now
   recorded on coordshim greenlights, but as a *field*, not as an *engine* that gates execution.
   TECHNE's live headless autonomy is carried by its own coordshim greenlight — the import-model
   decision is what routes it back onto ED authority.

3. **TECHNE's gates were still partly prose.** The forked `icarus/CLAUDE.md` + `USAGE.md` taught
   PM-autonomous grant in prose — exactly the failure mode `DESIGN.md` §6.1 says gets skimmed.
   (The D2/D5 invariants — reviewer certifies, conductor merges; only the bridge holds the docker
   socket — *are* code-enforced, and are the model to extend.) The import-model update (2026-07-12)
   reframes these to import-first and deprecates the autonomous-author fork.

4. **Escalation coverage is designed but under-exercised.** The canon has the right shape
   (`CHECKLIST.md`: per-item permanent failure → quarantine (dead-letter) + continue + escalate;
   transport/environment failure → stop + retry next drain — *earned from TECHNE's own ED-001 mail
   relay incident*), and TECHNE's `escalate()` exists — but it has never had a live exercise; the
   #8 retry succeeded on the happy path. **Escalation is the real HITL floor**: headless works only
   if the exception surface is well-defined and reliably detected.

---

## 3. Parallel building specifically

ED is fundamentally **per-directive** — it does not natively model N concurrent directives over
shared resources. What helps and what bites:

### 3.1 In your favor
- The registry is **append-only + validated + lock-checked** (ED-060's single locked/validated
  append path kills the ED-033 id-collision class) — a sound serialized substrate for concurrent
  authors.
- **Concurrency hazards are already earned canon.** The `flock`-on-smoke rule exists *because* two
  concurrent smokes raced the atomic write and self-inflicted the rate-limit failures being
  debugged (`DESIGN.md` §5.C). That scar tissue means the framework will not be blindsided by
  parallelism — it has already been burned once and codified the fix.
- **D2/D5 give natural serialization points.** A single conductor merging = no merge-race,
  correct-by-construction.

### 3.2 What parallel will hit
1. **No cross-directive conflict pre-check — the #1 thing to design before scaling width.** ED
   verifies each directive *in isolation*. Two parallel lanes touching the same files only discover
   the collision at merge time (observed live: eames had to rebase PR #11 and resolve `Library.jsx`
   + `api.js`). At width, merge-conflict becomes the *dominant* failure mode and there is currently
   no "will these two in-flight EDs collide" analysis.
2. **Single conductor = throughput bottleneck.** Correct, but it serializes merges; at N lanes it
   caps throughput. Parallelizing it safely requires either partitioned merge lanes (disjoint file
   sets) or a merge queue with conflict detection.
3. **Envelope scoping must become per-lane.** Parallel building multiplies the authority surface;
   a single global envelope lets one lane's autonomy bleed into another's territory. The
   envelope-version idea has to be per-repo-region / per-lane, not global.
4. **Metrics measure quality, not contention.** ED-062 / `METRICS.md` tracks per-directive
   findings, first-run smoke, and cycles-to-green — not queue depth, merge-conflict rate, or lane
   contention, which is what parallel scaling needs to see.

---

## 4. Roadmap — three horizons

The framework does not need a redesign; it needs three specific mechanisms built in order. Each
horizon is independently useful and independently shippable.

### Horizon A — Supervised-headless (essentially where TECHNE is now)
Human at launch + escalation; envelope as an accountability record. #8 proved the happy path
end-to-end (implement → review → certify → merge). **Prerequisite already met.** The import-model
update (below) consolidates governance onto ED so this horizon runs on the canon, not a fork.

Actions (done / in flight 2026-07-12):
- [x] `go_basis` authority column on coordshim greenlights (ED-063 alignment).
- [x] Import path grants `--go-basis delegated:ed:greenlit`; legacy path `delegated:pm-autonomous`.
- [x] **Import-model adopted** — deprecate TECHNE's forked framework docs; point at this canon;
      accept canon tiers (`FULL|CEREMONY`) in coordshim so imported ED tiers don't get rejected.

### Horizon B — Trust-it-unattended (raises the ceiling on "how long can it run alone")
The two mechanisms that turn the envelope from a record into a boundary:
1. **Machine-checkable envelope scope (`envelope:<version>`).** Define an envelope as a bounded,
   versioned authorization: repo(s) + label/queue + action classes + a risk ceiling + an explicit
   outward-surface allowlist. `validate-registry.py` (and, at runtime, the bridge/coordshim gate)
   checks each action *against* the active envelope: in-scope → auto-approve and record
   `go_basis=envelope:<version>`; out-of-scope → auto-escalate with the exact command, exactly as
   odo did by hand. This is the single highest-leverage build for zero-HITL.
2. **Exercise escalation across the failure classes.** Map TECHNE's escalation trigger coverage
   against the canon's quarantine/dead-letter pattern and drive each class at least once (merge
   fail, cert fail, ambiguous requirement, envelope breach, transport failure). Unproven ≠ broken,
   but this is the floor you are trusting when you walk away.

### Horizon C — Parallel building
Build these before widening beyond ~1 lane per repo:
1. **Cross-directive file-overlap detection.** Before dispatching directive B while A is in flight,
   compute the declared file sets (the ED package already names every file it builds — `DESIGN.md`
   §8.1 / checklist F1) and refuse/serialize on overlap. Cheapest early win against the dominant
   parallel failure mode.
2. **Merge queue or partitioned merge lanes.** Replace the single-conductor bottleneck with a
   conflict-aware merge queue, or partition lanes onto disjoint file sets.
3. **Per-lane envelopes** (extends B.1) so each concurrent lane's authority is independently scoped
   and attributable.
4. **Contention metrics** (extends ED-062): queue depth, merge-conflict rate, lane utilization.

---

## 5. Bottom line for the direction decision

This assessment *is* the import-vs-author decision. If ED is to be TECHNE's autonomy engine — and
the design says it is the right one — then the import-model must win: the fork cannot carry headless
governance because (a) its gates were prose, not code, and (b) it was drifting away from the very
canon that is actively hardening the machinery (envelope scope-checking, escalation) that headless
+ parallel depend on. Maintaining a fork of the safety system while the safety system evolves
underneath you is the one path that guarantees the gaps in §2 never close.

**Recorded outcome (2026-07-12): import-model adopted; TECHNE updated to consume this canon.**
Horizon A is essentially in hand. Horizon B (machine-checkable envelope + exercised escalation) is
the next build and the gate to true unattended operation. Horizon C (cross-directive conflict
detection first) is the gate to parallel width.
