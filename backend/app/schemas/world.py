from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    database_url: str
    llm_provider: str


class EventTraceItem(BaseModel):
    name: str
    detail: str
    metadata: dict[str, str]
    occurred_at: str


class WorldSummaryResponse(BaseModel):
    current_tick: int
    current_time_label: str
    active_sites: list[str]
    recent_events: list[EventTraceItem]


class WorldCharacterResponse(BaseModel):
    character_id: str
    real_name: str
    handle: str
    occupation: str
    gender: str
    personality_traits: list[str]
    status: str
    home_location_id: str | None
    created_at: str
    updated_at: str


class SpaceLocationResponse(BaseModel):
    location_id: str
    name: str
    location_type: str
    region: str
    description: str
    discovered_at: str
    discovery_source: str
    parent_location_id: str | None
    expansion_tier: int
    metadata: dict[str, str]


class ExpandSpaceLocationsRequest(BaseModel):
    probability: float = Field(default=0.35, ge=0.0, le=1.0)
    max_new_locations: int = Field(default=3, ge=1, le=20)


class ExpandSpaceLocationsResponse(BaseModel):
    created_count: int
    locations: list[SpaceLocationResponse]


class DemoPostRequest(BaseModel):
    agent_id: str = Field(default="agent-001")
    site_id: str = Field(default="forum.main")
    topic: str = Field(default="在共享网盘里上传了今天的观察记录")
    attach_cloud_file: bool = True


class ReferencedResourceResponse(BaseModel):
    resource_id: str
    resource_type: str
    title: str
    access_code: str
    owner_agent_id: str
    site_id: str
    metadata: dict[str, str]


class DemoPostResponse(BaseModel):
    draft_id: str
    content: str
    consistency_passed: bool
    violations: list[str]
    facts: list[str]
    referenced_resource: ReferencedResourceResponse | None
    event_trace: list[EventTraceItem]
