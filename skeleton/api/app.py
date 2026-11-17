"""API composition root (design 10.1) and the read routes (design 10.2).

This module reads no environment variable, key or secret (R9.7). ``llm`` is the only
provider path and is passed in by the caller.
"""

import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

from skeleton.api.errors import ApiCode, error_response, status_for
from skeleton.api.models import SnapshotDetail
from skeleton.ingest.models import IngestLimits
from skeleton.mcp.contract import ErrorResponse as ToolErrorResponse
from skeleton.mcp.tools import SignalTools
from skeleton.personas.llm import LLMClient
from skeleton.personas.loader import load_personas
from skeleton.signals.store import AnalysedSnapshot

_REF_RE = re.compile(r"^[A-Za-z0-9_:-]{1,128}$")


class ApiConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    allow_retained: bool = False
    ephemeral_ttl_s: int = 3600
    max_concurrent_ingests: int = 2
    allowed_hosts: frozenset[str] | None = None
    limits: IngestLimits = IngestLimits()


class ApiError(Exception):
    """A request failure carrying a machine code; the handler maps it to HTTP."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _json_error(code: str, message: str, status: int | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status if status is not None else status_for(code),
        content=error_response(code, message).model_dump(),
    )


def _resolve_dir(store: Path, ref: str) -> Path | None:
    """Map an opaque ref to a snapshot directory, or None. Never builds a path from unvalidated text."""
    if not _REF_RE.fullmatch(ref):
        return None
    for candidate in (
        store / "ephemeral" / ref,
        store / "retained" / ref.replace(":", "-"),
    ):
        if (candidate / "meta.json").is_file() and (candidate / "findings.json").is_file():
            return candidate
    return None


def _tool_result(result: BaseModel) -> JSONResponse:
    if isinstance(result, ToolErrorResponse):
        code = result.error.code.value
        try:
            status = status_for(code)
        except KeyError:  # invalid_argument has no table entry: a bad request
            status = 400
        return JSONResponse(
            status_code=status,
            content={**error_response(code, result.error.message).model_dump(), "snapshot_id": result.snapshot_id},
        )
    return JSONResponse(content=result.model_dump(mode="json"))


def create_app(
    *, store: Path, llm: LLMClient, persona_dir: Path, cfg: ApiConfig | None = None
) -> FastAPI:
    cfg = cfg or ApiConfig()
    # A bad persona raises PersonaError here, so startup fails. There is no default persona.
    personas = load_personas(Path(persona_dir))

    app = FastAPI(title="skeleton")
    app.state.store = Path(store)
    app.state.llm = llm
    app.state.personas = personas
    app.state.cfg = cfg

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _json_error(exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"])
        return _json_error("malformed", f"{loc}: {first['msg']}", 400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "snapshot_not_found" if exc.status_code == 404 else "malformed"
        return _json_error(code, str(exc.detail), exc.status_code)

    def _open(ref: str) -> AnalysedSnapshot:
        directory = _resolve_dir(app.state.store, ref)
        if directory is None:
            raise ApiError(ApiCode.snapshot_not_found, f"no snapshot for ref {ref!r}")
        return AnalysedSnapshot.open(directory)

    @app.get("/snapshots/{ref}")
    def get_snapshot(ref: str) -> SnapshotDetail:
        snap = _open(ref)
        return SnapshotDetail(meta=snap.snapshot.meta, analyzers=tuple(snap.findings.analyzers))

    @app.get("/snapshots/{ref}/findings")
    def list_findings(
        ref: str,
        analyzer: str | None = None,
        file: str | None = None,
        min_severity: float | None = None,
        limit: int | None = None,
    ) -> JSONResponse:
        tools = SignalTools(_open(ref))
        args = {
            k: v
            for k, v in {
                "analyzer": analyzer,
                "file": file,
                "min_severity": min_severity,
                "limit": limit,
            }.items()
            if v is not None
        }
        return _tool_result(tools.list_findings(args))

    @app.get("/snapshots/{ref}/files/{path:path}")
    def get_file(
        ref: str, path: str, line_start: int | None = None, line_end: int | None = None
    ) -> JSONResponse:
        tools = SignalTools(_open(ref))
        if line_start is None and line_end is None:
            return _tool_result(tools.get_file_facts({"file": path}))
        # A range was supplied: return those lines. A half-given range is malformed.
        if line_start is None or line_end is None:
            return _json_error("malformed", "line_start and line_end must be given together", 400)
        return _tool_result(
            tools.read_lines({"file": path, "line_start": line_start, "line_end": line_end})
        )

    return app
