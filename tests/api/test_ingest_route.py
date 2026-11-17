"""Synchronous POST /snapshots (task 6.5): ingest + analyse inline, error mapping, timeout."""
import functools
import os
import stat
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skeleton.api.app import ApiConfig, create_app
from skeleton.ingest import ingest_url
from skeleton.ingest.models import IngestCode, IngestError
from skeleton.personas.llm import FakeLLMClient
from tests.fixtures.make_repo import FixtureRepo

URL = "https://example.com/owner/repo.git"
MIT = (
    "MIT License\n\nPermission is hereby granted, free of charge, to any person "
    "obtaining a copy of this software, to deal in the Software without restriction.\n"
)
PERSONA = """
name = "example"
display_name = "Example Ghost"
voice = "Dry."
goals = ["Cite facts"]
allowed_tools = ["list_findings"]
example_lines = ["It sleeps."]
decline_line = "Silent."
"""


def _public(_host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.fixture
def persona_dir(tmp_path: Path) -> Path:
    d = tmp_path / "personas"
    d.mkdir()
    (d / "example.toml").write_text(PERSONA, encoding="utf-8")
    return d


@pytest.fixture
def store(tmp_path: Path):
    store = tmp_path / "store"
    yield store
    for root, dirs, files in os.walk(store):
        for n in [*dirs, *files]:
            p = os.path.join(root, n)
            if not os.path.islink(p):
                os.chmod(p, os.lstat(p).st_mode | stat.S_IWUSR)


@pytest.fixture
def real_ingest(tmp_path: Path):
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
    return functools.partial(
        ingest_url, resolver=_public, git_bin=str(wrapper), _allow_protocols="file"
    )


def _client(store, persona_dir, ingest_fn, **cfg) -> TestClient:
    app = create_app(
        store=store,
        llm=FakeLLMClient([]),
        persona_dir=persona_dir,
        cfg=ApiConfig(**cfg),
        ingest_fn=ingest_fn,
    )
    return TestClient(app)


def test_ingest_then_read_routes(store, persona_dir, real_ingest) -> None:
    client = _client(store, persona_dir, real_ingest)
    r = client.post("/snapshots", json={"url": URL})
    assert r.status_code == 201
    body = r.json()
    ref, sid = body["ref"], body["snapshot_id"]
    assert len(sid) == 40 and ref != sid  # ephemeral ref is opaque, not the SHA

    meta = client.get(f"/snapshots/{ref}")
    assert meta.status_code == 200
    assert meta.json()["meta"]["snapshot_id"] == sid
    assert client.get(f"/snapshots/{ref}/findings").status_code == 200
    assert client.get(f"/snapshots/{ref}/files/a.py").json()["line_count"] == 3


def test_retained_refused_by_default(store, persona_dir, real_ingest) -> None:
    client = _client(store, persona_dir, real_ingest)
    r = client.post("/snapshots", json={"url": URL, "intent": "retained"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "retained_not_allowed"


def test_retained_ref_is_snapshot_id(store, persona_dir, real_ingest) -> None:
    client = _client(store, persona_dir, real_ingest, allow_retained=True)
    r = client.post("/snapshots", json={"url": URL, "intent": "retained"})
    assert r.status_code == 201
    body = r.json()
    assert body["ref"] == body["snapshot_id"]
    assert client.get(f"/snapshots/{body['ref']}").status_code == 200


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (IngestCode.invalid_source, 422),
        (IngestCode.unsafe_archive, 422),
        (IngestCode.ref_not_found, 404),
        (IngestCode.size_limit_exceeded, 413),
        (IngestCode.file_limit_exceeded, 413),
        (IngestCode.clone_timeout, 504),
        (IngestCode.licence_not_permitted, 403),
    ],
)
def test_ingest_code_maps_to_status(store, persona_dir, code, status) -> None:
    def boom(*_a, **_k):
        raise IngestError(code, "nope")

    client = _client(store, persona_dir, boom)
    r = client.post("/snapshots", json={"url": URL})
    assert r.status_code == status
    assert r.json()["error"] == {"code": code.value, "message": "nope"}


def test_route_honours_timeout(store, persona_dir) -> None:
    def slow(*_a, **_k):
        time.sleep(1.0)
        raise IngestError(IngestCode.invalid_source, "late")

    client = _client(store, persona_dir, slow, ingest_timeout_s=0.1)
    with client:  # keep one event loop so the abandoned worker thread is not joined
        start = time.monotonic()
        r = client.post("/snapshots", json={"url": URL})
        assert time.monotonic() - start < 0.9
    assert r.status_code == 504
    assert r.json()["error"]["code"] == "clone_timeout"
