from __future__ import annotations

from fastapi import APIRouter, Request

from app.domain.events import StoryEvent
from app.domain.models import GeneratedPostDraft, WorldResource, WorldSnapshot
from app.schemas.world import (
    DemoPostRequest,
    DemoPostResponse,
    ExpandSpaceLocationsRequest,
    ExpandSpaceLocationsResponse,
    EventTraceItem,
    ReferencedResourceResponse,
    SpaceLocationResponse,
    WorldCharacterResponse,
    WorldSummaryResponse,
)

router = APIRouter()


def _map_event(event: StoryEvent) -> EventTraceItem:
    return EventTraceItem(
        name=event.name,
        detail=event.detail,
        metadata=event.metadata,
        occurred_at=event.occurred_at,
    )


def _map_resource(resource: WorldResource | None) -> ReferencedResourceResponse | None:
    if resource is None:
        return None
    return ReferencedResourceResponse(
        resource_id=resource.resource_id,
        resource_type=resource.resource_type,
        title=resource.title,
        access_code=resource.access_code,
        owner_agent_id=resource.owner_agent_id,
        site_id=resource.site_id,
        metadata=resource.metadata,
    )


def _map_world_summary(snapshot: WorldSnapshot) -> WorldSummaryResponse:
    return WorldSummaryResponse(
        current_tick=snapshot.current_tick,
        current_time_label=snapshot.current_time_label,
        active_sites=snapshot.active_sites,
        recent_events=[_map_event(event) for event in snapshot.recent_events],
    )


def _map_world_character(item) -> WorldCharacterResponse:
    return WorldCharacterResponse(
        character_id=item.character_id,
        real_name=item.real_name,
        handle=item.handle,
        occupation=item.occupation,
        gender=item.gender,
        personality_traits=item.personality_traits,
        status=item.status,
        home_location_id=item.home_location_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _map_space_location(item) -> SpaceLocationResponse:
    return SpaceLocationResponse(
        location_id=item.location_id,
        name=item.name,
        location_type=item.location_type,
        region=item.region,
        description=item.description,
        discovered_at=item.discovered_at,
        discovery_source=item.discovery_source,
        parent_location_id=item.parent_location_id,
        expansion_tier=item.expansion_tier,
        metadata=item.metadata,
    )


def _map_draft(draft: GeneratedPostDraft) -> DemoPostResponse:
    return DemoPostResponse(
        draft_id=draft.draft_id,
        content=draft.content,
        consistency_passed=draft.consistency_passed,
        violations=draft.violations,
        facts=draft.facts,
        referenced_resource=_map_resource(draft.referenced_resource),
        event_trace=[_map_event(event) for event in draft.event_trace],
    )


@router.get("/summary", response_model=WorldSummaryResponse)
def get_world_summary(request: Request) -> WorldSummaryResponse:
    container = request.app.state.container
    snapshot = container.world_service.get_summary()
    return _map_world_summary(snapshot)


@router.post("/demo-post", response_model=DemoPostResponse)
def create_demo_post(payload: DemoPostRequest, request: Request) -> DemoPostResponse:
    container = request.app.state.container
    draft = container.world_service.create_demo_post(payload)
    return _map_draft(draft)


@router.get("/characters", response_model=list[WorldCharacterResponse])
def get_world_characters(request: Request) -> list[WorldCharacterResponse]:
    container = request.app.state.container
    items = container.world_service.list_world_characters()
    return [_map_world_character(item) for item in items]


@router.get("/locations", response_model=list[SpaceLocationResponse])
def get_space_locations(request: Request) -> list[SpaceLocationResponse]:
    container = request.app.state.container
    items = container.world_service.list_space_locations()
    return [_map_space_location(item) for item in items]


@router.post("/locations/expand", response_model=ExpandSpaceLocationsResponse)
def expand_space_locations(
    payload: ExpandSpaceLocationsRequest,
    request: Request,
) -> ExpandSpaceLocationsResponse:
    container = request.app.state.container
    created = container.world_service.expand_space_locations(
        probability=payload.probability,
        max_new_locations=payload.max_new_locations,
    )
    return ExpandSpaceLocationsResponse(
        created_count=len(created),
        locations=[_map_space_location(item) for item in created],
    )
