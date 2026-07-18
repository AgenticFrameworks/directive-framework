# Launch Prompt Template

The launch prompt is what the executor reads FIRST. Assume it may misread the ED: every
load-bearing fact is duplicated here so a misread cannot cascade. Fill every <slot>;
delete nothing structural.

---

You are executing directive **<ED-id>: <title>**. Your job is: apply the package, wire it,
run the smoke, report. Nothing else.

## Files to READ (all of them, before anything else)

- <path/to/ED-XXX.md>
- <path/to/ED-XXX.files/ — the implementation package you will apply>
- <every other file, explicitly; no "read whatever's relevant">

## Files to BUILD / APPLY

- <exact target path> <- apply <package file> (apply as-is; do not retype or "improve")
- <exact target path for anything genuinely written fresh, e.g. smoke harness>

## Critical constants (verbatim — these exact values)

- model: `<...>`
- timeout(s): `<...>`
- caps/limits: `<...>`
- IDs/paths that must appear verbatim: `<...>`  (transcription risk — copy, don't type
  from memory)

## Execution rules

1. **Hard stop on red — do NOT iterate fixes past a red bar.** On any failed smoke bar:
   write `defects.md` (bar number, expected, got, hypothesis), append a BUILT-RED line to
   `<path>/directives.jsonl`, and exit. The fix cycle belongs to the authoring capacity,
   not you.
2. **Wall-clock kill: <N> minutes.** The smoke's watchdog enforces this in code; if you
   somehow exceed it outside the smoke, stop and report.
3. Run bars strictly in order. Bar 0 is wiring (cheap); do not start the slow portion
   until wiring is green.
4. Smoke result is written once, atomically, by the harness. Do not hand-edit result
   files. Do not run the smoke if its lockfile is held.

## Out of scope — MUST NOT touch

- <protected stores / canon files / sibling modules, explicit paths>
- <what later directives will do — not yours>

## Report

When done (green or red): result location, bar-by-bar one-liners, defects.md if red,
and the directives.jsonl line you appended.
