#!/usr/bin/env python3
"""postpone-handoff.py — mechanical postpone counter for the auto-handoff soft nudge.

Shipped by ED-006 (boundary B8). When the auto-handoff soft nudge fires mid-phase, the
on-duty capacity (coder / ED-author / reviewer) may postpone TWICE (each postpone buys
~20k tokens of runway — advisory, the repo has no token telemetry; the COUNT is what
this tool enforces). The third attempt is refused with the HiTL escalation message.

The counter is `postpones_used` in `_directives/cursor.json` (already in the ED-001
schema — no migration). This tool only ever INCREMENTS; the reset to 0 belongs to the
phase-transition writer (`tools/cursor-phase.py`) — single-writer-per-concern, see
AUTO-HANDOFF-SPEC.md.

Fail-closed: the cursor is validated (canonical validator) before AND after the write
(tmp + validate + os.replace) — a corrupt cursor is never incremented, and this tool
can never leave the cursor schema-invalid.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile

CANON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_POSTPONES = 2


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
    p.add_argument("--by", default="postpone-handoff",
                   help="updated_by stamp (default: postpone-handoff)")
    args = p.parse_args()

    cursor_path = os.path.join(args.project, "_directives", "cursor.json")
    rc, msg = run_validator(cursor_path)
    if rc != 0:
        print(f"postpone-handoff: cursor invalid — refusing to increment: {msg}",
              file=sys.stderr)
        sys.exit(2)

    with open(cursor_path, encoding="utf-8") as f:
        d = json.load(f)

    if d["postpones_used"] >= MAX_POSTPONES:
        print(f"postpone-handoff: budget exhausted ({MAX_POSTPONES} of "
              f"{MAX_POSTPONES}) — HiTL escalation required: hand off at the next "
              "boundary NOW", file=sys.stderr)
        sys.exit(2)

    d["postpones_used"] += 1
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
        print(f"postpone-handoff: post-write validation failed — cursor untouched: "
              f"{msg}", file=sys.stderr)
        sys.exit(2)
    os.replace(tmp, cursor_path)

    print(f"postpone-handoff: postpone {d['postpones_used']} of {MAX_POSTPONES} "
          "granted (~20k tokens) — hand off at the next natural boundary if the "
          "nudge persists; re-run tools/handoff-enrichment.py to refresh ED-STATE")
    sys.exit(0)


if __name__ == "__main__":
    main()
