#!/usr/bin/env bash
# tools/executor-run.sh — executor-harness glue (ED-002, boundary B2).
#
# usage: bash tools/executor-run.sh ED-NNN [--project DIR]
#
# The glue owns every state transition; no model is in the apply loop (earned:
# ED-001's executor regenerated an append-target instead of appending).
#   1. GREENLIGHT GATE  — latest registry state for ED-NNN must be GREENLIT.
#   2. INTAKE SANITY    — ED md + launch + files dir + .probes-complete + manifest.json.
#   3. CURSOR           — phase=execution role=coder active=ED-NNN (atomic, validated).
#   4. APPLY            — manifest-driven copy/append, mechanical, idempotent markers.
#   5. SMOKE            — run the ED's smoke; HARD STOP on red (no fix iteration).
#   6. REGISTRY         — BUILT-GREEN / BUILT-RED via append-registry.py (flock'd path).
#   7. CURSOR RESET     — role=orchestrator active=null, green or red.
# Synthesis (aider) EDs are NOT run by this v1 glue — see EXECUTOR-SPEC.md §Synthesis.
set -u

CANON="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # canon repo root (this script lives in canon tools/)
if [ ! -f "$CANON/execution-directives/append-registry.py" ]; then
    echo "executor-run: canon resolved to $CANON but execution-directives/append-registry.py is missing —" >&2
    echo "executor-run: this script must run from <canon>/tools/ (applied), not from the ED package dir" >&2
    exit 2
fi

if [ "${1:-}" != "--guarded" ]; then
    exec timeout 1800 bash "$0" --guarded "$@"   # wall-clock kill in code (30 min)
fi
shift

ID="${1:?usage: executor-run.sh ED-NNN [--project DIR]}"
shift
PROJ="$CANON"
while [ $# -gt 0 ]; do
    case "$1" in
        --project) PROJ="$(cd "$2" 2>/dev/null && pwd)" || { echo "executor-run: --project dir not found: $2" >&2; exit 2; }; shift 2 ;;
        *) echo "executor-run: unknown arg $1" >&2; exit 2 ;;
    esac
done

REG="$PROJ/_directives/registry.jsonl"
EDDIR="$PROJ/_directives/ED"
CURSOR="$PROJ/_directives/cursor.json"
LOCK="$EDDIR/.executor.lock"
APPEND="$CANON/execution-directives/append-registry.py"
VALIDATE_CURSOR="$CANON/tools/validate-cursor.py"

die() { echo "executor-run: $*" >&2; exit 2; }

[ -f "$REG" ] || die "no registry at $REG — run tools/init-runtime.py first"
mkdir -p "$EDDIR"
exec 9>"$LOCK"
flock -n 9 || die "another executor run holds $LOCK — refusing (one build at a time)"

# ---- 1. Greenlight gate: the GREENLIT registry line IS the sign-off signal ----
LAST=$(python3 - "$REG" "$ID" <<'EOF'
import json, sys
last = "NONE"
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    d = json.loads(line)
    if d.get("id") == sys.argv[2]:
        last = d.get("state", "NONE")
print(last)
EOF
)
[ "$LAST" = "GREENLIT" ] || die "refusing $ID: latest registry state is '$LAST', executor requires GREENLIT (greenlight is a registry line, nothing else)"

# ---- 2. Intake sanity (STRICT-HARD dual gate arrives with B4; this is the floor) ----
EDMD=$(ls "$EDDIR/$ID"*.md 2>/dev/null | grep -v -- "-launch.md" | head -1) || true
[ -n "${EDMD:-}" ] && [ -f "$EDMD" ] || die "refusing $ID: no directive file $EDDIR/$ID*.md"
LAUNCH="$EDDIR/$ID-launch.md"
[ -f "$LAUNCH" ] || die "refusing $ID: launch prompt $LAUNCH missing"
FILES="$EDDIR/$ID.files"
[ -d "$FILES" ] && [ -n "$(ls -A "$FILES")" ] || die "refusing $ID: package dir $FILES missing/empty"
[ -f "$FILES/.probes-complete" ] || die "refusing $ID: probes-complete seam missing — probes not durable on disk"
MANIFEST="$FILES/manifest.json"
[ -f "$MANIFEST" ] || die "refusing $ID: $MANIFEST missing (mechanical-apply contract)"
python3 - "$MANIFEST" "$FILES" <<'EOF' || exit 2
import json, os, sys
m = json.load(open(sys.argv[1], encoding="utf-8"))
files_dir = sys.argv[2]
ok = True
def err(msg):
    global ok; ok = False; print(f"executor-run: manifest: {msg}", file=sys.stderr)
