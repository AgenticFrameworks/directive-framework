#!/usr/bin/env python3
"""handoff-enrichment.py — phase/role-aware ED-STATE writer for the auto-handoff seam.

Shipped by ED-006 (boundary B8). Writes the project-supplied enrichment file
(`handoff-enrichment.md`) into the claude-loop signal dir — the ED-033 seam that
auto-handoff-monitor.js splices VERBATIM into its threshold reminder. The monitor
stays project-agnostic; THIS tool is the project side: it reads
`_directives/cursor.json` (validated via the canonical validator, never a re-derived
schema — ED-004 S6 doctrine) and renders the phase/role posture, postpone budget
state, and resume protocol the next session needs.

Fail-closed: an invalid cursor exits 2 AND removes any stale enrichment file, so a
corrupt state can never be spliced into a handoff reminder as if it were current.

`--doctor` is the advisory environment checker for the G3/G4 deadlock class (BASHIR):
policy-gate.sh can deny the hard backstop's only escape actions (the Write to the
pinned handoff path; the Bash call to auto-handoff-restart.sh) unless it carries an
auto-handoff carve-out mirroring buildlock-drift-gate.sh's ED-08 carve-out. Doctor
WARNS, never blocks (exit 0 unless --strict).
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile

CANON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENRICHMENT_NAME = "handoff-enrichment.md"

# Per-phase handoff posture (FABLE-1 decided posture: never mid-planning/mid-design;
# fresh-context-per-ED-phase is the structural reset; soft-nudge primary).
PHASE_POLICY = {
    "planning": ("NEVER hand off mid-planning — record a postpone "
                 "(tools/postpone-handoff.py) and stop at the planning->design boundary."),
    "design": ("NEVER hand off mid-design — record a postpone "
               "(tools/postpone-handoff.py) and stop at the design->validation boundary."),
    "validation": ("Finish the current gate walk, then hand off at the "
                   "validation->execution boundary; postpone if mid-walk."),
    "execution": ("Coder contexts are fresh-per-ED (structural reset). Finish the "
                  "current smoke bar, then hand off at the ED boundary — never "
                  "mid-apply."),
    "review": ("Stop at the review close-out (VERIFIED registry append), then hand "
               "off; postpone if mid-verdict."),
}


def run_validator(cursor_path):
    """Canonical cursor validation — call site mirrors tools/gate-runner.py:407-422
    (`validate-cursor.py <path>` single positional, exit 0/2)."""
    validator = os.path.join(CANON, "tools", "validate-cursor.py")
    if not os.path.isfile(validator):
        return 2, f"validator missing at {validator} — canon incomplete"
    try:
        proc = subprocess.run(["python3", validator, cursor_path],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 2, f"could not run validate-cursor.py: {exc}"
    return proc.returncode, (proc.stderr.strip() or proc.stdout.strip())


def build_block(cursor, now):
    phase = cursor["phase"]
    used = cursor["postpones_used"]
    active = cursor["active_directive"] or "none"
    boundary = cursor["boundary"] or "none"
    budget_note = ("BUDGET EXHAUSTED — HiTL escalation required; hand off at the "
                   "next boundary NOW" if used >= 2 else
                   f"{2 - used} postpone(s) remaining (each ~20k tokens), then HiTL")
    lines = [
        f"ED-STATE (directive-framework B8) — generated {now} by tools/handoff-enrichment.py",
        f"- phase: {phase}",
        f"- role: {cursor['role']}",
        f"- active_directive: {active}",
        f"- boundary: {boundary}",
        f"- postpones_used: {used} of 2 — {budget_note}",
        f"- phase policy: {PHASE_POLICY[phase]}",
        ("- resume protocol: read _directives/cursor.json, the ROADMAP.md row for the "
         "active boundary, and the active directive file (registry latest state wins) "
         "before any new work."),
    ]
    return "\n".join(lines) + "\n"


def cmd_write(args):
    signal_dir = args.signal_dir or os.environ.get("CLAUDE_LOOP_SIGNAL_DIR")
    if not signal_dir and not args.stdout:
        print("handoff-enrichment: no signal dir (--signal-dir or "
              "CLAUDE_LOOP_SIGNAL_DIR) and no --stdout — nothing to write to",
              file=sys.stderr)
        return 2
    enrichment_path = (os.path.join(signal_dir, ENRICHMENT_NAME)
                       if signal_dir else None)

    if args.remove:
        if enrichment_path and os.path.exists(enrichment_path):
            os.unlink(enrichment_path)
            print(f"handoff-enrichment: removed {enrichment_path}")
        else:
            print("handoff-enrichment: nothing to remove")
        return 0

    cursor_path = os.path.join(args.project, "_directives", "cursor.json")
    rc, msg = run_validator(cursor_path)
    if rc != 0:
        # Fail-closed: purge stale enrichment so a corrupt cursor is never spliced
        # into a handoff reminder as if current.
        if enrichment_path and os.path.exists(enrichment_path):
            os.unlink(enrichment_path)
            print("handoff-enrichment: removed stale enrichment (fail-closed)",
                  file=sys.stderr)
        print(f"handoff-enrichment: cursor invalid — {msg}", file=sys.stderr)
        return 2

    with open(cursor_path, encoding="utf-8") as f:
        cursor = json.load(f)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = build_block(cursor, now)

    if args.stdout:
        sys.stdout.write(block)
        return 0
    fd, tmp = tempfile.mkstemp(dir=signal_dir, prefix=".tmp-enrich-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(block)
    os.replace(tmp, enrichment_path)
    print(f"handoff-enrichment: wrote {enrichment_path} "
          f"(phase={cursor['phase']} role={cursor['role']} "
          f"postpones_used={cursor['postpones_used']})")
    return 0


def cmd_doctor(args):
    warns = 0

    def ok(msg):
        print(f"doctor OK: {msg}")

    def warn(msg):
        nonlocal warns
        warns += 1
        print(f"doctor WARN: {msg}")

    restart = os.path.expanduser(args.restart_script)
    if os.path.isfile(restart) and os.access(restart, os.X_OK):
        ok(f"restart script present + executable: {restart}")
    else:
        warn(f"restart script missing or not executable: {restart} — the hard "
             "backstop's escape path cannot complete")

    hooks_dir = os.path.expanduser(args.hooks_dir)
    for hook in ("auto-handoff-monitor.js", "auto-handoff-gate.js"):
        if os.path.isfile(os.path.join(hooks_dir, hook)):
            ok(f"hook present: {hook}")
        else:
            warn(f"hook missing: {os.path.join(hooks_dir, hook)}")

    pg = os.path.expanduser(args.policy_gate)
    if not os.path.isfile(pg):
        ok(f"no policy gate at {pg} — no deadlock surface")
    else:
        try:
            with open(pg, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as exc:
            content = ""
            warn(f"could not read policy gate {pg}: {exc}")
        if content and "auto-handoff" in content:
            ok("policy gate carries an auto-handoff carve-out reference")
        elif content:
            warn("CARVE-OUT MISSING (G3/G4): policy gate can deny the hard "
                 "backstop's only escape actions (Write to the pinned handoff "
                 "path; Bash auto-handoff-restart.sh) — mirror the "
                 "buildlock-drift-gate.sh ED-08 carve-out")

    if warns and args.strict:
        print(f"doctor: {warns} warning(s) — strict mode fails", file=sys.stderr)
        return 1
    print(f"doctor: {warns} warning(s) — advisory only")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--project", default=".", help="project root (default: cwd)")
    p.add_argument("--signal-dir", help="claude-loop signal dir "
                   "(default: $CLAUDE_LOOP_SIGNAL_DIR)")
    p.add_argument("--stdout", action="store_true",
                   help="print the block instead of writing the seam file")
    p.add_argument("--remove", action="store_true",
                   help="remove the enrichment file (orchestrator clears at "
                   "phase boundaries)")
    p.add_argument("--doctor", action="store_true",
                   help="advisory environment check (G3/G4 deadlock class)")
    p.add_argument("--strict", action="store_true",
                   help="doctor: exit 1 on warnings")
    p.add_argument("--policy-gate",
                   default="~/.claude/hooks/policy-gate.sh")
    p.add_argument("--restart-script",
                   default="~/.claude/scripts/auto-handoff-restart.sh")
    p.add_argument("--hooks-dir", default="~/.claude/hooks")
    args = p.parse_args()
    sys.exit(cmd_doctor(args) if args.doctor else cmd_write(args))


if __name__ == "__main__":
    main()
