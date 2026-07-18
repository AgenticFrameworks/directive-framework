# Prompt for Claude Design: "Kanban-of-Kanbans" cockpit for a project-build pipeline

**Build a conceptual UI. I'll drive the real design logic later — I want the idea visualized, not implemented.**

## What the system is

An end-to-end **build pipeline** that takes a half-baked idea and drives it to a shipped deliverable, with hard **phase boundaries** between stages. The governing rule: work done outside its current phase is *pointless by construction* (it has no downstream consumer). So the UI's entire job is to make **"what phase is this in, and what's the gate to the next phase"** spatially obvious.

Two doctrines the UI should embody everywhere:
- **Consumer-owns-done:** a phase/artifact isn't finished when its author feels done — it's finished when it passes the *next* phase's intake test.
- **Typed artifacts + context starvation:** each phase hands the next only a finished, typed artifact. Upstream (idea→plan→design) is interactive human convergence; downstream (execute) is delegable to agents consuming a frozen directive. An artifact with no consumer is visibly inert.

The UI is **recursive Kanban**: board → phase → work-item → sub-board. Every level zooms in. A persistent **side-chat** binds to whatever card is focused and is where the work actually happens; the board is the spatial map of where everything stands.

---

## LEVEL 1 — Master board: the pipeline phases as columns

These mirror the real directory structure. Cards flowing left→right are work items (an idea, a feature, a change) advancing through the pipeline; a card can only advance when it clears the boundary gate into the next column.

| Column (phase) | Dir | Holds | Build state |
|---|---|---|---|
| **PLAN** | `planning-directives/` | idea → plan convergence **+ the research desk** (see Level 2A) | partially designed |
| **DESIGN** | `design-directives/` | plan → design; architecture, design axioms | stub |
| **VALIDATE** | `validation-directives/` | design → validation intake test | stub |
| **EXECUTE** | `execution-directives/` | the fully-built engine: the **ED (Execution Directive)** system | **LIVE** |
| **REVIEW** | `review-directives/` | verify + post-mortem; failures feed back as checklist items | stub |

**Show the asymmetry, don't hide it:** EXECUTE is a live, richly-built slice; PLAN is partially built; DESIGN and REVIEW are scaffolded-but-empty ("intake test undesigned"). A stub column should read visibly differently from a live one.

---

## LEVEL 2A — PLAN drill-down: Ideation + Research desk

Opening PLAN reveals a two-lane board: an **Ideation** lane and a **Research** lane. The Research lane drives a real, already-built apparatus (the "biblioteca") — not a placeholder.

**Tiered research front door.** Research is four escalating pipelines; the user picks (or auto-routes to) the right tier per question. A research card carries its **tier** the way an ED carries its tier. Make the cost/depth tradeoff visible so nobody pays a deep price for a shallow question.

| Tier | Pipeline | Cost | Files to vault? |
|---|---|---|---|
| **Tier 0 — Recall** | answer from settled vault state | near-zero | reads existing |
| **Tier 1 — Quick lookup** | one live web call | low | no |
| **Tier 2 — Biblio** | headless researcher; files + indexes result | medium | yes |
| **Tier 3 — Deep pipeline** | 4-pass checkpointed: *enhance → deep-research → briefing digest → agent classifies into vault* | high | yes, deeply |

**The vault as a staged sub-Kanban.** Behind the tiers, research artifacts flow through their own left→right pipeline, exactly like EDs on the execute board:

`00-sources → 10-topics → [REVIEW GATE] → 30-findings → 40-actionables`

Each stage is a column; each card is a source/topic/finding with a status badge. The **REVIEW GATE** is a real boundary (mirrors ED cross-vet): a finding is only `settled` after clearing it — interactive review with the user, or adversarial self-review if run autonomously. A **gotchas** shelf (one card per landmine/incident) feeds both directions: into findings, and downstream as candidate checklist items for EXECUTE.

