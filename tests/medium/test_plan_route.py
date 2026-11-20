"""Plan route (medium R6.1 to R6.6, R4.7): MP4 and MP5 with a scripted fake provider."""
import functools
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from medium.api import create_medium_app
from medium.plan import SECTION_QUESTIONS, SECTIONS
from skeleton.api.app import ApiConfig, create_app
from skeleton.ingest import ingest_url
from skeleton.personas.llm import FakeLLMClient, LLMResponse
from tests.fixtures.make_repo import FixtureRepo

URL = "https://example.com/owner/repo.git"
MIT = (
    "MIT License\n\nPermission is hereby granted, free of charge, to any person "
    "obtaining a copy of this software, to deal in the Software without restriction.\n"
)
GOOD = {"text": "It sleeps here.", "citations": [{"file": "a.py", "line_start": 1, "line_end": 1}]}
BAD = {"text": "It never existed.", "citations": [{"file": "nope.py", "line_start": 1, "line_end": 1}]}


def _reply(*claims: dict) -> LLMResponse:
    return LLMResponse(text=json.dumps({"claims": list(claims)}))


@pytest.fixture
def make(tmp_path: Path):
    repo = FixtureRepo(tmp_path / "src")
    repo.commit(
        {"LICENSE": MIT, "a.py": "# TODO: fix\ndef f():\n    pass\n"},
        date="2024-01-01T00:00:00+0000",
    )
    wrapper = tmp_path / "git-wrapper.sh"
    wrapper.write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        f'  if [ "$a" = "{URL}" ]; then a="{repo.path}"; fi\n'
        '  set -- "$@" "$a"; shift\n'
        "done\n"
        'exec git "$@"\n'
    )
    wrapper.chmod(0o755)
    ingest = functools.partial(
        ingest_url,
        resolver=lambda _h: ["93.184.216.34"],
        git_bin=str(wrapper),
        _allow_protocols="file",
    )
    return ingest, repo


def _client_with_snapshot(make, monkeypatch, tmp_path_factory, script):
    ingest, repo = make
    # create_medium_app has no ingest seam; hand the skeleton factory the fixture ingest.
    monkeypatch.setattr("medium.api.create_app", functools.partial(create_app, ingest_fn=ingest))
    llm = FakeLLMClient(script)
    app = create_medium_app(tmp_path_factory.mktemp("store"), llm, ApiConfig(allow_retained=True))
    client = TestClient(app)
    r = client.post("/snapshots", json={"url": URL, "sha": repo.head(), "intent": "retained"})
    assert r.status_code == 201, r.text
    return client, r.json()["ref"], llm


def _ask(client: TestClient, ref: str) -> list[dict]:
    return [
        client.post(
            f"/snapshots/{ref}/ask", json={"persona": "ghost", "question": SECTION_QUESTIONS[s]}
        ).json()
        for s in SECTIONS
    ]


def test_each_section_equals_direct_ask(make, monkeypatch, tmp_path_factory) -> None:  # MP4
    script = [_reply(GOOD), _reply(GOOD), _reply(GOOD)]
    client, ref, _ = _client_with_snapshot(make, monkeypatch, tmp_path_factory, script)
    plan = client.post(f"/medium/snapshots/{ref}/plan")
    assert plan.status_code == 200
    body = plan.json()
    assert [s["section"] for s in body["sections"]] == list(SECTIONS)
    direct_client, dref, _ = _client_with_snapshot(make, monkeypatch, tmp_path_factory, script)
    direct = _ask(direct_client, dref)
    for section, expected in zip(body["sections"], direct, strict=True):
        assert section["result"] == expected
    assert body["snapshot_id"] == direct[0]["snapshot_id"]


def test_fabricated_citation_never_verified(make, monkeypatch, tmp_path_factory) -> None:  # MP5
    client, ref, _ = _client_with_snapshot(make, monkeypatch, tmp_path_factory, [_reply(BAD), _reply(BAD), _reply(GOOD), _reply(GOOD), _reply(GOOD)])
    body = client.post(f"/medium/snapshots/{ref}/plan").json()
    first = body["sections"][0]["result"]
    assert first["status"] == "declined"
    assert first["banishments"] and first["claims"] == []
    for section in body["sections"]:
        for claim in section["result"]["claims"]:
            assert all(c["file"] != "nope.py" for c in claim["citations"])


def test_declined_section_leaves_others_intact(make, monkeypatch, tmp_path_factory) -> None:
    script = [_reply(GOOD), _reply(BAD), _reply(BAD), _reply(GOOD)]
    client, ref, _ = _client_with_snapshot(make, monkeypatch, tmp_path_factory, script)
    body = client.post(f"/medium/snapshots/{ref}/plan").json()
    statuses = [s["result"]["status"] for s in body["sections"]]
    assert statuses == ["answered", "declined", "answered"]
    assert body["sections"][1]["result"]["claims"] == []


def test_snapshot_not_found_returned_unchanged(make, monkeypatch, tmp_path_factory) -> None:
    client, _, llm = _client_with_snapshot(make, monkeypatch, tmp_path_factory, [])
    r = client.post("/medium/snapshots/nope/plan")
    direct = client.post("/snapshots/nope/ask", json={"persona": "ghost", "question": "Why?"})
    assert r.status_code == direct.status_code == 404
    assert r.json() == direct.json()
    assert r.json()["error"]["code"] == "snapshot_not_found"
    assert "sections" not in r.json()
    assert llm.requests == []


def test_route_source_constructs_no_claims() -> None:
    src = (Path(__file__).resolve().parents[2] / "medium" / "api.py").read_text()
    for banned in ("AnswerResult(", "VerifiedClaim(", "Citation("):
        assert banned not in src
