from __future__ import annotations

from app.consistency.checker import ConsistencyChecker
from app.domain.events import StoryEvent
from app.domain.models import DraftPostPlan, GeneratedPostDraft
from app.infrastructure.llm.base import AbstractLLMClient


class GenerationService:
    def __init__(self, llm_client: AbstractLLMClient, consistency_checker: ConsistencyChecker) -> None:
        self.llm_client = llm_client
        self.consistency_checker = consistency_checker

    def generate_post(self, plan: DraftPostPlan) -> GeneratedPostDraft:
        content = self.llm_client.generate_forum_post(plan)
        event_trace = list(plan.event_trace)
        event_trace.append(
            StoryEvent(
                name="ContentDraftGenerated",
                detail="LLM 已基于结构化事实生成帖子草稿。",
                metadata={"draft_id": plan.draft_id},
            )
        )
        violations = self.consistency_checker.validate_post_content(plan, content)
        event_trace.append(
            StoryEvent(
                name="ConsistencyCheckPassed" if not violations else "ConsistencyCheckFailed",
                detail="草稿一致性校验已完成。",
                metadata={"violations": ",".join(violations) or "none"},
            )
        )
        if not violations:
            event_trace.append(
                StoryEvent(
                    name="ContentPublished",
                    detail="草稿已满足最小一致性要求，可进入发布流程。",
                    metadata={"draft_id": plan.draft_id},
                )
            )

        return GeneratedPostDraft(
            draft_id=plan.draft_id,
            content=content,
            consistency_passed=not violations,
            violations=violations,
            event_trace=event_trace,
            referenced_resource=plan.referenced_resource,
            facts=plan.facts,
        )
