"""Grounded turn end to end: persona generator, router and verifier (R4.12, R4.13, R4.19, R3.7)."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from skeleton.ingest.models import CodeGraph, FileEntry, SnapshotMeta
from skeleton.ingest.snapshot import Snapshot
from skeleton.mcp.router import ToolRouter
from skeleton.mcp.tools import SignalTools
from skeleton.personas.generator import ToolLoopGenerator
from skeleton.personas.llm import FakeLLMClient, LLMResponse, ToolCall
from skeleton.personas.loader import Persona
from skeleton.personas.prompt import assemble_system_prompt
from skeleton.signals.models import Finding, FindingSet
from skeleton.signals.store import AnalysedSnapshot
from skeleton.verify.codes import ReasonCode
from skeleton.verify.flow import run_grounded_turn
from skeleton.verify.models import AnswerResult, VerifyConfig

SNAP_ID = "b" * 40
SOURCE = "def hot():\n    return 1\n# TODO fix\n"
FINDING_ID = "churn:a.py:1-3"
DECLINE = "The spirits will not speak of this."


@pytest.fixture
def analysed(tmp_path: Path) -> AnalysedSnapshot:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text(SOURCE, encoding="utf-8")
    meta = SnapshotMeta(
        snapshot_id=SNAP_ID,
        source="https://example.com/r.git",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=True,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
        file_count=1,
        total_bytes=len(SOURCE),
        pinned_commit_time=None,
    )
    entry = FileEntry(
        path="a.py",
        size_bytes=len(SOURCE),
        line_count=3,
        is_symlink=False,
        parsed=True,
        decodable=True,
        has_syntax_errors=False,
        history=None,
    )
    snap = Snapshot(tmp_path, meta, CodeGraph(files=[entry], symbols={}, imports={}))
    finding = Finding(
        analyzer="churn",
        file="a.py",
        line_start=1,
        line_end=3,
        evidence=SOURCE.rstrip("\n"),
        severity=0.5,
        metrics={"commits": 847},
    )
    return AnalysedSnapshot(snap, FindingSet(snapshot_id=SNAP_ID, findings=[finding], analyzers=[]))


def _persona() -> Persona:
    return Persona(
        name="ghost",
        display_name="Ghost",
        voice="spooky",
        goals=["haunt"],
        allowed_tools=["get_snapshot", "list_findings", "get_file_facts", "read_lines"],
        example_lines=["boo"],
        decline_line=DECLINE,
    )


def _answer(*claims: dict) -> str:
    return json.dumps({"claims": list(claims)})


def _cite(start: int = 1, end: int = 1, quote: str | None = "def hot():") -> dict:
    return {"file": "a.py", "line_start": start, "line_end": end, "quote": quote}


GOOD = _answer({"text": "This function is the hot spot.", "citations": [_cite()]})


def _turn(analysed: AnalysedSnapshot, script: list[LLMResponse]) -> tuple[AnswerResult, FakeLLMClient]:
    fake = FakeLLMClient(script)
    persona = _persona()
    gen = ToolLoopGenerator(
        fake,
        persona,
        ToolRouter(SignalTools(analysed), persona.allowed_tools),
        assemble_system_prompt(persona, analysed.snapshot.meta),
        "What is risky?",
    )
    result = asyncio.run(
        run_grounded_turn(analysed, gen, decline_line=persona.decline_line, cfg=VerifyConfig())
    )
    return result, fake


def test_good_answer_renders(analysed: AnalysedSnapshot) -> None:
    result, fake = _turn(analysed, [LLMResponse(text=GOOD)])
    assert result.status == "answered"
    assert [c.text for c in result.claims] == ["This function is the hot spot."]
    assert result.banishments == ()
    assert result.snapshot_id == SNAP_ID
    assert len(fake.requests) == 1


def test_fabricated_line_is_banished_then_regenerated(analysed: AnalysedSnapshot) -> None:
    bad = _answer({"text": "Look at the end.", "citations": [_cite(99, 99, None)]})
    result, fake = _turn(analysed, [LLMResponse(text=bad), LLMResponse(text=GOOD)])
    assert result.status == "answered"
    assert [b.reason for b in result.banishments] == [ReasonCode.RANGE_OUT_OF_BOUNDS]
    assert [b.attempt for b in result.banishments] == [1]
    assert len(result.claims) == 1 and result.claims[0].text == "This function is the hot spot."
    assert "range_out_of_bounds" in fake.requests[1].messages[-1].content


def test_prose_number_is_banished_as_unbacked(analysed: AnalysedSnapshot) -> None:
    bad = _answer({"text": "It changed 42 times.", "citations": [_cite()]})
    result, _ = _turn(analysed, [LLMResponse(text=bad), LLMResponse(text=GOOD)])
    assert result.status == "answered"
    assert [b.reason for b in result.banishments] == [ReasonCode.UNBACKED_NUMBER]
    assert result.banishments[0].target is not None
    assert result.banishments[0].target.token == "42"  # type: ignore[union-attr]


def test_two_failures_decline_with_persona_line(analysed: AnalysedSnapshot) -> None:
    bad1 = _answer({"text": "Nowhere.", "citations": [_cite(99, 99, None)]})
    bad2 = _answer({"text": "No cite."})
    result, fake = _turn(analysed, [LLMResponse(text=bad1), LLMResponse(text=bad2)])
    assert result.status == "declined"
    assert result.claims == ()
    assert result.decline_line == DECLINE
    assert [b.reason for b in result.banishments] == [
        ReasonCode.RANGE_OUT_OF_BOUNDS,
        ReasonCode.UNCITED_CLAIM,
    ]
    assert len(fake.requests) == 2


def test_tool_call_finding_id_is_accepted_in_a_figure(analysed: AnalysedSnapshot) -> None:
    call = ToolCall(id="c1", name="list_findings", arguments={})
    claim = {
        "text": "This file is churned heavily.",
        "citations": [_cite()],
        "figures": [{"finding_id": FINDING_ID, "key": "commits", "value": 847}],
    }
    result, fake = _turn(
        analysed, [LLMResponse(tool_calls=(call,)), LLMResponse(text=_answer(claim))]
    )
    tool_reply = json.loads(fake.requests[1].messages[-1].content)
    assert tool_reply["findings"][0]["id"] == FINDING_ID
    assert result.status == "answered"
    assert result.banishments == ()
    assert result.claims[0].figures[0].finding_id == FINDING_ID
