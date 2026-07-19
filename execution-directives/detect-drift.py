#!/usr/bin/env python3
"""Detect drift between the ED registry (directives.jsonl) and the tree (ED-043).

validate-registry.py checks the registry's INTERNAL schema; this sibling checks the
registry against REALITY. Detection only, never reconstruction: the registry stays the
append-only authority, a mismatch is a *finding* to adjudicate (possibly a REOPENED),
never an auto-repair. This script writes nothing but its report to stdout.

Drift classes (levels calibrated against the real tree, 41 directives, 2026-07-09 —
see ED-043 §3/§4; a class is ERROR only if the real tree is clean on it or this ED's
package cleans it, so wiring into pre-commit cannot brick day-one commits):

  ERROR  missing-ed-file    registered id with no dev/directives/ED-<id>.md
  ERROR  orphan-ed-file     ED-<n>*.md on disk whose id the registry never heard of
                            (the ED-033 collision class; LAUNCH/slug files map to their
                            ED-<n> prefix and are not orphans of a registered id)
  ERROR  tier-mismatch      frontmatter `tier:` != the registry DESIGN line's tier
                            (probed clean on all 41 real EDs)
  WARN   status-mismatch    frontmatter `status:` != the registry's latest state.
                            WARN, not ERROR: ED-TEMPLATE.md calls status "informational
                            only" and 29/41 real EDs already mismatch — hard-failing
                            would block every commit. --strict promotes WARN to ERROR.
  ERROR  missing-files-dir  FULL-tier ED past DESIGN with no ED-<id>.files/ dir
                            (probed clean; ED-021 has no .files/ but is CEREMONY).
                            `.probes-complete` is deliberately NOT a drift class:
                            USAGE.md 1b makes the seam optional ("nothing breaks");
                            28/41 real FULL EDs legitimately lack it.
  ERROR  dashboard-markers  README dashboard marker pair missing/duplicated/inverted
  ERROR  stale-dashboard    README dashboard block != a fresh render of the registry
  ERROR  canon-divergence   portable/ed/canon/<f> differs from execution-directives/<f> with no
                            entry in portable/ed/canon/DIVERGENCE.md
  INFO   canon-divergence   ...same, but recorded in DIVERGENCE.md (known drift)
  ERROR  canon-missing      portable/ed/canon/<f> has no execution-directives/<f> counterpart

Registry loading and dashboard rendering are IMPORTED from derive-dashboard.py — one
STATES enum, one render, on purpose (the ED-022 lesson: parallel copies desync and die).
A registry that fails derive-dashboard's load() exits 2 here with a pointer at
validate-registry.py; schema validation is that tool's job, not this one's.

Exit codes: 0 = no ERROR findings (WARN/INFO may be present; --strict counts WARN as
ERROR), 1 = at least one ERROR finding, 2 = operational failure (unloadable registry,
missing path, missing derive-dashboard.py).
"""
import argparse
import importlib.util
import os
import re
import sys

FM_KEY = re.compile(r"^(\w[\w-]*):\s*(.*?)\s*$")
ED_FILE = re.compile(r"^(ED-\d+).*\.md$")


def op_fail(msg):
    print(f"detect-drift: {msg}", file=sys.stderr)
    sys.exit(2)


