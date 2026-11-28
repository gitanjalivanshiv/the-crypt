"""Ledger, plan and notice routes and the process entry (debt-collector R3, R4, R5)."""
import importlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from providers.errors import ProviderError
from skeleton.api.app import create_app
from skeleton.ingest.models import CodeGraph, FileEntry, SnapshotMeta
from skeleton.personas.llm import FakeLLMClient, LLMRequest, LLMResponse
from skeleton.personas.loader import load_personas
from skeleton.signals.models import AnalyzerStatus, Finding, FindingSet

interest = importlib.import_module("debt-collector.interest")
api = importlib.import_module("debt-collector.api")
main = importlib.import_module("debt-collector.main")
notice_mod = importlib.import_module("debt-collector.notice")

ROOT = Path(__file__).resolve().parents[2]
PERSONA_DIR = ROOT / "debt-collector" / "personas"
DECLINE = load_personas(PERSONA_DIR)["collector"].decline_line
SNAP_ID = "e" * 40
REF = "collector-ref-1"
FILE_LINES = 200


def _entry(path: str) -> FileEntry:
    return FileEntry(
        path=path,
        size_bytes=1,
        line_count=FILE_LINES,
        is_symlink=False,
        parsed=True,
        decodable=True,
        has_syntax_errors=False,
        history=None,
    )


def _finding(analyzer: str, file: str, start: int, end: int, severity: float, **metrics: float) -> Finding:
    return Finding(
        analyzer=analyzer,
        file=file,
        line_start=start,
        line_end=end,
        evidence=f"line {start}",
        severity=severity,
        metrics=metrics or {"age_days": 10},
    )


def _big_findings() -> list[Finding]:
    todo = [_finding("todo_age", "a.py", i, i, round(0.2 + (i % 7) * 0.1, 1), age_days=i) for i in range(1, 131)]
    churn = [
        _finding("churn", "a.py", 1, 20, 0.9, commit_count=80, author_count=4),
        _finding("churn", "b.py", 1, 40, 0.7, commit_count=50, author_count=3),
        _finding("churn", "b.py", 50, 52, 0.6, commit_count=30, author_count=2),
        _finding("churn", "a.py", 100, 110, 0.5, commit_count=20, author_count=2),
        _finding("churn", "a.py", 150, 150, 0.4, commit_count=15, author_count=1),
    ]
    stale = [
        _finding("staleness", "b.py", 100, 140, 0.8, commit_count=3, days_since_modified=2000),
        _finding("staleness", "a.py", 160, 170, 0.3, commit_count=2, days_since_modified=500),
        _finding("staleness", "b.py", 150, 150, 0.2, commit_count=2, days_since_modified=400),
        _finding("staleness", "a.py", 180, 190, 0.1, commit_count=1, days_since_modified=380),
    ]
    return todo + churn + stale


def make_store(root: Path, findings: list[Finding], analyzers: list[AnalyzerStatus]) -> Path:
    store = root / "store"
    snap = store / "ephemeral" / REF
    repo = snap / "repo"
    repo.mkdir(parents=True)
    for name in ("a.py", "b.py"):
        (repo / name).write_text("".join(f"line {n}\n" for n in range(1, FILE_LINES + 1)))
    graph = CodeGraph(files=[_entry("a.py"), _entry("b.py")], symbols={}, imports={})
    meta = SnapshotMeta(
        snapshot_id=SNAP_ID,
        source="s",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=True,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
        file_count=2,
        total_bytes=10,
        pinned_commit_time=None,
    )
    fs = FindingSet(snapshot_id=SNAP_ID, findings=findings, analyzers=analyzers)
    (snap / "meta.json").write_text(meta.model_dump_json(), encoding="utf-8")
    (snap / "graph.json").write_text(graph.model_dump_json(), encoding="utf-8")
    (snap / "findings.json").write_text(fs.model_dump_json(), encoding="utf-8")
    return store


OK = [AnalyzerStatus(name=n, state="ok") for n in ("churn", "staleness", "todo_age")]


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return make_store(tmp_path, _big_findings(), OK)


class Exploding:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        raise AssertionError("the model must not be called")


def _client(store: Path, llm: object | None = None) -> TestClient:
    return TestClient(api.create_collector_app(store=store, llm=llm or FakeLLMClient([])))


def _reply(*claims: dict) -> LLMResponse:
    return LLMResponse(text=json.dumps({"claims": list(claims)}))


GOOD = {"text": "This file has sat untouched.", "citations": [{"file": "a.py", "line_start": 1, "line_end": 1}]}


# ---- no model ----


