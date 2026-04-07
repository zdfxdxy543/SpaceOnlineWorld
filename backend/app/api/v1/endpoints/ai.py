from __future__ import annotations

import json
from itertools import count
import re

from fastapi import APIRouter, HTTPException, Request

from app.schemas.ai import (
    ActionExecuteRequest,
    ActionExecuteResponse,
    ActorSummaryResponse,
    CapabilitySpecResponse,
    SchedulerRunRequest,
    SchedulerRunResponse,
    StoryEventResponse,
)
from app.simulation.protocol import ActionRequest, ActionResult

router = APIRouter()
_action_counter = count(1)


def _map_events(items) -> list[StoryEventResponse]:
    return [
        StoryEventResponse(
            name=item.name,
            detail=item.detail,
            metadata=item.metadata,
            occurred_at=item.occurred_at,
        )
        for item in items
    ]


def _map_action_result(item: ActionResult) -> ActionExecuteResponse:
    return ActionExecuteResponse(
        action_id=item.action_id,
        capability=item.capability,
        status=item.status,
        output=item.output,
        facts=item.facts,
        events=_map_events(item.events),
        pipeline=item.pipeline,
        error_code=item.error_code,
        error_message=item.error_message,
    )


def _resolve_actor_ids(payload: SchedulerRunRequest, request: Request) -> tuple[list[str], object]:
    world_service = request.app.state.container.world_service
    settings = request.app.state.container.settings
    spawned_actor = world_service.maybe_spawn_random_agent(settings.scheduler_new_actor_probability)

    actor_ids = payload.actors
    if not actor_ids:
        if spawned_actor is not None:
            actor_ids = [spawned_actor.agent_id]
        else:
            actor_ids = [item.agent_id for item in world_service.list_agents()[:1]]

    # Enrich actor pool for more realistic multi-role interactions in scheduled stories.
    target_actor_count = max(1, settings.scheduler_target_actor_count)
    if len(actor_ids) < target_actor_count:
        existing = set(actor_ids)
        for agent in world_service.list_agents():
            if agent.agent_id in existing:
                continue
            actor_ids.append(agent.agent_id)
            existing.add(agent.agent_id)
            if len(actor_ids) >= target_actor_count:
                break

    if not actor_ids:
        raise HTTPException(status_code=400, detail="No SQL-backed actors available")

    unknown_actors = [actor_id for actor_id in actor_ids if not world_service.agent_exists(actor_id)]
    if unknown_actors:
        raise HTTPException(
            status_code=404,
            detail=f"Actors not found in SQL agents: {', '.join(unknown_actors)}",
        )

    return actor_ids, spawned_actor


def _extract_arc_info(story_id: str) -> tuple[str | None, str | None]:
    match = re.search(r"(?:life|detective)-arc-(arc-\d+)-phase-([a-z]+)-", story_id)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _persist_arc_progress(report, request: Request) -> None:
    arc_id, phase = _extract_arc_info(report.story_id)
    if not arc_id:
        return

    clue_thread_id = None
    resolution_thread_id = None
    resolution_news_id = None
    related_share_id = None

    for item in report.results:
        if item.status != "success":
            continue
        if item.capability == "forum.create_thread":
            thread_id = str(item.output.get("thread_id", "")).strip()
            if not thread_id:
                thread = item.output.get("thread", {})
                if isinstance(thread, dict):
                    thread_id = str(thread.get("id", "")).strip()
            if thread_id:
                if phase == "resolution":
                    resolution_thread_id = thread_id
                else:
                    clue_thread_id = thread_id
        if item.capability == "news.publish_article":
            article_id = str(item.output.get("article_id", "")).strip()
            if not article_id:
                article = item.output.get("article", {})
                if isinstance(article, dict):
                    article_id = str(article.get("article_id", "")).strip()
            if article_id:
                resolution_news_id = article_id
        if item.capability == "netdisk.create_share_link":
            share_id = str(item.output.get("share_id", "")).strip()
            if share_id:
                related_share_id = share_id

    resolve = phase == "resolution" and (bool(resolution_news_id) or bool(resolution_thread_id))
    request.app.state.container.story_arc_service.mark_progress(
        arc_id=arc_id,
        clue_thread_id=clue_thread_id,
        related_share_id=related_share_id,
        resolution_thread_id=resolution_thread_id,
        resolution_news_id=resolution_news_id,
        resolve=resolve,
    )


@router.get("/capabilities", response_model=list[CapabilitySpecResponse])
def list_capabilities(request: Request) -> list[CapabilitySpecResponse]:
    items = request.app.state.container.tool_registry.list_capabilities()
    return [
        CapabilitySpecResponse(
            name=item.name,
            site=item.site,
            description=item.description,
            input_schema=item.input_schema,
            read_only=item.read_only,
        )
        for item in items
    ]


