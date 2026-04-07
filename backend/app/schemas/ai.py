from __future__ import annotations

from pydantic import BaseModel, Field


class CapabilitySpecResponse(BaseModel):
    name: str
    site: str
    description: str
    input_schema: dict
    read_only: bool


class ActorSummaryResponse(BaseModel):
    id: str
    name: str
    status: str
    gender: str
    age_range: str
    occupation: str
    residence_city: str
    native_language: str
    personality_traits: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)


class ActionExecuteRequest(BaseModel):
    capability: str
    actor_id: str
    payload: dict = Field(default_factory=dict)
    idempotency_key: str


class StoryEventResponse(BaseModel):
    name: str
    detail: str
    metadata: dict[str, str]
    occurred_at: str


class ActionExecuteResponse(BaseModel):
    action_id: str
    capability: str
    status: str
    output: dict
    facts: list[str]
    events: list[StoryEventResponse]
    pipeline: dict = Field(default_factory=dict)
    error_code: str | None
    error_message: str | None


class SchedulerRunRequest(BaseModel):
    goal: str
    actors: list[str] = Field(default_factory=list)


class SchedulerRunResponse(BaseModel):
    story_id: str
    goal: str
    status: str
    results: list[ActionExecuteResponse]
    pending_steps: list[str]
    planner_name: str
    planner_source: str
    fallback_used: bool = False
    planner_detail: str = ""
    spawned_actor_id: str | None = None
    spawn_triggered: bool = False
