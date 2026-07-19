#!/usr/bin/env python3
"""tools/precipitate.py — deterministic vault->runtime planning adapter (ED-005, boundary B5).

Reads a biblio vault NOTEBOOK directory (the directory that contains
`50-design-directives/DD-NN.md` — 2-digit per-notebook serials, the vault ladder
contract) and precipitates each vault DD into a consuming project's `_directives/`
runtime as a PAIRED packet per RUNTIME-SPEC: `PD-NNN.md` (provenance/reasoning
pointer, non-consumable) + `DD-NNN.md` (the decision, body re-homed verbatim),
shared 3-digit serial. The vault is NEVER written — retarget, don't rebuild.

Usage:
    python3 tools/precipitate.py <vault-notebook-dir> [--project DIR]

Behavior contract (ED-005 §4):
- serial allocation: max existing serial across _directives/PD + _directives/DD,
  then +1 per new pair (never collides with hand-authored packets)
- PD written FIRST, then DD (an orphan PD is benign planning-in-progress; an
  orphan DD would trip the design-intake pd-dd-pairing check)
- exclusive create (open mode 'x') — a precipitation can NEVER clobber existing
  runtime state (ED-003 init hardening precedent)
- idempotent: each precipitated DD records `source:` = the vault DD id; sources
  already present in _directives/DD are skipped on re-run
- packets land `status: draft` — settling to `settled` is an explicit
  planning-phase act (gates/validation-intake.md dd-status-settled enforces it
  at design->validation)

Exit codes: 0 OK (including an all-skipped idempotent re-run), 2 any error
(fail-closed — no crash class may look recoverable).
"""

import os
import re
import sys
from datetime import datetime, timezone

CANON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VAULT_DD_RE = re.compile(r"^DD-([0-9]{2})\.md$")
SERIAL_RE = re.compile(r"^(DD|PD)-([0-9]{3})(?:[.-].*)?\.md$")


class PrecipError(Exception):
    """Any adapter error — always exit 2 (fail-closed)."""


