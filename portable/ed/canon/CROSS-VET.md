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

## Reviewer mandates (all three, every FULL ED)

1. **Replicate ≥1 load-bearing probe against real data.** Re-run it; compare with the
   ED's pasted output. Reading the prose is not review.
2. **Attack the headline gate adversarially.** Steelman an executor shortcut: "what would
   the smoke fail to catch?" Name the hole or show there isn't one.
3. **Police false ticks.** Audit the checklist walk: every `[x]` must cite an ED-body
   artifact (code block, probe output, diff) verifiable by a hostile reader. A tick whose
   body says "will do at greenlight" is a FALSE TICK — count it as RED and report the
   count. Honest deferrals are re-labeled `[ ] deferred-justified` with the gate reason.

## Verdict format

- **GO** — no NEEDS-FIX findings, false-tick count 0.
- **NEEDS-FIX** — numbered findings, each with severity (CRITICAL/HIGH/MED/LOW), the ED
  section it hits, and what correct looks like.

Every NEEDS-FIX is applied INLINE in the ED before greenlight — never deferred to a
follow-up directive. After fixes, the reviewer (or lead, for MED/LOW-only rounds)
confirms the deltas. Findings and fixes are recorded in ED §8 and the counts go into the
VETTED line of directives.jsonl.

CEREMONY-tier EDs skip mandates 1–2; the reviewer (or lead) sanity-checks scope and the
out-of-scope list only.
