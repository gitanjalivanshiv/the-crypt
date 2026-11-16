#!/usr/bin/env bash
# Finish a task: run the suite, commit, push.
#
#   ./scripts/done.sh 1.1 "text normalisation and toolchain"
#   ./scripts/done.sh 2.4 "archive safety checks" --no-test
#
# The pre-commit hook runs the .kiro disqualification guard on every commit,
# so that check happens whether or not you remember it.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

red()   { printf '\033[0;31m%s\033[0m\n' "$1"; }
green() { printf '\033[0;32m%s\033[0m\n' "$1"; }
dim()   { printf '\033[2m%s\033[0m\n' "$1"; }

[ $# -ge 2 ] || { red "usage: ./scripts/done.sh <task-id> <summary> [--no-test]"; exit 2; }
task="$1"; summary="$2"; shift 2
run_tests=1
for a in "$@"; do [ "$a" = "--no-test" ] && run_tests=0; done

if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  red "nothing changed — did the task actually run?"; exit 1
fi

if [ "$run_tests" = 1 ] && [ -d tests ] && command -v uv >/dev/null 2>&1; then
  dim "running tests…"
  if ! uv run pytest tests -q -x --no-header 2>&1 | tail -15; then
    red "tests failed — not committing."
    dim "fix it, or pass --no-test if this task legitimately has no passing suite yet."
    exit 1
  fi
fi

git add -A
git commit -q -m "Task $task: $summary" || { red "commit failed (guard?)"; exit 1; }
git push -q origin main || { red "push failed — commit is local, retry with: git push"; exit 1; }

green "Task $task committed and pushed."
echo
dim "Record this task's credit cost in docs/CREDIT-BUDGET.md while the dashboard is fresh."
