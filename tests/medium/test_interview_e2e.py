"""Interview loop end to end, server side (medium R4.1, R4.2, R4.7).

``create_medium_app`` must return the skeleton app's own ``AnswerResult`` JSON, unchanged,
for the same script and persona directory.
"""
import functools
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from medium.api import PERSONA_DIR, create_medium_app
from skeleton.api.app import ApiConfig, create_app
from skeleton.personas.llm import FakeLLMClient
from tests.medium.test_plan_route import BAD, GOOD, URL, _reply, make  # noqa: F401

QUESTION = "What lives in a.py?"
GHOST_DECLINE = tomllib.loads((PERSONA_DIR / "ghost.toml").read_text())["decline_line"]


def _ask(factory, make, tmp_path_factory, script) -> dict:  # noqa: F811  (pytest fixture shadows the import)
    ingest, repo = make
    llm = FakeLLMClient(script)
    app = factory(tmp_path_factory.mktemp("store"), llm, ingest)
    client = TestClient(app)
    r = client.post("/snapshots", json={"url": URL, "sha": repo.head(), "intent": "retained"})
    assert r.status_code == 201, r.text
    resp = client.post(
        f"/snapshots/{r.json()['ref']}/ask", json={"persona": "ghost", "question": QUESTION}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _medium(store: Path, llm, ingest, monkeypatch=None):
    # create_medium_app has no ingest seam; give it the fixture ingest via its create_app.
    from medium import api

    original = api.create_app
    api.create_app = functools.partial(create_app, ingest_fn=ingest)
    try:
        return create_medium_app(store, llm, ApiConfig(allow_retained=True))
    finally:
        api.create_app = original


def _skeleton(store: Path, llm, ingest):
    return create_app(
        store=store,
        llm=llm,
        persona_dir=PERSONA_DIR,
        cfg=ApiConfig(allow_retained=True),
        ingest_fn=ingest,
    )


SCRIPTS = {
    "verified": [_reply(GOOD)],
    "banished_then_regenerated": [_reply(BAD), _reply(GOOD)],
    "declined": [_reply(BAD), _reply(BAD)],
}


@pytest.mark.parametrize("name", list(SCRIPTS))
def test_medium_equals_skeleton(name, make, tmp_path_factory) -> None:  # noqa: F811
    script = SCRIPTS[name]
    medium = _ask(_medium, make, tmp_path_factory, script)
    skeleton = _ask(_skeleton, make, tmp_path_factory, script)
    assert medium == skeleton


def test_verified_answer(make, tmp_path_factory) -> None:  # noqa: F811
    body = _ask(_medium, make, tmp_path_factory, SCRIPTS["verified"])
    assert body["status"] == "answered"
    assert body["claims"] and body["banishments"] == []


def test_banished_then_regenerated(make, tmp_path_factory) -> None:  # noqa: F811
    body = _ask(_medium, make, tmp_path_factory, SCRIPTS["banished_then_regenerated"])
    assert body["status"] == "answered"
    assert body["banishments"] and body["claims"]
    assert len(body["attempts"]) == 2


def test_decline_carries_ghost_line(make, tmp_path_factory) -> None:  # noqa: F811
    body = _ask(_medium, make, tmp_path_factory, SCRIPTS["declined"])
    assert body["status"] == "declined"
    assert body["claims"] == []
    assert body["decline_line"] == GHOST_DECLINE
