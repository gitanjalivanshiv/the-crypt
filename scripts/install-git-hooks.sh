#!/usr/bin/env bash
# Install the .kiro guard as a real git pre-commit hook.
# Kiro hooks only fire while Kiro is open; this one is a disqualification risk,
# so it also runs on every commit and in CI.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
hook="$root/.git/hooks/pre-commit"
cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
"$(git rev-parse --show-toplevel)/scripts/check-kiro-committed.sh"
HOOK
chmod +x "$hook"
echo "Installed $hook"
