#!/usr/bin/env python3
"""tools/gate-runner.py — phase-boundary intake-gate runner (ED-004, boundary B4).

Consumes a gate TEMPLATE (gates/<gate>.md), extracts its machine-readable `gate-spec`
fenced JSON block, and runs the declared checks against a project's `_directives/`
runtime. The runner is READ-ONLY: it writes nothing, takes no lock (a smoke that
exercises it holds its own flock, C7), and never mutates registry/cursor state.

Usage:
    python3 tools/gate-runner.py <gates/TEMPLATE.md> [--project DIR] [--id ED-NNN]
    python3 tools/gate-runner.py --validate-templates <gates-dir>

Exit codes (the contract, see gates/GATES-SPEC.md):
    0  PASS    — every live blocking check passed
    1  BOUNCE  — a soft-gate check failed: the transition is BLOCKED but the
                 bounce-back is recoverable and cheap (fail-closed, not advisory)
    2  BLOCK   — a hard/strict check failed, OR any runner/template/cursor error
                 (unknown check id, malformed spec, unreadable registry): fail-closed

Check semantics:
    enforce=hard    failure -> BLOCK (exit 2)
    enforce=soft    failure -> BOUNCE (exit 1)
    enforce=report  printed, NEVER affects exit (graduation path: report->soft->hard
                    happens by later EDs editing the template, directive-governed)
    deferred:"BN"   printed as DEFERRED(BN), never pass/fail silently; only ids in
                    the sanctioned deferral registry may carry `deferred` — deferring
                    a live check id is itself a BLOCK (a template must not be able to
                    silently DEFER a shipped check)

Gates go LIVE at later boundaries (B6 wires design/validation flow, B7 flips the
executor to call this runner); B4 ships the framework only, so nothing here is
invoked by tools/executor-run.sh yet. B5 (ED-005) instantiated the planning packet
checks pd/dd-frontmatter-template: live in gates/design-intake.md, validating
packets against the canon planning-directives/(PD|DD)-TEMPLATE.md packet-spec.
"""

import json
import os
import re
import subprocess
import sys

CANON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ED_ID_RE = re.compile(r"ED-[0-9]{3}")
SERIAL_RE = re.compile(r"^(DD|PD)-([0-9]{3})(?:[.-].*)?\.md$")
BOUNDARY_RE = re.compile(r"^(planning|design|validation|execution|review)->"
                         r"(design|validation|execution|review)$")

# Ladder taxonomy (ROADMAP "Terminology guard"): 'advisory' (fail-open, ~/.claude
# policy vocab) is what a phase gate NEVER is, so it is not a valid strength here.
STRENGTHS = {"soft-gate", "hard-gate", "strict-hard"}
ENFORCE = {"hard", "soft", "report"}

# Open execution states — an ED whose latest registry state is one of these is not
# closed (everything closed = VERIFIED, or paper-only DESIGN/VETTED).
OPEN_EXECUTION_STATES = {"GREENLIT", "BUILT-GREEN", "BUILT-RED", "REOPENED"}

# Sanctioned deferrals: check id -> boundary that instantiates it. A `deferred`
# entry whose id is not here (or names a different boundary) is a BLOCK.
KNOWN_DEFERRED = {
    "vd-dd-consumption": "B6",
    "vd-attestation-present": "B6",
    "dd-ordering-dag": "B6",
    "dd-waived-or-consumed": "B6",
    "rd-packet-shape": "B9",
}


class GateError(Exception):
    """Runner/template/environment error — always exit 2 (fail-closed)."""


class CheckFail(Exception):
    """A check ran and its condition does not hold; enforce level decides exit."""


# ---------------------------------------------------------------- spec handling

