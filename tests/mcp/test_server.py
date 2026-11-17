"""The stdio server, run as a real subprocess over the MCP SDK client."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from skeleton.ingest.models import CodeGraph, FileEntry, SnapshotMeta
from skeleton.mcp.contract import TOOL_NAMES, build_contract
from skeleton.signals.models import FindingSet

ROOT = Path(__file__).resolve().parents[2]
SNAP_ID = "c" * 40


@pytest.fixture
def snapshot_dir(tmp_path: Path) -> Path:
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / "a.py").write_text("one\ntwo\n")
    graph = CodeGraph(
        files=[
            FileEntry(
                path="a.py",
                size_bytes=8,
                line_count=2,
                is_symlink=False,
                parsed=True,
                decodable=True,
                has_syntax_errors=False,
                history=None,
            )
        ],
        symbols={},
        imports={},
    )
    meta = SnapshotMeta(
        snapshot_id=SNAP_ID,
        source="s",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=False,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
        file_count=1,
        total_bytes=8,
        pinned_commit_time=None,
    )
    (tmp_path / "meta.json").write_text(meta.model_dump_json())
    (tmp_path / "graph.json").write_text(graph.model_dump_json())
    (tmp_path / "findings.json").write_text(
        FindingSet(snapshot_id=SNAP_ID, findings=[], analyzers=[]).model_dump_json()
    )
    return tmp_path


def _params(args: list[str], env: dict[str, str] | None = None) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "skeleton.mcp.server", *args],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT), **(env or {})},
    )


async def _list_tools(params: StdioServerParameters):  # type: ignore[no-untyped-def]
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return (await session.list_tools()).tools


def list_tools(params: StdioServerParameters):  # type: ignore[no-untyped-def]
    return anyio.run(_list_tools, params)


def test_tools_list_matches_contract(snapshot_dir: Path) -> None:
    tools = {t.name: t for t in list_tools(_params(["--snapshot", str(snapshot_dir)]))}
    contract = build_contract()["tools"]
    assert set(tools) == set(contract) == TOOL_NAMES  # type: ignore[arg-type]
    for name, tool in tools.items():
        assert tool.inputSchema == contract[name]["input_schema"]  # type: ignore[index]
        assert tool.description == contract[name]["description"]  # type: ignore[index]


def test_snapshot_from_env_and_allow_hides_tools(snapshot_dir: Path) -> None:
    params = _params(["--allow", "read_lines, get_snapshot,bogus"], {"CRYPT_SNAPSHOT": str(snapshot_dir)})
    assert sorted(t.name for t in list_tools(params)) == ["get_snapshot", "read_lines"]


def test_tool_call_delegates_and_disallowed_is_error(snapshot_dir: Path) -> None:
    async def run() -> tuple[dict, dict]:  # type: ignore[type-arg]
        params = _params(["--snapshot", str(snapshot_dir), "--allow", "read_lines"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                ok = await session.call_tool(
                    "read_lines", {"file": "a.py", "line_start": 1, "line_end": 2}
                )
                bad = await session.call_tool("get_snapshot", {})
                return (
                    json.loads(ok.content[0].text),  # type: ignore[union-attr]
                    json.loads(bad.content[0].text),  # type: ignore[union-attr]
                )

    ok, bad = anyio.run(run)
    assert ok["lines"] == ["one", "two"]
    assert bad["error"]["code"] == "tool_not_allowed"


def test_missing_snapshot_exits_nonzero() -> None:
    env = {k: v for k, v in os.environ.items() if k != "CRYPT_SNAPSHOT"}
    proc = subprocess.run(
        [sys.executable, "-m", "skeleton.mcp.server"],
        cwd=ROOT,
        env={**env, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode != 0
    assert "CRYPT_SNAPSHOT" in proc.stderr and "--snapshot" in proc.stderr


def test_bad_snapshot_path_exits_nonzero(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "skeleton.mcp.server", "--snapshot", str(tmp_path / "nope")],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode != 0
    assert "error" in proc.stderr


def test_mcp_json_matches_entry_point() -> None:
    cfg = json.loads((ROOT / ".kiro" / "settings" / "mcp.json").read_text())
    entry = cfg["mcpServers"]["crypt-signals"]
    assert set(entry["autoApprove"]) <= TOOL_NAMES
    args = entry["args"]
    assert args[args.index("-m") + 1] == "skeleton.mcp.server"
    assert "--snapshot" in args and args[args.index("--snapshot") + 1]
