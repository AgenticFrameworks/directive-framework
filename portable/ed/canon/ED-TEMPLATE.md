---
id: ED-XXX
title: <one-line objective>
tier: FULL            # FULL | CEREMONY — authoring capacity decides and states it
status: DESIGN        # mirror of the latest directives.jsonl line, informational only
created: <ISO8601 UTC>
checklist-run:        # "<date>, <result>" — appended after the CHECKLIST.md walk
review-channel:       # model/channel that performed cross-vet (see CROSS-VET.md pinning)
canon-refs:           # settled decisions this ED touches, if the project keeps a ledger
---

<!-- CEREMONY tier: keep frontmatter + sections 1, 7, and 8 only. State what is being
     done, why it is trivial, and what it must not touch. One paragraph. Done. -->

# 1. Objective & success criteria

What this directive builds and the observable condition that means it worked.
Success criteria must be checkable by the smoke plan (§6), not by satisfaction.

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

| Bar | Command | Expected (specific value) | On failure emit |
|---|---|---|---|

# 7. Out of scope

What later directives do; what the executor MUST NOT touch (protected stores, sibling
modules, canon files). Explicit paths.

# 8. Records (filled as lifecycle advances)

- Checklist walk: <per-item ticks with body citations, or N/A-because-X>
- Cross-vet findings + inline fixes applied: <list>
- Build result / defects: <link defects.md if BUILT-RED>
- Post-mortem: <new failure modes -> checklist items proposed>
