"""API app factory and read routes against a fixture snapshot on disk."""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skeleton.api.app import ApiConfig, create_app
from skeleton.ingest.models import CodeGraph, FileEntry, SnapshotMeta
from skeleton.personas.llm import FakeLLMClient
from skeleton.personas.loader import PersonaError
from skeleton.signals.models import AnalyzerStatus, Finding, FindingSet

SNAP_ID = "c" * 40
REF = "ephemeral-ref-1"

PERSONA = """
name = "example"
display_name = "Example Ghost"
voice = "Dry."
goals = ["Cite facts"]
allowed_tools = ["list_findings"]
example_lines = ["It sleeps."]
decline_line = "Silent."
"""


def _entry(path: str, lines: int, symlink: bool = False) -> FileEntry:
    return FileEntry(
        path=path,
        size_bytes=1,
        line_count=lines,
        is_symlink=symlink,
        parsed=True,
        decodable=True,
        has_syntax_errors=False,
        history=None,
    )


@pytest.fixture
def persona_dir(tmp_path: Path) -> Path:
    d = tmp_path / "personas"
    d.mkdir()
    (d / "example.toml").write_text(PERSONA, encoding="utf-8")
    return d


@pytest.fixture
def store(tmp_path: Path) -> Path:
    store = tmp_path / "store"
    snap = store / "ephemeral" / REF
    repo = snap / "repo"
    repo.mkdir(parents=True)
    (repo / "a.py").write_text("one\ntwo\nthree\n")
    os.symlink("a.py", repo / "link.py")
    graph = CodeGraph(
        files=[_entry("a.py", 3), _entry("link.py", 3, symlink=True)], symbols={}, imports={}
    )
    meta = SnapshotMeta(
        snapshot_id=SNAP_ID,
        source="s",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=False,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
        file_count=2,
        total_bytes=10,
        pinned_commit_time=None,
    )
    findings = FindingSet(
        snapshot_id=SNAP_ID,
        findings=[
            Finding(
                analyzer="todo_age",
                file="a.py",
                line_start=1,
                line_end=1,
                evidence="one",
                severity=0.5,
                metrics={"age_days": 10},
            )
        ],
        analyzers=[AnalyzerStatus(name="churn", state="skipped", reason="history_unavailable")],
    )
    (snap / "meta.json").write_text(meta.model_dump_json(), encoding="utf-8")
    (snap / "graph.json").write_text(graph.model_dump_json(), encoding="utf-8")
    (snap / "findings.json").write_text(findings.model_dump_json(), encoding="utf-8")
    return store


@pytest.fixture
def client(store: Path, persona_dir: Path) -> TestClient:
    return TestClient(
        create_app(store=store, llm=FakeLLMClient([]), persona_dir=persona_dir, cfg=ApiConfig())
    )


def test_get_snapshot(client: TestClient) -> None:
    r = client.get(f"/snapshots/{REF}")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["snapshot_id"] == SNAP_ID and body["meta"]["licence"] == "MIT"
    assert body["analyzers"][0]["state"] == "skipped"


def test_findings(client: TestClient) -> None:
    r = client.get(f"/snapshots/{REF}/findings", params={"analyzer": "todo_age"})
    assert r.status_code == 200
    body = r.json()
    assert body["snapshot_id"] == SNAP_ID
    assert body["findings"][0]["id"] == "todo_age:a.py:1-1"
    assert body["analyzers"]


def test_findings_invalid_argument(client: TestClient) -> None:
    r = client.get(f"/snapshots/{REF}/findings", params={"limit": 0})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_argument"


def test_file_facts(client: TestClient) -> None:
    r = client.get(f"/snapshots/{REF}/files/a.py")
    assert r.status_code == 200
    assert r.json()["line_count"] == 3


def test_file_lines_range(client: TestClient) -> None:
    r = client.get(f"/snapshots/{REF}/files/a.py", params={"line_start": 2, "line_end": 3})
    assert r.status_code == 200
    assert r.json()["lines"] == ["two", "three"]


@pytest.mark.parametrize(
    ("path", "params", "code", "status"),
    [
        ("nope.py", {}, "file_not_found", 404),
        ("link.py", {}, "symlink", 403),
        ("a%5Cb.py", {}, "path_unsafe", 400),
        ("%2e%2e/etc/passwd", {}, "path_unsafe", 400),
        ("a.py", {"line_start": 3, "line_end": 2}, "range_invalid", 400),
        ("a.py", {"line_start": 0, "line_end": 2}, "range_invalid", 400),
        ("a.py", {"line_start": 1, "line_end": 99}, "range_out_of_bounds", 400),
    ],
)
def test_verifier_codes_map_to_status(
    client: TestClient, path: str, params: dict[str, int], code: str, status: int
) -> None:
    r = client.get(f"/snapshots/{REF}/files/{path}", params=params)
    assert r.status_code == status
    assert r.json()["error"]["code"] == code


def test_half_range_is_malformed(client: TestClient) -> None:
    r = client.get(f"/snapshots/{REF}/files/a.py", params={"line_start": 1})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "malformed"


@pytest.mark.parametrize(
    "url",
    [
        "/snapshots/unknown",
        "/snapshots/unknown/findings",
        "/snapshots/unknown/files/a.py",
        "/snapshots/..%2F..%2Fetc",
    ],
)
def test_unknown_ref_is_snapshot_not_found(client: TestClient, url: str) -> None:
    r = client.get(url)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "snapshot_not_found"


def test_retained_ref_resolves(store: Path, persona_dir: Path) -> None:
    (store / "retained").mkdir()
    (store / "ephemeral" / REF).rename(store / "retained" / ("d" * 40))
    c = TestClient(create_app(store=store, llm=FakeLLMClient([]), persona_dir=persona_dir))
    assert c.get(f"/snapshots/{'d' * 40}").status_code == 200


def test_bad_persona_fails_startup(store: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "x.toml").write_text("name = ", encoding="utf-8")
    with pytest.raises(PersonaError):
        create_app(store=store, llm=FakeLLMClient([]), persona_dir=bad, cfg=ApiConfig())


def test_no_default_persona(client: TestClient) -> None:
    assert set(client.app.state.personas) == {"example"}  # type: ignore[attr-defined]


def test_app_reads_no_environment() -> None:
    src = (Path(__file__).parents[2] / "skeleton" / "api" / "app.py").read_text()
    assert "os.environ" not in src and "getenv" not in src
