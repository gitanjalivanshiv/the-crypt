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
    READ_LINES_MAX,
    GetFileFactsInput,
    GetFileFactsOutput,
    ListFindingsOutput,
    ReadLinesInput,
    ReadLinesOutput,
    ToolError,
)
from skeleton.signals.models import finding_id
from skeleton.signals.store import AnalysedSnapshot
from skeleton.verify.citation import Rejection, verify_citation
from skeleton.verify.codes import ReasonCode
from skeleton.verify.textnorm import normalised_lines


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

    def _check_file(
        self, arguments: Mapping[str, object] | None, with_range: bool
    ) -> ErrorResponse | tuple[str, int, int]:
        """Validate arguments and the citation. Returns (file, start, end) or an error."""
        model = ReadLinesInput if with_range else GetFileFactsInput
        try:
            args = model.model_validate(dict(arguments or {}), strict=True)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first["loc"]) or "arguments"
            return self._error(ErrorCode.INVALID_ARGUMENT, f"{loc}: {first['msg']}")
        start = args.line_start if isinstance(args, ReadLinesInput) else 1
        end = args.line_end if isinstance(args, ReadLinesInput) else 1
        if not with_range:
            # Existence and path safety only: a range of 1-1 would wrongly reject empty files.
            entry_args = {"file": args.file, "line_start": 1, "line_end": 1}
        else:
            entry_args = {"file": args.file, "line_start": start, "line_end": end}
        result = verify_citation(self._snap, {**entry_args, "quote": None})
        if isinstance(result, Rejection):
            if not with_range and result.code in (
                ReasonCode.RANGE_INVALID,
                ReasonCode.RANGE_OUT_OF_BOUNDS,
            ):
                return (args.file, start, end)
            return self._error(ErrorCode(result.code.value), result.message)
        return (args.file, start, end)

    def get_file_facts(
        self, arguments: Mapping[str, object] | None = None
    ) -> GetFileFactsOutput | ErrorResponse:
        checked = self._check_file(arguments, with_range=False)
        if isinstance(checked, ErrorResponse):
            return checked
        file = checked[0]
        graph = self._snap.snapshot.graph
        entry = self._snap.snapshot.entry(file)
        if entry is None:  # unreachable after verify_citation; keeps types honest
            return self._error(ErrorCode.FILE_NOT_FOUND, file)
        return GetFileFactsOutput(
            snapshot_id=self.snapshot_id,
            file=file,
            line_count=entry.line_count,
            symbols=list(graph.symbols.get(file, [])),
            imports=list(graph.imports.get(file, [])),
            history=entry.history,
            history_available=entry.history is not None,
        )

    def read_lines(
        self, arguments: Mapping[str, object] | None = None
    ) -> ReadLinesOutput | ErrorResponse:
        checked = self._check_file(arguments, with_range=True)
        if isinstance(checked, ErrorResponse):
            return checked
        file, start, end = checked
        data = self._snap.read_bytes(file)
        if data is None:
            return self._error(ErrorCode.FILE_NOT_FOUND, file)
        try:
            lines = normalised_lines(data)
        except UnicodeDecodeError:
            return self._error(ErrorCode.INVALID_ARGUMENT, f"{file}: not valid UTF-8")
        truncated = end - start + 1 > READ_LINES_MAX
        last = start + READ_LINES_MAX - 1 if truncated else end
        return ReadLinesOutput(
            snapshot_id=self.snapshot_id,
            file=file,
            lines=lines[start - 1 : last],
            line_start=start,
            returned_line_end=last,
            truncated=truncated,
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
