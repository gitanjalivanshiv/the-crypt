#!/usr/bin/env bash
# Show what the Gemini API actually says about your quota.
# The adapter strips the response body on purpose, so this calls the SDK directly.
# Prints no key material.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
[ -n "${GEMINI_API_KEY:-}" ] || { echo "GEMINI_API_KEY is not set in this shell."; exit 1; }

uv run python - <<'PY'
import asyncio, os, re
from google import genai

def redact(s): return re.sub(r'AIza[A-Za-z0-9_\-]{10,}', 'REDACTED', str(s))
MODEL = os.environ.get("MEDIUM_MODEL", "gemini-4-hydrogen")

async def main():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    try:
        r = await client.aio.models.generate_content(
            model=MODEL, contents="say ok",
            config={"max_output_tokens": 8},
        )
        print(f"OK  {MODEL} answered. Quota is available right now.")
    except Exception as e:
        body = redact(e)
        print(f"FAILED {type(e).__name__}")
        print(body[:1500])
        print()
        low = body.lower()
        if "perday" in low.replace("_", "").replace(" ", "") or "per day" in low:
            print(">> DAILY quota. Backoff and pacing cannot help. It resets on Google's")
            print("   schedule (usually midnight Pacific). Use fewer turns, or wait.")
        elif "perminute" in low.replace("_", "").replace(" ", "") or "per minute" in low:
            print(">> PER-MINUTE quota. Pacing helps: raise --delay-s.")
        if "retrydelay" in low.replace("_", "").replace(" ", ""):
            m = re.search(r'retry.?delay\D{0,6}(\d+)', body, re.I)
            if m: print(f">> Server asks for {m.group(1)}s before retrying.")

asyncio.run(main())
PY
