#!/usr/bin/env bash
# Verify the Gemini path end to end. Usage: ./scripts/check-gemini.sh
# Needs GEMINI_API_KEY in the environment. Prints no key material.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
red(){ printf '\033[0;31m%s\033[0m\n' "$1"; }
grn(){ printf '\033[0;32m%s\033[0m\n' "$1"; }

if [ -z "${GEMINI_API_KEY:-}" ]; then
  red "GEMINI_API_KEY is not set."
  echo "  Get one free (no card) at https://aistudio.google.com -> Get API key"
  echo "  Then:  export GEMINI_API_KEY='your-key'"
  exit 1
fi
echo "key present (length ${#GEMINI_API_KEY})"

echo
echo "1/3  adapter unit tests (no network)"
uv run pytest tests/providers -q --no-header 2>&1 | tail -2 || { red "unit tests failed"; exit 1; }

echo
echo "2/3  one live call"
MEDIUM_PROVIDER=gemini uv run python - <<'PY' || exit 1
import asyncio, os, re, sys
from providers.select import client_from_env, provider_from_env
from skeleton.personas.llm import LLMRequest, Message
def red(s): return re.sub(r'AIza[A-Za-z0-9_\-]+','REDACTED',str(s))
async def main():
    try:
        c = client_from_env()
        r = await c.complete(LLMRequest(system="Reply with exactly: ok",
              messages=(Message(role="user", content="say ok"),), max_tokens=32))
        print(f"   provider={provider_from_env()}  reply={r.text.strip()[:40]!r}")
    except Exception as e:
        print(f"   FAILED {type(e).__name__}: {red(e)[:300]}"); sys.exit(1)
asyncio.run(main())
PY

echo
echo "3/3  one real harness turn"
MEDIUM_PROVIDER=gemini uv run python -m medium.eval --runs 1 --max-turns 1 2>&1 | tail -12

echo
grn "Gemini path works. Full run:  MEDIUM_PROVIDER=gemini uv run python -m medium.eval --runs 2"