**Tier 3 is itself a drill-down.** Click a deep-pipeline card → its own board of the 4 passes as stages, each **checkpointed and resumable** (done-markers per pass) — a long run shows which pass it's on and resumes from where it stopped. A grounding source feeds the run, but an **agent assembles the deliverable**; the raw summary is never the final artifact. Show that handoff: "grounding → assembled finding."

**Consumer-owns-done, applied to research** (this is the wire into the rest of the pipeline): a finding is "done" only when a downstream author can **cite it as a probe** — it answers "what's risky here / what's already settled" for the thing being planned. Let a research card be **pinned to** the idea/ED that consumes it, so provenance shows: "ED-013 probes X because finding F-042 flagged it." An unpinned finding reads as inert.

---

## LEVEL 2B — EXECUTE drill-down: the ED lifecycle

EXECUTE is the fully-designed phase — model its drill-down richly. It's a mini-pipeline of its own:

`AUTHOR → CHECKLIST → CROSS-VET → GREENLIGHT → EXECUTE → VERIFY`

Each card is an **ED** (e.g. "ED-012: registry-schema validator") carrying live state (`DESIGN | VETTED | GREENLIT | BUILT-GREEN | BUILT-RED | VERIFIED`), a **tier** (`FULL` = full dry-run / `CEREMONY` = one-paragraph stub), a review-channel, and metrics (findings count, cycles-to-green, wall-clock, post-ship defects). State is **append-only and auditable** — nothing is silently rewritten; the dashboard is *derived*, never hand-edited.

**It recurses again.** Click an ED card → *its* board:
- **CHECKLIST** → one card per checklist item: tick / "N/A because X" / flag red (hard-stop).
- **CROSS-VET** → one card per reviewer finding (critical / high / false-tick), each resolvable.
- **EXECUTE** → one card per "smoke bar" test: pass/fail, **hard-stop-on-red**.

---

## LEVEL 3 — Side-chat work surface (all levels)

A persistent chat panel docks beside the board. Whatever card/slice is focused becomes its **active context**, and work happens conversationally; chat actions mutate the board live; selecting a card loads its context into chat. Examples across levels:
- PLAN/Research: "recall what we know about X" (T0), "quick-check Y" (T1), "run biblio on Z" (T2), "kick a deep pipeline on W" (T3), "promote this finding through the review gate," "pin F-042 to this idea."
- Pipeline: "advance this idea from PLAN into DESIGN," "author an ED from this design."
- EXECUTE: "tick checklist item 4," "this reviewer finding is a false positive, resolve it," "advance ED-012 to VERIFY."

Long-running Tier-3 pipelines are **first-class background citizens** — they progress pass-by-pass while the user works other cards, never modal blockers.

---

## LEVEL 4 — Single-card mockup specs (what each card shows at a glance)

Cards are the atom of the whole UI. Two card types matter most: the **ED card** (EXECUTE) and the **research-finding card** (PLAN). Both should be legible in under a second — status, tier, and blocked-state readable from across the board without opening anything.

### ED card

```
┌──────────────────────────────────────────────┐
│ ED-012  ·  FULL          [● BUILT-GREEN]  ⚑    │   ← id · tier badge · state chip · pin-in indicator
│ registry-schema pre-commit validator           │   ← title
│ ────────────────────────────────────────────── │
│ vet 0C 0H 1M 2L · ft1     smoke ✓ 1st · 1 cyc   │   ← findings by severity + false-ticks · smoke result + cycles-to-green
│ ⧗ 40m           def 0/0           ch:fable-5     │   ← author wall-clock · defects ED/exec · review-channel
│ ◂ probes: F-042, F-051                           │   ← research findings pinned INTO this ED (provenance)
└──────────────────────────────────────────────┘
```

