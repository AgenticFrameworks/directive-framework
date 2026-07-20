---
name: directive-framework
description: Native pi agent fusion of the directive-framework phase-gated pipeline. Use to drive an idea through Planning, Design, Validation, Execution, and Review with fail-closed phase gates, an append-only registry, and parallel lanes. Load when the directive_* tools or /directives command are available and a task needs phase-gated governance.
---

# Directive Framework (native pi fusion)

This skill is the discoverability entry point for the native directive pipeline
shipped as a pi package. The pipeline is fused into the pi agent harness as a
first-class mechanism — not a plugin the model loads on demand.

## What it provides

A five-phase artifact pipeline that turns an idea into reviewed work through
inspectable artifacts:

```
planning  ->  design  ->  validation  ->  execution  ->  review
 PD/DD       VD         GREENLIT        ED built        VERIFIED
                                        (hard stop      or REOPENED
                                         on red)
```

- **PD/DD** — paired planning + decision packets (planning output)
- **VD** — validation directive, the build plan with smoke bars
- **ED** — execution directive, the build package the coder implements
- **RD** — review directive, the review-phase output

## How to drive it

The extension registers `directive_*` tools and a `/directives` command. Drive
the pipeline by calling the tools in order:

1. `directive_plan` — allocate + draft a PD/DD pair (planning)
2. `directive_settle` — settle the active DD (design)
3. `directive_validate` — package a VD from the settled DD (validation)
4. `directive_greenlight` — sign off the VD (HiTL unless `directives.yolo`)
5. `directive_execute` — allocate an ED + dispatch a coder (turn-boundary
   kickoff in-session; run `/directives execute <vd_id>` for a true fresh
   session via `ctx.newSession`)
6. `directive_built` — record GREEN/RED (hard stop on red, no fix iteration)
7. `directive_review` — dispatch a reviewer (or `/directives review <ed_id>`)
8. `directive_verified` — mark the ED VERIFIED (final)

Status anytime: `directive_status` or `/directives`.

## Safety posture

- Phase gates are enforced **fail-closed at `tool_call` time**. The write gate
  covers `write`, `edit`, AND `bash` redirect targets — the model cannot route
  around a phase boundary with shell redirection.
- A **GREENLIT registry line with `go_basis`** is the only sign-off that
  authorizes execution. Nothing else does.
- **Parallel lanes** must declare disjoint file footprints, checked at register
  AND re-checked at execute time (closes the register->execute TOCTOU).
- With `directives.yolo` off (default), greenlight escalates to the captain.
  Destructive/irreversible/security-sensitive choices escalate regardless.

## Settings

In `~/.pi/agent/settings.json`:

```json
{ "directives": { "yolo": false, "autoInit": false } }
```

- `yolo: true` — model may self-greenlight routine work as
  `delegated:agent-yolo`; destructive choices still escalate.
- `autoInit: true` — auto-initialize the runtime for trusted projects (also
  gated behind project trust). Default off; opt in per-project with
  `/directives init`.

## Runtime state

Per-project, under `~/.pi/agent/directives/<slug>/` (override with
`DIRECTIVES_RUNTIME_DIR`): `cursor.json`, `registry.jsonl`, `PD/ DD/ VD/ ED/
RD/`, and `lanes/`. Canon stays clean — no runtime state ships in the package.

See the package `README.md` and `INSTALL.md` for install and configuration.