if not isinstance(m.get("apply"), list) or not m["apply"]:
    err("'apply' must be a non-empty list")
for i, e in enumerate(m.get("apply") or []):
    for k in ("from", "to", "mode"):
        if k not in e: err(f"apply[{i}] missing '{k}'")
    if e.get("mode") not in ("copy", "append"): err(f"apply[{i}].mode must be copy|append")
    if e.get("mode") == "append":
        if not e.get("marker"):
            err(f"apply[{i}] append requires 'marker'")
        else:
            # marker MUST occur in the source block, or the append can never be
            # idempotent (cross-vet F2a: re-append on every REOPEN cycle)
            src = os.path.join(files_dir, e.get("from", ""))
            if os.path.isfile(src) and e["marker"] not in open(src, encoding="utf-8").read():
                err(f"apply[{i}]: marker {e['marker']!r} does not occur in source "
                    f"{e.get('from')!r} — appended block must carry its own marker")
    for k in ("from", "to"):
        v = e.get(k, "")
        if v.startswith("/") or ".." in v.split("/"): err(f"apply[{i}].{k} must be relative, no '..': {v!r}")
    for k in ("from", "to", "marker"):
        v = e.get(k) or ""
        if any(c in v for c in "\t\n\r"):
            err(f"apply[{i}].{k} contains control characters (tab/newline) — refused (TSV transport)")
if not isinstance(m.get("smoke"), str) or not m["smoke"]:
    err("'smoke' must be a non-empty project-relative path")
elif m["smoke"].startswith("/") or ".." in m["smoke"].split("/") or any(c in m["smoke"] for c in "\t\n\r"):
    err(f"'smoke' must be relative, no '..', no control chars: {m['smoke']!r}")
sys.exit(0 if ok else 1)
EOF
SMOKE_REL=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['smoke'])" "$MANIFEST")

set_cursor() {  # phase role active(null|ED-NNN); returns nonzero on failure (never exits)
    python3 - "$CURSOR" "$1" "$2" "$3" <<'EOF' || return 1
import datetime, json, os, sys, tempfile
cur, phase, role, active = sys.argv[1:5]
d = json.load(open(cur, encoding="utf-8"))
d["phase"], d["role"] = phase, role
d["active_directive"] = None if active == "null" else active
d["updated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
d["updated_by"] = "executor-run"
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(cur), prefix=".tmp-cur-")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2); f.write("\n")
os.replace(tmp, cur)
EOF
    python3 "$VALIDATE_CURSOR" "$CURSOR" >/dev/null || return 1
}

append_state() {  # json-line
    local dash_args
    if [ -f "$PROJ/README.md" ] && grep -q 'ED-DASHBOARD:BEGIN' "$PROJ/README.md"; then
        dash_args=(--readme "$PROJ/README.md")
    else
        dash_args=(--no-dashboard)
    fi
    python3 "$APPEND" --registry "$REG" "${dash_args[@]}" "$1" \
        || die "registry append FAILED for: $1"
}

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# ---- 2b. Strict-hard intake gate (ED-010: gate the INCOMING cursor). The executor calls
# the real gate-runner execution-intake (the 15-check VD->ED + ED-dual strict-hard gate),
# not just the bash floor above. Unlike the ED-009 flip, the executor no longer pre-advances
# the cursor before the gate — the orchestrator PRE-POSITIONS it at phase=validation (this
# boundary's source) or phase=execution (its destination), role=orchestrator, active=null,
# per EXECUTOR-SPEC "Cursor pre-position contract", BEFORE invoking this script. The gate now
# tests THAT incoming cursor with teeth restored: cursor-valid, cursor-not-mid-build (no build
# in flight), cursor-phase-match (on-boundary). Only on a gate PASS does step 3 assume coder.
python3 "$CANON/tools/gate-runner.py" "$CANON/gates/execution-intake.md" --id "$ID" --project "$PROJ" \
    || die "refusing $ID: execution-intake strict-hard gate did not PASS (fail-closed) — fix the intake and re-run"
echo "executor-run: execution-intake gate PASS — proceeding to build"