def extract_gate_spec(path):
    """First fenced code block tagged `gate-spec` -> parsed JSON, or GateError."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as exc:
        raise GateError(f"cannot read template {path}: {exc}")
    block, in_block = [], False
    for line in lines:
        stripped = line.strip()
        if not in_block and stripped == "```gate-spec":
            in_block = True
            continue
        if in_block:
            if stripped == "```":
                break
            block.append(line)
    else:
        if in_block:
            raise GateError(f"{path}: unterminated ```gate-spec fence")
        raise GateError(f"{path}: no ```gate-spec fenced block found "
                        "(machine-readable contract, GATES-SPEC.md)")
    try:
        return json.loads("\n".join(block))
    except json.JSONDecodeError as exc:
        raise GateError(f"{path}: gate-spec block is not valid JSON: {exc.msg} "
                        f"(line {exc.lineno} of the block)")


def validate_spec(spec, path):
    """Schema-check a gate-spec; GateError on any violation (fail-closed)."""
    if not isinstance(spec, dict):
        raise GateError(f"{path}: gate-spec must be a JSON object")
    for key in ("gate", "strength", "boundary", "checks"):
        if key not in spec:
            raise GateError(f"{path}: gate-spec missing required key '{key}'")
    stem = os.path.splitext(os.path.basename(path))[0]
    if spec["gate"] != stem:
        raise GateError(f"{path}: gate-spec 'gate' is {spec['gate']!r} but the "
                        f"template file is {stem!r} — they must match")
    if spec["strength"] not in STRENGTHS:
        raise GateError(f"{path}: 'strength' must be one of {sorted(STRENGTHS)} "
                        f"(advisory is NEVER a phase gate — Terminology guard), "
                        f"got {spec['strength']!r}")
    if not isinstance(spec["boundary"], str) or not BOUNDARY_RE.fullmatch(spec["boundary"]):
        raise GateError(f"{path}: 'boundary' must match phase->phase "
                        f"(planning-start is the sanctioned no-gate exception), "
                        f"got {spec.get('boundary')!r}")
    checks = spec["checks"]
    if not isinstance(checks, list) or not checks:
        raise GateError(f"{path}: 'checks' must be a non-empty list")
    seen = set()
    for i, c in enumerate(checks):
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not c["id"]:
            raise GateError(f"{path}: checks[{i}] must be an object with a string 'id'")
        cid = c["id"]
        if cid in seen:
            raise GateError(f"{path}: duplicate check id {cid!r}")
        seen.add(cid)
        if c.get("enforce") not in ENFORCE:
            raise GateError(f"{path}: checks[{i}] ({cid}) 'enforce' must be one of "
                            f"{sorted(ENFORCE)}, got {c.get('enforce')!r}")
        deferred = c.get("deferred")
        if deferred is not None:
            if not isinstance(deferred, str) or not deferred:
                raise GateError(f"{path}: checks[{i}] ({cid}) 'deferred' must be a "
                                f"non-empty boundary label, got {deferred!r}")
            if cid not in KNOWN_DEFERRED:
                raise GateError(f"{path}: check {cid!r} is not in the sanctioned "
                                f"deferral registry — a template cannot defer a live "
                                f"check (fail-closed)")
            if KNOWN_DEFERRED[cid] != deferred:
                raise GateError(f"{path}: check {cid!r} defers to {deferred!r} but the "
                                f"sanctioned boundary is {KNOWN_DEFERRED[cid]!r}")
        elif cid not in CHECKS:
            raise GateError(f"{path}: unknown check id {cid!r} — not implemented and "
                            f"not a sanctioned deferral (fail-closed)")
    return spec


# ------------------------------------------------------------------- ctx + IO

def make_ctx(project, directive_id):
    root = os.path.abspath(project)
    return {
        "project": root,
        "id": directive_id,
        "registry": os.path.join(root, "_directives", "registry.jsonl"),
        "cursor": os.path.join(root, "_directives", "cursor.json"),
        "ed_dir": os.path.join(root, "_directives", "ED"),
        "dd_dir": os.path.join(root, "_directives", "DD"),
        "pd_dir": os.path.join(root, "_directives", "PD"),
    }


def require_id(ctx):
    if not ctx["id"]:
        raise GateError("this check requires --id ED-NNN (no directive id given)")
    return ctx["id"]


def load_registry(ctx):
    """registry.jsonl -> {id: [entry, ...]} in file order; malformed line = GateError."""
    path = ctx["registry"]
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as exc:
        raise GateError(f"cannot read registry {path}: {exc} (fail-closed)")
    history = {}
    for n, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GateError(f"registry {path} line {n} is not valid JSON: {exc.msg} "
                            f"(fail-closed — repair via append-registry.py discipline)")
        if not isinstance(d, dict) or not d.get("id"):
            raise GateError(f"registry {path} line {n} has no 'id' (fail-closed)")
        history.setdefault(d["id"], []).append(d)
    return history


def scan_md(dirpath):
    """os.scandir listing of regular *.md files (NUL/option-safe: no shell, no ls)."""
    try:
        with os.scandir(dirpath) as it:
            return sorted(e.name for e in it if e.is_file() and e.name.endswith(".md"))
    except OSError as exc:
        raise GateError(f"cannot scan {dirpath}: {exc}")


def parse_frontmatter(path):
    """Leading '---' block -> {key: value} (stdlib line-scan, no yaml)."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as exc:
        raise GateError(f"cannot read {path}: {exc}")
    if not lines or lines[0].strip() != "---":
        return {}
    fm = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fm
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return {}  # unterminated frontmatter — treat as none


