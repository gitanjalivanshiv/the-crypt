#!/usr/bin/env bash
# Coverage gate for skeleton/verify (R4.24): no "pragma: no cover", 100% line and branch.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
if grep -rn "pragma: no cover" skeleton/verify/ --include='*.py'; then
  echo "FAIL: 'pragma: no cover' is not allowed under skeleton/verify/" >&2
  exit 1
fi
exec uv run pytest tests/verify --cov=skeleton.verify --cov-branch --cov-fail-under=100 -q
