# Directive Framework

*An end-to-end application-building framework for agent-driven design, coding, and review —
available in an interactive HiTL mode and a headless, fully autonomous agent-driven mode.*

End-goal: an end-to-end build pipeline that takes a half-baked idea in and produces a
high-quality, intelligently designed, well-executed deliverable — with no-bullshit phase
boundaries in between. The guiding asymptote (a direction, not a claimed state): work
outside its phase becomes pointless by construction (no downstream consumer), not
forbidden by enforcement.

## Principles (settled 2026-07-02)

- **Consumer-owns-done:** a phase ends when its artifact passes the NEXT phase's intake
  test, not when its author feels finished.
- **Typed artifacts + context starvation:** delegated capacities receive only the upstream
  artifact; out-of-phase output has no consumer and dies of uselessness.
- **Upstream is human+lead, downstream is delegable:** idea→plan→design is interactive
  convergence and is never delegated wholesale; execution consumes a finished directive.
- **Roles are capacities, not agents:** one session or a fleet can run the whole chain.

## Status

| Slice | State |
|---|---|
| `execution-directives/` | **USABLE** — ED system v1. Entry point: `execution-directives/USAGE.md`. Spec: `execution-directives/DESIGN.md`. |
| `planning-directives/` | empty — intake test (idea→plan) undesigned |
| `design-directives/` | empty — intake test (plan→design) undesigned; ED authoring docs currently live in `execution-directives/` |
| `validation-directives/` | empty — new phase scaffold; design→validation intake test undesigned |
| `review-directives/` | empty — post-mortem/verify templates undesigned |

v2 parking lot: fresh-context intake checkers for boundaries 1–2. (Shipped from the
original list: generated status dashboard = ED-007 below; pinned cross-vet review
channel = ED-005.)

## Directive status (generated — never hand-edit between the markers)

Directive status is RUNTIME state, not canon: the registry lives in the per-project `_directives/registry.jsonl`, and the derived dashboard in `_directives/dashboard.md` (regenerated on every registry append). Canon carries no directive instances, registry, or dashboards (see RUNTIME-SPEC.md).

## Global availability (ED-002, 2026-07-02)

The ED system is invocable from any session/project via the global skill
`~/.claude/skills/ed/SKILL.md` (trigger `/ed`). Conventions the skill enforces:

- **Canon is read in place** from `execution-directives/` here — framework docs are never forked.
  Per-ED instantiation (copying ED-TEMPLATE.md into the consuming repo) is required and
  is not a fork. If this repo is unreachable, consumers hard-stop rather than
  reconstruct the lifecycle from memory.
- **Per-project state** lives in each consuming repo at `<repo-root>/dev/directives/`
  (EDs, `ED-XXX.files/`, own append-only `directives.jsonl`; per-project ID namespace).
  ag-os is the exception: its state stays in `execution-directives/` here.
- **Checklist growth flows back**: incidents in any project append to the canonical
  `execution-directives/CHECKLIST.md` with `origin <project>` tags, left uncommitted for this repo's
  normal flow.

A TEMPORARY portable snapshot of the ED system (ED-003, 2026-07-02, source commit
df3137d) lives in `portable/` for running execution phases on a host without this repo —
see `portable/INSTALL.md`; delete the snapshot when the remote work is done.
