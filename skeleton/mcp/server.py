"""Stdio MCP server (R5.1, R5.6, R5.8).

``python -m skeleton.mcp.server --snapshot <dir> [--allow a,b]``. The snapshot may instead come
from the ``CRYPT_SNAPSHOT`` environment variable. All behaviour is delegated to ``ToolRouter``
and ``SignalTools``; this module only adapts them to the MCP SDK.
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from skeleton.mcp.contract import (
    INPUT_MODELS,
    TOOL_DESCRIPTIONS,
    TOOL_NAMES,
)
from skeleton.mcp.router import ToolRouter
from skeleton.mcp.tools import SignalTools
from skeleton.signals.store import AnalysedSnapshot

ENV_SNAPSHOT = "CRYPT_SNAPSHOT"
SERVER_NAME = "crypt-signals"


def build_server(router: ToolRouter) -> Server:
    """Build an MCP server exposing only the tools the router allows."""
    server: Server = Server(SERVER_NAME)

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=name,
                description=TOOL_DESCRIPTIONS[name],
                inputSchema=INPUT_MODELS[name].model_json_schema(),
            )
            for name in router.tool_names
        ]

    @server.call_tool(validate_input=False)  # type: ignore[untyped-decorator]
    async def _call_tool(name: str, arguments: dict[str, object] | None) -> list[types.TextContent]:
        result = router.call(name, arguments)
        payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        return [types.TextContent(type="text", text=json.dumps(payload, sort_keys=True))]

    return server


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m skeleton.mcp.server", description=__doc__)
    parser.add_argument("--snapshot", help=f"snapshot directory (or set {ENV_SNAPSHOT})")
    parser.add_argument(
        "--allow",
        help=f"comma-separated tools to expose (default: all of {', '.join(sorted(TOOL_NAMES))})",
    )
    return parser.parse_args(argv)


def _run(snapshot_dir: str, allow: str | None) -> None:
    allowed = None if allow is None else [t.strip() for t in allow.split(",") if t.strip()]
    router = ToolRouter(SignalTools(AnalysedSnapshot.open(snapshot_dir)), allowed)
    server = build_server(router)

    async def serve() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(serve())


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    snapshot_dir = args.snapshot or os.environ.get(ENV_SNAPSHOT)
    if not snapshot_dir:
        print(
            f"error: no snapshot given. Pass --snapshot <dir> or set {ENV_SNAPSHOT}.",
            file=sys.stderr,
        )
        return 2
    try:
        _run(snapshot_dir, args.allow)
    except (OSError, ValueError) as exc:
        print(f"error: cannot open snapshot {snapshot_dir!r}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