# ---- 3. Cursor: coder on duty — release GUARANTEED on every exit path from here
# on via EXIT trap (double-final-review defect: append_state failure post-smoke left
# the cursor stuck at coder). TERM/INT routed through EXIT so a timeout kill releases too.
set_cursor execution coder "$ID" || die "cursor write/validate failed — refusing to proceed"
release_cursor() { set_cursor execution orchestrator null 2>/dev/null || true; }
trap release_cursor EXIT
trap 'exit 143' TERM INT

# ---- 4. Mechanical apply (no model in the loop) ----
PROJR="$(cd "$PROJ" && pwd -P)"
while IFS=$'\t' read -r MODE FROM TO MARKER; do
    SRC="$FILES/$FROM"; DST="$PROJ/$TO"
    [ -f "$SRC" ] || { set_cursor execution orchestrator null; die "apply: source missing: $SRC"; }
    mkdir -p "$(dirname "$DST")" || die "apply: mkdir failed for $TO"
    # containment: resolve symlinks (cross-vet F3 — a symlinked intermediate dir must
    # not let a write escape the project root)
    DSTDIR="$(cd "$(dirname "$DST")" && pwd -P)"
    case "$DSTDIR/" in
        "$PROJR/"*|"$PROJR/") : ;;
        *) set_cursor execution orchestrator null
           die "apply: $TO resolves outside the project root ($DSTDIR) — symlink escape refused" ;;
    esac
    # leaf containment (double-final-review, convergent finding): a destination that is
    # ITSELF a pre-existing symlink would write through to wherever it points
    [ ! -L "$DST" ] || die "apply: $TO is a pre-existing symlink — leaf-symlink destination refused (containment)"
    if [ "$MODE" = "copy" ]; then
        cp "$SRC" "$DST" || die "apply: cp failed for $TO"
        cmp -s "$SRC" "$DST" || { set_cursor execution orchestrator null; die "apply: cmp mismatch after copy: $DST"; }
        echo "executor-run: applied copy $FROM -> $TO"
    else
        if grep -qF -- "$MARKER" "$DST" 2>/dev/null; then
            echo "executor-run: WARNING append $TO already carries marker '$MARKER' — skipped (idempotent). If this block was never applied, the marker collides with unrelated content; markers must be globally unique block headers (EXECUTOR-SPEC §manifest)."
        else
            cat "$SRC" >> "$DST" || die "apply: append write failed for $TO"
            echo "executor-run: applied append $FROM -> $TO"
        fi
    fi
done < <(python3 - "$MANIFEST" <<'EOF'
import json, sys
for e in json.load(open(sys.argv[1], encoding="utf-8"))["apply"]:
    print("\t".join([e["mode"], e["from"], e["to"], e.get("marker", "-")]))
EOF
)

# ---- 5. Smoke: hard stop on red, no fix iteration ----
# fd 9 (executor lock) is closed for the child so an ED smoke can never inherit or
# re-lock the executor's own lock fd (cross-vet F4)
if bash "$PROJ/$SMOKE_REL" 9>&-; then
    # ---- 6a. GREEN ----
    append_state "{\"id\":\"$ID\",\"state\":\"BUILT-GREEN\",\"ts\":\"$(now)\",\"smoke_first_run\":\"GREEN\",\"cycles_to_green\":1}"
    set_cursor execution orchestrator null
    echo "executor-run: $ID BUILT-GREEN — smoke green, registry appended, cursor released"
    exit 0
else
    # ---- 6b. RED: defects file + BUILT-RED + exit. The fix cycle belongs to the author. ----
    DEFECTS="$EDDIR/$ID-defects.md"
    {
        echo "# $ID defects — smoke RED $(now)"
        echo "Smoke: $SMOKE_REL exited nonzero. Result JSON (if the harness persisted one):"
        RESULT_GLOB=$(ls "$EDDIR/$ID"-smoke-result.json 2>/dev/null | head -1)
        if [ -n "${RESULT_GLOB:-}" ]; then cat "$RESULT_GLOB"; else echo "(no result file found)"; fi
        echo
        echo "Hard stop honored: NO fix iteration was attempted. Route the fix through the authoring capacity."
    } > "$DEFECTS"
    append_state "{\"id\":\"$ID\",\"state\":\"BUILT-RED\",\"ts\":\"$(now)\",\"smoke_first_run\":\"RED\"}"
    set_cursor execution orchestrator null
    echo "executor-run: $ID BUILT-RED — defects at $DEFECTS, registry appended, cursor released" >&2
    exit 1
fi