def parse_packet(path):
    """(frontmatter dict, body str). Frontmatter = leading '---' block, key: value
    line-scan (stdlib, no yaml — same discipline as tools/gate-runner.py)."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        raise PrecipError(f"cannot read {path}: {exc}")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    fm = {}
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return fm, "\n".join(lines[i + 1:])
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return {}, text  # unterminated frontmatter — treat as none (gate-runner parity)


def scan_md(dirpath):
    """os.scandir listing of regular *.md files (NUL/option-safe: no shell, no ls)."""
    try:
        with os.scandir(dirpath) as it:
            return sorted(e.name for e in it if e.is_file() and e.name.endswith(".md"))
    except OSError as exc:
        raise PrecipError(f"cannot scan {dirpath}: {exc}")


def main(argv):
    args = list(argv[1:])
    vault, project = None, CANON
    i = 0
    while i < len(args):
        if args[i] == "--project" and i + 1 < len(args):
            project = args[i + 1]
            i += 2
        elif vault is None and not args[i].startswith("-"):
            vault = args[i]
            i += 1
        else:
            print(f"precipitate: unknown/misplaced arg {args[i]!r}", file=sys.stderr)
            return 2
    if vault is None:
        print("usage: precipitate.py <vault-notebook-dir> [--project DIR]",
              file=sys.stderr)
        return 2
    vault = os.path.abspath(vault)
    dd_src = os.path.join(vault, "50-design-directives")
    if not os.path.isdir(dd_src):
        raise PrecipError(f"not a vault notebook: {dd_src} missing (expected "
                          f"<notebook>/50-design-directives/DD-NN.md — vault "
                          f"ladder contract)")
    pd_dir = os.path.join(project, "_directives", "PD")
    dd_dir = os.path.join(project, "_directives", "DD")
    for d in (pd_dir, dd_dir):
        if not os.path.isdir(d):
            raise PrecipError(f"runtime dir missing: {d} — run tools/init-runtime.py "
                              f"first")

    # vault sources, ordered by 2-digit vault serial (scan_md sorts; 2-digit
    # zero-padded means lexicographic == numeric). Non-contract files are skipped
    # VISIBLY, never silently (probe: real vaults contain stray non-serial .md).
    sources = []
    for name in scan_md(dd_src):
        m = VAULT_DD_RE.fullmatch(name)
        if not m:
            print(f"precipitate: skip non-contract file {name} "
                  f"(vault DDs are DD-NN.md)")
            continue
        fm, body = parse_packet(os.path.join(dd_src, name))
        source_id = fm.get("id") or (f"{os.path.basename(vault)}"
                                     f"/50-design-directives/DD-{m.group(1)}")
        sources.append((name, source_id, fm, body))

    # existing runtime state: precipitated source ids + max shared serial
    seen_sources = {}
    max_serial = 0
    for d, kind in ((dd_dir, "DD"), (pd_dir, "PD")):
        for name in scan_md(d):
            m = SERIAL_RE.fullmatch(name)
            if not m or m.group(1) != kind:
                continue
            max_serial = max(max_serial, int(m.group(2)))
            if kind == "DD":
                fm, _ = parse_packet(os.path.join(d, name))
                if fm.get("source"):
                    seen_sources[fm["source"]] = name

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new, skipped = 0, 0
    for vname, source_id, vfm, vbody in sources:
        if source_id in seen_sources:
            print(f"precipitate: skip {source_id} (already precipitated as "
                  f"{seen_sources[source_id]})")
            skipped += 1
            continue
        serial = max_serial + 1
        if serial > 999:
            raise PrecipError("serial space exhausted (>999) — 3-digit id contract "
                              "(RUNTIME-SPEC); refusing")
        max_serial = serial
        nnn = f"{serial:03d}"
        derived = vfm.get("derived_from", "")
        pd_path = os.path.join(pd_dir, f"PD-{nnn}.md")
        dd_path = os.path.join(dd_dir, f"DD-{nnn}.md")
        pd_text = (
            "---\n"
            f"id: PD-{nnn}\n"
            f"pair: DD-{nnn}\n"
            "status: draft\n"
            f"source: {source_id}\n"
            f"created: {ts}\n"
            "---\n"
            "\n"
            f"# PD-{nnn} — provenance for DD-{nnn}\n"
            "\n"
            "Non-consumable reasoning pointer (written by tools/precipitate.py — do\n"
            "not execute from this packet; the consumable decision is the paired DD).\n"
            "The reasoning chain that produced the decision lives in the source vault\n"
            "notebook ladder (10-sections -> 20-findings -> 30-actionables ->\n"
            "50-design-directives):\n"
            "\n"
            f"- source: {source_id}\n"
            f"- derived_from: {derived or '(not recorded in vault frontmatter)'}\n"
        )
        dd_fm = ["---", f"id: DD-{nnn}", f"pair: PD-{nnn}", "status: draft",
                 f"source: {source_id}"]
        if derived:
            dd_fm.append(f"derived_from: {derived}")
        dd_fm += [f"created: {ts}", "---"]
        dd_text = "\n".join(dd_fm) + "\n\n" + vbody.strip() + "\n"
        # PD FIRST (orphan PD benign), exclusive create — never clobber
        try:
            with open(pd_path, "x", encoding="utf-8") as f:
                f.write(pd_text)
        except FileExistsError:
            raise PrecipError(f"refusing to clobber existing {pd_path} (open 'x')")
        try:
            with open(dd_path, "x", encoding="utf-8") as f:
                f.write(dd_text)
        except FileExistsError:
            raise PrecipError(f"refusing to clobber existing {dd_path} (open 'x'); "
                              f"orphan PD-{nnn} left in place (benign, visible — "
                              f"pd-dd-pairing does not block PD-without-DD)")
        seen_sources[source_id] = f"DD-{nnn}.md"
        print(f"precipitate: PD-{nnn} + DD-{nnn} <- {source_id} ({vname})")
        new += 1
    print(f"precipitate: {new} new pair(s), {skipped} skipped, vault untouched")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except PrecipError as exc:
        print(f"precipitate: ERROR — {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001 — fail closed, never a silent crash
        print(f"precipitate: ERROR — unexpected {type(exc).__name__}: {exc}",
              file=sys.stderr)
        sys.exit(2)
