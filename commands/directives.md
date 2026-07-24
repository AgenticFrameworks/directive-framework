---
description: Operate the phase-gated directive-framework pipeline (init runtime, run intake gates, precipitate PD/DD packets, run an ED, or launch the planning cockpit) against a target project.
---

# /directives — phase-gated directive pipeline

You are operating the **directive-framework** pipeline for the user. The framework
canon lives at the plugin root: `${CLAUDE_PLUGIN_ROOT}`. Runtime state (packets,
cursor, registry) belongs in the **consuming project's** `_directives/` directory,
never in the framework canon.

The pipeline has five phases with deterministic intake gates between them:

```
planning  ->  design  ->  validation  ->  execution  ->  review
 PD/DD        (gate)       VD             ED built        RD
```

## Resolve the target project

Determine the project to operate on, in order:
1. An explicit path in the user's `/directives` argument.
2. The current working directory, if it is a real project.
Ask if it is ambiguous. Call it `$PROJECT` below.

## Actions

Pick the action from the user's request; if unclear, list these and ask.

- **init** — create the runtime substrate:
  `python3 ${CLAUDE_PLUGIN_ROOT}/tools/init-runtime.py --project "$PROJECT"`
- **plan** — write paired planning packets by hand or precipitate them from a
  research vault, then verify the planning→design gate:
  `python3 ${CLAUDE_PLUGIN_ROOT}/tools/precipitate.py <vault-notebook-dir> --project "$PROJECT"`
  Packet contracts: `${CLAUDE_PLUGIN_ROOT}/planning-directives/PD-TEMPLATE.md` and
  `DD-TEMPLATE.md` (frontmatter `id`, `pair`, `status`, `created`; shared serial
  `PD-NNN ⇄ DD-NNN`; every DD needs its PD).
- **gate** — run a phase-boundary intake gate (exit 0 PASS / 1 BOUNCE / 2 BLOCK):
  `python3 ${CLAUDE_PLUGIN_ROOT}/tools/gate-runner.py ${CLAUDE_PLUGIN_ROOT}/gates/design-intake.md --project "$PROJECT"`
  Other gates in `${CLAUDE_PLUGIN_ROOT}/gates/`: `validation-intake.md`,
  `execution-intake.md`, `review-intake.md`.
- **execute** — run a greenlit execution directive mechanically:
  `bash ${CLAUDE_PLUGIN_ROOT}/tools/executor-run.sh ED-NNN`
- **cockpit** — launch the interactive planning front door (converse to converge,
  writes gate-passing PD/DD packets, one-click gate):
  `python3 ${CLAUDE_PLUGIN_ROOT}/cockpit/server/app.py --project "$PROJECT"`
  then open the printed `http://localhost:PORT/`. Needs `PERPLEXITY_API_KEY` or
  `OPENROUTER_API_KEY` in the environment only for the chat loop.

## Rules

- Never write runtime packets into `${CLAUDE_PLUGIN_ROOT}` (the canon); always
  target `$PROJECT/_directives/`.
- Gates are fail-closed: a BOUNCE means fix the packets and re-run; a BLOCK means a
  canon/cursor error — stop and report, do not force past it.
- Report the gate verdict and any packet ids you created or changed.

For the full contracts read `${CLAUDE_PLUGIN_ROOT}/RUNTIME-SPEC.md`,
`${CLAUDE_PLUGIN_ROOT}/gates/GATES-SPEC.md`, and the per-phase specs.
