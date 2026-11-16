#!/usr/bin/env bash
# Kiroween 2026 disqualification guard.
#
# The Official Rules: "Do NOT add the /.kiro directory or sub-folders to your .gitignore,
# as this could disqualify your submission."
#
# Run from a Kiro command hook, a git pre-commit hook, and CI.
set -euo pipefail

fail() { printf '\033[0;31mFAIL\033[0m  %s\n' "$1" >&2; exit 1; }

cd "$(git rev-parse --show-toplevel)"

# 1. No gitignore file may name .kiro in an active (non-comment) rule.
while IFS= read -r ignorefile; do
  [ -f "$ignorefile" ] || continue
  # Strip comments and blank lines, then look for a kiro rule.
  if hits=$(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$ignorefile" \
            | grep -nE '(^|[/![:space:]])\.?kiro(/|$|[[:space:]])'); then
    fail "$ignorefile has an active rule matching .kiro:
$hits
Remove it — this is a disqualification risk."
  fi
done < <(git ls-files --cached --others --exclude-standard | grep -E '(^|/)\.gitignore$' || true)

# 2. .kiro must actually be tracked by git.
if [ -d .kiro ]; then
  if [ -z "$(git ls-files .kiro)" ] && [ -z "$(git diff --cached --name-only -- .kiro)" ]; then
    fail ".kiro/ exists but no file inside it is staged or tracked by git."
  fi
else
  fail ".kiro/ does not exist at the repository root."
fi

# 3. Git must not be ignoring anything under .kiro for any other reason.
ignored="$(git ls-files --others --ignored --exclude-standard -- .kiro 2>/dev/null || true)"
[ -z "$ignored" ] || fail "git is ignoring these files under .kiro/:
$ignored"

# 4. The required steering files must be present.
for f in product tech structure grounding-rule credit-policy; do
  [ -f ".kiro/steering/$f.md" ] || fail "missing .kiro/steering/$f.md"
done

printf '\033[0;32mOK\033[0m    .kiro is committed and not ignored\n'