# --------------------------------------------------------------------- checks

def check_ed_id_shape(ctx):
    ed_id = require_id(ctx)
    if not ED_ID_RE.fullmatch(ed_id):
        raise CheckFail(f"expected id matching ED-[0-9]{{3}} (fullmatch), got {ed_id!r}")
    return f"id {ed_id} matches ED-[0-9]{{3}}"


def _ed_md_candidates(ctx):
    ed_id = require_id(ctx)
    if not os.path.isdir(ctx["ed_dir"]):
        raise CheckFail(f"no ED dir at {ctx['ed_dir']} — run tools/init-runtime.py")
    names = scan_md(ctx["ed_dir"])
    # mirror of the executor's discovery (executor-run.sh:71) with two glue-generated
    # exclusions: -launch.md (the launch prompt) and -defects.md (written by the glue
    # on BUILT-RED, executor-run.sh:203 — counting it would make every post-RED
    # re-greenlight unpassable, contradicting the REOPENED re-entry decision)
    return [n for n in names
            if (n == f"{ed_id}.md" or n.startswith(f"{ed_id}-"))
            and not n.endswith("-launch.md") and not n.endswith("-defects.md")]


def check_ed_md_exactly_one(ctx):
    cands = _ed_md_candidates(ctx)
    if len(cands) != 1:
        raise CheckFail(f"expected exactly one directive file {ctx['id']}*.md "
                        f"(excluding -launch.md/-defects.md) in _directives/ED, "
                        f"got {len(cands)}: {cands!r}")
    return f"directive file: {cands[0]}"


def check_ed_launch_exists(ctx):
    ed_id = require_id(ctx)
    launch = os.path.join(ctx["ed_dir"], f"{ed_id}-launch.md")
    if not os.path.isfile(launch):
        raise CheckFail(f"launch prompt missing: _directives/ED/{ed_id}-launch.md "
                        f"(executor intake, executor-run.sh:73-74)")
    return f"launch prompt present: {ed_id}-launch.md"


def check_ed_package_nonempty(ctx):
    ed_id = require_id(ctx)
    files_dir = os.path.join(ctx["ed_dir"], f"{ed_id}.files")
    if not os.path.isdir(files_dir):
        raise CheckFail(f"package dir missing: _directives/ED/{ed_id}.files/")
    with os.scandir(files_dir) as it:
        if not any(True for _ in it):
            raise CheckFail(f"package dir empty: _directives/ED/{ed_id}.files/")
    return f"package dir non-empty: {ed_id}.files/"


def check_ed_probes_complete(ctx):
    ed_id = require_id(ctx)
    seam = os.path.join(ctx["ed_dir"], f"{ed_id}.files", ".probes-complete")
    if not os.path.isfile(seam):
        raise CheckFail(f"probes-complete seam missing: {ed_id}.files/.probes-complete "
                        f"— probes not durable on disk (executor-run.sh:77)")
    return "probes-complete seam present"


