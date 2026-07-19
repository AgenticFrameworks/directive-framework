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

Gates go LIVE at later boundaries (B7 flips the executor to call this runner);
B4 ships the framework only, so nothing here is invoked by tools/executor-run.sh
yet. B5 (ED-005) instantiated the planning packet checks
pd/dd-frontmatter-template: live in gates/design-intake.md, validating packets
against the canon planning-directives/(PD|DD)-TEMPLATE.md packet-spec. B6
(ED-007) instantiated the validation slice: dd-ordering-dag and
dd-waived-or-consumed live in gates/validation-intake.md; vd-dd-consumption and
vd-attestation-present live in gates/execution-intake.md, validating VD packets
against the canon validation-directives/VD-TEMPLATE.md packet-spec. The
attestation check asserts PRESENCE+schema of registry attest keys only — never
truth (B10 audits).
"""

import json
import os
import re
import subprocess
import sys

CANON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ED_ID_RE = re.compile(r"ED-[0-9]{3}")
SERIAL_RE = re.compile(r"^(DD|PD|VD)-([0-9]{3})(?:[.-].*)?\.md$")
BOUNDARY_RE = re.compile(r"^(planning|design|validation|execution|review)->"
                         r"(design|validation|execution|review)$")

# Ladder taxonomy (ROADMAP "Terminology guard"): 'advisory' (fail-open, ~/.claude
# policy vocab) is what a phase gate NEVER is, so it is not a valid strength here.
STRENGTHS = {"soft-gate", "hard-gate", "strict-hard"}
ENFORCE = {"hard", "soft", "report"}

# Enforce-level FLOOR per live check (B7, ED-005 F1 — DOWNGRADE vector): a template
# carrying one of these cids at an enforce BELOW its floor is a BLOCK — a canon
# template must not silently DOWNGRADE a shipped check (report<soft<hard). Seeded
# from the LIVE enforce levels at B7. (OMISSION — a live check dropped from a
# template it belongs to — needs a check->gate registry the runner does not have;
# scoped OUT here and deferred, recorded in ED-008 §4.)
ENFORCE_RANK = {"report": 0, "soft": 1, "hard": 2}
MIN_ENFORCE = {
    "pd-dd-pairing": "soft",
    "pd-frontmatter-template": "soft",
    "dd-frontmatter-template": "soft",
    "dd-status-settled": "soft",
    "dd-ordering-dag": "soft",
    "dd-waived-or-consumed": "soft",
    "ed-id-shape": "hard",
    "ed-md-exactly-one": "hard",
    "ed-launch-exists": "hard",
    "ed-package-nonempty": "hard",
    "ed-probes-complete": "hard",
    "ed-manifest-floor": "hard",
    "ed-checklist-run": "hard",
    "ed-chain-walkback": "hard",
    "ed-vetted-before-greenlit": "hard",
    "ed-latest-greenlit": "hard",
    "cursor-valid": "hard",
    "cursor-not-mid-build": "hard",
    "cursor-phase-match": "hard",
    "vd-dd-consumption": "hard",
    "vd-attestation-present": "hard",
    "no-open-execution": "hard",
}

# Closed / not-open execution states (ALLOWLIST, fail-closed): an ED whose LATEST
# registry state is NOT one of these counts as an OPEN execution — including any
# unknown/missing state (B7, ED-004 gpt MED: flipped from a denylist so a novel
# state can never read as closed). Closed = VERIFIED (fully done) or paper-stage
# DESIGN/VETTED.
CLOSED_EXECUTION_STATES = {"DESIGN", "VETTED", "VERIFIED"}

# Sanctioned deferrals: check id -> boundary that instantiates it. A `deferred`
# entry whose id is not here (or names a different boundary) is a BLOCK.
KNOWN_DEFERRED = {
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
        floor = MIN_ENFORCE.get(cid)
        if floor is not None and ENFORCE_RANK[c["enforce"]] < ENFORCE_RANK[floor]:
            raise GateError(f"{path}: check {cid!r} carries enforce={c['enforce']!r} "
                            f"below its floor {floor!r} — a template cannot DOWNGRADE "
                            f"a live check (fail-closed, ED-005 F1)")
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
        "vd_dir": os.path.join(root, "_directives", "VD"),
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


def check_ed_chain_walkback(ctx):
    cands = _ed_md_candidates(ctx)
    if len(cands) != 1:
        raise CheckFail(f"cannot locate a unique directive file to read frontmatter "
                        f"from (got {cands!r}) — fix ed-md-exactly-one first")
    fm = parse_frontmatter(os.path.join(ctx["ed_dir"], cands[0]))
    fmt = fm.get("format", "").strip()
    if fmt in ("", "v1"):
        # FORMAT-GATED: v1/absent EDs predate the chain-walkback contract — PASS
        # with a note (v1 EDs shipped before EXECUTION-SPEC; the key is not retro-
        # required). ED-008 itself is authored v1 and passes here.
        return (f"{cands[0]} is format={fmt or '(absent)'} (v1) — chain-walkback "
                f"not required (PASS with note)")
    if fmt != "v2":
        # B7 cross-vet C1 (fail-closed): an unrecognized non-empty format must NOT
        # silently downgrade to v1 — a `format: V2` / `format: 2` typo would skip
        # this hard gate entirely. The only valid values are absent/v1 or v2; any
        # other is a defect, not a v1 pass.
        raise CheckFail(f"{cands[0]} carries an unrecognized format={fmt!r} — a "
                        f"directive is either v1 (absent format) or exactly "
                        f"'format: v2'; an unknown format cannot silently skip "
                        f"ed-chain-walkback (fail-closed); see "
                        f"execution-directives/EXECUTION-SPEC.md")
    val = fm.get("chain-walkback", "")
    if not val:
        raise CheckFail(f"{cands[0]} is format: v2 but frontmatter "
                        f"'chain-walkback:' is missing/empty — a v2 ED must record "
                        f"the traced chain (e.g. 'VD-001 -> DD-001,DD-002 -> "
                        f"PD-001,PD-002'); see execution-directives/EXECUTION-SPEC.md")
    # PRESENCE + schema only; the traced chain's TRUTH is audited at B10, like the
    # completeness attestation.
    return f"chain-walkback recorded (format: v2): {val!r}"


def check_ed_vetted_before_greenlit(ctx):
    ed_id = require_id(ctx)
    hist = load_registry(ctx).get(ed_id, [])
    if not hist:
        raise CheckFail(f"no registry lines for {ed_id}")
    states = [d.get("state") for d in hist]
    if "GREENLIT" not in states:
        raise CheckFail(f"no GREENLIT line for {ed_id} (history: {states})")
    last_greenlit = len(states) - 1 - states[::-1].index("GREENLIT")
    vetted_before = [i for i, s in enumerate(states[:last_greenlit]) if s == "VETTED"]
    if not vetted_before:
        raise CheckFail(f"no VETTED line precedes the latest GREENLIT for {ed_id} "
                        f"(history: {states}) — cross-vet is not optional")
    # B7 (ED-004 LOW-1): a REOPENED invalidates any prior vet — the VETTED that
    # clears the latest GREENLIT must come AFTER the last REOPENED, else a stale
    # pre-reopen vet would wave a reopened+re-greenlit ED through unreviewed.
    if "REOPENED" in states:
        last_reopened = len(states) - 1 - states[::-1].index("REOPENED")
        if not any(i > last_reopened for i in vetted_before):
            raise CheckFail(f"latest GREENLIT for {ed_id} is not preceded by a "
                            f"VETTED line AFTER the last REOPENED (history: "
                            f"{states}) — a reopened directive needs a FRESH "
                            f"cross-vet, not a pre-reopen one")
    return "VETTED precedes the latest GREENLIT (fresh vs any REOPENED)"


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
    phase = d.get("phase")
    boundary = (spec or {}).get("boundary", "?->?")
    m = BOUNDARY_RE.fullmatch(boundary)
    if not m:
        raise CheckFail(f"cursor-phase-match needs a phase->phase boundary from the "
                        f"gate-spec, got {boundary!r}")
    src, dst = m.group(1), m.group(2)
    if phase not in (src, dst):
        raise CheckFail(f"cursor phase={phase!r} is off this boundary {boundary!r} "
                        f"— the transition is valid only while the cursor sits at "
                        f"its source ({src}) or destination ({dst}) phase (B7: "
                        f"graduated from report to hard)")
    return (f"cursor phase={phase!r} matches boundary {boundary!r} "
            f"(at {'source' if phase == src else 'destination'})")


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
    # B6 (ED-007): accepts the closed vocabulary settled/waived/consumed that
    # DD-TEMPLATE reserved; scans only DD-NNN packets (SERIAL_RE), not stray
    # *.md — closing the B5 hardening-backlog scan-alignment item.
    packets = _scan_packets(ctx, "DD", "dd_dir")
    if not packets:
        return "no DD-NNN packets in _directives/DD — nothing to check (PASS with note)"
    open_dds = []
    for name, _serial in packets:
        fm = parse_frontmatter(os.path.join(ctx["dd_dir"], name))
        status = fm.get("status", "(missing)")
        if status not in ("settled", "waived", "consumed"):
            open_dds.append(f"{name}: status={status}")
    if open_dds:
        raise CheckFail("every DD must carry frontmatter status settled/waived/"
                        "consumed before validation intake; offenders: "
                        + "; ".join(open_dds))
    return f"{len(packets)} DD packet(s), all status settled/waived/consumed"


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
    """Canon <subdir>/<kind>-TEMPLATE.md -> {key: compiled regex}.

    VD resolves from validation-directives/ (ED-007, B6); PD/DD from
    planning-directives/. Resolved from CANON (the runner's own location, same
    precedent as check_cursor_valid) — never from the consuming project. Every
    malformation is GateError: a broken canon contract must BLOCK, never read
    as a packet problem (which would BOUNCE, understating the failure)."""
    subdir = "validation-directives" if kind == "VD" else "planning-directives"
    path = os.path.join(CANON, subdir, f"{kind}-TEMPLATE.md")
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
    # B7 (ED-005 HIGH-1): a kind-aware required-key FLOOR — reject a canon template
    # that DROPS a floor key so it can't silently weaken the check. PD/DD carry the
    # pair twin; VD has no twin but must keep its consumption/independence keys.
    FLOOR = {
        "PD": {"id", "pair", "status", "created"},
        "DD": {"id", "pair", "status", "created"},
        "VD": {"id", "status", "created", "author", "consumes", "parallelism"},
    }
    missing_floor = FLOOR.get(kind, set()) - set(req)
    if missing_floor:
        raise GateError(f"{path}: packet-spec 'required' drops floor key(s) "
                        f"{sorted(missing_floor)} for {kind} — a canon template "
                        f"cannot silently weaken the check (fail-closed)")
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


# Validation-slice checks (ED-007, B6): dd-ordering-dag / dd-waived-or-consumed
# (gates/validation-intake.md, soft) and vd-dd-consumption /
# vd-attestation-present (gates/execution-intake.md, hard). VD packets live in
# _directives/VD/ and validate against the canon
# validation-directives/VD-TEMPLATE.md packet-spec via _load_packet_spec
# (GateError fail-closed, even on packet-empty projects). VDs have NO pair twin
# — their cross-refs are consumes: DD ids — so they deliberately do NOT go
# through _check_packets_frontmatter (which hardcodes the PD/DD pairing). The
# attestation check asserts PRESENCE + schema of the registry attest keys only,
# never truth (B10 audits); the keys ride on a valid state line — the
# append/validate-registry line contract is NOT evolved by B6.

def _scan_packets(ctx, kind, dirkey):
    """[(name, serial), ...] of KIND-NNN packets; [] when the dir is absent.

    Memoized per (kind, dirkey) in ctx["_packet_cache"] so every check in ONE gate
    run shares one snapshot (B7, GPT-2 ED-007: closes the per-check rescan TOCTOU
    with no signature change). A duplicate serial (e.g. VD-001.md + VD-001.z.md)
    raises CheckFail (B7, GPT-1 ED-007): consumers key by serial (vd_authors[vid],
    edges, consumes) so a later scan silently OVERWRITES the earlier packet's
    author/ordering — author-independence evasion + silent merge. Rejecting here
    closes the deliberate AND the accidental stray-backup path for every consumer."""
    cache = ctx.setdefault("_packet_cache", {})
    key = (kind, dirkey)
    if key in cache:
        return cache[key]
    dirpath = ctx[dirkey]
    if not os.path.isdir(dirpath):
        cache[key] = []
        return []
    out, seen = [], {}
    for name in scan_md(dirpath):
        m = SERIAL_RE.fullmatch(name)
        if m and m.group(1) == kind:
            serial = m.group(2)
            if serial in seen:
                raise CheckFail(f"duplicate {kind} serial {kind}-{serial}: "
                                f"{seen[serial]!r} and {name!r} — one serial, one "
                                f"packet (a stray same-serial file silently "
                                f"overwrites author/consumes/ordering by serial)")
            seen[serial] = name
            out.append((name, serial))
    cache[key] = out
    return out


def _parse_id_list(value, kind):
    """Single-line comma list 'DD-001, DD-002' -> ids; ValueError on a bad ref
    (parse_frontmatter is line-scoped, so multi-line lists cannot occur)."""
    ids = []
    for part in value.split(","):
        ref = part.strip()
        if not re.fullmatch(kind + "-[0-9]{3}", ref):
            raise ValueError(f"malformed {kind} ref {ref!r} "
                             f"(expected a comma list of {kind}-NNN)")
        ids.append(ref)
    return ids


def _dag_or_fail(edges, what):
    """edges: {node: set(prerequisite nodes)} — Kahn-style resolve loop;
    CheckFail naming the residual cycle members when the ordering is no DAG."""
    pending = {n: set(deps) for n, deps in edges.items() if deps}
    resolved = set(edges) - set(pending)
    while pending:
        ready = [n for n, deps in pending.items() if deps <= resolved]
        if not ready:
            raise CheckFail(f"{what} ordering is not a DAG — cycle among: "
                            + ", ".join(sorted(pending)))
        for n in ready:
            resolved.add(n)
            del pending[n]


def check_dd_ordering_dag(ctx):
    packets = _scan_packets(ctx, "DD", "dd_dir")
    if not packets:
        return "no DD-NNN packets — nothing to order (PASS with note)"
    ids = {f"DD-{serial}" for _name, serial in packets}
    edges, declared, errs = {}, 0, []
    for name, serial in packets:
        did = f"DD-{serial}"
        after = parse_frontmatter(os.path.join(ctx["dd_dir"], name)).get("after")
        if not after:
            edges[did] = set()
            continue
        declared += 1
        try:
            refs = _parse_id_list(after, "DD")
        except ValueError as exc:
            errs.append(f"{name}: after: {exc}")
            edges[did] = set()
            continue
        for ref in refs:
            if ref == did:
                errs.append(f"{name}: after: self-reference {ref}")
            elif ref not in ids:
                errs.append(f"{name}: after: references {ref} which is not a "
                            f"DD packet on disk")
        edges[did] = {r for r in refs if r != did and r in ids}
    if errs:
        raise CheckFail("DD after: violations: " + "; ".join(errs))
    if not declared:
        return (f"{len(packets)} DD packet(s), no after: keys — trivially a "
                f"DAG (PASS with note)")
    _dag_or_fail(edges, "DD after:")
    return f"{len(packets)} DD packet(s), {declared} with after:, ordering is a DAG"


def check_dd_waived_or_consumed(ctx):
    packets = _scan_packets(ctx, "DD", "dd_dir")
    if not packets:
        return "no DD-NNN packets — nothing to consume or waive (PASS with note)"
    errs, dd_status = [], {}
    for name, serial in packets:
        fm = parse_frontmatter(os.path.join(ctx["dd_dir"], name))
        did = f"DD-{serial}"
        dd_status[did] = fm.get("status", "(missing)")
        if dd_status[did] == "waived" and not fm.get("waived"):
            errs.append(f"{name}: status waived requires a non-empty "
                        f"'waived: <reason>' key")
    vd_packets = _scan_packets(ctx, "VD", "vd_dir")
    consumed = set()
    for name, _serial in vd_packets:
        consumes = parse_frontmatter(
            os.path.join(ctx["vd_dir"], name)).get("consumes")
        if consumes:
            try:
                consumed.update(_parse_id_list(consumes, "DD"))
            except ValueError as exc:
                # a malformed VD consumes: list propagates — never silently
                # swallowed as "nothing consumed"
                errs.append(f"{name}: consumes: {exc}")
    for did in sorted(dd_status):
        if dd_status[did] == "consumed" and did not in consumed:
            errs.append(f"{did}: status consumed but no VD lists it in consumes:")
    if vd_packets:
        uncovered = sorted(d for d, s in dd_status.items()
                           if s != "waived" and d not in consumed)
        if uncovered:
            errs.append("DD(s) neither consumed by a VD nor waived: "
                        + ", ".join(uncovered))
    if errs:
        raise CheckFail("waived/consumed violations: " + "; ".join(errs))
    if not vd_packets:
        return (f"{len(packets)} DD packet(s), zero VD packets — coverage not "
                f"yet enforceable here; hard backstop at execution-intake "
                f"(PASS with note)")
    return (f"{len(packets)} DD packet(s) all consumed-or-waived across "
            f"{len(vd_packets)} VD packet(s)")


def check_vd_dd_consumption(ctx):
    # canon VD template loads FIRST: a broken canon contract must BLOCK even
    # when the project has no packets yet (ED-005 precedent)
    required = _load_packet_spec("VD")
    vd_packets = _scan_packets(ctx, "VD", "vd_dir")
    dd_packets = _scan_packets(ctx, "DD", "dd_dir")
    if not vd_packets and not dd_packets:
        return "no DD or VD packets — nothing to package (PASS with note)"
    errs, dd_status = [], {}
    for name, serial in dd_packets:
        fm = parse_frontmatter(os.path.join(ctx["dd_dir"], name))
        did = f"DD-{serial}"
        dd_status[did] = fm.get("status", "(missing)")
        if dd_status[did] == "waived" and not fm.get("waived"):
            errs.append(f"{name}: status waived without a non-empty "
                        f"'waived: <reason>' key")
    vd_ids = {f"VD-{serial}" for _name, serial in vd_packets}
    vd_authors, consumed, vd_edges = {}, set(), {}
    for name, serial in vd_packets:
        vid = f"VD-{serial}"
        fm = parse_frontmatter(os.path.join(ctx["vd_dir"], name))
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
        fm_id = fm.get("id")
        if fm_id is not None and fm_id != vid:
            errs.append(f"{name}: id={fm_id!r} != filename serial {vid}")
        if fm.get("pair") is not None:
            errs.append(f"{name}: VD packets have no pair twin — drop 'pair:' "
                        f"(cross-refs are consumes: DD ids)")
        if fm.get("status") == "draft":
            errs.append(f"{name}: status draft — settle the VD before "
                        f"execution intake")
        vd_authors[vid] = fm.get("author", "")
        consumes = fm.get("consumes")
        if consumes:
            try:
                refs = _parse_id_list(consumes, "DD")
            except ValueError as exc:
                errs.append(f"{name}: consumes: {exc}")
                refs = []
            for ref in refs:
                if ref not in dd_status:
                    errs.append(f"{name}: consumes {ref} which is not a DD "
                                f"packet on disk")
                elif dd_status[ref] == "waived":
                    errs.append(f"{name}: consumes {ref} which is waived "
                                f"(waived-consumed contradiction)")
                elif dd_status[ref] not in ("settled", "consumed"):
                    errs.append(f"{name}: consumes {ref} whose status is "
                                f"{dd_status[ref]!r} (need settled/consumed)")
            consumed.update(refs)
        after = fm.get("after")
        arefs = []
        if after:
            try:
                arefs = _parse_id_list(after, "VD")
            except ValueError as exc:
                errs.append(f"{name}: after: {exc}")
                arefs = []
            for ref in arefs:
                if ref == vid:
                    errs.append(f"{name}: after: self-reference {ref}")
                elif ref not in vd_ids:
                    errs.append(f"{name}: after: references {ref} which is "
                                f"not a VD packet on disk")
        vd_edges[vid] = {r for r in arefs if r != vid and r in vd_ids}
    if dd_packets and not vd_packets:
        errs.append(f"{len(dd_packets)} DD packet(s) but zero VD packets — "
                    f"the DD set is unpackaged (author VDs before execution "
                    f"intake)")
    else:
        uncovered = sorted(d for d, s in dd_status.items()
                           if s != "waived" and d not in consumed)
        if uncovered:
            errs.append("DD(s) neither consumed by a VD nor waived: "
                        + ", ".join(uncovered))
    if vd_packets:
        # author independence: the operational fresh-context mechanism is the
        # cursor; the gate checks the RECORDED authors (ED frontmatter vs VD)
        cands = _ed_md_candidates(ctx)
        if len(cands) != 1:
            errs.append(f"cannot locate a unique directive file to read "
                        f"'author:' from (got {cands!r})")
        else:
            ed_author = parse_frontmatter(
                os.path.join(ctx["ed_dir"], cands[0])).get("author", "")
            if not ed_author:
                errs.append(f"{cands[0]}: frontmatter 'author:' missing/empty "
                            f"— VD/ED author independence unverifiable "
                            f"(fail-closed)")
            else:
                for vid in sorted(vd_authors):
                    if vd_authors[vid] and vd_authors[vid] == ed_author:
                        errs.append(f"{vid}: author {vd_authors[vid]!r} == ED "
                                    f"author — validation must be "
                                    f"independently authored")
    if errs:
        raise CheckFail("VD->ED consumption violations: " + "; ".join(errs))
    _dag_or_fail(vd_edges, "VD after:")
    return (f"{len(vd_packets)} VD packet(s) validate against canon "
            f"VD-TEMPLATE.md; {len(dd_packets)} DD packet(s) all "
            f"consumed-or-waived; VD authors independent of the ED author")


def check_vd_attestation_present(ctx):
    ed_id = require_id(ctx)
    if not _scan_packets(ctx, "DD", "dd_dir"):
        return "no DD-NNN packets — no DD set to attest (PASS with note)"
    valid, malformed = [], []
    for d in load_registry(ctx).get(ed_id, []):
        if "attest" not in d:
            continue
        problems = []
        if d.get("attest") != "dd-set-complete":
            problems.append(f"attest={d.get('attest')!r} (expected "
                            f"'dd-set-complete')")
        basis = d.get("basis")
        if not isinstance(basis, str) or not basis.strip():
            problems.append("empty/missing 'basis'")
        risk = d.get("risk_accepted")
        if not isinstance(risk, str) or not risk.strip():
            problems.append("empty/missing 'risk_accepted'")
        if problems:
            malformed.append(" + ".join(problems))
        else:
            valid.append(d)
    if valid:
        note = ""
        if malformed:
            note = (f"; {len(malformed)} malformed attest line(s) also "
                    f"present: " + " | ".join(malformed))
        return (f"dd-set-complete attestation present for {ed_id} (basis "
                f"{valid[0].get('basis')!r}; PRESENCE+schema only — truth is "
                f"audited at B10){note}")
    detail = ""
    if malformed:
        detail = "malformed attest line(s): " + " | ".join(malformed) + " — "
    raise CheckFail(
        "no valid dd-set-complete attestation line for " + ed_id + ": " + detail
        + "the VD author appends the attest keys piggybacked on a valid state "
          "line, e.g. "
        + '{"id":"' + ed_id + '","state":"<STATE>","ts":"<UTC now>",'
          '"attest":"dd-set-complete","basis":"<why the DD set is complete>",'
          '"risk_accepted":"<residual risk accepted>"}'
        + " via append-registry.py")


def check_no_open_execution(ctx):
    history = load_registry(ctx)
    open_eds = []
    for did, hist in sorted(history.items()):
        if ED_ID_RE.fullmatch(did) and hist[-1].get("state") not in CLOSED_EXECUTION_STATES:
            open_eds.append(f"{did}={hist[-1].get('state')}")
    if open_eds:
        raise CheckFail("execution is not closed — review intake requires every ED "
                        "latest state within the closed allowlist {DESIGN, VETTED, "
                        "VERIFIED} (any other/unknown state counts as OPEN, "
                        "fail-closed); open: " + ", ".join(open_eds))
    return "no ED in an open execution state (every ED VERIFIED or paper-stage)"


CHECKS = {
    "ed-id-shape": check_ed_id_shape,
    "ed-md-exactly-one": check_ed_md_exactly_one,
    "ed-launch-exists": check_ed_launch_exists,
    "ed-package-nonempty": check_ed_package_nonempty,
    "ed-probes-complete": check_ed_probes_complete,
    "ed-manifest-floor": check_ed_manifest_floor,
    "ed-checklist-run": check_ed_checklist_run,
    "ed-chain-walkback": check_ed_chain_walkback,
    "ed-vetted-before-greenlit": check_ed_vetted_before_greenlit,
    "ed-latest-greenlit": check_ed_latest_greenlit,
    "cursor-valid": check_cursor_valid,
    "cursor-not-mid-build": check_cursor_not_mid_build,
    "cursor-phase-match": check_cursor_phase_match,
    "pd-dd-pairing": check_pd_dd_pairing,
    "pd-frontmatter-template": check_pd_frontmatter_template,
    "dd-frontmatter-template": check_dd_frontmatter_template,
    "dd-status-settled": check_dd_status_settled,
    "dd-ordering-dag": check_dd_ordering_dag,
    "dd-waived-or-consumed": check_dd_waived_or_consumed,
    "vd-dd-consumption": check_vd_dd_consumption,
    "vd-attestation-present": check_vd_attestation_present,
    "no-open-execution": check_no_open_execution,
}


# Checks that need the gate-spec (for its boundary) as a 2nd arg. B7: graduating
# cursor-phase-match to a blocking enforce level routes it through the ENFORCE
# branch, which must now also pass spec — a single set drives BOTH branches.
WANTS_SPEC = {"cursor-phase-match"}


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
                detail = fn(ctx, spec) if cid in WANTS_SPEC else fn(ctx)
                print(f"gate-runner: [REPORT] {cid} — {detail}")
            except (CheckFail, GateError) as exc:
                print(f"gate-runner: [REPORT] {cid} — could not evaluate: {exc}")
            continue
        try:
            detail = fn(ctx, spec) if cid in WANTS_SPEC else fn(ctx)
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
