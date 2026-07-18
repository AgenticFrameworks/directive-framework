#!/usr/bin/env python3
"""Sync-aware single append path for the ED registry (ED-060, audit F2, Gitea issue #2).

Registry appends were hand-authored: sessions scouted the next id by reading the jsonl
tail, then echo'd a line by hand. That produced the ED-033 id collision (two concurrent
sessions claimed the same id) and recurring stale-dashboard commit-gate refusals. This
tool is the one mediated append path:

  * exclusive `flock` on the registry file for the read-check-write window (kills the
    concurrent-session collision class; lock wait is BOUNDED, never indefinite)
  * `--next-id` prints the next free id (max ED-NNN + 1) under the same lock
  * the candidate line runs through validate-registry.py's `validate_line` BEFORE any
    byte is written (per-state field rules: tier, review_channel+findings,
    authoring_wallclock_min, smoke_first_run, reason)
  * id guards: a DESIGN line must carry a FRESH id; any other state must reference an
    id already in the registry — both directions of the ED-033 class refused
  * after a successful append the dashboard is regenerated via derive-dashboard.py so
    the pre-commit currency gate never sees a stale derived view
  * `--sync` is a RESERVED interface only: it errors until Phase 1 forge-sync.py lands
    (ED<->forge contract agos-grp-d8c9e5, item 6)

Exit codes (each failure message says which):
  0  appended (and dashboard regenerated), or --next-id printed
  2  refused — invalid/failed-validation line, id-guard violation, bad usage;
     NOTHING was written
  3  lock not acquired within --lock-timeout seconds; NOTHING was written
  4  line WAS appended but the dashboard regeneration failed — the append is durable;
     rerun derive-dashboard.py before committing or the commit gate will refuse
  5  --sync requested but forge-sync is not installed (Phase 1)

validate-registry.py has hyphens, so it is imported via importlib
(spec_from_file_location), not `import` — probed at authoring (ED-060 §3 P1).
"""
import argparse
import fcntl
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REGISTRY = os.path.abspath(os.path.join(HERE, "..", "..", "directives", "directives.jsonl"))
DEFAULT_README = os.path.abspath(os.path.join(HERE, "..", "README.md"))
DERIVE_DASHBOARD = os.path.join(HERE, "derive-dashboard.py")
VALIDATE_REGISTRY = os.path.join(HERE, "validate-registry.py")
ID_RE = re.compile(r"^ED-(\d+)$")


def die(code, msg):
    print(f"append-registry: {msg}", file=sys.stderr)
    sys.exit(code)


