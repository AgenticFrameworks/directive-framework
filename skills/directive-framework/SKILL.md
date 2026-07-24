---
name: directive-framework
description: Phase-gated operating system for agent-assisted delivery — turns an idea into reviewed work through inspectable artifacts and fail-closed intake gates (Planning -> Design -> Validation -> Execution -> Review). Use when the user says 'execution directive', 'author an ED', 'run this through the directive framework/pipeline', wants phase-gated governance for a change, or asks to plan/validate/execute/review with directive rigor. The /ed and /directives commands are the explicit entry points.
---

# Directive Framework

A clean-canon, phase-gated pipeline for agent-assisted software delivery. It turns an
idea into reviewed work through explicit, inspectable artifacts — not conversational
promises. The framework canon is the plugin root: `${CLAUDE_PLUGIN_ROOT}`.

```
planning   ->   design   ->   validation   ->   execution   ->   review
 PD/DD          (gate)         VD                ED built          RD
```

Each boundary has a deterministic intake gate (exit 0 PASS / 1 BOUNCE / 2 BLOCK).
Runtime state (packets, cursor, registry) lives in the **consuming project's**
`_directives/`, never in the canon.

## When to use which entry point

- **`/ed`** — drive one atomic change through the Execution Directive lifecycle
  (author -> checklist -> cross-vet -> greenlight gate -> mechanical execute -> verify).
  This is the replacement for the legacy ag-os `/ed`.
- **`/directives`** — operate any phase: init runtime, precipitate/verify PD/DD
  planning packets, run an intake gate, execute an ED, or launch the interactive
  planning cockpit.

## Core tooling (all under `${CLAUDE_PLUGIN_ROOT}`)

| Task | Command |
|---|---|
| Init a project's runtime | `python3 tools/init-runtime.py --project DIR` |
| Precipitate PD/DD from a vault | `python3 tools/precipitate.py <vault> --project DIR` |
| Run a phase gate | `python3 tools/gate-runner.py gates/<gate>.md --project DIR` |
| Execute a greenlit ED | `bash tools/executor-run.sh ED-NNN --project DIR` |
| Launch the planning cockpit | `python3 cockpit/server/app.py --project DIR` |

Gates: `gates/design-intake.md`, `validation-intake.md`, `execution-intake.md`,
`review-intake.md`. Packet contracts: `planning-directives/{PD,DD}-TEMPLATE.md`.

## Rules

- Never write runtime packets into the canon (`${CLAUDE_PLUGIN_ROOT}`); target
  `DIR/_directives/`.
- Gates are fail-closed. BOUNCE = fix the artifacts and re-run; BLOCK = a canon/cursor
  error — stop and report, never force past it.
- The executor is mechanical: no model in the apply loop, a red smoke is a hard stop.

Full contracts: `RUNTIME-SPEC.md`, `gates/GATES-SPEC.md`, and the per-phase specs.
