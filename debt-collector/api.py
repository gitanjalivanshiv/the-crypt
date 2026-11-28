"""Collector app factory and routes (debt-collector design sections 4 and 5).

The ledger and the plan are arithmetic over findings read through the skeleton's own
HTTP routes, in process. The notice is one call to the skeleton's ``/ask``, returned
unchanged. This module calls no model and builds no prompt or claim.
"""

from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from skeleton.api.app import ApiConfig, create_app
from skeleton.mcp.contract import MAX_LIMIT, ListFindingsOutput
from skeleton.personas.llm import LLMClient
from skeleton.signals.models import Finding

from .interest import Coverage, Ledger, build_ledger, build_plan
from .notice import notice_question

PERSONA_DIR = Path(__file__).resolve().parent / "personas"
PERSONA_NAME = "collector"

router = APIRouter()


class _Upstream(Exception):
    """A non-200 from the skeleton, to be returned as it came."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(response.status_code)
        self.response = response


def _passthrough(resp: httpx.Response) -> Response:
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


def _client(request: Request) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=request.app)
    return httpx.AsyncClient(transport=transport, base_url="http://collector")


async def _get(client: httpx.AsyncClient, url: str, **params: object) -> httpx.Response:
    resp = await client.get(url, params=params or None)
    if resp.status_code != 200:
        raise _Upstream(resp)
    return resp


def _items(out: ListFindingsOutput) -> dict[str, Finding]:
    return {f.id: Finding.model_validate(f.model_dump(exclude={"id"})) for f in out.findings}


async def _read_findings(
    client: httpx.AsyncClient, ref: str
) -> tuple[str, dict[str, Finding], list[Coverage]]:
    """Snapshot id, findings by skeleton id, and per-analyzer coverage (design 4.1)."""
    detail = (await _get(client, f"/snapshots/{ref}")).json()
    snapshot_id: str = detail["meta"]["snapshot_id"]
    first = ListFindingsOutput.model_validate(
        (await _get(client, f"/snapshots/{ref}/findings", limit=MAX_LIMIT)).json()
    )
    found = _items(first)
    seen = sorted({f.analyzer for f in found.values()})
    if first.total_matching <= len(first.findings):
        counts = {name: sum(f.analyzer == name for f in found.values()) for name in seen}
        return snapshot_id, found, [Coverage(analyzer=n, returned=c, matching=c) for n, c in counts.items()]
    names = sorted({*seen, *(a.name for a in first.analyzers if a.state == "ok")})
    coverage: list[Coverage] = []
    for name in names:
        out = ListFindingsOutput.model_validate(
            (await _get(client, f"/snapshots/{ref}/findings", analyzer=name, limit=MAX_LIMIT)).json()
        )
        found.update(_items(out))
        coverage.append(Coverage(analyzer=name, returned=len(out.findings), matching=out.total_matching))
    return snapshot_id, found, coverage


async def _ledger(client: httpx.AsyncClient, ref: str) -> Ledger:
    snapshot_id, found, coverage = await _read_findings(client, ref)
    return build_ledger(snapshot_id, [(f, fid) for fid, f in found.items()], coverage)


@router.get("/collector/snapshots/{ref}/ledger")
async def ledger(ref: str, request: Request) -> Response:
    async with _client(request) as client:
        try:
            result = await _ledger(client, ref)
        except _Upstream as exc:
            return _passthrough(exc.response)
    return JSONResponse(content=result.model_dump(mode="json"))


@router.get("/collector/snapshots/{ref}/plan")
async def plan(ref: str, request: Request) -> Response:
    async with _client(request) as client:
        try:
            snapshot_id, found, _ = await _read_findings(client, ref)
        except _Upstream as exc:
            return _passthrough(exc.response)
    result = build_plan(snapshot_id, [(f, fid) for fid, f in found.items()])
    return JSONResponse(content=result.model_dump(mode="json"))


@router.post("/collector/snapshots/{ref}/notice")
async def notice(ref: str, request: Request) -> Response:
    async with _client(request) as client:
        try:
            level = (await _ledger(client, ref)).escalation
        except _Upstream as exc:
            return _passthrough(exc.response)
        resp = await client.post(
            f"/snapshots/{ref}/ask",
            json={"persona": PERSONA_NAME, "question": notice_question(level)},
        )
    return _passthrough(resp)


def create_collector_app(store: Path, llm: LLMClient, cfg: ApiConfig | None = None) -> FastAPI:
    app = create_app(store=Path(store), llm=llm, persona_dir=PERSONA_DIR, cfg=cfg)
    app.include_router(router)
    return app
