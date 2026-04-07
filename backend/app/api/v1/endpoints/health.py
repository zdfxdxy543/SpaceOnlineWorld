from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.world import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    container = request.app.state.container
    db_info = container.database_session_manager.describe()
    return HealthResponse(
        status="ok",
        app_name=container.settings.app_name,
        environment=container.settings.environment,
        database_url=db_info["database_url"],
        llm_provider=container.settings.llm_provider,
    )
