# Directive Framework

[![CI](https://github.com/Agent-Frameworks/directive-framework/actions/workflows/test.yml/badge.svg)](https://github.com/Agent-Frameworks/directive-framework/actions/workflows/test.yml)

**Directive Framework** is a clean-canon, phase-gated operating system for agent-assisted software delivery. It turns an idea into reviewed work through explicit, inspectable artifacts—not conversational promises.

**Version:** 1.1.0

## What it provides

- A five-phase artifact pipeline: **Planning → Design → Validation → Execution → Review**.
- Paired reasoning and decision packets (`PD` / `DD`), validated build plans (`VD`), execution directives (`ED`), and review directives (`RD`).
- Deterministic phase-intake gates, fail-closed lifecycle controls, cursor ownership, and a mechanical executor.
- Canon/runtime separation: reusable framework canon stays clean; each consumer owns `_directives/` runtime state.
- Built-in review and intent-drift protocols, plus a reproducible release check.

## Quick start

Clone the repository, then initialize runtime state in the project you want to operate on:

```bash
python3 /path/to/directive-framework/tools/init-runtime.py --project /path/to/project
python3 /path/to/directive-framework/tools/gate-runner.py --validate-templates /path/to/directive-framework/gates
```

Runtime packets, cursor state, registry history, metrics, and dashboards belong in the consuming project's `_directives/` directory. They are never part of this framework's deliverable canon.

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
| `tests/` | Tracked canon regression checks |

## Guarantees and limits

The framework mechanically validates schema, lifecycle, packet coverage, ordering, and gate contracts. It does **not** claim that a reviewer’s semantic conclusion or a recorded session identity is cryptographic proof of independent reasoning; those are auditable review responsibilities.

## Release and quality

The tracked test suite validates all gate templates, compiles tools, and enforces canon purity. The release builder creates an allowlisted archive that excludes project runtime, credentials, handoffs, and local build artifacts.

See `RUNTIME-SPEC.md`, `gates/GATES-SPEC.md`, and `execution-directives/EXECUTION-SPEC.md` for the complete contracts.

## License

See [LICENSE](LICENSE).
