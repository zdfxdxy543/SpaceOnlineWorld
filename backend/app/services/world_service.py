from __future__ import annotations

import random

from app.domain.models import AgentProfile, AgentSummary, GeneratedPostDraft, SpaceLocation, WorldCharacter, WorldSnapshot
from app.schemas.world import DemoPostRequest
from app.services.generation_service import GenerationService
from app.simulation.engine import SimulationEngine
from app.repositories.world_repository import AbstractWorldRepository


class WorldService:
    def __init__(
        self,
        world_repository: AbstractWorldRepository,
        simulation_engine: SimulationEngine,
        generation_service: GenerationService,
    ) -> None:
        self.world_repository = world_repository
        self.simulation_engine = simulation_engine
        self.generation_service = generation_service

    def get_summary(self) -> WorldSnapshot:
        return self.world_repository.get_world_snapshot()

    def list_agents(self) -> list[AgentSummary]:
        return self.world_repository.list_agents()

    def agent_exists(self, agent_id: str) -> bool:
        return self.world_repository.agent_exists(agent_id)

    def get_agent(self, agent_id: str) -> AgentProfile:
        return self.world_repository.get_agent(agent_id)

    def maybe_spawn_random_agent(self, probability: float) -> AgentSummary | None:
        if probability <= 0:
            return None
        if random.random() > probability:
            return None
        return self.world_repository.create_random_agent()

    def list_world_characters(self) -> list[WorldCharacter]:
        return self.world_repository.list_world_characters()

    def list_space_locations(self) -> list[SpaceLocation]:
        return self.world_repository.list_space_locations()

    def expand_space_locations(self, *, probability: float, max_new_locations: int) -> list[SpaceLocation]:
        clamped_probability = max(0.0, min(1.0, probability))
        limit = max(0, max_new_locations)
        return self.world_repository.expand_space_locations(
            probability=clamped_probability,
            max_new_locations=limit,
        )

    def create_demo_post(self, payload: DemoPostRequest) -> GeneratedPostDraft:
        plan = self.simulation_engine.prepare_demo_post(
            agent_id=payload.agent_id,
            site_id=payload.site_id,
            topic=payload.topic,
            attach_cloud_file=payload.attach_cloud_file,
        )
        return self.generation_service.generate_post(plan)
