"""Retention and refs: ephemeral refs, TTL sweep, DELETE, retained gate (design 10.3)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skeleton.api.app import ApiConfig, create_app
from skeleton.api.retention import RetainedNotAllowed, Retention, resolve_intent
from skeleton.ingest.models import CodeGraph, SnapshotMeta
from skeleton.personas.llm import FakeLLMClient
from skeleton.signals.models import FindingSet

SNAP_ID = "e" * 40

PERSONA = """
name = "example"
display_name = "Example Ghost"
voice = "Dry."
goals = ["Cite facts"]
allowed_tools = ["list_findings"]
example_lines = ["It sleeps."]
decline_line = "Silent."
"""


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _write_snapshot(directory: Path, licence: str = "GPL-3.0-only") -> None:
    directory.mkdir(parents=True)
    meta = SnapshotMeta(
        snapshot_id=SNAP_ID,
        source="s",
        licence=licence,
        retainable=False,
        intent="ephemeral",
        history_available=False,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
        file_count=0,
        total_bytes=0,
        pinned_commit_time=None,
    )
    (directory / "meta.json").write_text(meta.model_dump_json(), encoding="utf-8")
    (directory / "graph.json").write_text(
        CodeGraph(files=[], symbols={}, imports={}).model_dump_json(), encoding="utf-8"
    )
    (directory / "findings.json").write_text(
        FindingSet(snapshot_id=SNAP_ID, findings=[], analyzers=[]).model_dump_json(),
        encoding="utf-8",
    )


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "store"


@pytest.fixture
def retention(store: Path, clock: Clock) -> Retention:
    return Retention(store, ttl_s=3600, clock=clock)


@pytest.fixture
def client(store: Path, tmp_path: Path, clock: Clock) -> TestClient:
    personas = tmp_path / "personas"
    personas.mkdir()
    (personas / "example.toml").write_text(PERSONA, encoding="utf-8")
    app = create_app(
        store=store, llm=FakeLLMClient([]), persona_dir=personas, cfg=ApiConfig(), clock=clock
    )

    @app.get("/_intent")
    def _intent(intent: str | None = None) -> dict[str, str]:
        return {"intent": resolve_intent(intent, allow_retained=app.state.cfg.allow_retained)}

    return TestClient(app)


def test_same_repo_requests_get_different_refs(retention: Retention) -> None:
    a, b = retention.new_ephemeral_ref(), retention.new_ephemeral_ref()
    assert a != b
    assert len(a) >= 22


def test_retained_ref_is_snapshot_id() -> None:
    assert Retention.retained_ref(SNAP_ID) == SNAP_ID


def test_ttl_sweep_deletes_directory(retention: Retention, clock: Clock) -> None:
    ref = retention.new_ephemeral_ref()
    _write_snapshot(retention.ephemeral_dir(ref))
    clock.now = 3599
    assert retention.sweep() == []
    assert retention.ephemeral_dir(ref).is_dir()
    clock.now = 3600
    assert retention.sweep() == [ref]
    assert not retention.ephemeral_dir(ref).exists()


def test_lazy_sweep_on_request(client: TestClient, store: Path, clock: Clock) -> None:
    retention: Retention = client.app.state.retention  # type: ignore[attr-defined]
    ref = retention.new_ephemeral_ref()
    _write_snapshot(store / "ephemeral" / ref)
    assert client.get(f"/snapshots/{ref}").status_code == 200
    clock.now = 4000
    r = client.get(f"/snapshots/{ref}")
    assert r.status_code == 404
    assert not (store / "ephemeral" / ref).exists()


def test_delete_route(client: TestClient, store: Path) -> None:
    retention: Retention = client.app.state.retention  # type: ignore[attr-defined]
    ref = retention.new_ephemeral_ref()
    _write_snapshot(store / "ephemeral" / ref)
    assert client.delete(f"/snapshots/{ref}").status_code == 204
    assert not (store / "ephemeral" / ref).exists()
    r = client.delete(f"/snapshots/{ref}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "snapshot_not_found"


def test_delete_does_not_touch_retained(client: TestClient, store: Path) -> None:
    _write_snapshot(store / "retained" / SNAP_ID)
    assert client.delete(f"/snapshots/{SNAP_ID}").status_code == 404
    assert (store / "retained" / SNAP_ID).is_dir()


def test_retained_refused_by_default(client: TestClient) -> None:
    r = client.get("/_intent", params={"intent": "retained"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "retained_not_allowed"


def test_default_intent_is_ephemeral(client: TestClient) -> None:
    assert client.get("/_intent").json() == {"intent": "ephemeral"}


def test_retained_allowed_when_configured() -> None:
    assert resolve_intent("retained", allow_retained=True) == "retained"
    with pytest.raises(RetainedNotAllowed):
        resolve_intent("retained", allow_retained=False)


def test_ephemeral_snapshot_shows_licence(client: TestClient, store: Path) -> None:
    retention: Retention = client.app.state.retention  # type: ignore[attr-defined]
    ref = retention.new_ephemeral_ref()
    _write_snapshot(store / "ephemeral" / ref, licence="GPL-3.0-only")
    meta = client.get(f"/snapshots/{ref}").json()["meta"]
    assert meta["licence"] == "GPL-3.0-only"
    assert meta["retainable"] is False


def test_shutdown_removes_ephemeral(store: Path, tmp_path: Path, clock: Clock) -> None:
    personas = tmp_path / "personas"
    personas.mkdir()
    (personas / "example.toml").write_text(PERSONA, encoding="utf-8")
    _write_snapshot(store / "ephemeral" / "abc")
    _write_snapshot(store / "retained" / SNAP_ID)
    app = create_app(store=store, llm=FakeLLMClient([]), persona_dir=personas, clock=clock)
    with TestClient(app):
        assert (store / "ephemeral" / "abc").is_dir()
    assert not (store / "ephemeral" / "abc").exists()
    assert (store / "retained" / SNAP_ID).is_dir()
