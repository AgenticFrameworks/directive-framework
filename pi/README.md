# directive-framework-pi

Native [pi](https://github.com/earendil-works/pi-coding-agent) agent fusion of the
[directive-framework](..) phase-gated pipeline. Fuses the framework's
Planning → Design → Validation → Execution → Review artifact pipeline into the pi
agent harness as a first-class mechanism — not a plugin the model loads on demand.

This is the pi surface of the directive-framework repo, alongside the existing
`.claude-plugin/` (Claude Code) and `portable/ed/` (standalone skill) surfaces.

## What it is

- **`extensions/directives.ts`** — pi extension registering 14 `directive_*`
  tools, the `/directives` command, `before_agent_start` phase-context
  injection, and a fail-closed `tool_call` write gate covering `write`, `edit`,
  and `bash` redirect targets.
- **`runtime/directives-runtime.mjs`** — deterministic, fail-closed substrate
  owning every state mutation: cursor writes, append-only registry appends,
  packet validation, phase-gate checks, lane overlap detection. The extension
  shells out to it; the model never touches cursor/registry/gate state.
- **`skills/directive-framework/SKILL.md`** — discoverability skill so
  `/skill:directive-framework` loads the usage doc.

## Why native, not a plugin

The framework's doctrine is "prose is not enforcement; every rule that matters
migrates into code." Fusing it natively means:

1. The pipeline is part of the agent's own config surface, not an external repo
   the model is told to read.
2. Phase gates fire at the moment of relevance — on `tool_call` — fail-closed,
   so the model cannot skim past a phase boundary in prose.
3. Phase context is injected into the system prompt per turn.
4. Fresh-context-per-phase via `/directives execute|review` commands
   (`ctx.newSession`). The tool path delivers an in-session turn-boundary
   kickoff (honestly documented as the weaker guarantee).
5. Parallel building is a first-class dispatch primitive: lanes register
   provably-disjoint file footprints, enforced in code before launch AND
   re-checked at execute time.
6. Authority is checkable end-to-end from the registry alone: a GREENLIT line
   with `go_basis` is the only sign-off.

## Install

See [INSTALL.md](INSTALL.md).

## Settings

In `~/.pi/agent/settings.json`:

```json
{ "directives": { "yolo": false, "autoInit": false } }
```

- `yolo: true` — model may self-greenlight routine work; destructive choices
  still escalate.
- `autoInit: true` — auto-initialize the runtime for trusted projects (also
  gated behind `ctx.isProjectTrusted()`).

## Runtime state

Per-project, under `~/.pi/agent/directives/<slug>/` (override with
`DIRECTIVES_RUNTIME_DIR`): `cursor.json`, `registry.jsonl`, `PD/ DD/ VD/ ED/
RD/`, `lanes/`. No runtime state ships in the package (clean-canon rule).

## Safety

- Write gate covers `write`/`edit`/`bash` redirect targets; defense-in-depth
  heuristic, not a full shell parser. Hard floor: bash writes outside the
  runtime dir are blocked in non-execution phases.
- Lane footprints compared by resolved absolute path equality, never substring.
- GREENLIT requires a prior VETTED line; BUILT requires GREENLIT; VERIFIED
  requires BUILT-GREEN. Reopen requires a non-empty reason.
- `BUILT-RED` is a hard stop: the coder writes defects and exits. No fix
  iteration.

## License

AGPL-3.0-only, inheriting the repo's [LICENSE](../LICENSE).
