#!/usr/bin/env python3
"""Validate an ED directives.jsonl registry line-by-line (ED-012, flaw A3).

Base checks (blank-line, JSON-parse, id/state/ts presence+string-type, state-enum) mirror
derive-dashboard.py's load() (execution-directives/derive-dashboard.py:14,29-46) so both tools agree on
what "malformed" means. This script closes two residual gaps `load()` does NOT cover
(probed live against the real registry, 2026-07-04):

  1. A non-dict JSON line (e.g. a bare list/number/string) makes `d.keys()` raise
     AttributeError in load() -- git still refuses the commit (nonzero exit) but the user
     sees a raw Python traceback instead of an actionable message. Probe: appending
     `[1,2,3]` as a line reproduced this against the live pre-commit hook.
  2. The metrics fields USAGE.md calls "mandatory where shown" are not actually checked by
     load() -- it reads them via `.get(key, "?")` and renders "?" silently. A VETTED line
     with no `findings` block, or a `findings.critical` typoed as the string "zero" instead
     of an int, committed cleanly through the live hook in both probes.

Per-state extra rules below were each checked against the live registry (13 directives, 57
lines, 2026-07-04) before being made mandatory -- a field is only required if EVERY existing
line for that state already carries it. `defects_post_ship` (VERIFIED) and `cycles_to_green`
(BUILT-GREEN) do NOT meet that bar (ED-009 has real, legitimate lines without them), so those
are type-checked only when present, never required. `smoke_first_run` is required on both
BUILT-GREEN and BUILT-RED, but its VALUE is not cross-checked against the outer state --
ED-003's BUILT-GREEN line legitimately carries `"smoke_first_run":"RED"` (first attempt
failed, second cycle passed, final state recorded is BUILT-GREEN).

REOPENED (ED-022): a directive that reached VERIFIED (or BUILT-*) is found defective post-hoc
and sent back for rework -- it re-enters the lifecycle at EXECUTE. Its one required field is
`reason` (non-empty string): why it was reopened. This is the state that ED-021 line 101
genuinely occupied (invalid CSS-chain VERIFIED superseded by a rendered Playwright proof);
prior sessions had no token for it and mis-coerced it to BUILT-RED.

go_basis (ED-063): the authority behind a greenlight -- who/what granted GO and on what basis
(`human:<name>`, `delegated:<basis>`, `envelope:<version>`). Required on GREENLIT lines dated
at/after GO_BASIS_REQUIRED_FROM only. The 53 pre-existing GREENLIT lines are all earlier than
the cutoff and none carry the field (ED-063 §3 P1); the registry is append-only and cannot be
backfilled, so they are grandfathered -- the same "field required only where every existing
line already has it" discipline as above, expressed as a ts cutoff instead of an all-or-nothing
gate. This is the on-ramp to the ED<->forge Phase-2 authorization envelope, whose invariant is
"every grant cites its authority -- human word or envelope version" (agos-grp-d8c9e5 item 6).
"""
import argparse
import json
import os
import sys

STATES = {"DESIGN", "VETTED", "GREENLIT", "BUILT-GREEN", "BUILT-RED", "VERIFIED", "REOPENED"}
FINDINGS_KEYS = ("critical", "high", "med", "low", "false_ticks")

# ED-063: go_basis is required on GREENLIT lines whose `ts` is at/after this cutoff. Set to one
# second after the latest pre-existing GREENLIT line (ED-062, ts 2026-07-12T08:13:30Z; ED-063
# §3 P1) so all 53 historical GREENLIT lines are grandfathered -- append-only history cannot be
# backfilled. ED-063's own GREENLIT is the first line required to carry it (self-dogfooding).
# The registry's `ts` values are uniform ISO-8601 UTC "...Z" strings, so lexicographic string
# comparison equals chronological order (ED-063 §3 P1 probe confirms the format is uniform).
GO_BASIS_REQUIRED_FROM = "2026-07-12T08:13:31Z"


def _err(errors, n, msg):
    errors.append(f"line {n}: {msg}")


def _check_int_ge0(errors, n, label, value):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _err(errors, n, f"{label!r} must be a non-negative int, got {value!r}")
        return False
    return True


def _check_findings(errors, n, findings):
    if not isinstance(findings, dict):
        _err(errors, n, f"'findings' must be a JSON object, got {type(findings).__name__}")
        return
    missing = [k for k in FINDINGS_KEYS if k not in findings]
    if missing:
        _err(errors, n, f"'findings' missing required keys {missing}")
    for k in FINDINGS_KEYS:
        if k in findings:
            _check_int_ge0(errors, n, f"findings.{k}", findings[k])


