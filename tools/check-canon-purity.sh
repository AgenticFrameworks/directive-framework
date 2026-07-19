#!/usr/bin/env bash
# tools/check-canon-purity.sh — deterministic clean-canon guard (ED-003).
# Exit 0 = canon pure; exit 1 = violations listed. Purity means git-TRACKED files
# include NO runtime state: no _directives/ paths, no registry/cursor/dashboard
# instances, no ED/PD/DD/VD/RD instance packets (any case), and no tracked
# markdown file carries a RENDERED dashboard block (cross-vet F1: the README-only
# check let the incident class re-open under any other tracked filename). The
# rendered-block scan is .md-scoped and line-anchored ('^<!-- ED-DASHBOARD:BEGIN')
# on purpose: shipped .py sources legitimately embed the marker as a string
# constant (init-runtime.py's skeleton has it at column 0), and docs may mention
# the marker name inline — only a block actually rendered into tracked markdown
# is runtime state in canon.
# Fail-CLOSED filename handling (REOPENED fix, double-final-review convergent
# finding): '--' terminators keep option-like tracked names (leading '-') from
# being eaten as basename/grep options, and the NUL-delimited ls-files loop keeps
# newline-containing tracked paths from splitting into unmatched fragments.
# Accepted conservative corner: command substitution strips TRAILING newlines
# from a basename, so a name like $'ED-123.md\n' collapses and gets flagged —
# the guard errs toward flagging pathological names (same behavior as the old
# grep pipe; over-report, never under-report).
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
fail=0
say() { echo "canon-purity: $*" >&2; fail=1; }

while IFS= read -r -d '' f; do
    case "$f" in
        _directives/*) say "tracked runtime path: $f" ;;
    esac
    case "$(basename -- "$f")" in
        registry.jsonl|cursor.json|directives.jsonl) say "tracked registry/cursor instance: $f" ;;
    esac
    # instance packets: (PD|DD|VD|ED|RD)-NNN*.md anywhere tracked, ANY case
    # (cross-vet F2) — canon holds templates like ED-TEMPLATE.md, which do not
    # match the NNN form. Matched with bash =~ on the WHOLE lowercased basename
    # (POSIX regexec, no REG_NEWLINE): an embedded newline cannot split this
    # check the way a line-based grep pipe could (delta-confirm residual,
    # second REOPENED fix).
    bn=$(basename -- "$f")
    if [[ "${bn,,}" =~ ^(pd|dd|vd|ed|rd)-[0-9]{3}.*\.md$ ]]; then
        say "tracked directive instance packet: $f"
    fi
    # rendered dashboard block in ANY tracked markdown (cross-vet F1)
    case "$f" in
        *.md)
            if [ -f "$f" ] && grep -q -e '^<!-- ED-DASHBOARD:BEGIN' -- "$f"; then
                say "tracked file carries a generated dashboard block (runtime state in canon): $f"
            fi ;;
    esac
done < <(git ls-files -z)

if [ "$fail" -eq 0 ]; then
    echo "canon-purity: OK — no runtime state in tracked canon"
    exit 0
fi
exit 1