def test_ledger_ranked_with_coverage_and_ids(store: Path) -> None:
    c = _client(store)
    r = c.get(f"/collector/snapshots/{REF}/ledger")
    assert r.status_code == 200
    body = r.json()
    lines = body["lines"]
    assert len(lines) == 130 + 5 + 4 - 30  # todo_age clamped to 100
    assert [x["rank"] for x in lines] == list(range(1, len(lines) + 1))
    keys = [(-x["interest"], -x["severity"], x["finding_id"]) for x in lines]
    assert keys == sorted(keys)
    cov = {x["analyzer"]: x for x in body["coverage"]}
    assert cov["todo_age"] == {"analyzer": "todo_age", "returned": 100, "matching": 130}
    assert cov["churn"]["returned"] == cov["churn"]["matching"] == 5
    assert cov["staleness"]["returned"] == cov["staleness"]["matching"] == 4
    assert body["truncated"] is True
    skeleton_ids = set()
    for name in cov:
        out = c.get(f"/snapshots/{REF}/findings", params={"analyzer": name, "limit": 100}).json()
        skeleton_ids |= {f["id"] for f in out["findings"]}
    assert {x["finding_id"] for x in lines} == skeleton_ids
    assert body["snapshot_id"] == SNAP_ID
    assert body["escalation"] in interest.LEVELS


def test_ledger_boss_flags_and_units(store: Path) -> None:
    lines = _client(store).get(f"/collector/snapshots/{REF}/ledger").json()["lines"]
    assert [x["rank"] for x in lines if x["boss"]] == [1, 2, 3]
    for line in lines:
        assert all(interest.metric_unit(k) != interest.UNSPECIFIED_UNIT for k in line["metrics"])
    assert all(interest.FIGURES[k].unit for k in ("principal", "interest"))


def test_complete_first_call_is_not_truncated(tmp_path: Path) -> None:
    findings = _big_findings()[130:]
    c = _client(make_store(tmp_path, findings, OK))
    body = c.get(f"/collector/snapshots/{REF}/ledger").json()
    assert body["truncated"] is False
    assert len(body["lines"]) == 9


def test_empty_snapshot_gives_empty_ledger(tmp_path: Path) -> None:
    c = _client(make_store(tmp_path, [], []))
    r = c.get(f"/collector/snapshots/{REF}/ledger")
    assert r.status_code == 200
    body = r.json()
    assert body["lines"] == [] and body["escalation"] == "courtesy" and body["truncated"] is False
    assert body["totals"] == {"principal": 0.0, "interest": 0.0, "severity": 0.0}
    assert c.get(f"/collector/snapshots/{REF}/plan").json()["entries"] == []


@pytest.mark.parametrize("route", ["ledger", "plan"])
def test_snapshot_not_found_returned_unchanged(store: Path, route: str) -> None:
    c = _client(store)
    r = c.get(f"/collector/snapshots/nope/{route}")
    direct = c.get("/snapshots/nope")
    assert r.status_code == direct.status_code == 404
    assert r.json() == direct.json()
    assert r.json()["error"]["code"] == "snapshot_not_found"
    assert "lines" not in r.json() and "entries" not in r.json()


def test_ledger_and_plan_make_no_model_call(store: Path) -> None:  # CP8
    llm = Exploding()
    c = _client(store, llm)
    assert c.get(f"/collector/snapshots/{REF}/ledger").status_code == 200
    assert c.get(f"/collector/snapshots/{REF}/plan").status_code == 200
    assert llm.calls == 0


def test_plan_matches_ledger_and_is_ordered(store: Path) -> None:  # CP6
    c = _client(store)
    ledger = c.get(f"/collector/snapshots/{REF}/ledger").json()
    plan = c.get(f"/collector/snapshots/{REF}/plan").json()
    entries = plan["entries"]
    assert {x["finding_id"] for x in entries} == {x["finding_id"] for x in ledger["lines"]}
    by_id = {x["finding_id"]: x for x in ledger["lines"]}
    assert all(by_id[e["finding_id"]]["interest"] == e["interest"] for e in entries)
    assert all(by_id[e["finding_id"]]["boss"] == e["boss"] for e in entries)
    ratios = [e["interest_per_effort"] for e in entries]
    assert ratios == sorted(ratios, reverse=True)
    assert [e["rank"] for e in entries] == list(range(1, len(entries) + 1))


def test_plan_sources_resolve(store: Path) -> None:  # CP7
    c = _client(store)
    entries = c.get(f"/collector/snapshots/{REF}/plan").json()["entries"]
    assert entries
    for e in entries:
        s = e["source"]
        r = c.get(
            f"/snapshots/{REF}/files/{s['file']}",
            params={"line_start": s["line_start"], "line_end": s["line_end"]},
        )
        assert r.status_code == 200, (e, r.text)


