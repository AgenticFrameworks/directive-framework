# Directive Framework

[![CI](https://github.com/AgenticFrameworks/directive-framework/actions/workflows/test.yml/badge.svg)](https://github.com/AgenticFrameworks/directive-framework/actions/workflows/test.yml)

**Directive Framework** is a clean-canon, phase-gated operating system for agent-assisted software delivery.
It turns an idea into reviewed work through explicit, inspectable artifacts — not conversational promises.

**Version:** 1.2.0

## What it provides

- A five-phase artifact pipeline: **Planning → Design → Validation → Execution → Review**.
- Paired reasoning and decision packets (`PD` / `DD`), validated build plans (`VD`), execution directives (`ED`), and review directives (`RD`).
- Deterministic phase-intake gates, fail-closed lifecycle controls, cursor ownership, and a mechanical executor.
- Canon/runtime separation: reusable framework canon stays clean; each consumer owns `_directives/` runtime state.
- Built-in review and intent-drift protocols, plus a reproducible release check.
- Three native install surfaces: a Claude Code plugin, a standalone portable skill, and a **pi agent package** that fuses the pipeline into the pi harness with fail-closed `tool_call` phase gates.

## Surfaces

| Surface | Path | Install |
|---|---|---|
| Claude Code plugin | `.claude-plugin/` | drop the repo into Claude Code's plugin dir |
| Portable skill | `portable/ed/` | copy `SKILL.md` + canon into any skill-aware agent |
| pi agent package | `pi/` | `pi install git:github.com/daedalusos/directive-framework` |

The pi package is the native fusion: a pi extension (`pi/extensions/directives.ts`) registers `directive_*` tools, a `/directives` command, per-turn phase-context injection, and a fail-closed write gate covering `write`/`edit`/`bash` redirect targets; a deterministic runtime (`pi/runtime/directives-runtime.mjs`) owns every cursor/registry/gate mutation. See `pi/README.md` and `pi/INSTALL.md`.

## Quick start

Clone the repository, then initialize runtime state in the project you want to operate on:

```bash
python3 /path/to/directive-framework/tools/init-runtime.py --project /path/to/project
python3 /path/to/directive-framework/tools/gate-runner.py --validate-templates /path/to/directive-framework/gates
```

Runtime packets, cursor state, registry history, metrics, and dashboards belong in the consuming project's `_directives/` directory.
They are never part of this framework's deliverable canon.

## Core commands

```bash
# Validate all phase-gate contracts
bash tests/test-canon.sh

# Build a clean release artifact and print its SHA-256
python3 tools/package-release.py

# Run a greenlit execution directive
bash tools/executor-run.sh ED-NNN
```

## Repository layout

| Path | Purpose |
|---|---|
| `planning-directives/` | PD/DD packet contracts and planning protocol |
| `validation-directives/` | VD packet contract and validation protocol |
| `execution-directives/` | ED templates, lifecycle tools, and execution contract |
| `review-directives/` | RD packet contract and review protocol |
| `gates/` | Machine-readable phase-boundary gate specifications |
| `tools/` | Deterministic runtime, validation, executor, and release tools |
| `.claude-plugin/` | Claude Code plugin manifest |
| `portable/` | Standalone skill bundle for any skill-aware agent |
| `pi/` | Native pi agent package (extension + runtime + skill) |
| `tests/` | Tracked canon regression checks |

## Guarantees and limits

The framework mechanically validates schema, lifecycle, packet coverage, ordering, and gate contracts.
It does **not** claim that a reviewer's semantic conclusion or a recorded session identity is cryptographic proof of independent reasoning; those are auditable review responsibilities.

## Release and quality

The tracked test suite validates all gate templates, compiles tools, and enforces canon purity.
The release builder (`tools/package-release.py`) creates an allowlisted archive that excludes project runtime, credentials, handoffs, and local build artifacts; the archive version is read from `.claude-plugin/plugin.json` so the two never drift.

Releases are tagged `v<version>` on `main`; the canon archive and its SHA-256 are attached to the GitHub Release.
The pi package is installed directly from the repo via `pi install` and is not bundled into the canon archive.

See `RUNTIME-SPEC.md`, `gates/GATES-SPEC.md`, and `execution-directives/EXECUTION-SPEC.md` for the complete contracts.

## License

See [LICENSE](LICENSE).
