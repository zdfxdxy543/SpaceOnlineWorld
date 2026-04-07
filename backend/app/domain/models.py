from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.events import StoryEvent


@dataclass(slots=True)
class AgentProfile:
    agent_id: str
    display_name: str
    role: str
    goals: list[str]


@dataclass(slots=True)
class AgentSummary:
    agent_id: str
    display_name: str
    status: str
    gender: str
    age_range: str
    occupation: str
    residence_city: str
    native_language: str
    personality_traits_json: str
    values_json: str
    hobbies_json: str


@dataclass(slots=True)
class WorldCharacter:
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


@dataclass(slots=True)
class SpaceLocation:
    location_id: str
    name: str
    location_type: str
    region: str
    description: str
    discovered_at: str
    discovery_source: str
    parent_location_id: str | None
    expansion_tier: int
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class WorldResource:
    resource_id: str
    resource_type: str
    title: str
    access_code: str
    owner_agent_id: str
    site_id: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class WorldSnapshot:
    current_tick: int
    current_time_label: str
    active_sites: list[str]
    recent_events: list[StoryEvent]


@dataclass(slots=True)
class DraftPostPlan:
    draft_id: str
    site_id: str
    topic: str
    agent: AgentProfile
    referenced_resource: WorldResource | None
    facts: list[str]
    event_trace: list[StoryEvent]


@dataclass(slots=True)
class GeneratedPostDraft:
    draft_id: str
    content: str
    consistency_passed: bool
    violations: list[str]
    event_trace: list[StoryEvent]
    referenced_resource: WorldResource | None
    facts: list[str]


@dataclass(slots=True)
class Category:
    slug: str
    name: str
    description: str


@dataclass(slots=True)
class Product:
    product_id: str
    name: str
    description: str
    price: float
    category: str
    stock: int
    seller_id: str
    created_at: str = field(default_factory=lambda: "2000-01-01T00:00:00")
    updated_at: str = field(default_factory=lambda: "2000-01-01T00:00:00")


@dataclass(slots=True)
class Order:
    order_id: str
    product_id: str
    quantity: int
    buyer_id: str
    seller_id: str
    total_price: float
    status: str
    created_at: str = field(default_factory=lambda: "2000-01-01T00:00:00")
