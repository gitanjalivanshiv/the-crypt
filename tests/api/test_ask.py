"""POST /snapshots/{ref}/ask with a scripted FakeLLMClient."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from skeleton.api.app import ApiConfig, create_app
from skeleton.personas.llm import FakeLLMClient, LLMResponse
from skeleton.verify.models import AnswerResult, VerifyConfig
from tests.api.test_read_routes import REF, SNAP_ID, persona_dir, store  # noqa: F401

GOOD = {"text": "It sleeps here.", "citations": [{"file": "a.py", "line_start": 1, "line_end": 1}]}
BAD = {"text": "It never existed.", "citations": [{"file": "nope.py", "line_start": 1, "line_end": 1}]}


def _reply(*claims: dict) -> LLMResponse:
    return LLMResponse(text=json.dumps({"claims": list(claims)}))


def _ask(store: Path, persona_dir: Path, script: list[LLMResponse], persona: str = "example", cfg: ApiConfig | None = None):  # noqa: F811
    llm = FakeLLMClient(script)
    client = TestClient(
        create_app(store=store, llm=llm, persona_dir=persona_dir, cfg=cfg or ApiConfig())
    )
    return client.post(f"/snapshots/{REF}/ask", json={"persona": persona, "question": "Why?"}), llm


def test_answered(store: Path, persona_dir: Path) -> None:  # noqa: F811
    r, _ = _ask(store, persona_dir, [_reply(GOOD)])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "answered" and body["snapshot_id"] == SNAP_ID
    assert body["claims"][0]["text"] == GOOD["text"]
    assert body["banishments"] == []


def test_declined(store: Path, persona_dir: Path) -> None:  # noqa: F811
    r, llm = _ask(store, persona_dir, [_reply(BAD), _reply(BAD)])
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "declined" and body["claims"] == []
    assert body["decline_line"] == "Silent."
    assert [b["attempt"] for b in body["banishments"]] == [1, 2]
    assert len(llm.requests) == 2


def test_banished_then_answered(store: Path, persona_dir: Path) -> None:  # noqa: F811
    r, _ = _ask(store, persona_dir, [_reply(BAD), _reply(GOOD)])
    body = r.json()
    assert body["status"] == "answered"
    assert [c["text"] for c in body["claims"]] == [GOOD["text"]]
    assert body["banishments"][0]["reason"] == "file_not_found"
    assert [a["outcome"] for a in body["attempts"]] == ["banished", "accepted"]


def test_unknown_persona(store: Path, persona_dir: Path) -> None:  # noqa: F811
    r, llm = _ask(store, persona_dir, [], persona="nobody")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "persona_not_found"
    assert llm.requests == []


def test_body_is_answer_result_unchanged(store: Path, persona_dir: Path) -> None:  # noqa: F811
    r, _ = _ask(store, persona_dir, [_reply(BAD), _reply(GOOD)])
    body = r.json()
    parsed = AnswerResult.model_validate(body)
    assert set(body) == set(AnswerResult.model_fields)
    assert parsed.model_dump(mode="json") == body

FORTY_TWO = {
    "text": "It has 42 lines.",
    "citations": [{"file": "a.py", "line_start": 1, "line_end": 1}],
}
def test_injected_allowed_numbers(store: Path, persona_dir: Path) -> None:  # noqa: F811
    r, _ = _ask(store, persona_dir, [_reply(FORTY_TWO), _reply(FORTY_TWO)])
    body = r.json()
    assert body["status"] == "declined"
    assert body["banishments"][0]["reason"] == "unbacked_number"
    allowed = ApiConfig(verify=VerifyConfig(allowed_numbers=frozenset({"42"})))
    r, _ = _ask(store, persona_dir, [_reply(FORTY_TWO)], cfg=allowed)
    body = r.json()
    assert body["status"] == "answered"
    assert [c["text"] for c in body["claims"]] == [FORTY_TWO["text"]]
    assert body["banishments"] == []
