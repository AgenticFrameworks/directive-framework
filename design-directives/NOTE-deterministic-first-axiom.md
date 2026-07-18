# NOTE — Deterministic-first design axiom

> Status: **note** — pre-design-phase input, not a settled framework principle.
> When the `design-directives/` channel (plan→design intake test) gets designed, this axiom is a
> candidate acceptance criterion for any architecture that includes an LLM/inference component.
>
> Provenance: Marshall, 2026-07-04, during the AriatAI persona-coherence brainstorm
> (`ariat-teams-chatui/brainstorms/2026-07-04-ariatai-core-instruction-coherence.md`).
> Stated as a general design philosophy, not project-specific.

## The axiom

**Determinism is the default; inference is a fallback you opt into with accepted risk.**

Consistency holds the most value — more than expected outcome. If a system works the same
way every time, the expected outcome falls into place naturally, and you have a **fixed
baseline to pivot from and steer toward the desired outcome**. An inference-first system has
no stable baseline: when output is wrong you can't tell bad logic from a bad model roll, so
there is nothing to steer against. Deterministic-first means every wrong answer is
*reproducible*, and reproducible is fixable.

## The per-stage test (design-time)

For each stage of a pipeline/architecture, ask:

1. **Can this stage reach the desired outcome deterministically?**
   - **Yes → it MUST be code.** No exceptions for convenience.
   - **No → inference is permitted**, but the hand-off is *explicit and labeled*, never implicit.
2. **Exception by owner's choice:** inference may also take a stage the code could own IF the
   human owner judges the quality-to-convenience-to-risk ratio low enough to accept an
   inferred judgement with accepted risk. This is an opt-in, recorded decision — not a default.

## Design consequences

- The LLM's legitimate home is **phrasing/formatting of already-resolved results** — not
  routing, counting, disambiguation, or orchestration.
- If a pipeline must be deterministic, **the LLM cannot be the orchestrator** — a deterministic
  ladder written into a prompt is still inference-first if the model chooses whether to run it.
  Determinism must be structural (code holds the wheel), not aspirational (prose asks nicely).
- Where accepted-risk inference exists, gate it behind a **configurable threshold** (e.g.
  resolver confidence ≥ 0.9 → auto-proceed with stated assumption; below → ask), never a
  vibe embedded in prose. The owner sets the line.
- Prose instructions that hand-coach a model through logic a function could own are a design
  smell: bloat that should be refactored into code.
