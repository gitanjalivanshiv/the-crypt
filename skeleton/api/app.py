"""API composition root (design 10.1) and the read routes (design 10.2).

This module reads no environment variable, key or secret (R9.7). ``llm`` is the only
provider path and is passed in by the caller.
"""

import asyncio
import re
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

from skeleton.api.errors import ApiCode, error_response, status_for
from skeleton.api.models import AskRequest, SnapshotDetail, SnapshotRequest
from skeleton.api.retention import RetainedNotAllowed, Retention, resolve_intent
from skeleton.ingest import _remove, ingest_url
from skeleton.ingest.models import IngestCode, IngestError, IngestLimits
from skeleton.ingest.snapshot import Snapshot
from skeleton.mcp.contract import ErrorResponse as ToolErrorResponse
from skeleton.mcp.router import ToolRouter
from skeleton.mcp.tools import SignalTools
from skeleton.personas.generator import ToolLoopGenerator
from skeleton.personas.llm import LLMClient
from skeleton.personas.loader import load_personas
from skeleton.personas.prompt import assemble_system_prompt
from skeleton.signals.store import AnalysedSnapshot, analyse
from skeleton.verify.flow import run_grounded_turn
from skeleton.verify.models import AnswerResult, VerifyConfig

_REF_RE = re.compile(r"^[A-Za-z0-9_:-]{1,128}$")


class ApiConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    allow_retained: bool = False
    ephemeral_ttl_s: int = 3600
    max_concurrent_ingests: int = 2
    allowed_hosts: frozenset[str] | None = None
    limits: IngestLimits = IngestLimits()
    ingest_timeout_s: float = 300.0


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
    *,
    store: Path,
    llm: LLMClient,
    persona_dir: Path,
    cfg: ApiConfig | None = None,
    clock: Callable[[], float] | None = None,
    ingest_fn: Callable[..., Snapshot] = ingest_url,
) -> FastAPI:
    cfg = cfg or ApiConfig()
    # A bad persona raises PersonaError here, so startup fails. There is no default persona.
    personas = load_personas(Path(persona_dir))

    retention = Retention(Path(store), cfg.ephemeral_ttl_s, clock or time.monotonic)
    sweep_interval = max(1.0, min(60.0, cfg.ephemeral_ttl_s / 2))

    async def _sweeper() -> None:
        while True:
            await asyncio.sleep(sweep_interval)
            retention.sweep()

    @asynccontextmanager
    async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(_sweeper())
        try:
            yield
        finally:
            task.cancel()
            retention.cleanup_all()

    app = FastAPI(title="skeleton", lifespan=_lifespan)
    app.state.retention = retention
    app.state.store = Path(store)
    app.state.llm = llm
    app.state.personas = personas
    app.state.cfg = cfg

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _json_error(exc.code, exc.message)

    @app.exception_handler(RetainedNotAllowed)
    async def _retained(_: Request, exc: RetainedNotAllowed) -> JSONResponse:
        return _json_error(exc.code, str(exc))

    @app.middleware("http")
    async def _lazy_sweep(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        retention.sweep()
        return await call_next(request)

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

    @app.post("/snapshots")
    async def create_snapshot(body: SnapshotRequest) -> JSONResponse:
        """Synchronous ingest then analyse, bounded by ``cfg.ingest_timeout_s`` (task 6.5)."""
        intent = resolve_intent(body.intent, allow_retained=cfg.allow_retained)
        abandoned = threading.Event()

        def _work() -> tuple[Snapshot, str]:
            snap = ingest_fn(
                body.url,
                ref=body.ref,
                sha=body.sha,
                intent=intent,
                limits=cfg.limits,
                store=app.state.store,
            )
            try:
                if abandoned.is_set():
                    raise IngestError(IngestCode.clone_timeout, "request timed out")
                analyse(snap.root)
            except BaseException:
                _remove(snap.root)
                raise
            if abandoned.is_set():  # the request gave up while we ran: leave nothing behind
                _remove(snap.root)
                raise IngestError(IngestCode.clone_timeout, "request timed out")
            if intent == "retained":
                return snap, Retention.retained_ref(snap.meta.snapshot_id)
            return snap, snap.root.name

        try:
            snap, ref = await asyncio.wait_for(asyncio.to_thread(_work), cfg.ingest_timeout_s)
        except TimeoutError:
            abandoned.set()
            return _json_error(
                IngestCode.clone_timeout, f"ingest exceeded {cfg.ingest_timeout_s}s"
            )
        except IngestError as exc:
            return _json_error(exc.code, exc.detail)
        if intent == "ephemeral":
            retention.register(ref)
        return JSONResponse(
            status_code=201,
            content={
                "ref": ref,
                "snapshot_id": snap.meta.snapshot_id,
                "licence": snap.meta.licence,
            },
        )

    @app.get("/snapshots/{ref}")
    def get_snapshot(ref: str) -> SnapshotDetail:
        snap = _open(ref)
        return SnapshotDetail(meta=snap.snapshot.meta, analyzers=tuple(snap.findings.analyzers))

    @app.delete("/snapshots/{ref}", status_code=204)
    def delete_snapshot(ref: str) -> Response:
        if not retention.delete(ref):
            raise ApiError(ApiCode.snapshot_not_found, f"no ephemeral snapshot for ref {ref!r}")
        return Response(status_code=204)

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

    @app.post("/snapshots/{ref}/ask")
    async def ask(ref: str, body: AskRequest) -> AnswerResult:
        snap = _open(ref)
        persona = app.state.personas.get(body.persona)
        if persona is None:
            raise ApiError(ApiCode.persona_not_found, f"no persona named {body.persona!r}")
        router = ToolRouter(SignalTools(snap), list(persona.allowed_tools))
        generator = ToolLoopGenerator(
            app.state.llm,
            persona,
            router,
            assemble_system_prompt(persona, snap.snapshot.meta),
            body.question,
        )
        return await run_grounded_turn(
            snap, generator, decline_line=persona.decline_line, cfg=VerifyConfig()
        )

    return app
