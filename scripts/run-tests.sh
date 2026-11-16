#!/usr/bin/env bash
# Hook-safe test runner.
#
# Kiro command hooks fire from the first save onwards, long before the test
# directories exist. A hook that fails noisily on every save gets switched off,
# which is how a project ends up with no automated checks at all. So: skip
# cleanly when there is nothing to run, and fail loudly only when a real test
# fails.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

target="${1:-tests}"

if [ ! -d "$target" ]; then
  echo "skip: $target does not exist yet"
  exit 0
fi

if ! find "$target" -name 'test_*.py' -o -name '*_test.py' | grep -q .; then
  echo "skip: no tests in $target yet"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "skip: uv is not installed — see docs/EXECUTION-PLAN.md"
  exit 0
fi

exec uv run pytest "$target" -q