def test_build_app_with_empty_environment(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for var in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    c = TestClient(main.build_app(env={"CRYPT_STORE": str(store)}))
    assert c.get(f"/collector/snapshots/{REF}/ledger").status_code == 200
    assert c.get(f"/collector/snapshots/{REF}/plan").status_code == 200


def test_build_app_translates_collector_variables(tmp_path: Path) -> None:
    seen: list[str | None] = []

    def factory(model: str | None) -> FakeLLMClient:
        seen.append(model)
        return FakeLLMClient([])

    main.build_app(
        env={
            "COLLECTOR_PROVIDER": "anthropic",
            "COLLECTOR_MODEL": "m-x",
            "MEDIUM_MODEL": "ignored",
            "CRYPT_STORE": str(tmp_path),
        },
        client_factory=factory,
    )
    assert seen == ["m-x"]


def test_offline_client_raises_provider_error() -> None:
    import asyncio

    with pytest.raises(ProviderError):
        asyncio.run(main.OfflineClient().complete(LLMRequest(system="s", messages=())))


# ---- FakeLLMClient ----


def _ask_app(store: Path, script: list[LLMResponse]):
    llm = FakeLLMClient(script)
    app = create_app(store=store, llm=llm, persona_dir=PERSONA_DIR)
    return TestClient(app), llm


def test_notice_equals_skeleton_ask(store: Path) -> None:  # CP9
    script = [_reply(GOOD)]
    c = _client(store, FakeLLMClient(script))
    level = c.get(f"/collector/snapshots/{REF}/ledger").json()["escalation"]
    r = c.post(f"/collector/snapshots/{REF}/notice")
    direct, _ = _ask_app(store, script)
    expected = direct.post(
        f"/snapshots/{REF}/ask",
        json={"persona": "collector", "question": notice_mod.notice_question(level)},
    )
    assert r.status_code == expected.status_code == 200
    assert r.content == expected.content
    assert r.json()["status"] == "answered"


def test_notice_question_has_no_digit_and_names_level(store: Path) -> None:  # CP11
    llm = FakeLLMClient([_reply(GOOD)])
    c = _client(store, llm)
    level = c.get(f"/collector/snapshots/{REF}/ledger").json()["escalation"]
    c.post(f"/collector/snapshots/{REF}/notice")
    user_texts = [m.content for m in llm.requests[0].messages if m.role == "user"]
    question = next(t for t in user_texts if "notice" in t)
    assert not re.search(r"\d", question)
    assert level in question
    assert question == notice_mod.notice_question(level)


def test_claim_repeating_computed_interest_is_banished(store: Path) -> None:  # CP10
    c = _client(store, FakeLLMClient([]))
    top = c.get(f"/collector/snapshots/{REF}/ledger").json()["lines"][0]
    bad = {
        "text": f"The largest debt costs {top['interest']} lines per year.",
        "citations": [{"file": top["file"], "line_start": top["line_start"], "line_end": top["line_end"]}],
    }
    c = _client(store, FakeLLMClient([_reply(bad), _reply(bad)]))
    body = c.post(f"/collector/snapshots/{REF}/notice").json()
    assert body["status"] == "declined"
    assert {b["reason"] for b in body["banishments"]} == {"unbacked_number"}


def test_notice_without_provider_declines(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    c = TestClient(main.build_app(env={"CRYPT_STORE": str(store)}))
    r = c.post(f"/collector/snapshots/{REF}/notice")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "declined" and body["decline_line"] == DECLINE
    assert c.get(f"/collector/snapshots/{REF}/ledger").status_code == 200


def test_notice_snapshot_not_found_unchanged(store: Path) -> None:
    llm = FakeLLMClient([])
    c = _client(store, llm)
    r = c.post("/collector/snapshots/nope/notice")
    direct = c.get("/snapshots/nope")
    assert r.status_code == direct.status_code == 404
    assert r.json() == direct.json()
    assert llm.requests == []


# ---- source greps ----


def test_api_source_constructs_no_claims_or_prompts() -> None:
    src = (ROOT / "debt-collector" / "api.py").read_text()
    for banned in ("AnswerResult(", "VerifiedClaim(", "Citation(", "LLMRequest", "assemble_system_prompt"):
        assert banned not in src


def test_collector_never_imports_medium() -> None:
    for path in (ROOT / "debt-collector").glob("*.py"):
        assert not re.search(r"^\s*(import|from)\s+medium\b", path.read_text(), re.MULTILINE), path
