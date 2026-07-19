---
id: ED-XXX
title: <one-line objective>
tier: FULL            # FULL | CEREMONY — authoring capacity decides and states it
format: v2            # v2 ships the chain-walkback + intent-chunk synthesis contract (EXECUTION-SPEC.md). Omit / v1 for legacy apply-only EDs.
status: DESIGN        # mirror of the latest directives.jsonl line, informational only
created: <ISO8601 UTC>
author:               # the authoring capacity (fable). Must differ from every consumed VD author (execution-intake vd-dd-consumption) and from the coder.
chain-walkback:       # v2 REQUIRED: traced lineage "VD-NNN -> DD-NNN[,DD-NNN…] -> PD-NNN[,PD-NNN…]" (presence gated at execution-intake; shape and truth audited at B10)
checklist-run:        # "<date>, <result>" — appended after the CHECKLIST.md walk
review-channel:       # model/channel that performed cross-vet (see CROSS-VET.md pinning)
canon-refs:           # settled decisions this ED touches, if the project keeps a ledger
related:               # optional — see USAGE.md "Related artifacts"; list of {kind: ref}
---

<!-- Filename convention (optional): ED-<id>.md, or ED-<id>-<subject-slug>.md for a scan
     aid in flat directories (e.g. ED-042-vlanid-fix.md). The `id:` field above is the
     primary key everywhere (directives.jsonl, cross-references) — the slug is cosmetic. -->

<!-- CEREMONY tier: keep frontmatter + sections 0 (if v2), 1, 7, and 8 only. State what is
     being done, why it is trivial, the traced chain, and what it must not touch. Done. -->

# 0. Chain walk-back

<!-- v2 REQUIRED (skip only for v1/apply-only EDs). Trace this ED back to the validated
     plan it executes: which VD it consumes, which DDs that VD packaged, which PDs decided
     those DDs, and one line on why this ED is the faithful execution of that plan. The
     `chain-walkback:` frontmatter key is the machine-checkable form of this same trace;
     the two must agree. Truth is audited at B10 — this section is the presence half. -->

This ED consumes `VD-NNN`, which packaged `DD-NNN, DD-NNN` (decided by `PD-NNN, PD-NNN`).
One line: why this directive is the faithful execution of that validated plan.

# 1. Objective & success criteria

What this directive builds and the observable condition that means it worked.
Success criteria must be checkable by the smoke plan (§6), not by satisfaction.
Give each criterion a stable id (`S1`, `S2`, ...); every id must appear in the §6 bar
table's `Covers` column, or in an explicit `unverifiable-because-X` ledger line at the
bottom of §6.

# 2. Traced context (verbatim, cited)

Every external call site, signature, schema element, and interface this ED relies on —
**copied verbatim from battle-tested source and cited `file:line`**, never re-derived.

# 3. Probes (run at authoring time, real data, real outputs)

Every risky operation (join, API call, parse, schema/default assumption, size, wall-time)
is RUN while writing this ED, and the actual command + actual output pasted here with a
date. "Will verify at build time" is banned — a probe deferred is a defect scheduled.

| # | Risk | Command run | Actual output (pasted) | Date |
|---|---|---|---|---|

# 4. Decisions (accepted + rejected)

Each decision with its rejected alternatives and why. A rejected alternative recorded here
is settled — it is never re-surfaced downstream as a live choice.

# 5. Implementation package

The reviewed source of truth is FILES, not prose. Place the actual implementation in
`ED-XXX.files/` (full files or unified diffs). The executor APPLIES this package; it never
retypes code out of the ED body. List every file and its purpose:

| File in ED-XXX.files/ | Applies to | Purpose |
|---|---|---|

**Synthesis EDs (`format: v2`, written not applied):** decompose the implementation into
ordered **intent-separated chunks** (one coherent purpose per chunk — never split by line
count or file boundary; see `execution-directives/EXECUTION-SPEC.md`). For each chunk give:

| Chunk | Intent (one purpose) | Coding instruction (architecture `file:line` + formatting) | Dry-run smoke (optional) |
|---|---|---|---|

The coder is handed one chunk at a time; author ≠ coder; the GREENLIT registry line is the
sign-off. Apply EDs (`copy`/`append` only, no coder) may omit the chunk table.

Transcription-risk strings — the few values the executor must genuinely type (CLI args,
launch constants, IDs not shipped in files). Flag each: "this exact string, verbatim":

- `<string>` — where it goes

# 6. Smoke plan (barred)

Numbered pass/fail bars, run in order. Requirements for the plan as a whole:
- Wiring (file writes, dirs, fixtures) testable BEFORE any slow/expensive portion.
- Each bar re-runnable in isolation, or the dependency chain documented here.
- Each bar's failure emits a specific, actionable message (expected Y, got Z, hypothesis).
- Result written ONCE, atomically, at end (tmp + `os.replace`); abnormal exits (watchdog)
  persist a partial-RED result BEFORE exiting; a lockfile refuses concurrent smokes.
- Wall-clock kill enforced IN CODE (watchdog/alarm), budget from MEASURED invocation wall
  time, never inner/API-reported time.
- Coverage total: every §1 criterion id appears in >=1 bar's `Covers` cell, or in an
  `unverifiable-because-X` ledger line at the bottom of this section (honest deferral,
  same spirit as `[ ] deferred-justified`).

| Bar | Command | Expected (specific value) | Covers | On failure emit |
|---|---|---|---|---|

# 7. Out of scope

What later directives do; what the executor MUST NOT touch (protected stores, sibling
modules, canon files). Explicit paths.

# 8. Records (filled as lifecycle advances)

- Checklist walk: <per-item ticks with body citations, or N/A-because-X>
- Cross-vet findings + inline fixes applied: <list>
- Build result / defects: <link defects.md if BUILT-RED>
- Post-mortem: <new failure modes -> checklist items proposed>
