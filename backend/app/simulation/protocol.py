from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.events import StoryEvent


@dataclass(slots=True)
class CapabilitySpec:
    name: str
    site: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool


@dataclass(slots=True)
class ActionRequest:
    action_id: str
    capability: str
    actor_id: str
    payload: dict[str, Any]
    idempotency_key: str


@dataclass(slots=True)
class ActionResult:
    action_id: str
    capability: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    facts: list[str] = field(default_factory=list)
    events: list[StoryEvent] = field(default_factory=list)
    pipeline: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class FactExecutionResult:
    capability: str
    site: str
    actor_id: str
    facts: list[str] = field(default_factory=list)
    events: list[StoryEvent] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    generation_context: dict[str, Any] = field(default_factory=dict)
    requires_content_generation: bool = False


@dataclass(slots=True)
class ContentGenerationRequest:
    capability: str
    site: str
    actor_id: str
    instruction: str
    desired_fields: list[str]
    fact_context: dict[str, Any] = field(default_factory=dict)
    style_context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GeneratedContent:
    fields: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    raw_response: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConsistencyCheckResult:
    passed: bool
    violations: list[str] = field(default_factory=list)
    normalized_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PublicationResult:
    output: dict[str, Any] = field(default_factory=dict)
    facts: list[str] = field(default_factory=list)
    events: list[StoryEvent] = field(default_factory=list)


@dataclass(slots=True)
class StoryStep:
    step_id: str
    capability: str
    actor_id: str
    payload: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass(slots=True)
class StoryPlan:
    story_id: str
    goal: str
    steps: list[StoryStep]
    planner_name: str = "unknown"
    planner_source: str = "unknown"
    fallback_used: bool = False
    planner_detail: str = ""


@dataclass(slots=True)
class SchedulerRunReport:
    story_id: str
    goal: str
    status: str
    results: list[ActionResult] = field(default_factory=list)
    pending_steps: list[str] = field(default_factory=list)
    planner_name: str = "unknown"
    planner_source: str = "unknown"
    fallback_used: bool = False
    planner_detail: str = ""
