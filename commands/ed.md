---
description: Run a change through the directive-framework Execution Directive lifecycle — author -> checklist -> cross-vet -> greenlight gate -> mechanical execute -> verify. Use when the user types /ed, says 'execution directive', 'author an ED', or wants a change built with directive-framework rigor.
---

# /ed — Execution Directive lifecycle (directive-framework)

Take a change from intent to verified build through the framework's fail-closed
execution phase. This replaces the legacy ag-os `/ed` router: the canon here is the
plugin itself at `${CLAUDE_PLUGIN_ROOT}`, and no model is ever in the apply loop —
`executor-run.sh` owns every state transition mechanically.

Resolve the target project (`/ed` argument, else the cwd; ask if ambiguous) as
`$PROJECT`. Ensure its runtime exists:
`python3 ${CLAUDE_PLUGIN_ROOT}/tools/init-runtime.py --project "$PROJECT"`.

## Lifecycle

1. **Author** — write the ED from the canon template into `$PROJECT/_directives/ED/`,
   following `${CLAUDE_PLUGIN_ROOT}/execution-directives/ED-TEMPLATE.md` (and
   `LAUNCH-TEMPLATE.md` for the launch packet). One ED per atomic change; keep it
   self-contained (exact paths, names, values).
2. **Checklist walk** — walk `${CLAUDE_PLUGIN_ROOT}/execution-directives/CHECKLIST.md`
   (canon list first, then the project's `_directives/checklist.md` earned appendix).
3. **Cross-vet** — run the independent cross-vet per
   `${CLAUDE_PLUGIN_ROOT}/execution-directives/CROSS-VET.md`. This is a real second
   pass, not a rubber stamp.
4. **Greenlight gate** — the change may not execute until the execution-intake gate
   passes (exit 0 PASS / 1 BOUNCE / 2 BLOCK):
   `python3 ${CLAUDE_PLUGIN_ROOT}/tools/gate-runner.py ${CLAUDE_PLUGIN_ROOT}/gates/execution-intake.md --project "$PROJECT" --id ED-NNN`
   Only proceed on an explicit user greenlight AND a PASS.
5. **Execute** — mechanical, idempotent apply owned by the harness:
   `bash ${CLAUDE_PLUGIN_ROOT}/tools/executor-run.sh ED-NNN --project "$PROJECT"`
   It enforces the greenlight, runs the ED's smoke test, and records BUILT-GREEN or
   BUILT-RED in the append-only registry. A red smoke is a HARD STOP — no fix loop.
6. **Verify** — confirm the registry state and the smoke result; report BUILT-GREEN /
   BUILT-RED and the ED id. Do a brief post-mortem if anything bounced or went red.

## Rules

- Runtime packets go in `$PROJECT/_directives/`, never in `${CLAUDE_PLUGIN_ROOT}`
  (the canon stays clean).
- Gates are fail-closed: BOUNCE = fix and re-run; BLOCK = canon/cursor error, stop and
  report. Never force past a gate.
- Do not hand-edit the registry or cursor — the tools own those transitions.

Full contract: `${CLAUDE_PLUGIN_ROOT}/execution-directives/EXECUTION-SPEC.md` and
`${CLAUDE_PLUGIN_ROOT}/gates/GATES-SPEC.md`. For planning/design/validation phases or
the interactive cockpit, use `/directives`.