@router.get("/actors", response_model=list[ActorSummaryResponse])
def list_actors(request: Request) -> list[ActorSummaryResponse]:
    world_service = request.app.state.container.world_service
    agents = world_service.list_agents()
    result: list[ActorSummaryResponse] = []
    for agent in agents:
        try:
            personality_traits = json.loads(agent.personality_traits_json)
        except json.JSONDecodeError:
            personality_traits = []
        try:
            values = json.loads(agent.values_json)
        except json.JSONDecodeError:
            values = []
        try:
            hobbies = json.loads(agent.hobbies_json)
        except json.JSONDecodeError:
            hobbies = []

        result.append(
            ActorSummaryResponse(
                id=agent.agent_id,
                name=agent.display_name,
                status=agent.status,
                gender=agent.gender,
                age_range=agent.age_range,
                occupation=agent.occupation,
                residence_city=agent.residence_city,
                native_language=agent.native_language,
                personality_traits=personality_traits,
                values=values,
                hobbies=hobbies,
            )
        )
    return result


@router.post("/execute", response_model=ActionExecuteResponse)
def execute_action(payload: ActionExecuteRequest, request: Request) -> ActionExecuteResponse:
    world_service = request.app.state.container.world_service
    if not world_service.agent_exists(payload.actor_id):
        raise HTTPException(status_code=404, detail=f"Actor not found in SQL agents: {payload.actor_id}")

    action_request = ActionRequest(
        action_id=f"manual-action-{next(_action_counter):05d}",
        capability=payload.capability,
        actor_id=payload.actor_id,
        payload=payload.payload,
        idempotency_key=payload.idempotency_key,
    )
    result = request.app.state.container.tool_registry.execute(action_request)
    return _map_action_result(result)


@router.post("/scheduler/run", response_model=SchedulerRunResponse)
def run_scheduler(payload: SchedulerRunRequest, request: Request) -> SchedulerRunResponse:
    actor_ids, spawned_actor = _resolve_actor_ids(payload, request)

    report = request.app.state.container.story_scheduler.run(goal=payload.goal, actors=actor_ids)
    return SchedulerRunResponse(
        story_id=report.story_id,
        goal=report.goal,
        status=report.status,
        results=[_map_action_result(item) for item in report.results],
        pending_steps=report.pending_steps,
        planner_name=report.planner_name,
        planner_source=report.planner_source,
        fallback_used=report.fallback_used,
        planner_detail=report.planner_detail,
        spawned_actor_id=spawned_actor.agent_id if spawned_actor else None,
        spawn_triggered=spawned_actor is not None,
    )


@router.post("/scheduler/run-life", response_model=SchedulerRunResponse)
def run_life_scheduler(payload: SchedulerRunRequest, request: Request) -> SchedulerRunResponse:
    actor_ids, spawned_actor = _resolve_actor_ids(payload, request)
    report = request.app.state.container.life_story_scheduler.run(goal=payload.goal, actors=actor_ids)
    return SchedulerRunResponse(
        story_id=report.story_id,
        goal=report.goal,
        status=report.status,
        results=[_map_action_result(item) for item in report.results],
        pending_steps=report.pending_steps,
        planner_name=report.planner_name,
        planner_source=report.planner_source,
        fallback_used=report.fallback_used,
        planner_detail=report.planner_detail,
        spawned_actor_id=spawned_actor.agent_id if spawned_actor else None,
        spawn_triggered=spawned_actor is not None,
    )


@router.post("/scheduler/run-life-arc", response_model=SchedulerRunResponse)
def run_life_arc_scheduler(payload: SchedulerRunRequest, request: Request) -> SchedulerRunResponse:
    actor_ids, spawned_actor = _resolve_actor_ids(payload, request)
    report = request.app.state.container.life_arc_story_scheduler.run(goal=payload.goal, actors=actor_ids)
    _persist_arc_progress(report, request)
    return SchedulerRunResponse(
        story_id=report.story_id,
        goal=report.goal,
        status=report.status,
        results=[_map_action_result(item) for item in report.results],
        pending_steps=report.pending_steps,
        planner_name=report.planner_name,
        planner_source=report.planner_source,
        fallback_used=report.fallback_used,
        planner_detail=report.planner_detail,
        spawned_actor_id=spawned_actor.agent_id if spawned_actor else None,
        spawn_triggered=spawned_actor is not None,
    )


@router.post("/scheduler/run-detective-arc", response_model=SchedulerRunResponse)
def run_detective_arc_scheduler(payload: SchedulerRunRequest, request: Request) -> SchedulerRunResponse:
    actor_ids, spawned_actor = _resolve_actor_ids(payload, request)
    report = request.app.state.container.detective_arc_story_scheduler.run(goal=payload.goal, actors=actor_ids)
    _persist_arc_progress(report, request)
    return SchedulerRunResponse(
        story_id=report.story_id,
        goal=report.goal,
        status=report.status,
        results=[_map_action_result(item) for item in report.results],
        pending_steps=report.pending_steps,
        planner_name=report.planner_name,
        planner_source=report.planner_source,
        fallback_used=report.fallback_used,
        planner_detail=report.planner_detail,
        spawned_actor_id=spawned_actor.agent_id if spawned_actor else None,
        spawn_triggered=spawned_actor is not None,
    )
