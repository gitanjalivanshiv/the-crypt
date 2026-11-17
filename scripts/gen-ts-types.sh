#!/usr/bin/env bash
# Regenerate skeleton/ui-shell/src/types.generated.ts from the API's OpenAPI schema.
# Pass --check to fail (exit 1) if the committed file differs from a fresh generation.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/skeleton/ui-shell/src/types.generated.ts"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PY="python3"
[ -x "$ROOT/.venv/bin/python" ] && PY="$ROOT/.venv/bin/python"

mkdir -p "$TMP/personas" "$TMP/store"
cat > "$TMP/personas/example.toml" <<'EOF'
name = "example"
display_name = "Example Ghost"
voice = "Dry."
goals = ["Cite facts"]
allowed_tools = ["list_findings"]
example_lines = ["It sleeps."]
decline_line = "Silent."
EOF

(cd "$ROOT" && TMP="$TMP" "$PY" - > "$TMP/openapi.json" <<'EOF'
import json, os
from pathlib import Path
from skeleton.api.app import create_app
from skeleton.personas.llm import FakeLLMClient

t = Path(os.environ["TMP"])
app = create_app(store=t / "store", llm=FakeLLMClient([]), persona_dir=t / "personas")
print(json.dumps(app.openapi(), indent=2, sort_keys=True))
EOF
)

GEN="$TMP/types.generated.ts"
(cd "$ROOT/skeleton/ui-shell" && pnpm dlx openapi-typescript@7.13.0 "$TMP/openapi.json" -o "$GEN" >&2)

if [ "${1:-}" = "--check" ]; then
  diff -u "$OUT" "$GEN" || { echo "types.generated.ts is stale; run scripts/gen-ts-types.sh" >&2; exit 1; }
else
  cp "$GEN" "$OUT"
fi
