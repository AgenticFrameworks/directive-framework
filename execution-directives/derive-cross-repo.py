#!/usr/bin/env python3
"""Cross-repo view over every project's ED registry and handoffs.

Read-only derivation from each repo's authoritative per-repo state:
  - ED status:  <projects-root>/*/dev/directives/directives.jsonl (append-only registry)
  - Handoffs:   <projects-root>/*/handoffs/*.md

No writes anywhere. No new authority introduced. Filters compose; --json
emits machine-readable output. Fails soft on unreadable files (warns to
stderr), fails hard on malformed registry lines to match validate-registry.py.
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

STATES = {"DESIGN", "VETTED", "GREENLIT", "BUILT-GREEN", "BUILT-RED", "VERIFIED", "REOPENED"}


def warn(msg):
    print(f"derive-cross-repo: {msg}", file=sys.stderr)


def die(msg):
    warn(msg)
    sys.exit(2)


def load_registry(path):
    """Return {ed_id: {state, ts, tier, ...}} or die on malformed lines."""
    eds = {}
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f.read().splitlines(), 1):
            if not line.strip():
                die(f"{path}:{n}: blank line in append-only registry")
            try:
                d = json.loads(line)
            except json.JSONDecodeError as exc:
                die(f"{path}:{n}: invalid JSON ({exc.msg})")
            missing = {"id", "state", "ts"} - d.keys()
            if missing:
                die(f"{path}:{n}: missing required keys {sorted(missing)}")
            if d["state"] not in STATES:
                die(f"{path}:{n}: unknown state {d['state']!r}")
            e = eds.setdefault(d["id"], {})
            e["state"], e["ts"] = d["state"], d["ts"]
            if d["state"] == "DESIGN":
                e["tier"] = d.get("tier", "?")
    return eds


def scan_eds(projects_root):
    """Yield (repo, ed_id, ed_record) across all repos with a directives.jsonl."""
    pattern = os.path.join(projects_root, "*", "dev", "directives", "directives.jsonl")
    for reg in sorted(glob.glob(pattern)):
        repo = reg.split(os.sep)[-4]
        try:
            eds = load_registry(reg)
        except SystemExit:
            raise
        except OSError as e:
            warn(f"{reg}: {e}")
            continue
        for ed_id, rec in eds.items():
            yield repo, ed_id, rec


def scan_handoffs(projects_root):
    """Yield (repo, handoff_file, mtime_iso) for every per-repo handoff file."""
    pattern = os.path.join(projects_root, "*", "handoffs", "*.md")
    for path in sorted(glob.glob(pattern)):
        repo = path.split(os.sep)[-3]
        try:
            mt = os.path.getmtime(path)
        except OSError as e:
            warn(f"{path}: {e}")
            continue
        iso = datetime.fromtimestamp(mt, tz=timezone.utc).isoformat(timespec="seconds")
        yield repo, os.path.basename(path), iso


FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def read_related(path):
    """Best-effort parse of the `related:` list in an ED file's YAML frontmatter.

    Returns list of {kind, ref} dicts or []. Does not import yaml (stdlib only).
    """
    try:
        with open(path, encoding="utf-8") as f:
            head = f.read(4096)
    except OSError:
        return []
    m = FRONTMATTER.match(head)
    if not m:
        return []
    fm = m.group(1)
    lines = fm.splitlines()
    out = []
    in_related = False
    for line in lines:
        if re.match(r"^related\s*:", line):
            in_related = True
            continue
        if in_related:
            stripped = line.strip()
            if not stripped.startswith("- "):
                break
            m2 = re.match(r"-\s*(\w+)\s*:\s*(.+)", stripped)
            if m2:
                out.append({"kind": m2.group(1), "ref": m2.group(2).strip()})
    return out


def render_table(rows, cols):
    widths = [max(len(c), max((len(str(r[c])) for r in rows), default=0)) for c in cols]
    sep = "  ".join("-" * w for w in widths)
    head = "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    body = ["  ".join(str(r[c]).ljust(w) for c, w in zip(cols, widths)) for r in rows]
    return "\n".join([head, sep] + body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects-root", default=os.path.expanduser("~/Projects"))
    ap.add_argument("--since", metavar="ISO_DATE",
                    help="filter to rows with ts >= this (YYYY-MM-DD or full ISO8601)")
    ap.add_argument("--state", choices=sorted(STATES), help="filter to one state")
    ap.add_argument("--repo", help="filter to one repo (basename under projects-root)")
    ap.add_argument("--chain", metavar="ED_ID",
                    help="find <repo>/dev/directives/ED_ID.md and print its `related:` chain")
    ap.add_argument("--no-handoffs", action="store_true", help="skip the handoffs section")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of tables")
    args = ap.parse_args()

    if args.chain:
        target = args.chain
        matches = []
        pattern = os.path.join(args.projects_root, "*", "dev", "directives", f"{target}*.md")
        for path in sorted(glob.glob(pattern)):
            repo = path.split(os.sep)[-4]
            related = read_related(path)
            matches.append({"repo": repo, "path": path, "related": related})
        if args.json:
            json.dump({"chain": matches}, sys.stdout, indent=2, sort_keys=True)
            print()
        else:
            if not matches:
                print(f"no ED matching '{target}*' found under {args.projects_root}")
            for m in matches:
                print(f"{m['repo']}: {m['path']}")
                if not m["related"]:
                    print("  (no `related:` frontmatter)")
                for r in m["related"]:
                    print(f"  - {r['kind']}: {r['ref']}")
        return

    ed_rows = []
    for repo, ed_id, rec in scan_eds(args.projects_root):
        if args.repo and repo != args.repo:
            continue
        if args.state and rec["state"] != args.state:
            continue
        if args.since and rec["ts"] < args.since:
            continue
        ed_rows.append({"repo": repo, "id": ed_id, "state": rec["state"],
                        "ts": rec["ts"], "tier": rec.get("tier", "?")})
    ed_rows.sort(key=lambda r: (r["repo"], r["id"]))

    handoff_rows = []
    if not args.no_handoffs:
        for repo, name, iso in scan_handoffs(args.projects_root):
            if args.repo and repo != args.repo:
                continue
            if args.since and iso < args.since:
                continue
            handoff_rows.append({"repo": repo, "file": name, "mtime": iso})
        handoff_rows.sort(key=lambda r: (r["repo"], r["mtime"]))

    if args.json:
        json.dump({"eds": ed_rows, "handoffs": handoff_rows}, sys.stdout, indent=2, sort_keys=True)
        print()
        return

    print(f"# ED directives across {args.projects_root} ({len(ed_rows)} rows)")
    if ed_rows:
        print(render_table(ed_rows, ["repo", "id", "tier", "state", "ts"]))
    else:
        print("(none)")
    if not args.no_handoffs:
        print()
        print(f"# Handoffs across {args.projects_root} ({len(handoff_rows)} rows)")
        if handoff_rows:
            print(render_table(handoff_rows, ["repo", "file", "mtime"]))
        else:
            print("(none)")


if __name__ == "__main__":
    main()
