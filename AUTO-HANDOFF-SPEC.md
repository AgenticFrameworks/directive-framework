# Auto-Handoff Spec — phase/role awareness (boundary B8)

Canon artifact, shipped by ED-006. Makes the global auto-handoff machinery
(`~/.claude/hooks/auto-handoff-monitor.js` / `auto-handoff-gate.js` /
`~/.claude/scripts/auto-handoff-restart.sh`) phase/role-AWARE for this framework's
projects **without adding any new global hook**: the global machinery stays
project-agnostic; the project side supplies awareness through the ED-033 enrichment
seam and owns the postpone/reset mechanics in `_directives/cursor.json`.

## Posture (FABLE-1, decided — do not re-open)

- **The global phase-blind token hook stays OFF.** No new hook gates by phase. Phase
  awareness enters exclusively via project-supplied enrichment text; the decision to
  stop is made by the orchestrator/agent at boundaries, not by a phase-reading gate.
- **Handoff is orchestrator-owned.** The soft nudge lands at ED/phase boundaries —
  never mid-planning, never mid-design, never mid-apply.
- **The heavy lifting is structural, not a gate:** the fresh-context-per-ED-phase
  invariant already resets the coder each ED, so a coder session never accumulates a
  handoff-tripping context.
- **Exactly ONE high hard backstop**, well above normal, as a runaway catch only.

## Mapping onto the global machinery (the graduated ladder, reused)

The global monitor already emits three tiers; B8 adopts them as the ladder — no new
thresholds are invented:

| Tier (global) | Fires at | B8 ladder rung | Sanctioned response |
|---|---|---|---|
| threshold reminder | threshold | advisory soft nudge | postpone (budget below) or hand off at the next boundary |
| URGENT | +10% over | soft-gate (blocking, recoverable) in spirit | stop at the NEXT natural boundary and hand off |
| HARD STOP (gate) | +18% over (`auto-handoff-gate.js`, gate_margin_pct=2) | **the ONE hard backstop** | only escape: Write the pinned handoff + run the restart script |

The +18% tool gate **is** the single hard backstop — B8 ships no second one.

## The enrichment seam (ED-033)

`auto-handoff-monitor.js` splices `$CLAUDE_LOOP_SIGNAL_DIR/handoff-enrichment.md`
VERBATIM into every threshold reminder when present. The project side:

- `tools/handoff-enrichment.py` renders the ED-STATE block (phase, role,
  active_directive, boundary, postpone budget state, per-phase policy line, resume
  protocol) from a **validated** cursor. Invalid cursor → exit 2 AND the stale
  enrichment file is removed (fail-closed: corrupt state is never spliced as current).
- **Who runs it:** the orchestrator, at every cursor transition it performs (phase
  change, directive activation) and after every recorded postpone. Coder sessions
  never write the seam — the glue's cursor writes are same-phase and the coder is
  structurally fresh.
- `--remove` clears the seam (e.g. when a project leaves the pipeline).

## Postpone budget (count in code, size advisory)

- Budget: **2 postpones per phase occupancy, ~20k tokens each, then HiTL escalation.**
- `tools/postpone-handoff.py` is the only sanctioned incrementer of
  `postpones_used` (already in the ED-001 cursor schema — no migration). At the
  budget it refuses (exit 2) with the HiTL escalation message and does not write.
- The **count** is enforced mechanically; the **~20k size** of each postpone is
  advisory — the repo has no token telemetry, and importing the harness bridge file
  would couple canon to a host detail. Honest limitation, recorded here.

## Reset ownership (B8 open decision — SETTLED)

`postpones_used` **resets to 0 on phase change, performed by the phase-transition
writer** — `tools/cursor-phase.py`, the sanctioned orchestrator-side transition tool.
Same-phase transitions preserve the count. Rejected alternatives:

- *gate-runner side effect* — the runner is read-only by ED-004 contract; a write
  side effect would break its own purity guarantee and create a second cursor writer
  racing the executor.
- *orchestrator-by-hand* — hand-edited cursor JSON is exactly what ED-001 built the
  validator to prevent; prose obligations rot.

The executor's `set_cursor` (tools/executor-run.sh:118-131) is untouched: its writes
are same-phase (`execution` coder⇄orchestrator) and it preserves `postpones_used` by
construction (it loads the existing dict and only overwrites
phase/role/active_directive/updated/updated_by).

## Environment prerequisites (G3/G4 deadlock class — BASHIR)

The hard backstop's ONLY escape actions are a `Write` to the pinned handoff path and
a `Bash` call containing `auto-handoff-restart.sh`. A global policy gate
(`~/.claude/hooks/policy-gate.sh`) that can deny either action can DEADLOCK the
session at the backstop (BASHIR G3/G4). Before relying on the backstop:

- policy-gate.sh must carry an auto-handoff carve-out (mirror the
  `buildlock-drift-gate.sh` ED-08 carve-out pattern: allow_always on the pinned
  handoff Write and the restart-script Bash).
- `tools/handoff-enrichment.py --doctor` checks this advisorily (restart script
  present + executable, monitor/gate hooks present, carve-out reference present) and
  WARNS `CARVE-OUT MISSING (G3/G4)` when absent — exit 0 unless `--strict`.
- Fixing the global gate itself is `~/.claude` wiring, outside this repo's canon;
  the doctor makes the gap visible instead of silently trusting the backstop.

## Out of scope for B8

- `tools/executor-run.sh` (B7 owns executor changes), `tools/gate-runner.py`,
  `gates/*`, `planning-directives/*` (B5), any `~/.claude` global file.
- No global hook is added, removed, or edited by this framework.
