"""ToolLoopGenerator behaviour (R4.12, R5.6)."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from skeleton.ingest.models import CodeGraph, SnapshotMeta
from skeleton.ingest.snapshot import Snapshot
from skeleton.mcp.router import ToolRouter
from skeleton.mcp.tools import SignalTools
from skeleton.personas.generator import MAX_TOOL_ROUNDS, ToolLoopGenerator
from skeleton.personas.llm import FakeLLMClient, LLMResponse, ToolCall
from skeleton.personas.loader import Persona
from skeleton.signals.models import FindingSet
from skeleton.signals.store import AnalysedSnapshot
from skeleton.verify.codes import ReasonCode
from skeleton.verify.flow import AttemptFailure
from skeleton.verify.models import Banishment

SNAP_ID = "a" * 40


def _router(allowed: list[str] | None = None) -> ToolRouter:
    meta = SnapshotMeta(
        snapshot_id=SNAP_ID,
        source="https://example.com/r.git",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=True,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
        file_count=0,
        total_bytes=0,
        pinned_commit_time=None,
    )
    snap = Snapshot(Path("."), meta, CodeGraph(files=[], symbols={}, imports={}))
    findings = FindingSet(snapshot_id=SNAP_ID, findings=[], analyzers=[])
    return ToolRouter(SignalTools(AnalysedSnapshot(snap, findings)), allowed)


def _persona(tools: list[str]) -> Persona:
    return Persona(
        name="ghost",
        display_name="Ghost",
        voice="spooky",
        goals=["haunt"],
        allowed_tools=tools,
        example_lines=["boo"],
        decline_line="nothing to see",
    )


def _call(i: int, name: str = "get_snapshot") -> ToolCall:
    return ToolCall(id=f"c{i}", name=name, arguments={})


def _gen(fake: FakeLLMClient, tools: list[str], router: ToolRouter | None = None):
    return ToolLoopGenerator(fake, _persona(tools), router or _router(), "SYS", "Q?")


def test_returns_final_text_unchanged() -> None:
    text = '  {"claims": []}\n'
    fake = FakeLLMClient([LLMResponse(text=text)])
    assert asyncio.run(_gen(fake, ["get_snapshot"])(1, None)) == text
    assert fake.requests[0].system == "SYS"
    assert fake.requests[0].messages[0].content == "Q?"
    assert [t.name for t in fake.requests[0].tools] == ["get_snapshot"]


def test_tool_result_is_fed_back() -> None:
    fake = FakeLLMClient([LLMResponse(tool_calls=(_call(1),)), LLMResponse(text="done")])
    assert asyncio.run(_gen(fake, ["get_snapshot"])(1, None)) == "done"
    last = fake.requests[1].messages[-1]
    assert last.role == "tool" and last.tool_call_id == "c1"
    assert json.loads(last.content)["snapshot_id"] == SNAP_ID


def test_tool_round_cap() -> None:
    script = [LLMResponse(tool_calls=(_call(i),)) for i in range(MAX_TOOL_ROUNDS + 1)]
    script[-1] = LLMResponse(text="forced", tool_calls=(_call(99),))
    fake = FakeLLMClient(script)
    assert asyncio.run(_gen(fake, ["get_snapshot"])(1, None)) == "forced"
    assert len(fake.requests) == MAX_TOOL_ROUNDS + 1
    assert fake.requests[-1].tools == ()
    executed = [m for m in fake.requests[-1].messages if m.role == "tool"]
    assert len(executed) == MAX_TOOL_ROUNDS


def test_disallowed_tool_returns_tool_not_allowed_even_if_router_permits() -> None:
    fake = FakeLLMClient(
        [LLMResponse(tool_calls=(_call(1, "list_findings"),)), LLMResponse(text="ok")]
    )
    gen = _gen(fake, ["get_snapshot"], _router(None))
    assert asyncio.run(gen(1, None)) == "ok"
    reply = json.loads(fake.requests[1].messages[-1].content)
    assert reply["error"]["code"] == "tool_not_allowed"


def test_disallowed_tool_rejected_by_router_too() -> None:
    fake = FakeLLMClient([LLMResponse(tool_calls=(_call(1),)), LLMResponse(text="ok")])
    gen = _gen(fake, ["get_snapshot", "list_findings"], _router(["list_findings"]))
    asyncio.run(gen(1, None))
    assert [t.name for t in fake.requests[0].tools] == ["list_findings"]
    reply = json.loads(fake.requests[1].messages[-1].content)
    assert reply["error"]["code"] == "tool_not_allowed"


def test_attempt_two_includes_rendered_rejections() -> None:
    ban = Banishment(
        claim_text="c",
        reason=ReasonCode.UNCITED_CLAIM,
        message="claim has no citation",
        attempt=1,
        snapshot_id=SNAP_ID,
    )
    fake = FakeLLMClient([LLMResponse(text="a"), LLMResponse(text="b")])
    gen = _gen(fake, [])
    asyncio.run(gen(1, None))
    asyncio.run(gen(2, [ban]))
    assert len(fake.requests[0].messages) == 1
    fb = fake.requests[1].messages[-1].content
    assert "These claims were rejected" in fb
    assert "uncited_claim: claim has no citation" in fb


def test_attempt_two_after_failure_renders_failure() -> None:
    fake = FakeLLMClient([LLMResponse(text="b")])
    asyncio.run(_gen(fake, [])(2, AttemptFailure("unparseable", "bad json")))
    assert "unparseable" in fake.requests[0].messages[-1].content
