"""Serve the Medium with a scripted ghost, so a banishment can be demonstrated
with no provider key at all.

    uv run python -m demo.banishment

Why this exists: across ten recorded harness runs and 46 judged claims the model
fabricated nothing, so the banishment -- the whole point of the project -- has never once
occurred on its own. It cannot be captured by pointing a camera at a live run and waiting.
See docs/VIDEO-PLAN.md.

What is real here and what is not: the ghost's words are scripted, and nothing else is. The
snapshot is a real clone of the pinned patient repo, the verifier is the production
verifier, the reason code and its message are produced by it, and the retry is the flow's
own single regeneration (skeleton R4.12). The first reply cites a file that does not exist,
so the verifier banishes it with ``file_not_found``; the second cites a file that does, and
is accepted. ``tests/api/test_ask.py::test_banished_then_answered`` covers the same path.

Say out loud, on camera, that the reply is scripted. An undisclosed scripted reply that a
judge notices discredits every other claim in the video.
"""

import argparse
import json
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient

from medium.api import create_medium_app
from skeleton.api.app import ApiConfig
from skeleton.personas.llm import LLMRequest, LLMResponse

ROOT = Path(__file__).resolve().parents[1]
PATIENT_JSON = ROOT / "demo" / "patient.json"
DEFAULT_STORE = ROOT / "demo" / "crypt-store"
PERSONA = "ghost"

# Mirrors skeleton.personas.generator.render_feedback. A request carrying either prefix is
# the flow's regeneration, not a first attempt, so the scripted ghost answers truthfully.
RETRY_MARKERS = ("These claims were rejected:", "Your previous answer could not be used")

# No digits in either claim text: a figure must be backed by Finding.metrics or the verifier
# banishes it as unbacked_number, which would bury the reason code this demo is about.
FABRICATED = {
    "text": "The rot began in the midnight module, where the old layout was decided.",
    "citations": [{"file": "setuptools/midnight.py", "line_start": 1, "line_end": 4}],
}
GROUNDED = {
    "text": "Discovery is where the layout is decided.",
    "citations": [{"file": "setuptools/discovery.py", "line_start": 1, "line_end": 20}],
}


def say(message: str = "") -> None:
    """Print immediately. Python buffers stdout when it is not a terminal, so without this
    the snapshot ref stays invisible until the server exits -- useless for a demo."""
    print(message, flush=True)


def _reply(claim: dict[str, object]) -> LLMResponse:
    return LLMResponse(text=json.dumps({"claims": [claim]}))


class ScriptedGhost:
    """An ``LLMClient`` that fabricates on every first attempt and grounds on every retry.

    Keyed on the request rather than a call counter, so it stays correct for any number of
    turns, for the plan route's several questions, and if an attempt is ever skipped.
    """

    def __init__(self) -> None:
        self.fabricated = 0
        self.grounded = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        retry = any(
            m.role == "user" and m.content.startswith(RETRY_MARKERS) for m in request.messages
        )
        if retry:
            self.grounded += 1
            return _reply(GROUNDED)
        self.fabricated += 1
        return _reply(FABRICATED)


def _patient() -> dict[str, str]:
    primary = json.loads(PATIENT_JSON.read_text(encoding="utf-8"))["primary"]
    return {"url": primary["clone_url"], "sha": primary["commit"]}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m demo.banishment", description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000, help="must match the medium/ui proxy")
    p.add_argument("--store", type=Path, default=DEFAULT_STORE)
    p.add_argument("--ui-port", type=int, default=5173, help="only used to print the UI URL")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    args.store.mkdir(parents=True, exist_ok=True)
    app = create_medium_app(
        store=args.store, llm=ScriptedGhost(), cfg=ApiConfig(allow_retained=True)
    )

    patient = _patient()
    say(f"cloning {patient['url']} at {patient['sha'][:12]} (about 20s)...")
    with TestClient(app) as http:
        r = http.post("/snapshots", json={**patient, "intent": "retained"})
        if r.status_code != 201:
            raise SystemExit(f"ingest failed: HTTP {r.status_code} {r.text}")
        ref = r.json()["ref"]

    say()
    say("  ready. the ghost is scripted; the verifier is not.")
    say(f"  UI    http://127.0.0.1:{args.ui_port}/?ref={ref}")
    say(f"  API   http://{args.host}:{args.port}/snapshots/{ref}")
    say()
    say("  Ask anything. Every turn is banished once, then answered.")
    say()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