At-a-glance encodings:
- **State chip** is the dominant color signal. `DESIGN` neutral · `VETTED` blue · `GREENLIT` amber · `BUILT-GREEN` green · `BUILT-RED` **red, loudest on the board** · `VERIFIED` green + check/lock (settled).
- **Tier badge** (`FULL` vs `CEREMONY`) — weight/size difference; CEREMONY reads lighter (it's a stub-tier).
- **Vet line** — `C/H/M/L` counts by severity + `ft` false-ticks. Any non-zero **critical/high** shows a warning accent even on an otherwise-green card.
- **Smoke** — ✓/✗ + whether it passed first-run + cycles-to-green. A red smoke is a hard-stop; the card should look *stopped*, not just tinted.
- **Metrics row** — wall-clock, defects (ED-side/exec-side), pinned review-channel.
- **⚑ pin-in indicator** (top-right) + **◂ probes line** — the research findings this ED consumes. This is the visible wire back to PLAN. An ED in FULL tier with *zero* probes pinned is a soft warning ("what did authoring probe against?").

### Research-finding card

```
┌──────────────────────────────────────────────┐
│ F-042  ·  T3-deep        [◇ settled]      ▸2    │   ← id · tier that produced it · gate status · pinned-to count
│ NotebookLM headless auth has no non-interactive │   ← title / claim
│ path (py3.13+ broke cookie route)               │
│ ────────────────────────────────────────────── │
│ 30-findings · reviewed ✓ (interactive)          │   ← vault stage · review-gate status + mode
│ grounding→assembled · src×3        ◷ 2d ago     │   ← handoff marker · source count · age
│ ▸ consumed by: ED-012, ED-013                    │   ← what downstream cites this (the consumer)
└──────────────────────────────────────────────┘
```

At-a-glance encodings:
- **Gate-status chip** is the dominant signal, mirroring the vault stages: `sourced` neutral · `topic` neutral · `needs-review` **amber (sitting on the gate)** · `settled` green/locked · `gotcha` distinct hazard style.
- **Tier-that-produced-it** (`T0-recall`/`T1-lookup`/`T2-biblio`/`T3-deep`) — same tier language as the front door, so you can see how expensive this knowledge was to get.
- **Review mode** — `interactive` vs `self-review (autonomous)`; an autonomous `needs-human-review` finding carries an extra "unverified" flag.
- **Handoff marker** — `grounding→assembled` confirms an agent authored it (raw summaries never ship as findings); show source count.
- **▸ consumed-by line + pinned-to count** — the consumer-owns-done signal. A `settled` finding with **zero consumers** renders **muted/inert** ("filed but pointless-by-construction") — the single most important visual rule tying research to the doctrine.

### Shared card grammar (applies to every card at every level)

- **One dominant status color** per card (state chip or gate chip). Everything else is secondary text weight — avoid rainbow cards.
- **Red = blocked/stopped is sacred:** `BUILT-RED`, failed smoke bar, red checklist item, an unconsumed finding, a phase with no intake test. These must be the loudest thing on screen; never let them blend into "in progress."
- **Provenance is always a line, not a hover:** every card shows where it came from (◂ probes / pinned-from) and where it's going (▸ consumed-by / advances-to). Flow is visible on the face of the card, not buried in a detail panel.
- **Tier is always a badge:** whether it's an ED (`FULL`/`CEREMONY`) or a research card (`T0–T3`), the cost/depth tier is a persistent, glanceable chip — the recurring "how heavy is this" signal across the whole cockpit.

---

## Feel

An **operations cockpit** for shepherding ideas into shipped work — not a to-do app. Convey **flow and provenance**: where a card came from, which gate it's blocked on, what its downstream intake test demands. Phase boundaries read as real thresholds. Red/blocked states (failed smoke bars, red checklist items, a phase whose intake test doesn't exist yet, an unconsumed finding) must be unmissable. The Research lane reads as a research desk *inside* the planning cockpit — escalating tiers as gears you shift into, a living vault of accumulated findings, every finding earning its place by being consumed downstream.

## What I want back

A few directions for: (1) the master phase-board, (2) the recursive drill-down mechanic (slide-over vs. full board-swap vs. breadcrumb-zoom), (3) how the side-chat docks and binds to the focused card, and (4) how the research tier-selector and staged vault present. Concept-level — don't lock into implementation.
