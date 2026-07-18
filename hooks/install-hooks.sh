#!/usr/bin/env bash
# Install the ED dashboard-currency pre-commit hook into this clone.
#
# Git hooks are NOT version-controlled (.git/hooks is per-clone local state), so the hook
# ships as a tracked file and each clone must run this once. The guarantee it provides is
# therefore LOCAL: a machine that never ran this installer can still commit a stale
# dashboard. (ED-008 §7 records this as an accepted limitation of any git-hook approach.)
#
# Idempotent: safe to re-run. Refuses to clobber a foreign pre-commit hook.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
src_rel="dev/directive-framework/hooks/pre-commit"
src="$repo_root/$src_rel"
hooks_dir="$(git rev-parse --git-path hooks)"   # honors core.hooksPath / worktrees
dst="$hooks_dir/pre-commit"

if [ ! -f "$src" ]; then
  echo "install-hooks: hook source not found: $src" >&2
  exit 1
fi

# Executability is a property of THIS installer, not of the executor's manual chmod or of
# core.fileMode luck: git SILENTLY skips a non-executable hook (only an advice.ignoredHook
# hint), so a 0644 target defeats the gate entirely. Make +x here, idempotently.
chmod +x "$src"

mkdir -p "$hooks_dir"

# Already pointing at our hook? Nothing to do.
if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
  echo "install-hooks: already installed ($dst -> $src)"
  exit 0
fi

if [ -e "$dst" ] || [ -L "$dst" ]; then
  echo "install-hooks: $dst already exists and is not our hook." >&2
  echo "Inspect it, then remove it and re-run if you want the ED gate:" >&2
  echo "  rm -- \"$dst\" && bash \"$src_rel\"/../install-hooks.sh" >&2
  exit 1
fi

ln -s "$src" "$dst"
echo "install-hooks: installed $dst -> $src"
