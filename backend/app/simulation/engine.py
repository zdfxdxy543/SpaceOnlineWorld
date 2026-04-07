from __future__ import annotations

from itertools import count

from app.domain.events import StoryEvent
from app.domain.models import DraftPostPlan, WorldResource
from app.repositories.world_repository import AbstractWorldRepository


class SimulationEngine:
    def __init__(self, world_repository: AbstractWorldRepository) -> None:
        self.world_repository = world_repository
        self._draft_counter = count(1)

    def prepare_demo_post(self, *, agent_id: str, site_id: str, topic: str, attach_cloud_file: bool) -> DraftPostPlan:
        agent = self.world_repository.get_agent(agent_id)
        resource: WorldResource | None = None
        facts = [
            f"发帖人={agent.display_name}",
            f"角色定位={agent.role}",
            f"发布站点={site_id}",
            f"主题={topic}",
        ]
        event_trace = [
            StoryEvent(
                name="AgentIntentCreated",
                detail="角色提交了一次跨站发帖意图。",
                metadata={"agent_id": agent_id, "site_id": site_id},
            )
        ]

        if attach_cloud_file:
            resource = self.world_repository.create_cloud_resource(
                owner_agent_id=agent.agent_id,
                site_id="cloud.drive",
                title=f"{topic} - 附件",
            )
            facts.extend(
                [
                    f"已创建共享文件ID={resource.resource_id}",
                    f"共享文件提取码={resource.access_code}",
                ]
            )
            event_trace.append(
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="系统已先创建网盘文件，再允许角色对外发文。",
                    metadata={"resource_id": resource.resource_id},
                )
            )

        event_trace.append(
            StoryEvent(
                name="FactPersisted",
                detail="结构化事实已准备完成，可供文本生成阶段读取。",
                metadata={"fact_count": str(len(facts))},
            )
        )

        draft_id = f"draft-{next(self._draft_counter):04d}"
        return DraftPostPlan(
            draft_id=draft_id,
            site_id=site_id,
            topic=topic,
            agent=agent,
            referenced_resource=resource,
            facts=facts,
            event_trace=event_trace,
        )