def validate_line(n, raw, errors):
    if not raw.strip():
        _err(errors, n, "blank line in append-only registry")
        return
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as exc:
        _err(errors, n, f"invalid JSON ({exc.msg})")
        return
    if not isinstance(d, dict):
        _err(errors, n, f"registry entry must be a JSON object, got {type(d).__name__}")
        return
    missing = {"id", "state", "ts"} - d.keys()
    if missing:
        _err(errors, n, f"missing required keys {sorted(missing)}")
        return
    for key in ("id", "ts"):
        if not isinstance(d[key], str):
            _err(errors, n, f"{key!r} must be a string, got {type(d[key]).__name__}")
    state = d["state"]
    if state not in STATES:
        _err(errors, n, f"unknown state {state!r} (allowed: {sorted(STATES)})")
        return

    if state == "DESIGN":
        if "tier" not in d:
            _err(errors, n, "DESIGN line missing required key 'tier'")
        elif d["tier"] not in ("FULL", "CEREMONY"):
            _err(errors, n, f"'tier' must be 'FULL' or 'CEREMONY', got {d['tier']!r}")
    elif state == "VETTED":
        if "review_channel" not in d:
            _err(errors, n, "VETTED line missing required key 'review_channel'")
        elif not isinstance(d["review_channel"], str) or not d["review_channel"].strip():
            _err(errors, n, "'review_channel' must be a non-empty string")
        if "findings" not in d:
            _err(errors, n, "VETTED line missing required key 'findings'")
        else:
            _check_findings(errors, n, d["findings"])
    elif state == "GREENLIT":
        if "authoring_wallclock_min" not in d:
            _err(errors, n, "GREENLIT line missing required key 'authoring_wallclock_min'")
        else:
            _check_int_ge0(errors, n, "authoring_wallclock_min", d["authoring_wallclock_min"])
        # go_basis (ED-063): prospectively required — grandfather any GREENLIT dated before the
        # cutoff. `ts` is guaranteed a string here only if the base check above passed; guard on
        # isinstance so a non-string ts falls through to its own error rather than raising.
        if isinstance(d.get("ts"), str) and d["ts"] >= GO_BASIS_REQUIRED_FROM:
            if "go_basis" not in d:
                _err(errors, n, f"GREENLIT line (ts >= {GO_BASIS_REQUIRED_FROM}) missing "
                                "required key 'go_basis' (the greenlight authority, e.g. "
                                "'human:marsh', 'delegated:<basis>', 'envelope:<version>')")
            elif not isinstance(d["go_basis"], str) or not d["go_basis"].strip():
                _err(errors, n, "'go_basis' must be a non-empty string")
    elif state in ("BUILT-GREEN", "BUILT-RED"):
        if "smoke_first_run" not in d:
            _err(errors, n, f"{state} line missing required key 'smoke_first_run'")
        elif d["smoke_first_run"] not in ("GREEN", "RED"):
            _err(errors, n, f"'smoke_first_run' must be 'GREEN' or 'RED', got {d['smoke_first_run']!r}")
    elif state == "VERIFIED":
        if "defects_post_ship" in d:
            dp = d["defects_post_ship"]
            if not isinstance(dp, dict):
                _err(errors, n, f"'defects_post_ship' must be a JSON object, got {type(dp).__name__}")
            else:
                for k in ("ed_side", "executor_side"):
                    if k in dp:
                        _check_int_ge0(errors, n, f"defects_post_ship.{k}", dp[k])
    elif state == "REOPENED":
        if "reason" not in d:
            _err(errors, n, "REOPENED line missing required key 'reason'")
        elif not isinstance(d["reason"], str) or not d["reason"].strip():
            _err(errors, n, "'reason' must be a non-empty string")


def validate_registry(path):
    if not os.path.isfile(path):
        return [f"registry not found: {path}"]
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except UnicodeDecodeError as exc:
        return [f"registry not valid UTF-8 at byte {exc.start}: {exc.reason}"]
    if not lines:
        return ["registry is empty"]
    errors = []
    for n, raw in enumerate(lines, 1):
        validate_line(n, raw, errors)
    return errors


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", default=os.path.abspath(
        os.path.join(here, "..", "_directives", "registry.jsonl")))
    args = ap.parse_args()
    errors = validate_registry(args.registry)
    if errors:
        print(f"validate-registry: {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    with open(args.registry, encoding="utf-8") as f:
        nlines = len(f.read().splitlines())
    print(f"validate-registry: {nlines} lines OK")


if __name__ == "__main__":
    main()
