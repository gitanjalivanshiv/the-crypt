"""In-process tool dispatcher with a per-persona allow-list (R5.6, R5.7).

Failures are returned as ``ErrorResponse`` values, never raised.
"""

from collections.abc import Callable, Iterable, Mapping

from skeleton.mcp.contract import (
    TOOL_GET_FILE_FACTS,
    TOOL_GET_SNAPSHOT,
    TOOL_LIST_FINDINGS,
    TOOL_NAMES,
    TOOL_READ_LINES,
    ErrorCode,
    ErrorResponse,
    ToolError,
)
from skeleton.mcp.tools import SignalTools

ToolResult = object


class ToolRouter:
    """Dispatches tool calls to ``SignalTools``, exposing only the allowed tools.

    ``allowed=None`` exposes every tool. Names in ``allowed`` that are not real tools are ignored.
    """

    def __init__(self, tools: SignalTools, allowed: Iterable[str] | None = None) -> None:
        self._tools = tools
        self._handlers: dict[str, Callable[[Mapping[str, object] | None], ToolResult]] = {
            TOOL_GET_SNAPSHOT: self._get_snapshot,
            TOOL_LIST_FINDINGS: tools.list_findings,
            TOOL_GET_FILE_FACTS: tools.get_file_facts,
            TOOL_READ_LINES: tools.read_lines,
        }
        requested = TOOL_NAMES if allowed is None else frozenset(allowed)
        self._allowed = frozenset(requested & self._handlers.keys())

    def _get_snapshot(self, arguments: Mapping[str, object] | None) -> ToolResult:
        if arguments:
            return self._error(ErrorCode.INVALID_ARGUMENT, "get_snapshot takes no arguments")
        return self._tools.get_snapshot()

    def _error(self, code: ErrorCode, message: str) -> ErrorResponse:
        return ErrorResponse(
            error=ToolError(code=code, message=message),
            snapshot_id=self._tools.snapshot_id,
        )

    @property
    def tool_names(self) -> list[str]:
        """Allowed tool names, sorted."""
        return sorted(self._allowed)

    def call(self, name: str, arguments: Mapping[str, object] | None = None) -> ToolResult:
        if not isinstance(name, str) or name not in self._handlers:
            return self._error(ErrorCode.INVALID_ARGUMENT, f"unknown tool: {name!r}")
        if name not in self._allowed:
            return self._error(
                ErrorCode.TOOL_NOT_ALLOWED, f"tool not allowed for this persona: {name}"
            )
        try:
            return self._handlers[name](arguments)
        except Exception as exc:  # noqa: BLE001 - contract: return structured errors, never raise
            return self._error(ErrorCode.INVALID_ARGUMENT, f"{name} failed: {type(exc).__name__}")
