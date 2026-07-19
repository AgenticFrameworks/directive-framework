# Executor Spec — the harness that runs greenlit EDs

Canon artifact, shipped by ED-002 (boundary B2; designed in FABLE-2, reconciled with the
roadmap). The two-model split: **the orchestrator (Fable-class, subscription) authors and
adjudicates; the executor applies and reports.** The glue below owns every state
transition — a model is never trusted with registry writes, gate decisions, or file
append/copy operations *(earned: ED-001's executor regenerated `.gitignore` from memory
instead of appending, deleting a live rule)*.

## Entry point

```
bash tools/executor-run.sh ED-NNN [--project DIR]
```

Runs under a `timeout 1800` re-exec (wall-clock kill in code) and a per-project flock
(`_directives/ED/.executor.lock`) — one build at a time.

## The pipeline (all deterministic, fail-closed)

1. **Greenlight gate** — the latest `registry.jsonl` line for `ED-NNN` must be state
   `GREENLIT`. **The GREENLIT registry line IS the sign-off signal**; there is no other
   token. Any other latest state (including a prior `BUILT-GREEN`) refuses — re-running a
   built ED requires an explicit `REOPENED` + re-greenlight, never a silent rebuild.
2. **Intake sanity** (floor until B4's STRICT-HARD dual gate): directive file
   `_directives/ED/ED-NNN*.md`, launch prompt `ED-NNN-launch.md`, non-empty
   `ED-NNN.files/`, the `.probes-complete` seam, and a valid `manifest.json`.
3. **Cursor** — `phase=execution role=coder active_directive=ED-NNN` (atomic write,
   validated by `tools/validate-cursor.py`); released to `role=orchestrator
   active_directive=null` on every exit path — **guaranteed by an EXIT trap** installed
   at acquisition (TERM/INT routed through it), so even a registry-append failure after
   a green smoke, or a timeout kill, cannot leave the cursor stuck at `coder`.
4. **Mechanical apply** — from `manifest.json` (schema below). `copy` is verified with
   `cmp`; `append` is idempotent via a required `marker` (skip if present). Absolute
   paths and `..` are rejected.
5. **Smoke** — the ED's own barred smoke, run exactly once. **Hard stop on red: no fix
   iteration.**
6. **Registry** — `BUILT-GREEN` (`smoke_first_run`, `cycles_to_green`) or `BUILT-RED`
   plus a defects file, appended through `execution-directives/append-registry.py`
   (flock'd, line-validated). Dashboard regen runs only when the project README carries
   the `ED-DASHBOARD:BEGIN` marker; otherwise `--no-dashboard`.

## manifest.json (per-ED package contract)

```json
{
  "apply": [
    {"from": "init-runtime.py", "to": "tools/init-runtime.py", "mode": "copy"},
    {"from": "gitignore-append.txt", "to": ".gitignore", "mode": "append",
     "marker": "# --- ED-001: per-project directive runtime"}
  ],
  "smoke": "_directives/ED/ED-NNN.files/smoke.sh"
}
```

- `from` — relative to the ED's `.files/` dir; `to` — relative to the project root.
  Absolute paths, `..`, and control characters are rejected (`smoke` too); the resolved
  destination directory (symlinks followed, `pwd -P`) must stay under the project root,
  and a destination that is ITSELF a pre-existing symlink is refused (leaf containment).
- `mode: copy` → byte-identical apply (cmp-verified). `mode: append` → append-once,
  guarded by `marker`.
- **Marker contract:** the marker MUST occur inside the appended source block (validated —
  a marker absent from the source is refused, since the append could never be idempotent),
  and MUST be a globally unique block header (convention: `# --- ED-NNN: <slug> ---`).
  A marker already present in the destination skips the append with a WARNING — if the
  block was never applied, that is a marker collision the author must fix.
- `smoke` — project-relative path to the ED's smoke script. It runs with fd 9 closed
  (the executor's lock fd is never inherited).

## Synthesis EDs (aider) — not run by this v1 glue

EDs whose implementation must be *written* (not applied) use the aider/GPT coder:

```
set -a; . <canon-repo>/.env; set +a     # OPENROUTER_API_KEY (repo-local .env)
aider --model openrouter/openai/gpt-5.6-sol --yes-always --no-auto-commits --no-check-update \
      --read <ED md + package files> --message "$(cat <ED-NNN-launch.md>)" <target files>
```

Until B7 defines intent-chunk synthesis, this invocation is issued by the orchestrator,
and the glue is then used for the smoke/registry tail. Never route `anthropic/*` slugs
through OpenRouter. Reasoning models need generous completion budgets — an API review
call at `max_tokens 2000` returned empty content (all tokens consumed by reasoning);
use ≥16k.

## Authority audit

Every `GREENLIT` line carries `go_basis` (`human:<name>`, `delegated:<basis>`,
`envelope:<version>`) — enforced by `validate-registry.py` for lines after
2026-07-12. The executor refuses anything not greenlit, so authority is checkable
end-to-end from the registry alone.