def load_dd_module(canon_dir):
    path = os.path.join(canon_dir, "derive-dashboard.py")
    if not os.path.isfile(path):
        op_fail(f"derive-dashboard.py not found in canon dir: {canon_dir}")
    spec = importlib.util.spec_from_file_location("derive_dashboard", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_frontmatter(path):
    """First ---...--- block as a flat dict; inline comments stripped from values."""
    fm = {}
    with open(path, encoding="utf-8") as f:
        if f.readline().strip() != "---":
            return fm
        for line in f:
            if line.strip() == "---":
                break
            m = FM_KEY.match(line)
            if m:
                fm[m.group(1)] = m.group(2).split("#", 1)[0].strip()
    return fm


class Report:
    def __init__(self, strict):
        self.strict = strict
        self.errors = self.warns = self.infos = 0

    def emit(self, level, cls, subject, expected, found):
        if level == "WARN" and self.strict:
            level = "ERROR"
        key = {"ERROR": "errors", "WARN": "warns", "INFO": "infos"}[level]
        setattr(self, key, getattr(self, key) + 1)
        print(f"DRIFT {level} {cls} {subject}: expected {expected}, found {found}")


def check_files_and_frontmatter(rep, eds, runtime_dir):
    ids_on_disk = set()
    for fname in sorted(os.listdir(runtime_dir)):
        m = ED_FILE.match(fname)
        if m:
            ids_on_disk.add(m.group(1))
    for ed_id in sorted(eds):
        md = os.path.join(runtime_dir, f"{ed_id}.md")
        if not os.path.isfile(md):
            rep.emit("ERROR", "missing-ed-file", ed_id,
                     f"{ed_id}.md in {runtime_dir}", "no such file")
            continue
        e = eds[ed_id]
        fm = read_frontmatter(md)
        reg_tier = e.get("tier")
        if reg_tier and reg_tier != "?" and fm.get("tier") != reg_tier:
            rep.emit("ERROR", "tier-mismatch", ed_id,
                     f"frontmatter tier '{reg_tier}' (registry DESIGN line)",
                     f"'{fm.get('tier', '<none>')}'")
        if fm.get("status", "<none>") != e["state"]:
            rep.emit("WARN", "status-mismatch", ed_id,
                     f"frontmatter status '{e['state']}' (registry latest)",
                     f"'{fm.get('status', '<none>')}'")
        if reg_tier == "FULL" and e["state"] != "DESIGN":
            if not os.path.isdir(os.path.join(runtime_dir, f"{ed_id}.files")):
                rep.emit("ERROR", "missing-files-dir", ed_id,
                         f"{ed_id}.files/ (FULL tier, state {e['state']})", "no such dir")
    for ed_id in sorted(ids_on_disk - set(eds)):
        rep.emit("ERROR", "orphan-ed-file", ed_id,
                 "a registry line for this id (append-only, ED-033 rule)",
                 f"{ed_id}*.md on disk, id never registered")


def check_dashboard(rep, dd, eds, nlines, readme):
    if not os.path.isfile(readme):
        rep.emit("ERROR", "dashboard-markers", readme,
                 "README hosting the dashboard markers", "no such file")
        return
    with open(readme, encoding="utf-8") as f:
        text = f.read()
    b, e = text.count(dd.BEGIN), text.count(dd.END)
    if b != 1 or e != 1 or text.index(dd.BEGIN) > text.index(dd.END):
        rep.emit("ERROR", "dashboard-markers", readme,
                 "exactly one BEGIN/END pair, in order", f"BEGIN={b} END={e}")
        return
    block = dd.render(eds, nlines)
    pre, rest = text.split(dd.BEGIN, 1)
    _, post = rest.split(dd.END, 1)
    if pre + dd.BEGIN + "\n" + block + "\n" + dd.END + post != text:
        rep.emit("ERROR", "stale-dashboard", readme,
                 f"dashboard rendered from the registry ({len(eds)} directives, "
                 f"{nlines} lines)",
                 "a different block; regenerate with derive-dashboard.py and "
                 "adjudicate why it drifted")


def check_canon(rep, canon_dir, portable_dir):
    if not os.path.isdir(portable_dir):
        return  # no portable snapshot in this checkout -- nothing to compare
    recorded = ""
    div = os.path.join(portable_dir, "DIVERGENCE.md")
    if os.path.isfile(div):
        with open(div, encoding="utf-8") as f:
            recorded = f.read()
    for fname in sorted(os.listdir(portable_dir)):
        if fname == "DIVERGENCE.md" or not os.path.isfile(os.path.join(portable_dir, fname)):
            continue
        counterpart = os.path.join(canon_dir, fname)
        if not os.path.isfile(counterpart):
            rep.emit("ERROR", "canon-missing", fname,
                     f"counterpart {counterpart}", "no such file")
            continue
        with open(os.path.join(portable_dir, fname), "rb") as a, \
                open(counterpart, "rb") as b:
            if a.read() == b.read():
                continue
        if re.search(r"\b" + re.escape(fname) + r"\b", recorded):
            rep.emit("INFO", "canon-divergence", fname,
                     "match with execution-directives/ canon", "recorded divergence (DIVERGENCE.md)")
        else:
            rep.emit("ERROR", "canon-divergence", fname,
                     "byte-match with execution-directives/ canon OR a DIVERGENCE.md entry",
                     "silent divergence since the portable snapshot")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    ap = argparse.ArgumentParser(
        description="read-only ED registry<->tree drift detector (ED-043)")
    ap.add_argument("--runtime-dir", default=os.path.abspath(os.path.join(here, "..", "_directives")))
    ap.add_argument("--registry", default=None,
                    help="default: <runtime-dir>/registry.jsonl")
    ap.add_argument("--readme",
                    default=os.path.abspath(os.path.join(here, "..", "_directives", "dashboard.md")))
    ap.add_argument("--canon-dir", default=here,
                    help="dir holding derive-dashboard.py + canon files")
    ap.add_argument("--portable-dir",
                    default=os.path.abspath(os.path.join(here, "..", "portable", "ed", "canon")))
    ap.add_argument("--strict", action="store_true",
                    help="count WARN findings as ERROR for the exit code")
    args = ap.parse_args()
    registry = args.registry or os.path.join(args.runtime_dir, "registry.jsonl")
    if not os.path.isdir(args.runtime_dir):
        op_fail(f"runtime dir not found: {args.runtime_dir}")

    dd = load_dd_module(args.canon_dir)
    try:
        eds, nlines = dd.load(registry)
    except SystemExit:
        op_fail("registry failed to load -- fix schema first: "
                f"python3 {os.path.join(args.canon_dir, 'validate-registry.py')} "
                f"--registry {registry}")

    rep = Report(args.strict)
    check_files_and_frontmatter(rep, eds, args.runtime_dir)
    check_dashboard(rep, dd, eds, nlines, args.readme)
    check_canon(rep, args.canon_dir, args.portable_dir)

    print(f"detect-drift: {rep.errors} error(s), {rep.warns} warning(s), "
          f"{rep.infos} info -- {len(eds)} directives, {nlines} registry lines")
    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()