def check_ed_manifest_floor(ctx):
    """Mirror of the executor's manifest floor (executor-run.sh:78-115)."""
    ed_id = require_id(ctx)
    files_dir = os.path.join(ctx["ed_dir"], f"{ed_id}.files")
    manifest = os.path.join(files_dir, "manifest.json")
    if not os.path.isfile(manifest):
        raise CheckFail(f"manifest missing: {ed_id}.files/manifest.json "
                        f"(mechanical-apply contract)")
    try:
        with open(manifest, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckFail(f"manifest.json unreadable/invalid JSON: {exc}")
    errs = []
    apply = m.get("apply")
    if not isinstance(apply, list) or not apply:
        errs.append("'apply' must be a non-empty list")
        apply = []
    for i, e in enumerate(apply):
        if not isinstance(e, dict):
            errs.append(f"apply[{i}] must be an object")
            continue
        # paths validated BEFORE any dereference: strings only (a non-string must
        # never slip past the isinstance guards as floor-OK), relative, no '..',
        # no control chars — only then may the marker check open the source
        paths_ok = True
        for k in ("from", "to"):
            v = e.get(k)
            if not isinstance(v, str) or not v:
                errs.append(f"apply[{i}].{k} must be a non-empty string")
                paths_ok = False
            elif v.startswith("/") or ".." in v.split("/"):
                errs.append(f"apply[{i}].{k} must be relative, no '..': {v!r}")
                paths_ok = False
            elif any(c in v for c in "\t\n\r"):
                errs.append(f"apply[{i}].{k} contains control characters")
                paths_ok = False
        if e.get("mode") not in ("copy", "append"):
            errs.append(f"apply[{i}].mode must be copy|append")
        if e.get("mode") == "append":
            marker = e.get("marker")
            if not isinstance(marker, str) or not marker:
                errs.append(f"apply[{i}] append requires a non-empty string 'marker'")
            elif any(c in marker for c in "\t\n\r"):
                errs.append(f"apply[{i}].marker contains control characters")
            elif paths_ok:
                src = os.path.join(files_dir, e["from"])
                if os.path.isfile(src):
                    with open(src, encoding="utf-8") as f:
                        if marker not in f.read():
                            errs.append(f"apply[{i}]: marker {marker!r} does not "
                                        f"occur in source {e['from']!r}")
    smoke = m.get("smoke")
    if not isinstance(smoke, str) or not smoke:
        errs.append("'smoke' must be a non-empty project-relative path")
    elif smoke.startswith("/") or ".." in smoke.split("/") \
            or any(c in smoke for c in "\t\n\r"):
        errs.append(f"'smoke' must be relative, no '..', no control chars: {smoke!r}")
    if errs:
        raise CheckFail("manifest floor: " + "; ".join(errs))
    return f"manifest floor OK ({len(apply)} apply entries + smoke)"


def check_ed_checklist_run(ctx):
    cands = _ed_md_candidates(ctx)
    if len(cands) != 1:
        raise CheckFail(f"cannot locate a unique directive file to read frontmatter "
                        f"from (got {cands!r}) — fix ed-md-exactly-one first")
    fm = parse_frontmatter(os.path.join(ctx["ed_dir"], cands[0]))
    val = fm.get("checklist-run", "")
    if not val:
        raise CheckFail(f"{cands[0]} frontmatter 'checklist-run:' is missing/empty — "
                        f"the CHECKLIST.md walk must be recorded before greenlight")
    return f"checklist-run recorded: {val!r}"


def check_ed_vetted_before_greenlit(ctx):
    ed_id = require_id(ctx)
    hist = load_registry(ctx).get(ed_id, [])
    if not hist:
        raise CheckFail(f"no registry lines for {ed_id}")
    states = [d.get("state") for d in hist]
    if "GREENLIT" not in states:
        raise CheckFail(f"no GREENLIT line for {ed_id} (history: {states})")
    last_greenlit = len(states) - 1 - states[::-1].index("GREENLIT")
    if "VETTED" not in states[:last_greenlit]:
        raise CheckFail(f"no VETTED line precedes the latest GREENLIT for {ed_id} "
                        f"(history: {states}) — cross-vet is not optional")
    return "VETTED precedes the latest GREENLIT"


def check_ed_latest_greenlit(ctx):
    ed_id = require_id(ctx)
    hist = load_registry(ctx).get(ed_id, [])
    if not hist:
        raise CheckFail(f"no registry lines for {ed_id}")
    latest = hist[-1]
    state = latest.get("state")
    if state == "REOPENED":
        raise CheckFail(
            f"latest state for {ed_id} is REOPENED — re-entry to execution requires a "
            f"FRESH GREENLIT line whose go_basis cites the reopen (append via "
            f"append-registry.py after the fix is re-vetted); the gate never waves a "
            f"reopened directive through (ED-003 precedent, ED-002 post-mortem d)")
    if state != "GREENLIT":
        raise CheckFail(f"latest state for {ed_id} is {state!r}, gate requires GREENLIT "
                        f"(greenlight is a registry line, nothing else)")
    basis = latest.get("go_basis")
    if not isinstance(basis, str) or not basis.strip():
        raise CheckFail(f"GREENLIT line for {ed_id} has empty/missing go_basis")
    return f"latest GREENLIT with go_basis {basis!r}"


def check_cursor_valid(ctx):
    validator = os.path.join(CANON, "tools", "validate-cursor.py")
    if not os.path.isfile(validator):
        raise GateError(f"validator missing at {validator} — canon incomplete")
    # call site copied from the harness pattern: `validate-cursor.py <path>` single
    # positional, exit 0/2 (tools/validate-cursor.py:86-92)
    try:
        proc = subprocess.run(["python3", validator, ctx["cursor"]],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateError(f"could not run validate-cursor.py: {exc}")
    if proc.returncode != 0:
        raise CheckFail("cursor invalid: "
                        + (proc.stderr.strip() or proc.stdout.strip()
                           or f"exit {proc.returncode}"))
    return proc.stdout.strip() or "cursor valid"


def _read_cursor(ctx):
    try:
        with open(ctx["cursor"], encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckFail(f"cannot read cursor {ctx['cursor']}: {exc}")


def check_cursor_not_mid_build(ctx):
    d = _read_cursor(ctx)
    if d.get("role") == "coder" and d.get("active_directive") is not None:
        raise CheckFail(f"a build is in flight (role=coder, "
                        f"active={d.get('active_directive')}) — refusing the phase "
                        f"transition while the executor owns the cursor")
    return f"cursor idle for transition (role={d.get('role')}, " \
           f"active={d.get('active_directive')})"


def check_cursor_phase_match(ctx, spec=None):
    d = _read_cursor(ctx)
    boundary = (spec or {}).get("boundary", "?->?")
    return (f"cursor phase={d.get('phase')!r} vs boundary {boundary!r} "
            f"(report-only in B4: bootstrap-era cursors legitimately sit mid-pipeline; "
            f"graduates to enforce with B7)")


def check_pd_dd_pairing(ctx):
    if not os.path.isdir(ctx["dd_dir"]):
        return "no _directives/DD dir — nothing to pair (PASS with note)"
    dd_serials = {}
    for name in scan_md(ctx["dd_dir"]):
        m = SERIAL_RE.fullmatch(name)
        if m and m.group(1) == "DD":
            dd_serials[m.group(2)] = name
    if not dd_serials:
        return "DD/ has no DD-NNN packets — nothing to pair (PASS with note)"
    pd_serials = set()
    if os.path.isdir(ctx["pd_dir"]):
        for name in scan_md(ctx["pd_dir"]):
            m = SERIAL_RE.fullmatch(name)
            if m and m.group(1) == "PD":
                pd_serials.add(m.group(2))
    orphans = sorted(s for s in dd_serials if s not in pd_serials)
    if orphans:
        raise CheckFail("every DD-NNN needs its shared-serial PD-NNN (RUNTIME-SPEC "
                        "naming table); unpaired DD serial(s): "
                        + ", ".join(f"DD-{s} ({dd_serials[s]})" for s in orphans))
    return f"{len(dd_serials)} DD packet(s), all PD-paired by shared serial"


def check_dd_status_settled(ctx):
    if not os.path.isdir(ctx["dd_dir"]):
        return "no _directives/DD dir — nothing to check (PASS with note)"
    names = scan_md(ctx["dd_dir"])
    if not names:
        return "DD/ is empty — nothing to check (PASS with note)"
    unsettled = []
    for name in names:
        fm = parse_frontmatter(os.path.join(ctx["dd_dir"], name))
        status = fm.get("status", "(missing)")
        if status != "settled":
            unsettled.append(f"{name}: status={status}")
    if unsettled:
        raise CheckFail("every DD must carry frontmatter 'status: settled' before "
                        "validation intake; offenders: " + "; ".join(unsettled))
    return f"{len(names)} DD packet(s), all status: settled"


# Packet-template enforcement (ED-005, B5): the canon planning templates carry a
# fenced ```packet-spec JSON block — {"packet": "PD"|"DD", "required": {key: regex}}.
# Canon-template problems are GateError (BLOCK: canon incomplete/malformed, fail-
# closed); packet violations are CheckFail (enforce=soft in design-intake -> BOUNCE).

def extract_packet_spec(path):
    """First fenced code block tagged `packet-spec` -> parsed JSON, or GateError.

    Deliberately PARALLEL to extract_gate_spec, not shared: validate_templates
    classifies doc files by the gate-spec error text (a known message-coupling),
    so the gate-spec extractor stays byte-untouched (ED-005 §4)."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as exc:
        raise GateError(f"cannot read canon template {path}: {exc} (fail-closed)")
    block, in_block = [], False
    for line in lines:
        stripped = line.strip()
        if not in_block and stripped == "```packet-spec":
            in_block = True
            continue
        if in_block:
            if stripped == "```":
                break
            block.append(line)
    else:
        if in_block:
            raise GateError(f"{path}: unterminated ```packet-spec fence")
        raise GateError(f"{path}: no ```packet-spec fenced block found "
                        "(machine-readable contract, "
                        "planning-directives/PLANNING-SPEC.md)")
    try:
        return json.loads("\n".join(block))
    except json.JSONDecodeError as exc:
        raise GateError(f"{path}: packet-spec block is not valid JSON: {exc.msg} "
                        f"(line {exc.lineno} of the block)")


def _load_packet_spec(kind):
    """Canon planning-directives/<kind>-TEMPLATE.md -> {key: compiled regex}.

    Resolved from CANON (the runner's own location, same precedent as
    check_cursor_valid) — never from the consuming project. Every malformation
    is GateError: a broken canon contract must BLOCK, never read as a packet
    problem (which would BOUNCE, understating the failure)."""
    path = os.path.join(CANON, "planning-directives", f"{kind}-TEMPLATE.md")
    if not os.path.isfile(path):
        raise GateError(f"canon template missing: {path} — canon incomplete "
                        f"(fail-closed)")
    spec = extract_packet_spec(path)
    if not isinstance(spec, dict) or spec.get("packet") != kind:
        got = spec.get("packet") if isinstance(spec, dict) else spec
        raise GateError(f"{path}: packet-spec 'packet' must be {kind!r}, got {got!r}")
    req = spec.get("required")
    if not isinstance(req, dict) or not req:
        raise GateError(f"{path}: packet-spec 'required' must be a non-empty object")
    compiled = {}
    for key, pattern in req.items():
        if not isinstance(pattern, str) or not pattern:
            raise GateError(f"{path}: required[{key!r}] must be a non-empty "
                            f"regex string")
        try:
            compiled[key] = re.compile(pattern)
        except re.error as exc:
            raise GateError(f"{path}: required[{key!r}] is not a valid regex: {exc}")
    return compiled


def _check_packets_frontmatter(ctx, kind, dirkey):
    # canon template loads FIRST: a broken canon contract must BLOCK even when
    # the project has no packets yet (fail-closed before the cheap PASS-with-note)
    required = _load_packet_spec(kind)
    dirpath = ctx[dirkey]
    if not os.path.isdir(dirpath):
        return f"no _directives/{kind} dir — nothing to check (PASS with note)"
    packets = []
    for name in scan_md(dirpath):
        m = SERIAL_RE.fullmatch(name)
        if m and m.group(1) == kind:
            packets.append((name, m.group(2)))
    if not packets:
        return f"{kind}/ has no {kind}-NNN packets — nothing to check (PASS with note)"
    other = "PD" if kind == "DD" else "DD"
    errs = []
    for name, serial in packets:
        fm = parse_frontmatter(os.path.join(dirpath, name))
        if not fm:
            errs.append(f"{name}: no frontmatter block")
            continue
        for key, rx in required.items():
            val = fm.get(key)
            if val is None or val == "":
                errs.append(f"{name}: missing required key '{key}'")
            elif not rx.fullmatch(val):
                errs.append(f"{name}: {key}={val!r} does not fullmatch "
                            f"/{rx.pattern}/")
        # RUNTIME-SPEC shared-serial contract, enforced in code (not per-template):
        # id agrees with the filename serial; pair carries the same serial
        fm_id = fm.get("id")
        if fm_id is not None and fm_id != f"{kind}-{serial}":
            errs.append(f"{name}: id={fm_id!r} != filename serial {kind}-{serial}")
        fm_pair = fm.get("pair")
        if fm_pair is not None and fm_pair != f"{other}-{serial}":
            errs.append(f"{name}: pair={fm_pair!r} != shared-serial {other}-{serial} "
                        f"(RUNTIME-SPEC naming table)")
    if errs:
        raise CheckFail(f"packet(s) violate the canon {kind}-TEMPLATE packet-spec: "
                        + "; ".join(errs))
    return f"{len(packets)} {kind} packet(s) validate against canon {kind}-TEMPLATE.md"


def check_pd_frontmatter_template(ctx):
    return _check_packets_frontmatter(ctx, "PD", "pd_dir")


def check_dd_frontmatter_template(ctx):
    return _check_packets_frontmatter(ctx, "DD", "dd_dir")


def check_no_open_execution(ctx):
    history = load_registry(ctx)
    open_eds = []
    for did, hist in sorted(history.items()):
        if ED_ID_RE.fullmatch(did) and hist[-1].get("state") in OPEN_EXECUTION_STATES:
            open_eds.append(f"{did}={hist[-1].get('state')}")
    if open_eds:
        raise CheckFail("execution is not closed — review intake requires every ED "
                        "latest state outside {GREENLIT, BUILT-GREEN, BUILT-RED, "
                        "REOPENED}; open: " + ", ".join(open_eds))
    return "no ED in an open execution state (everything VERIFIED or paper-stage)"


CHECKS = {
    "ed-id-shape": check_ed_id_shape,
    "ed-md-exactly-one": check_ed_md_exactly_one,
    "ed-launch-exists": check_ed_launch_exists,
    "ed-package-nonempty": check_ed_package_nonempty,
    "ed-probes-complete": check_ed_probes_complete,
    "ed-manifest-floor": check_ed_manifest_floor,
    "ed-checklist-run": check_ed_checklist_run,
    "ed-vetted-before-greenlit": check_ed_vetted_before_greenlit,
    "ed-latest-greenlit": check_ed_latest_greenlit,
    "cursor-valid": check_cursor_valid,
    "cursor-not-mid-build": check_cursor_not_mid_build,
    "cursor-phase-match": check_cursor_phase_match,
    "pd-dd-pairing": check_pd_dd_pairing,
    "pd-frontmatter-template": check_pd_frontmatter_template,
    "dd-frontmatter-template": check_dd_frontmatter_template,
    "dd-status-settled": check_dd_status_settled,
    "no-open-execution": check_no_open_execution,
}


# ----------------------------------------------------------------------- modes

def run_gate(template, project, directive_id):
    spec = validate_spec(extract_gate_spec(template), template)
    ctx = make_ctx(project, directive_id)
    gate = spec["gate"]
    hard_fails, soft_fails = [], []
    for c in spec["checks"]:
        cid = c["id"]
        if c.get("deferred"):
            print(f"gate-runner: [DEFERRED({c['deferred']})] {cid} — arrives with "
                  f"{c['deferred']}; not silently passed")
            continue
        fn = CHECKS[cid]
        if c["enforce"] == "report":
            # report never affects exit — even a crashed report check only prints
            try:
                detail = fn(ctx, spec) if cid == "cursor-phase-match" else fn(ctx)
                print(f"gate-runner: [REPORT] {cid} — {detail}")
            except (CheckFail, GateError) as exc:
                print(f"gate-runner: [REPORT] {cid} — could not evaluate: {exc}")
            continue
        try:
            detail = fn(ctx)
        except CheckFail as exc:
            level = c["enforce"]
            (hard_fails if level == "hard" else soft_fails).append(cid)
            print(f"gate-runner: [FAIL:{level}] {cid} — {exc}")
            continue
        print(f"gate-runner: [PASS] {cid} — {detail}")
    if hard_fails:
        print(f"gate-runner: {gate} BLOCK (exit 2) — hard failure(s): "
              f"{', '.join(hard_fails)}", file=sys.stderr)
        return 2
    if soft_fails:
        print(f"gate-runner: {gate} BOUNCE (exit 1) — soft-gate (blocking, "
              f"recoverable) failure(s): {', '.join(soft_fails)} — fix and re-run; "
              f"nothing downstream has been built", file=sys.stderr)
        return 1
    print(f"gate-runner: {gate} PASS (exit 0) — {spec['boundary']} transition clear")
    return 0


def validate_templates(gates_dir):
    if not os.path.isdir(gates_dir):
        raise GateError(f"not a directory: {gates_dir}")
    names = scan_md(gates_dir)
    templates, docs = [], []
    for name in names:
        path = os.path.join(gates_dir, name)
        try:
            spec = extract_gate_spec(path)
        except GateError as exc:
            if "no ```gate-spec fenced block" in str(exc):
                docs.append(name)   # spec/doc files (GATES-SPEC.md) carry no block
                continue
            raise
        validate_spec(spec, path)
        templates.append(name)
        print(f"gate-runner: template OK — {name} (gate={spec['gate']}, "
              f"strength={spec['strength']}, boundary={spec['boundary']}, "
              f"{len(spec['checks'])} checks)")
    for name in docs:
        print(f"gate-runner: no gate-spec block (doc, skipped) — {name}")
    if not templates:
        raise GateError(f"{gates_dir}: no templates with a gate-spec block found")
    print(f"gate-runner: --validate-templates OK — {len(templates)} template(s), "
          f"{len(docs)} doc(s)")
    return 0


def main(argv):
    args = list(argv[1:])
    if args and args[0] == "--validate-templates":
        if len(args) != 2:
            print("usage: gate-runner.py --validate-templates <gates-dir>",
                  file=sys.stderr)
            return 2
        return validate_templates(args[1])
    template, project, directive_id = None, CANON, None
    i = 0
    while i < len(args):
        if args[i] == "--project" and i + 1 < len(args):
            project = args[i + 1]
            i += 2
        elif args[i] == "--id" and i + 1 < len(args):
            directive_id = args[i + 1]
            i += 2
        elif template is None and not args[i].startswith("-"):
            template = args[i]
            i += 1
        else:
            print(f"gate-runner: unknown/misplaced arg {args[i]!r}", file=sys.stderr)
            return 2
    if template is None:
        print("usage: gate-runner.py <gates/TEMPLATE.md> [--project DIR] [--id ED-NNN]\n"
              "       gate-runner.py --validate-templates <gates-dir>", file=sys.stderr)
        return 2
    return run_gate(template, project, directive_id)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except GateError as exc:
        print(f"gate-runner: BLOCK (exit 2) — {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001 — any crash is a runner error: never
        # exit 1 (=BOUNCE, "recoverable") on an unhandled exception; fail closed
        print(f"gate-runner: BLOCK (exit 2) — unexpected "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
