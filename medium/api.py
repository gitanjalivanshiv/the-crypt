"""Medium app factory and plan route (medium design section 4).

Each plan section is one in-process call to the skeleton's ``POST /snapshots/{ref}/ask``.
This module builds no prompt, calls no model and constructs no claim.
"""
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from medium.plan import SECTION_QUESTIONS, SECTIONS, PlanResult, PlanSection
from skeleton.api.app import ApiConfig, create_app
from skeleton.personas.llm import LLMClient
from skeleton.verify.models import AnswerResult

PERSONA_DIR = Path(__file__).resolve().parent / "personas"

router = APIRouter()


@router.post("/medium/snapshots/{ref}/plan")
async def plan(ref: str, request: Request) -> Response:
    sections: list[PlanSection] = []
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medium") as client:
        for section in SECTIONS:
            resp = await client.post(
                f"/snapshots/{ref}/ask",
                json={"persona": "ghost", "question": SECTION_QUESTIONS[section]},
            )
            if resp.status_code != 200:
                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    media_type=resp.headers.get("content-type"),
                )
            sections.append(
                PlanSection(section=section, result=AnswerResult.model_validate(resp.json()))
            )
    result = PlanResult(snapshot_id=sections[0].result.snapshot_id, sections=tuple(sections))
    return JSONResponse(content=result.model_dump(mode="json"))


def create_medium_app(store: Path, llm: LLMClient, cfg: ApiConfig | None = None) -> FastAPI:
    app = create_app(store=Path(store), llm=llm, persona_dir=PERSONA_DIR, cfg=cfg)
    app.include_router(router)
    return app