def load_validate_line():
    spec = importlib.util.spec_from_file_location("validate_registry", VALIDATE_REGISTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_line


def acquire_lock(f, timeout):
    """Bounded-wait exclusive flock: LOCK_NB retried until timeout (kill rule in code,
    CHECKLIST B4 — a plain blocking flock could hang a session indefinitely)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                die(3, f"could not lock registry within {timeout}s — another appender "
                       "is in flight; retry, or check for a wedged holder "
                       "(fuser -v on the registry). NOTHING was written.")
            time.sleep(0.1)


def existing_ids(lines):
    ids = set()
    for line in lines:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and isinstance(d.get("id"), str):
            ids.add(d["id"])
    return ids


def next_id(lines):
    nums = []
    for i in existing_ids(lines):
        m = ID_RE.match(i)
        if m:
            nums.append(int(m.group(1)))
    if not nums:
        die(2, "no ED-NNN ids found in registry; cannot derive --next-id")
    return "ED-{:03d}".format(max(nums) + 1)


def regen_dashboard(registry, readme):
    """Any nonzero rc is failure: a non-dict registry line makes derive-dashboard die
    with a raw traceback at rc=1, not its documented exit 2 (probed, ED-060 §3 P4)."""
    proc = subprocess.run(
        [sys.executable, DERIVE_DASHBOARD, "--registry", registry, "--readme", readme],
        capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("line", nargs="?",
                    help="the JSON registry line to append, or '-' to read it from stdin")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--readme", default=DEFAULT_README,
                    help="README carrying the dashboard marker pair (passed to derive-dashboard.py)")
    ap.add_argument("--next-id", action="store_true",
                    help="print the next free ED-NNN id under the registry lock and exit")
    ap.add_argument("--lock-timeout", type=float, default=10.0,
                    help="seconds to wait for the registry flock before giving up (default 10)")
    ap.add_argument("--no-dashboard", action="store_true",
                    help="skip dashboard regeneration (smoke/plumbing use only; the "
                         "commit gate WILL refuse a stale dashboard)")
    ap.add_argument("--sync", action="store_true",
                    help="RESERVED: mirror this append to the forge (Phase 1, not installed)")
    args = ap.parse_args()

    if args.sync:
        die(5, "forge-sync not installed (Phase 1) — --sync is a reserved interface "
               "per the ED<->forge contract (agos-grp-d8c9e5 item 6). "
               "Re-run without --sync.")
    if not os.path.isfile(args.registry):
        die(2, f"registry not found: {args.registry}")
    if args.next_id and args.line:
        die(2, "--next-id takes no line argument")
    if not args.next_id and not args.line:
        die(2, "nothing to do: pass a JSON line (or '-' for stdin), or --next-id")

    raw = None
    if not args.next_id:
        raw = sys.stdin.read() if args.line == "-" else args.line
        raw = raw.strip()
        if not raw:
            die(2, "empty line; NOTHING was written")
        if "\n" in raw:
            die(2, "candidate is more than one line; the registry takes exactly one "
                   "JSON object per append. NOTHING was written.")

    # a+ so open never truncates and the fd is lockable + appendable
    with open(args.registry, "a+", encoding="utf-8") as f:
        acquire_lock(f, args.lock_timeout)
        f.seek(0)
        content = f.read()
        lines = content.splitlines()

        if args.next_id:
            print(next_id(lines))
            return

        # validate the candidate BEFORE any byte is written
        errors = []
        load_validate_line()(len(lines) + 1, raw, errors)
        if errors:
            for e in errors:
                print(f"append-registry: {e}", file=sys.stderr)
            die(2, "candidate line failed validation; NOTHING was written")

        d = json.loads(raw)  # validate_line guarantees a dict with id/state/ts
        ids = existing_ids(lines)
        if d["state"] == "DESIGN" and d["id"] in ids:
            die(2, f"id collision: {d['id']} already exists in the registry but the "
                   f"candidate is a DESIGN line (a NEW directive needs a fresh id — "
                   f"run --next-id; this is the ED-033 class). NOTHING was written.")
        if d["state"] != "DESIGN" and d["id"] not in ids:
            die(2, f"unknown id: {d['id']} has no DESIGN line in the registry but the "
                   f"candidate state is {d['state']} (state changes must reference an "
                   f"existing directive — typo?). NOTHING was written.")

        out = raw + "\n"
        if content and not content.endswith("\n"):
            out = "\n" + out  # repair a missing trailing newline instead of gluing lines
        f.write(out)
        f.flush()
        os.fsync(f.fileno())
        # lock releases on close; dashboard regen below re-reads the file read-only

    print(f"append-registry: appended {d['id']} {d['state']} "
          f"({len(lines) + 1} lines) -> {args.registry}")

    if args.no_dashboard:
        print("append-registry: dashboard regen SKIPPED (--no-dashboard); the commit "
              "gate will refuse until derive-dashboard.py runs")
        return
    rc, msg = regen_dashboard(args.registry, args.readme)
    if rc != 0:
        tail = "\n".join(msg.splitlines()[-6:])
        die(4, "line WAS appended, but dashboard regeneration failed "
               f"(derive-dashboard rc={rc}):\n{tail}\n"
               "Fix and rerun: python3 " + DERIVE_DASHBOARD)
    print(msg)


if __name__ == "__main__":
    main()
