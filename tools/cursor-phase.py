#!/usr/bin/env python3
"""cursor-phase.py — sanctioned phase-transition writer for `_directives/cursor.json`.

Shipped by ED-006 (boundary B8). The orchestrator's mechanical cursor writer for
phase/role transitions outside the executor (the executor keeps its own same-phase
writes — `set_cursor` in tools/executor-run.sh:118-131 only ever flips role within
`phase=execution` and PRESERVES `postpones_used`).

**Reset ownership (the B8 open decision, settled here):** `postpones_used` resets to 0
on every PHASE CHANGE, performed by THIS writer as part of the same atomic cursor
write. Same-phase transitions (role flips) preserve the count. Rationale in
AUTO-HANDOFF-SPEC.md: the postpone budget is per-phase-occupancy; the writer that
flips the phase already owns an atomic validated write, so bundling the reset avoids
a second writer racing the first; and the gate-runner is read-only by contract
(ED-004), so a runner side effect was rejected.

Fail-closed both ways: refuses to transition a schema-invalid cursor (repair is a
manual act), and validates the NEW content in a tmp file via the canonical validator
before os.replace — bad enum arguments are caught by the validator itself, never by a
re-derived schema (ED-004 S6 doctrine).
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile

CANON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_validator(cursor_path):
    """Call site mirrors tools/gate-runner.py:407-422 (single positional, exit 0/2)."""
    validator = os.path.join(CANON, "tools", "validate-cursor.py")
    if not os.path.isfile(validator):
        return 2, f"validator missing at {validator} — canon incomplete"
    try:
        proc = subprocess.run(["python3", validator, cursor_path],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 2, f"could not run validate-cursor.py: {exc}"
    return proc.returncode, (proc.stderr.strip() or proc.stdout.strip())


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--project", default=".", help="project root (default: cwd)")
    p.add_argument("--phase", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--directive", default="none",
                   help="active directive id, or 'none' (default)")
    p.add_argument("--boundary", default="none",
                   help="boundary label, or 'none' (default)")
    p.add_argument("--by", default="cursor-phase",
                   help="updated_by stamp (default: cursor-phase)")
    args = p.parse_args()

    cursor_path = os.path.join(args.project, "_directives", "cursor.json")
    rc, msg = run_validator(cursor_path)
    if rc != 0:
        print(f"cursor-phase: current cursor invalid — refusing to transition "
              f"(repair it manually, then validate): {msg}", file=sys.stderr)
        sys.exit(2)

    with open(cursor_path, encoding="utf-8") as f:
        d = json.load(f)
    old_phase, old_role, old_used = d["phase"], d["role"], d["postpones_used"]

    phase_changed = args.phase != old_phase
    d["phase"] = args.phase
    d["role"] = args.role
    d["active_directive"] = None if args.directive == "none" else args.directive
    d["boundary"] = None if args.boundary == "none" else args.boundary
    if phase_changed:
        d["postpones_used"] = 0
    d["updated"] = datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    d["updated_by"] = args.by

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(cursor_path), prefix=".tmp-cur-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
        f.write("\n")
    rc, msg = run_validator(tmp)
    if rc != 0:
        os.unlink(tmp)
        print(f"cursor-phase: proposed transition is invalid — cursor untouched: "
              f"{msg}", file=sys.stderr)
        sys.exit(2)
    os.replace(tmp, cursor_path)

    reset_note = ("postpones_used reset to 0 (phase change)" if phase_changed
                  else f"postpones_used preserved ({old_used}) (same phase)")
    print(f"cursor-phase: {old_phase}/{old_role} -> {args.phase}/{args.role} "
          f"active={d['active_directive']} boundary={d['boundary']} — {reset_note}")
    sys.exit(0)


if __name__ == "__main__":
    main()
