from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import count
import random
import re
import time
from typing import Any

from app.domain.events import StoryEvent
from app.simulation.planner import AbstractStoryPlanner
from app.simulation.protocol import ActionRequest, ActionResult, CapabilitySpec, SchedulerRunReport, StoryPlan, StoryStep
from app.simulation.tool_registry import ToolRegistry


class StoryScheduler:
    _REFERENCE_KEY_ALIASES: dict[str, tuple[str, ...]] = {
        "file_id": ("share_id", "resource_id"),
        "page_slug": ("slug",),
        "webpage_slug": ("slug",),
    }

    def __init__(
        self,
        planner: AbstractStoryPlanner,
        tool_registry: ToolRegistry,
        *,
        publication_delay_probability: float = 0.0,
        publication_delay_min_seconds: float = 0.0,
        publication_delay_max_seconds: float = 0.0,
    ) -> None:
        self.planner = planner
        self.tool_registry = tool_registry
        self._action_counter = count(1)
        self.publication_delay_probability = max(0.0, min(1.0, publication_delay_probability))
        self.publication_delay_min_seconds = max(0.0, publication_delay_min_seconds)
        self.publication_delay_max_seconds = max(self.publication_delay_min_seconds, publication_delay_max_seconds)

    def run(self, *, goal: str, actors: list[str]) -> SchedulerRunReport:
        allowed_actors = set(actors)
        capabilities = self.tool_registry.list_capabilities()
        capability_map = {item.name: item for item in capabilities}
        try:
            plan = self.planner.build_story_plan(goal=goal, actors=actors, capabilities=capabilities)
            plan = self._augment_story_plan(plan=plan, actors=actors, capability_map=capability_map)
        except Exception as error:
            failure = ActionResult(
                action_id=f"action-{next(self._action_counter):05d}",
                capability="planner.build_story_plan",
                status="failed",
                error_code="llm_planner_failed",
                error_message=str(error),
                events=[
                    StoryEvent(
                        name="PlannerFailed",
                        detail="调度规划阶段失败，已取消本次请求。",
                        metadata={"goal": goal},
                    )
                ],
            )
            return SchedulerRunReport(
                story_id="planner-failed",
                goal=goal,
                status="failed",
                results=[failure],
                pending_steps=[],
                planner_name="siliconflow",
                planner_source="remote_llm",
                fallback_used=False,
                planner_detail="Planner failed after retry limit.",
            )
        completed_steps: set[str] = set()
        remaining_steps = {step.step_id: step for step in plan.steps}
        results: list[ActionResult] = []
        step_results: dict[str, ActionResult] = {}

        progressed = True
        while remaining_steps and progressed:
            progressed = False
            for step_id in list(remaining_steps.keys()):
                step = remaining_steps[step_id]
                if any(dep not in completed_steps for dep in step.depends_on):
                    continue

                if step.actor_id not in allowed_actors:
                    failure = ActionResult(
                        action_id=f"action-{next(self._action_counter):05d}",
                        capability=step.capability,
                        status="failed",
                        error_code="invalid_actor",
                        error_message=f"Step actor is not allowed or missing from SQL users: {step.actor_id}",
                        events=[
                            StoryEvent(
                                name="AgentIntentCreated",
                                detail="调度器已下发结构化动作请求。",
                                metadata={"story_id": plan.story_id, "step_id": step.step_id},
                            )
                        ],
                    )
                    results.append(failure)
                    return SchedulerRunReport(
                        story_id=plan.story_id,
                        goal=goal,
                        status="failed",
                        results=results,
                        pending_steps=list(remaining_steps.keys()),
                        planner_name=plan.planner_name,
                        planner_source=plan.planner_source,
                        fallback_used=plan.fallback_used,
                        planner_detail=plan.planner_detail,
                    )

                try:
                    resolved_payload = self._resolve_payload(step.payload, step_results)
                except ValueError as error:
                    failure = ActionResult(
                        action_id=f"action-{next(self._action_counter):05d}",
                        capability=step.capability,
                        status="failed",
                        error_code="unresolved_reference",
                        error_message=str(error),
                        events=[
                            StoryEvent(
                                name="AgentIntentCreated",
                                detail="调度器已下发结构化动作请求。",
                                metadata={"story_id": plan.story_id, "step_id": step.step_id},
                            )
                        ],
                    )
                    results.append(failure)
                    return SchedulerRunReport(
                        story_id=plan.story_id,
                        goal=goal,
                        status="failed",
                        results=results,
                        pending_steps=list(remaining_steps.keys()),
                        planner_name=plan.planner_name,
                        planner_source=plan.planner_source,
                        fallback_used=plan.fallback_used,
                        planner_detail=plan.planner_detail,
                    )

                action_id = f"action-{next(self._action_counter):05d}"
                request = ActionRequest(
                    action_id=action_id,
                    capability=step.capability,
                    actor_id=step.actor_id,
                    payload=resolved_payload,
                    idempotency_key=f"{plan.story_id}:{step.step_id}:{action_id}",
                )

                delay_seconds = self._compute_publication_delay_seconds(step.capability, capability_map)
                scheduled_publish_at = None
                if delay_seconds > 0:
                    scheduled_publish_at = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
                    time.sleep(delay_seconds)

                result = self.tool_registry.execute(request)
                result.events.insert(
                    0,
                    StoryEvent(
                        name="AgentIntentCreated",
                        detail="调度器已下发结构化动作请求。",
                        metadata={"story_id": plan.story_id, "step_id": step.step_id},
                    ),
                )
                if delay_seconds > 0 and scheduled_publish_at:
                    result.events.insert(
                        1,
                        StoryEvent(
                            name="PublicationDelayApplied",
                            detail="发布阶段已应用时间机制，内容在等待窗口后发布。",
                            metadata={
                                "story_id": plan.story_id,
                                "step_id": step.step_id,
                                "delay_seconds": f"{delay_seconds:.2f}",
                                "scheduled_publish_at": scheduled_publish_at,
                            },
                        ),
                    )
                results.append(result)

                if result.status == "success":
                    completed_steps.add(step_id)
                    step_results[step_id] = result
                    remaining_steps.pop(step_id)
                    progressed = True
                else:
                    return SchedulerRunReport(
                        story_id=plan.story_id,
                        goal=goal,
                        status="failed",
                        results=results,
                        pending_steps=list(remaining_steps.keys()),
                        planner_name=plan.planner_name,
                        planner_source=plan.planner_source,
                        fallback_used=plan.fallback_used,
                        planner_detail=plan.planner_detail,
                    )

        status = "success" if not remaining_steps else "partial"
        return SchedulerRunReport(
            story_id=plan.story_id,
            goal=goal,
            status=status,
            results=results,
            pending_steps=list(remaining_steps.keys()),
            planner_name=plan.planner_name,
            planner_source=plan.planner_source,
            fallback_used=plan.fallback_used,
            planner_detail=plan.planner_detail,
        )

    def _resolve_payload(self, payload: dict[str, Any], step_results: dict[str, ActionResult]) -> dict[str, Any]:
        return {key: self._resolve_value(value, step_results) for key, value in payload.items()}

    def _resolve_value(self, value: Any, step_results: dict[str, ActionResult]) -> Any:
        if isinstance(value, dict):
            return {key: self._resolve_value(item, step_results) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_value(item, step_results) for item in value]
        if not isinstance(value, str):
            return value

        stripped = value.strip()
        if not stripped:
            return value

        if stripped.startswith("${") and stripped.endswith("}"):
            stripped = stripped[2:-1]

        if stripped.startswith("$"):
            return self._resolve_reference_path(stripped[1:], step_results)

        legacy_match = re.match(r"^(thread|board|post)_from_(step[_-]\d+)$", stripped)
        if legacy_match:
            kind = legacy_match.group(1)
            step_id = legacy_match.group(2)
            return self._resolve_legacy_reference(kind, step_id, step_results)

        return value

    def _resolve_reference_path(self, reference: str, step_results: dict[str, ActionResult]) -> Any:
        parts = reference.split(".")
        if len(parts) < 2:
            raise ValueError(f"Invalid reference syntax: ${reference}")

        step_id = parts[0]
        result = step_results.get(step_id)
        if result is None:
            raise ValueError(f"Reference step not completed: {step_id}")

        current: Any = {"output": result.output, "facts": result.facts}
        for token in parts[1:]:
            current = self._extract_token(current, token, reference)
        return current

    def _extract_token(self, current: Any, token: str, reference: str) -> Any:
        token_match = re.match(r"^(\w+)(?:\[(\d+)\])?$", token)
        if not token_match:
            raise ValueError(f"Invalid reference token '{token}' in ${reference}")

        key = token_match.group(1)
        index = token_match.group(2)

        if not isinstance(current, dict):
            raise ValueError(f"Reference key '{key}' not found in ${reference}")

        resolved_key = key
        if key not in current:
            for alias in self._REFERENCE_KEY_ALIASES.get(key, ()):
                if alias in current:
                    resolved_key = alias
                    break

        if resolved_key not in current:
            raise ValueError(f"Reference key '{key}' not found in ${reference}")

        next_value = current[resolved_key]
        if index is not None:
            if not isinstance(next_value, list):
                raise ValueError(f"Reference target '{resolved_key}' is not a list in ${reference}")
            item_index = int(index)
            if item_index >= len(next_value):
                raise ValueError(f"Reference index out of range in ${reference}")
            return next_value[item_index]
        return next_value

    def _resolve_legacy_reference(self, kind: str, step_id: str, step_results: dict[str, ActionResult]) -> Any:
        result = step_results.get(step_id)
        if result is None:
            raise ValueError(f"Reference step not completed: {step_id}")

        if kind == "thread":
            return (
                result.output.get("thread_id")
                or result.output.get("thread", {}).get("id")
                or self._get_first_list_item_value(result.output.get("threads"), "id")
            )
        if kind == "board":
            return result.output.get("board", {}).get("slug") or result.output.get("board_id")
        if kind == "post":
            return result.output.get("post_id") or result.output.get("post", {}).get("id")
        raise ValueError(f"Unsupported legacy reference kind: {kind}")

    @staticmethod
    def _get_first_list_item_value(items: Any, key: str) -> Any:
        if not isinstance(items, list) or not items:
            return None
        first = items[0]
        if not isinstance(first, dict):
            return None
        return first.get(key)

    def _compute_publication_delay_seconds(
        self,
        capability_name: str,
        capability_map: dict[str, CapabilitySpec],
    ) -> float:
        capability = capability_map.get(capability_name)
        if capability is None or capability.read_only:
            return 0.0
        if self.publication_delay_max_seconds <= 0:
            return 0.0
        if random.random() > self.publication_delay_probability:
            return 0.0
        if self.publication_delay_max_seconds <= self.publication_delay_min_seconds:
            return self.publication_delay_min_seconds
        return random.uniform(self.publication_delay_min_seconds, self.publication_delay_max_seconds)

    def _augment_story_plan(
        self,
        *,
        plan: StoryPlan,
        actors: list[str],
        capability_map: dict[str, CapabilitySpec],
    ) -> StoryPlan:
        if not plan.steps:
            return plan

        by_capability: dict[str, list[StoryStep]] = {}
        for step in plan.steps:
            by_capability.setdefault(step.capability, []).append(step)

        if "forum.create_thread" not in by_capability:
            return plan

        extended_steps = list(plan.steps)
        created_thread_step = by_capability["forum.create_thread"][0]
        latest_step_id = extended_steps[-1].step_id

        if "forum.reply_thread" in capability_map:
            reply_actors = [actor for actor in actors if actor != created_thread_step.actor_id]
            for actor_id in reply_actors[:2]:
                next_step_id = self._next_step_id(extended_steps)
                extended_steps.append(
                    StoryStep(
                        step_id=next_step_id,
                        capability="forum.reply_thread",
                        actor_id=actor_id,
                        payload={
                            "thread_id": f"${created_thread_step.step_id}.output.thread_id",
                            "content": "Provide one concrete clue update and one open question for follow-up.",
                        },
                        depends_on=[latest_step_id],
                        rationale="补充多角色视角，形成连续讨论链。",
                    )
                )
                latest_step_id = next_step_id

        if "news.publish_article" in capability_map:
            existing_news_steps = by_capability.get("news.publish_article", [])
            if len(existing_news_steps) < 2:
                share_step = by_capability.get("netdisk.create_share_link", [None])[0]
                news_actor = actors[-1] if actors else created_thread_step.actor_id
                payload = {
                    "title": "Follow-up: Discussion Expands Around New Evidence",
                    "content": "Publish a follow-up that summarizes thread progress and unresolved points.",
                    "category": "investigation",
                    "related_thread_ids": [f"${created_thread_step.step_id}.output.thread_id"],
                }
                if share_step is not None:
                    payload["related_share_ids"] = [f"${share_step.step_id}.output.share_id"]

                next_step_id = self._next_step_id(extended_steps)
                extended_steps.append(
                    StoryStep(
                        step_id=next_step_id,
                        capability="news.publish_article",
                        actor_id=news_actor,
                        payload=payload,
                        depends_on=[latest_step_id],
                        rationale="增加后续新闻节点，避免故事只停留在开头。",
                    )
                )

        if len(extended_steps) == len(plan.steps):
            return plan

        return StoryPlan(
            story_id=plan.story_id,
            goal=plan.goal,
            steps=extended_steps,
            planner_name=plan.planner_name,
            planner_source=plan.planner_source,
            fallback_used=plan.fallback_used,
            planner_detail=f"{plan.planner_detail} Auto-augmented with discussion and follow-up steps.",
        )

    @staticmethod
    def _next_step_id(steps: list[StoryStep]) -> str:
        max_number = 0
        for step in steps:
            match = re.search(r"(\d+)$", step.step_id)
            if not match:
                continue
            max_number = max(max_number, int(match.group(1)))
        return f"step-{max_number + 1}"
