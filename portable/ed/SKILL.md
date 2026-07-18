---
name: ed
description: "Run a change through the ED (Execution Directive) system: author -> checklist -> cross-vet -> explicit greenlight -> execute -> verify. Use when the user types /ed, says 'execution directive', 'author an ED', 'run this through the ED system', or wants a change built with directive-framework rigor. PORTABLE SNAPSHOT variant — carries its own canon copy for hosts where the ag-os repo is unreachable."
trigger: /ed
---

> **TEMPORARY PORTABLE SNAPSHOT — read this banner first.**
> This is a one-off, read-only snapshot of the ag-os directive framework, taken from
> `dev/directive-framework/execute/` at commit `df3137d` on 2026-07-02. The canonical
> home is the ag-os repo (git.cloudmarsh.com, CloudMarsh-Lan/ag-os); improvements land
> ONLY there — never edit the files in this bundle. Do NOT install this on a host that
> already has the ag-os-backed /ed skill (the machine where ag-os lives at
> `~/Projects/ag-os`). Uninstall (`rm -rf ~/.claude/skills/ed`) when the remote work is
> done.

# /ed — Execution Directive lifecycle (portable snapshot)

The ED system takes a change from intent to verified build with no-bullshit gates:
**author → checklist walk → independent cross-vet → explicit greenlight → execute →
verify → post-mortem**. Every change gets an ED; trivial ones use the CEREMONY tier
(costs a paragraph).

## Canon (bundled with this skill)

The entry point is the snapshot canon INSIDE this skill's own directory — read it FIRST:

```
~/.claude/skills/ed/canon/USAGE.md
```

It names the rest (ED-TEMPLATE.md, CHECKLIST.md, CROSS-VET.md, LAUNCH-TEMPLATE.md), all
present in the same `canon/` directory. Two deliberate deviations from what USAGE.md
describes — these OVERRIDE its same-directory description, they are not broken canon:

- **DESIGN.md is intentionally excluded** from this bundle (background/rationale only;
  USAGE.md itself says you do not need it to operate).
- **Directive state does NOT live next to the canon.** `directives.jsonl` and the ED
  files live in the project you are working on, at `<repo-root>/dev/directives/` (see
  below) — never inside this skill directory.

Instantiation vs forking: copying `canon/ED-TEMPLATE.md` into your project as
`ED-<id>.md` is REQUIRED (USAGE.md step 1). Editing the `canon/` files themselves is
FORBIDDEN — they are a dated snapshot; changes belong in the ag-os repo.

## Per-project state

Each consuming repo keeps its own directive state; nothing global, nothing shared:

- **Location:** `<repo-root>/dev/directives/` (create lazily on first ED). It holds
  `ED-XXX.md`, `ED-XXX.files/`, and the repo's own append-only `directives.jsonl` — the
  ONLY status authority for that repo; dashboards are derived, never hand-edited.
- **IDs** are namespaced per project and continue from the highest existing `ED-XXX` in
  that dir. If the dir already exists holding non-ED content, ask the user before writing.

## Cross-vet channel

No pinned review channel exists. Use an independent fresh context (subagent at minimum,
a different model/channel where available) and record the downgrade honestly in the ED's
`review-channel:` frontmatter and the VETTED line, e.g.
`<model>, fresh general-purpose subagent (no project pin yet)`.

## Checklist growth — record locally, return manually

The canonical CHECKLIST.md (ag-os) is unreachable from this host, so growth CANNOT flow
back automatically. A NEW failure mode found while building here is recorded in the local
ED's §8 post-mortem as a proposed checklist item, tagged
`*(Earned, origin <project>: <incident>)*`, for manual return to the canonical
CHECKLIST.md later. Do not edit the bundled `canon/CHECKLIST.md`.

## On invocation

1. Read `~/.claude/skills/ed/canon/USAGE.md`; hard-stop and tell the user if this
   skill's `canon/` directory is missing or incomplete.
2. Follow its lifecycle exactly — including the explicit-greenlight gate
   (never build without a GO) and HARD STOP ON RED during execution (write defects.md
   and exit; do not iterate fixes past a failed bar).
3. Author into `<repo-root>/dev/directives/` per the state rules above.
