# Runtime Spec — the per-project `_directives/` substrate

Canon artifact, shipped by ED-001 (Foundation), extended by ED-003 (canon purity + rot:
derived views moved into runtime). This file is the CONTRACT between canon (this repo:
templates + per-slice spec only, plugin-ready) and runtime (per-project state). The
clean-canon rule it encodes: **no directive instances, no registry, no checklist state,
no dashboards, no metrics ever live in canon.** All of that lives in the consuming
project's `_directives/`.

## Layout (created by `tools/init-runtime.py`, idempotent)

```
<project>/_directives/
├── PD/              Planning Directives  — reasoning packets, paired 1:1 with DDs
├── DD/              Decision Directives  — settled decision packets (planning output)
├── VD/              Validation Directives — the build plan; consumable by ED-00
├── ED/              Execution Directives  — per-boundary build packages (ED-NNN.md + ED-NNN.files/)
├── RD/              Review Directives     — review-phase output (shape settled in the review slice)
├── registry.jsonl   append-only status registry (see below)
├── dashboard.md     DERIVED ED dashboard — regenerated on registry appends; never an authority
├── METRICS.md       DERIVED metrics view — written on demand by execution-directives/derive-metrics.py
├── cursor.json      phase/role cursor (see schema below)
└── checklist.md     per-project earned-items appendix; canonical walk list stays in canon
```

`dashboard.md` is created as a marker skeleton by `init-runtime.py` (and lazily by
`append-registry.py`/`derive-dashboard.py` if missing); `METRICS.md` appears on the first
`derive-metrics.py` run. Both are derived views of `registry.jsonl` — regenerate at will,
never hand-edit, never treat as authority (ED-003; the pre-ED-003 defaults rendered the
dashboard into the canon README, which put runtime state into tracked canon).

## Naming decisions (settled by ED-001 — do not re-open)

| Decision | Value | Rationale |
|---|---|---|
| Runtime dir name | `_directives/` (leading underscore) | sorts first, visually distinct from source dirs, matches locked design vocabulary |
| Registry name/format | `registry.jsonl`, JSON-lines | append-only semantics native to JSONL; v1 validators already operate line-wise (`validate-registry.py validate_line`); scripts take `--registry`, so no rename churn |
| PD↔DD pairing | shared serial: `DD-012.md` ⇄ `PD-012.md`, plus frontmatter `pair:` cross-link | 1:1 pairing becomes a deterministic existence check, not an inference |
| Directive id form | `(PD|DD|VD|ED|RD)-NNN` (three digits, zero-padded) | one regex everywhere; matches v1 ED convention |
| Cursor | single file `cursor.json`, atomic replace writes only | one source of phase/role truth for gates (B4), handoff awareness (B8), and the executor harness (B2) |
| Derived views (dashboard, metrics) | runtime siblings of the registry, never canon files | ED-003: the v1 defaults regenerated the dashboard into the canon README on every append — runtime state leaked into tracked canon |
| Historical v1 state (63 EDs + registry in the superseded ag-os copy) | stays in place, read-only archive; never imported into canon or any runtime | probe 2026-07-18: this repo is already instance-free; ag-os copy is must-not-touch |

## cursor.json schema (strict — no extra keys; evolve only via a directive)

```json
{
  "phase": "planning | design | validation | execution | review",
  "role": "orchestrator | author | coder | reviewer | idle",
  "active_directive": null,
  "boundary": null,
  "postpones_used": 0,
  "updated": "YYYY-MM-DDTHH:MM:SSZ",
  "updated_by": "init-runtime | fable | coder | hook | human"
}
```

- `active_directive`: null or an id matching `(PD|DD|VD|ED|RD)-NNN`.
- `boundary`: null or a free label (e.g. `"B1-foundation"`).
- `postpones_used`: handoff-postpone counter consumed by the phase/role-aware auto-handoff
  (reset to 0 at each phase boundary by the orchestrator).
- Writers MUST use atomic replace (tmp + rename). Validator: `tools/validate-cursor.py`
  (exit 0 valid / exit 2 with field-naming errors). `updated` is calendar-valid ISO-8601
  UTC, exactly `YYYY-MM-DDTHH:MM:SSZ`, ASCII digits only (ED-003 hardening: a shape-only
  regex accepted month 13, non-ASCII digits, and trailing whitespace).

## registry.jsonl

Same line contract as the v1 system (states `DESIGN | VETTED | GREENLIT | BUILT-GREEN |
BUILT-RED | VERIFIED | REOPENED`, per-state required fields, `go_basis` on GREENLIT):
enforced by `execution-directives/validate-registry.py`; appends go through
`execution-directives/append-registry.py --registry <project>/_directives/registry.jsonl`.
Both scripts default to `<canon>/../_directives/registry.jsonl` resolved from their own
location — i.e. the canon repo's own runtime when run in place (ED-003: the v1 defaults
pointed at the out-of-repo ag-os archive). Created zero-byte by init — the validator
reports "registry is empty" until the first append; that is expected, not a defect.
Init uses exclusive create (`O_EXCL`) for `registry.jsonl`, `cursor.json`,
`checklist.md`, and `dashboard.md`: a re-init can NEVER truncate or clobber existing
runtime state (ED-003 hardening; closes the init TOCTOU). Dashboards are derived views,
never authorities.

## Canon purity guard

`tools/check-canon-purity.sh` is the deterministic clean-canon check (exit 0 pure /
exit 1 with violations listed): no git-TRACKED `_directives/` paths, no tracked
registry/cursor instances, no tracked `(PD|DD|VD|ED|RD)-NNN*.md` instance packets, and
no generated dashboard block in the README. It is the pre-flight for plugin packaging
(B11) and a standing invariant everywhere else.

## Bootstrap note (canon repo only)

The canon repo dogfoods the framework: its own `_directives/` holds the directives that
build the framework itself. The clean-canon rule is enforced by git-ignoring
`_directives/` in this repo (see `.gitignore`), so runtime state never enters the tracked
plugin surface. Consuming projects may choose to track their `_directives/` — that is a
per-project call; canon's is always ignored.
