# Cross-Vet Protocol

Adversarial, independent review of an ED between checklist walk and greenlight.
Self-audit is structurally untrustworthy; this step exists to refuse the dressing.

## Independence requirement

The reviewing capacity must be a context that did NOT author the ED: fresh context at
minimum; a different model/channel where available. Record the channel used in the ED's
`review-channel:` frontmatter.

**Channel pinning:** review quality must be a property of the process, not routing luck.
The project pins a named review channel with a minimum-capability bar. If the pinned
channel is unavailable, the directive WAITS — or the lead explicitly accepts the downgrade
and records it in the ED and in directives.jsonl (`"review_downgrade": "<why>"`).

**ag-os pinned channel (2026-07-04):** fresh `claude-opus-4-8` subagent; minimum-capability
bar Opus-class. Authoring sessions here run Fable-tier, so this pin guarantees the reviewer
is a different model, not the author's model grading itself. Unavailable → WAIT, or record
`review_downgrade` per the rule above.

## Reviewer mandates (all four, every FULL ED)

1. **Replicate ≥1 load-bearing probe against real data.** Re-run it; compare with the
   ED's pasted output. Reading the prose is not review.
2. **Attack the headline gate adversarially.** Steelman an executor shortcut: "what would
   the smoke fail to catch?" Name the hole or show there isn't one.
3. **Police false ticks.** Audit the checklist walk: every `[x]` must cite an ED-body
   artifact (code block, probe output, diff) verifiable by a hostile reader. A tick whose
   body says "will do at greenlight" is a FALSE TICK — count it as RED and report the
   count. Honest deferrals are re-labeled `[ ] deferred-justified` with the gate reason.
4. **Audit the §1→§6 coverage mapping.** Parse the §1 criterion ids and the §6 `Covers`
   column: the mapping must be total (every id covered or explicitly ledgered
   `unverifiable-because-X`), and no `Covers` claim may be a false tick — a bar that
   names a criterion it does not exercise counts against the false-tick tally reported
   at VETTED (mandate 3).

## Verdict format

- **GO** — no NEEDS-FIX findings, false-tick count 0.
- **NEEDS-FIX** — numbered findings, each with severity (CRITICAL/HIGH/MED/LOW), the ED
  section it hits, and what correct looks like.

Every NEEDS-FIX is applied INLINE in the ED before greenlight — never deferred to a
follow-up directive. After the fixes are applied, an **independent context confirms them —
never the author/lead, at any severity.** Use a fresh subagent on the pinned channel; it
receives the findings list plus the applied changes (diffs/edited sections) and returns,
per finding, **resolved / not-resolved**, plus a **regression check** (did a fix break
something the ED already had right?). This is a SCOPED confirmation, not a fresh cross-vet:
reviewer mandates 1–2 are re-run only if a fix touched a load-bearing probe or the headline
gate. If any finding comes back not-resolved, the author re-fixes and the delta-confirm
repeats — the ED does not reach VETTED until an independent pass returns all-resolved /
zero-regression. Record the delta-confirm channel and per-finding verdict in ED §8, and
summarize it in the VETTED line of directives.jsonl (`"delta_confirm"`). Findings and fix
counts also go into that VETTED line.

Rationale (flaw A2, 2026-07-04): the reviewer was independent but the JUDGE of the reviewer
was not — the lead (same lineage as the author) previously confirmed MED/LOW rounds,
letting the author certify their own fixes. Independent delta-confirm at all severities
closes that last same-lineage link.

CEREMONY-tier EDs skip mandates 1–2 and 4 (no §3 probes, no §6 to map); the reviewer (or lead) sanity-checks scope and the
out-of-scope list only.
