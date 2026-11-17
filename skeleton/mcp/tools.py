"""Pure-Python tool implementations. No MCP SDK import.

The stdio server, the in-process router and the API all call these, so validation is shared.
"""

from collections.abc import Mapping

from pydantic import ValidationError

from skeleton.mcp.contract import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    ErrorCode,
    ErrorResponse,
    FindingWithId,
    GetSnapshotOutput,
    ListFindingsInput,
    ListFindingsOutput,
    ToolError,
)
from skeleton.signals.models import finding_id
from skeleton.signals.store import AnalysedSnapshot


class SignalTools:
    def __init__(self, analysed_snapshot: AnalysedSnapshot) -> None:
        self._snap = analysed_snapshot

    @property
    def snapshot_id(self) -> str:
        return self._snap.snapshot_id

    def _error(self, code: ErrorCode, message: str) -> ErrorResponse:
        return ErrorResponse(
            error=ToolError(code=code, message=message), snapshot_id=self.snapshot_id
        )

    def get_snapshot(self) -> GetSnapshotOutput:
        meta = self._snap.snapshot.meta
        return GetSnapshotOutput(
            snapshot_id=meta.snapshot_id,
            source=meta.source,
            licence=meta.licence,
            history_available=meta.history_available,
            file_count=meta.file_count,
            analyzers=list(self._snap.findings.analyzers),
        )

    def list_findings(
        self, arguments: Mapping[str, object] | None = None
    ) -> ListFindingsOutput | ErrorResponse:
        try:
            args = ListFindingsInput.model_validate(dict(arguments or {}), strict=False)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first["loc"]) or "arguments"
            return self._error(ErrorCode.INVALID_ARGUMENT, f"{loc}: {first['msg']}")

        requested = DEFAULT_LIMIT if args.limit is None else args.limit
        if requested < 1:
            return self._error(ErrorCode.INVALID_ARGUMENT, "limit: must be at least 1")
        clamped = requested > MAX_LIMIT
        limit = MAX_LIMIT if clamped else requested

        matching = [
            f
            for f in self._snap.findings.findings
            if (args.analyzer is None or f.analyzer == args.analyzer)
            and (args.file is None or f.file == args.file)
            and (args.min_severity is None or f.severity >= args.min_severity)
        ]
        matching.sort(key=lambda f: (-f.severity, f.file, f.line_start))
        return ListFindingsOutput(
            snapshot_id=self.snapshot_id,
            findings=[
                FindingWithId(**f.model_dump(), id=finding_id(f))
                for f in matching[:limit]
            ],
            total_matching=len(matching),
            limit_applied=limit,
            clamped=clamped,
            analyzers=list(self._snap.findings.analyzers),
        )
