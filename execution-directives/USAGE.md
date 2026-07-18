# ED System — Usage (entry point)

Read this first. If you are a session holding a build that is blocked awaiting an execute
order, this file tells you exactly what to produce and in what order. Background/rationale
lives in `DESIGN.md`; you do not need it to operate.

## Roles are capacities, not agents

The system names three *capacities*: **authoring** (writes the ED), **reviewing**
(independently vets it), **executing** (applies it and runs the smoke). Any topology works —
one session can author and later execute; a fleet can split them — with ONE structural rule:
**the reviewing capacity must be an independent context** (fresh context, and a different
model/channel where available — record it in `review-channel:`). Self-review is not review.

Whatever holds the ED and adjudicates results is "the lead" below; whatever applies the
package is "the executor" — even if they are the same session at different times. Write every
ED as if the executor is a context-starved, literal, transcription-error-prone reader,
because one day it will be.

## Lifecycle

```
1. AUTHOR     Copy ED-TEMPLATE.md -> ED-<id>.md. Pick tier (FULL | CEREMONY), state it.
              1a. Run every risky operation NOW (probes), paste real outputs into the ED §3.
              1b. When the §3 probe table is filled and pasted, DECLARE the probes-complete
                  micro-seam: `touch ED-<id>.files/.probes-complete`. It marks a safe handoff
                  boundary (probes are durable on disk; resume does not re-run them) that the
                  auto-handoff cursor honors. Skipping it only forgoes the seam — behavior
                  degrades to prior, nothing breaks.
              1c. Put the actual implementation files in ED-<id>.files/ — the executor
                  applies files, it does not retype code out of prose.
2. CHECKLIST  Walk CHECKLIST.md top-to-bottom. Every item: ticked with a citation into
              the ED body, or "N/A because X", or fix the ED. Never proceed with a red
              item. Record `checklist-run:` in frontmatter.
3. CROSS-VET  Independent review per CROSS-VET.md. Apply every NEEDS-FIX inline, in the
              ED, before greenlight. Append status VETTED to directives.jsonl.
4. GREENLIGHT Explicit GO from the user (or a lead holding delegated authority). Never
              build without it. Append GREENLIT.
5. EXECUTE    Fire the launch prompt (LAUNCH-TEMPLATE.md). Executor: read the named
              files, apply the package, run the smoke bars in order.
              HARD STOP ON RED — do not iterate fixes past a failed bar. Write
              defects.md and exit. The fix cycle belongs to the authoring capacity.
              Append BUILT-GREEN or BUILT-RED.
6. VERIFY     Lead independently re-runs/inspects the smoke result (trust-but-verify).
              Append VERIFIED.
7. POST-MORTEM Any new failure mode becomes a checklist item that would have caught it
              (see CHECKLIST.md maintenance rules — growth pairs with consolidation).
```

**Re-entry — `REOPENED`.** If a directive that already reached VERIFIED (or a BUILT-* state)
is later found defective, append a `REOPENED` line carrying a required `reason` and re-enter
at step 5 (EXECUTE → BUILT-* → VERIFIED). It is a re-entry into the existing lifecycle, not a
new numbered step; history is append-only, so the superseding VERIFIED cites the REOPENED it
answers (`supersedes`).

## Depth tiers

- **FULL** — complete quasi-dry-run: probes against real data, files/diffs, barred smoke
  plan. Any non-trivial change.
- **CEREMONY** — a record-only stub (frontmatter + objective + what/why + out-of-scope).
  Trivial/mechanical changes. Costs a paragraph.

Every change gets an ED; the tier keeps that cheap. The authoring capacity decides and
states the tier. Nobody polices it — a skipped tier decision is caught at cross-vet.

## Status registry — directives.jsonl

The ONLY source of directive state. Dashboards/readmes are derived views, never
hand-edited authorities. Append one line per state change (never rewrite history):

```json
{"id":"ED-001","state":"DESIGN","ts":"2026-07-02T11:00:00Z","tier":"FULL"}
{"id":"ED-001","state":"VETTED","ts":"...","review_channel":"<model/channel>","findings":{"critical":0,"high":2,"false_ticks":1}}
{"id":"ED-001","state":"GREENLIT","ts":"...","authoring_wallclock_min":40,"go_basis":"human:marsh"}
{"id":"ED-001","state":"BUILT-GREEN","ts":"...","smoke_first_run":"GREEN","cycles_to_green":1}
{"id":"ED-001","state":"VERIFIED","ts":"...","defects_post_ship":{"ed_side":0,"executor_side":0}}
```

States: `DESIGN | VETTED | GREENLIT | BUILT-GREEN | BUILT-RED | VERIFIED | REOPENED`.
`REOPENED` — a VERIFIED/built directive found defective post-hoc and sent back for rework;
carries a required `reason` (non-empty string) and re-enters the lifecycle at EXECUTE (→
BUILT-* → VERIFIED again). It is a re-entry, not a numbered step.
The metrics fields (findings, cycles_to_green, wallclock, defect attribution) are mandatory
where shown — they are how the system's value gets measured instead of asserted.

## Related artifacts (optional convention)

An ED rarely exists alone — a brainstorm may precede it, a handoff may resume it, a commit
may implement it. Frontmatter across brainstorm notes, EDs, and handoffs may carry an
optional `related:` list of `{kind: ref}` pairs so the chain is queryable:

```yaml
related:
  - brainstorm: brainstorms/2026-07-09-eds-handoffs-per-project.md
  - ed: dev/directives/ED-042.md
  - handoff: handoffs/HANDOFF-20260709T014500Z.md
  - commit: <sha>
```

Convention only — optional, no parser, no schema enforcement, absence is fine.
`derive-cross-repo.py --chain <id>` renders the chain when the frontmatter is present.
`id:` remains the primary key everywhere; `related:` is a scan aid across artifact types.

## Files in this slice

| File | What |
|---|---|
| `USAGE.md` | this entry point |
| `ED-TEMPLATE.md` | copy per directive; defines FULL and CEREMONY shapes |
| `CHECKLIST.md` | post-author, pre-greenlight hard-stop walk |
| `CROSS-VET.md` | reviewer mandates + channel pinning |
| `LAUNCH-TEMPLATE.md` | executor-proof launch prompt skeleton |
| `directives.jsonl` | append-only status + metrics registry |
| `DESIGN.md` | full system spec + origin assessment (background) |
