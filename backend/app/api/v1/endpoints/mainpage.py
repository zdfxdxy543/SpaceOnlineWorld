from __future__ import annotations

import json
from itertools import count

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.mainpage import MainPageDetail, MainPageGenerateRequest, MainPageGenerateResponse, MainPageSummary
from app.simulation.protocol import ActionRequest

router = APIRouter()
_action_counter = count(1)


@router.post("/generate", response_model=MainPageGenerateResponse)
def generate_main_page(payload: MainPageGenerateRequest, request: Request) -> MainPageGenerateResponse:
    world_service = request.app.state.container.world_service
    if not world_service.agent_exists(payload.actor_id):
        raise HTTPException(status_code=404, detail=f"Actor not found: {payload.actor_id}")

    action_request = ActionRequest(
        action_id=f"manual-action-{next(_action_counter):05d}",
        capability="main.generate_page",
        actor_id=payload.actor_id,
        payload={
            "title": payload.title,
            "description": payload.description,
            "slug": payload.slug,
            "style": payload.style,
        },
        idempotency_key=(
            f"manual-main-generate:{payload.actor_id}:{payload.title}:{payload.slug or ''}:{next(_action_counter):05d}"
        ),
    )
    result = request.app.state.container.tool_registry.execute(action_request)
    if result.status != "success":
        raise HTTPException(
            status_code=400,
            detail=result.error_message or result.error_code or "main_page_generation_failed",
        )

    output = result.output
    return MainPageGenerateResponse(
        status="published",
        page_id=str(output.get("page_id", "")),
        slug=str(output.get("slug", "")),
        url=str(output.get("url", "")),
        title=str(output.get("title", "")),
    )


@router.get("/pages", response_model=list[MainPageSummary])
def list_main_pages(request: Request, limit: int = Query(default=50, ge=1, le=200)) -> list[MainPageSummary]:
    service = request.app.state.container.mainpage_service
    records = service.list_pages(limit=limit)
    return [
        MainPageSummary(
            page_id=item.page_id,
            slug=item.slug,
            title=item.title,
            url=f"/main/{item.slug}",
            published_at=item.published_at,
        )
        for item in records
    ]


@router.get("/pages/{slug}", response_model=MainPageDetail)
def get_main_page(slug: str, request: Request) -> MainPageDetail:
    service = request.app.state.container.mainpage_service
    page = service.get_page_by_slug(slug=slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Main page not found")

    try:
        assets = json.loads(page.assets_json)
    except json.JSONDecodeError:
        assets = []

    if not isinstance(assets, list):
        assets = []

    normalized_assets: list[dict[str, str]] = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        normalized_assets.append(
            {
                "path": str(item.get("path", "")),
                "content": str(item.get("content", "")),
                "content_type": str(item.get("content_type", "text/plain")),
            }
        )

    return MainPageDetail(
        page_id=page.page_id,
        slug=page.slug,
        title=page.title,
        url=f"/main/{page.slug}",
        published_at=page.published_at,
        html_content=page.html_content,
        assets=normalized_assets,
        author_id=page.author_id,
        updated_at=page.updated_at,
    )
