# Portable ED bundle — install (TEMPORARY snapshot)

One-off, read-only snapshot of the ag-os ED system (source:
`dev/directive-framework/execute/` at commit `df3137d`, 2026-07-02) so ED execution
phases can run on a host where the ag-os repo is unreachable. Canonical home stays the
ag-os repo; this bundle never receives edits and gets deleted when the remote work is
done.

**Do NOT install on a host that already has the ag-os-backed /ed skill** (i.e., the
machine where ag-os lives at `~/Projects/ag-os`).

## Install

Transport this `portable/` directory to the target host (scp/rsync, or clone the ag-os
repo there), then — **from inside `portable/`** — run:

```
mkdir -p ~/.claude/skills && cp -rT ed ~/.claude/skills/ed
```

That is the whole install. It gives the target host:

- `~/.claude/skills/ed/SKILL.md` — the /ed skill (Claude Code picks it up automatically;
  trigger `/ed` in any session)
- `~/.claude/skills/ed/canon/` — the five operating docs (USAGE, ED-TEMPLATE, CHECKLIST,
  CROSS-VET, LAUNCH-TEMPLATE), read in place by the skill

Re-running the same command is safe (`-T` merges in place; it does not nest).

## Verify

```
ls ~/.claude/skills/ed/canon/USAGE.md
```

resolves → installed. In a Claude Code session, `/ed` now routes through the bundled
canon. Directive state for whatever you build lands in that project's repo at
`<repo-root>/dev/directives/` — never inside the skill directory.

## Uninstall (when the remote work is done)

```
rm -rf ~/.claude/skills/ed
```

Bring any new checklist items recorded in your EDs' §8 post-mortems back to the
canonical `execute/CHECKLIST.md` in ag-os by hand.
