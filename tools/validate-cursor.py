#!/usr/bin/env python3
"""validate-cursor.py — deterministic schema check for `_directives/cursor.json`.

Shipped by ED-001 (Foundation). Exit 0 = valid; exit 2 = invalid (every error names the
offending field with expected vs got). Consumers: phase-boundary gates (B4), the
phase/role-aware auto-handoff (B8), and the executor harness (B2).

Schema is STRICT: exactly the keys below, no extras — schema evolution happens by
explicit migration in a directive, never by silent key creep. Enums here must match
init-runtime.py (same shipped package; drift between the two is a defect).
"""
import datetime
import json
import re
import sys

PHASES = {"planning", "design", "validation", "execution", "review"}
ROLES = {"orchestrator", "author", "coder", "reviewer", "idle"}
REQUIRED = {"phase", "role", "active_directive", "boundary",
            "postpones_used", "updated", "updated_by"}
DIRECTIVE_RE = re.compile(r"(PD|DD|VD|ED|RD)-[0-9]{3}")
def _valid_ts(v):
    """Calendar-valid ISO-8601 UTC, exactly YYYY-MM-DDTHH:MM:SSZ, ASCII digits only
    (ED-003 hardening: shape-only regex accepted month 13, non-ASCII digits, and a
    trailing newline)."""
    if not isinstance(v, str) or len(v) != 20 or not v.isascii():
        return False
    try:
        datetime.datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def validate(path):
    """Returns (errors, data) — single read; the caller must not re-open the file
    (ED-003 hardening: the old OK-message re-read raced the validated content)."""
    errors = []
    data = None
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as exc:
        return [f"cannot read {path}: {exc}"], None
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc.msg} (line {exc.lineno})"], None
    if not isinstance(d, dict):
        return [f"cursor must be a JSON object, got {type(d).__name__}"], None
    data = d

    missing = REQUIRED - d.keys()
    extra = d.keys() - REQUIRED
    if missing:
        errors.append(f"missing required keys {sorted(missing)}")
    if extra:
        errors.append(f"unknown keys {sorted(extra)} (schema is strict; "
                      "evolve it via a directive, not key creep)")

    if "phase" in d and d["phase"] not in PHASES:
        errors.append(f"'phase' must be one of {sorted(PHASES)}, got {d['phase']!r}")
    if "role" in d and d["role"] not in ROLES:
        errors.append(f"'role' must be one of {sorted(ROLES)}, got {d['role']!r}")
    for key in ("active_directive", "boundary"):
        if key in d and d[key] is not None:
            if not isinstance(d[key], str) or not d[key].strip():
                errors.append(f"'{key}' must be null or a non-empty string, got {d[key]!r}")
            elif key == "active_directive" and not DIRECTIVE_RE.fullmatch(d[key]):
                errors.append(f"'active_directive' must match (PD|DD|VD|ED|RD)-NNN, "
                              f"got {d[key]!r}")
    if "postpones_used" in d:
        v = d["postpones_used"]
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            errors.append(f"'postpones_used' must be a non-negative int, got {v!r}")
    if "updated" in d:
        if not _valid_ts(d["updated"]):
            errors.append(f"'updated' must be a calendar-valid ISO-8601 UTC "
                          f"'YYYY-MM-DDTHH:MM:SSZ' (ASCII), got {d['updated']!r}")
    if "updated_by" in d:
        if not isinstance(d["updated_by"], str) or not d["updated_by"].strip():
            errors.append(f"'updated_by' must be a non-empty string, got {d['updated_by']!r}")
    return errors, data


def main():
    if len(sys.argv) != 2:
        print("usage: validate-cursor.py <path/to/cursor.json>", file=sys.stderr)
        sys.exit(2)
    errors, d = validate(sys.argv[1])
    if errors:
        print(f"validate-cursor: {len(errors)} problem(s) in {sys.argv[1]}:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(2)
    print(f"validate-cursor: OK — phase={d['phase']} role={d['role']} "
          f"active={d['active_directive']} boundary={d['boundary']}")
    sys.exit(0)


if __name__ == "__main__":
    main()
