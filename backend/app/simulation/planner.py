from __future__ import annotations

from abc import ABC, abstractmethod
from itertools import count
import random
import re

from app.simulation.protocol import CapabilitySpec, StoryPlan, StoryStep


class AbstractStoryPlanner(ABC):
    @abstractmethod
    def build_story_plan(
        self,
        *,
        goal: str,
        actors: list[str],
        capabilities: list[CapabilitySpec],
    ) -> StoryPlan:
        raise NotImplementedError


def _should_enable_image_generation(*, goal: str, default: bool) -> bool:
    normalized = re.sub(r"\s+", " ", goal.strip().lower())
    if not normalized:
        return default

    disabled_keywords = (
        "no image",
        "without image",
        "text only",
        "plain text",
        "不需要图片",
        "不要图片",
        "无需图片",
        "纯文字",
    )
    if any(keyword in normalized for keyword in disabled_keywords):
        return False

    enabled_keywords = (
        "image",
        "picture",
        "photo",
        "illustration",
        "poster",
        "封面",
        "插图",
        "图片",
        "配图",
    )
    if any(keyword in normalized for keyword in enabled_keywords):
        return True

    return default


class RuleBasedStoryPlanner(AbstractStoryPlanner):
    _SUSPICIOUS_SCENARIOS = [
        {
            "file_title": "Warehouse Movement Log",
            "file_name": "warehouse_timeline.txt",
            "purpose": "Archive late-night movement, light changes, and timing anomalies near the old warehouse.",
            "thread_title": "[Evidence] Warehouse lights after curfew",
            "thread_content": "Collected notes suggest repeated movement around the old warehouse after closing hours.",
            "tags": ["evidence", "warehouse", "timeline"],
        },
        {
            "file_title": "Dockside Transfer Notes",
            "file_name": "dock_transfer_log.txt",
            "purpose": "Record suspicious dockside handoff timing and vehicle movement for later cross-checking.",
            "thread_title": "[Evidence] Unscheduled dockside handoff",
            "thread_content": "I compiled a short record of an unscheduled transfer near the dock. The timing does not match routine deliveries.",
            "tags": ["evidence", "dock", "transfer"],
        },
        {
            "file_title": "Witness Corridor Memo",
            "file_name": "witness_corridor_memo.txt",
            "purpose": "Preserve witness-style notes about repeated hallway meetings and abrupt departures.",
            "thread_title": "[Witness Notes] Repeated corridor meetings",
            "thread_content": "This memo collects consistent observations about the same pair meeting briefly and leaving by separate exits.",
            "tags": ["witness", "memo", "suspicious"],
        },
        {
            "file_title": "Transit Timeline Extract",
            "file_name": "transit_timeline.txt",
            "purpose": "Track suspicious transit timing gaps and cross-reference them against reported sightings.",
            "thread_title": "[Timeline] Transit gap around reported sighting",
            "thread_content": "The timeline below highlights a service gap that overlaps with the reported sighting window.",
            "tags": ["timeline", "transit", "evidence"],
        },
    ]

    def __init__(self) -> None:
        self._story_counter = count(1)

    def build_story_plan(
        self,
        *,
        goal: str,
        actors: list[str],
        capabilities: list[CapabilitySpec],
    ) -> StoryPlan:
        if not actors:
            actors = ["aria"]

        actor = actors[0]
        capability_names = {cap.name for cap in capabilities}
        steps: list[StoryStep] = []
        story_number = next(self._story_counter)
        scenario = self._select_suspicious_scenario(goal=goal, story_number=story_number)

        if "forum.read_board" in capability_names:
            steps.append(
                StoryStep(
                    step_id="step-1",
                    capability="forum.read_board",
                    actor_id=actor,
                    payload={"board_slug": "town-square", "limit": 10},
                    rationale="先读取公共上下文，减少知识越界风险。",
                )
            )

        should_generate_image = _should_enable_image_generation(goal=goal, default=True)

        # 插入图片生成步骤（按目标与能力决定）
        image_cap = None
        if should_generate_image and "image.generate" in capability_names:
            image_cap = StoryStep(
                step_id="step-img-1",
                capability="image.generate",
                actor_id=actor,
                payload={
                    "prompt": scenario["thread_title"] + " " + scenario["thread_content"][:40],
                    "width": 512,
                    "height": 512,
                },
                depends_on=["step-1"] if steps else [],
                rationale="为帖子生成配图。",
            )
            steps.append(image_cap)
            image_dep = [image_cap.step_id]
        else:
            image_dep = ["step-1"] if steps else []

        if {"netdisk.upload_file", "netdisk.create_share_link", "forum.create_thread"}.issubset(capability_names):
            steps.append(
                StoryStep(
                    step_id="step-2",
                    capability="netdisk.upload_file",
                    actor_id=actor,
                    payload={
                        "title": scenario["file_title"],
                        "purpose": scenario["purpose"],
                        "file_name": scenario["file_name"],
                    },
                    depends_on=image_dep,
                    rationale="先生成可追溯证据文件。",
                )
            )
            steps.append(
                StoryStep(
                    step_id="step-3",
                    capability="netdisk.create_share_link",
                    actor_id=actor,
                    payload={
                        "resource_id": "$step-2.output.resource_id",
                    },
                    depends_on=["step-2"],
                    rationale="创建分享链接与提取码供论坛引用。",
                )
            )
            steps.append(
                StoryStep(
                    step_id="step-4",
                    capability="forum.create_thread",
                    actor_id=actor,
                    payload={
                        "board_slug": "town-square",
                        "title": scenario["thread_title"],
                        "content": scenario["thread_content"],
                        "tags": scenario["tags"],
                        "image_url": "$step-img-1.output.image_url" if image_cap else None,
                        "netdisk_share_id": "$step-3.output.share_id",
                        "netdisk_access_code": "$step-3.output.access_code",
                    },
                    depends_on=["step-3"],
                    rationale="在帖子中引用真实可访问的网盘证据和图片。",
                )
            )
        elif "forum.create_thread" in capability_names:
            steps.append(
                StoryStep(
                    step_id="step-2",
                    capability="forum.create_thread",
                    actor_id=actor,
                    payload={
                        "board_slug": "town-square",
                        "title": scenario["thread_title"],
                        "content": scenario["thread_content"],
                        "tags": scenario["tags"],
                        "image_url": "$step-img-1.output.image_url" if image_cap else None,
                    },
                    depends_on=image_dep,
                    rationale="建立可追踪的初始事件节点并插入图片。",
                )
            )

        story_id = f"story-{story_number:04d}"
        return StoryPlan(
            story_id=story_id,
            goal=goal,
            steps=steps,
            planner_name="rule_based",
            planner_source="local_rule",
            fallback_used=False,
            planner_detail="Plan generated by the built-in deterministic rule-based planner.",
        )

    def _select_suspicious_scenario(self, *, goal: str, story_number: int) -> dict[str, object]:
        normalized_goal = re.sub(r"\s+", " ", goal.strip().lower())
        keyword_map = {
            "warehouse": 0,
            "dock": 1,
            "witness": 2,
            "transit": 3,
            "station": 3,
        }
        for keyword, index in keyword_map.items():
            if keyword in normalized_goal:
                return self._SUSPICIOUS_SCENARIOS[index]

        if any(phrase in normalized_goal for phrase in ["generate a story", "something suspicious", "suspicious"]):
            return self._SUSPICIOUS_SCENARIOS[(story_number - 1) % len(self._SUSPICIOUS_SCENARIOS)]

        return {
            "file_title": "Field Notes Archive",
            "file_name": "field_notes.txt",
            "purpose": f"Preserve notes related to: {goal.strip() or 'unusual activity'}.",
            "thread_title": "[Story Seed] Unusual activity under review",
            "thread_content": "I collected a short set of notes about an unusual pattern worth reviewing.",
            "tags": ["story", "seed"],
        }


class LifeEventStoryPlanner(AbstractStoryPlanner):
    _LIFE_EVENTS = [
        {
            "title": "[Daily] Morning Market Was Crowded",
            "content": "The market opened early and lines were longer than usual. Prices stayed stable, but everyone discussed the weather shift.",
            "tags": ["daily", "market", "community"],
        },
        {
            "title": "[Daily] Neighborhood Cleanup This Weekend",
            "content": "Several neighbors proposed a cleanup walk this weekend. People are sharing tools and meeting points.",
            "tags": ["daily", "neighborhood", "event"],
        },
        {
            "title": "[Daily] Bus Schedule Updated Near Station",
            "content": "The station posted a minor schedule update. Commuters are comparing the new timing and planning alternatives.",
            "tags": ["daily", "transit", "notice"],
        },
        {
            "title": "[Daily] Community Kitchen Added Evening Slot",
            "content": "The community kitchen added an evening slot this week. Volunteers are coordinating ingredient pickup.",
            "tags": ["daily", "community", "kitchen"],
        },
    ]

    def __init__(
        self,
        *,
        netdisk_probability: float = 0.15,
        news_probability: float = 0.10,
    ) -> None:
        self._story_counter = count(1)
        self.netdisk_probability = max(0.0, min(1.0, netdisk_probability))
        self.news_probability = max(0.0, min(1.0, news_probability))

    def build_story_plan(
        self,
        *,
        goal: str,
        actors: list[str],
        capabilities: list[CapabilitySpec],
    ) -> StoryPlan:
        if not actors:
            actors = ["aria"]

        capability_names = {cap.name for cap in capabilities}
        story_number = next(self._story_counter)
        event = self._LIFE_EVENTS[(story_number - 1) % len(self._LIFE_EVENTS)]
        if goal.strip():
            event = {
                "title": "[Daily] Community Update",
                "content": f"Residents are discussing: {goal.strip()}",
                "tags": ["daily", "community"],
            }

        primary_actor = actors[0]
        secondary_actor = actors[1] if len(actors) > 1 else primary_actor
        tertiary_actor = actors[2] if len(actors) > 2 else secondary_actor

        rng = random.Random(f"life-{story_number}-{goal.strip().lower()}-{','.join(actors)}")
        steps: list[StoryStep] = []

        if "forum.create_thread" not in capability_names:
            return StoryPlan(
                story_id=f"life-story-{story_number:04d}",
                goal=goal,
                steps=[],
                planner_name="life_event_rule",
                planner_source="local_rule",
                fallback_used=False,
                planner_detail="No forum.create_thread capability available for life-event planner.",
            )

        should_generate_image = _should_enable_image_generation(goal=goal, default=True)

        # 插入图片生成步骤（按目标与能力决定）
        image_cap = None
        if should_generate_image and "image.generate" in capability_names:
            image_cap = StoryStep(
                step_id="step-img-1",
                capability="image.generate",
                actor_id=primary_actor,
                payload={
                    "prompt": event["title"] + " " + event["content"][:40],
                    "width": 512,
                    "height": 512,
                },
                rationale="为生活主题帖生成配图。",
            )
            steps.append(image_cap)
            image_dep = [image_cap.step_id]
        else:
            image_dep = []

        steps.append(
            StoryStep(
                step_id="step-1",
                capability="forum.create_thread",
                actor_id=primary_actor,
                payload={
                    "board_slug": "town-square",
                    "title": event["title"],
                    "content": event["content"],
                    "tags": event["tags"],
                    "image_url": "$step-img-1.output.image_url" if image_cap else None,
                },
                depends_on=image_dep,
                rationale="发布一个生活化主题帖，作为讨论起点并插入图片。",
            )
        )

        next_index = 2
        reply_count = 2 if len(actors) >= 3 else 1
        if "forum.reply_thread" in capability_names:
            reply_actors = [secondary_actor, tertiary_actor][:reply_count]
            for reply_actor in reply_actors:
                steps.append(
                    StoryStep(
                        step_id=f"step-{next_index}",
                        capability="forum.reply_thread",
                        actor_id=reply_actor,
                        payload={
                            "thread_id": "$step-1.output.thread_id",
                            "content": "Share one practical detail from daily experience and one suggestion for neighbors.",
                        },
                        depends_on=[f"step-{next_index - 1}"] if next_index > 2 else ["step-1"],
                        rationale="让不同角色参与生活讨论，增加真实互动感。",
                    )
                )
                next_index += 1

        social_post_step_id: str | None = None
        if "social.create_post" in capability_names:
            social_depends_on = [steps[-1].step_id] if steps else []
            steps.append(
                StoryStep(
                    step_id=f"step-{next_index}",
                    capability="social.create_post",
                    actor_id=primary_actor,
                    payload={
                        "content": event["content"],
                        "tags": event["tags"],
                        "image_url": "$step-img-1.output.image_url" if image_cap else None,
                    },
                    depends_on=social_depends_on,
                    rationale="同步生成更适合社交首页的生活动态并插入图片。",
                )
            )
            social_post_step_id = f"step-{next_index}"
            next_index += 1

        if social_post_step_id and "social.reply_post" in capability_names:
            reply_actors = [secondary_actor, tertiary_actor][:reply_count]
            for reply_actor in reply_actors:
                steps.append(
                    StoryStep(
                        step_id=f"step-{next_index}",
                        capability="social.reply_post",
                        actor_id=reply_actor,
                        payload={
                            "post_id": f"${social_post_step_id}.output.post_id",
                            "content": "Add a short, friendly response that reflects the shared daily update.",
                        },
                        depends_on=[social_post_step_id],
                        rationale="补足社交媒体式的轻量互动。",
                    )
                )
                next_index += 1

        share_step_id: str | None = None
        if (
            {"netdisk.upload_file", "netdisk.create_share_link", "forum.create_thread"}.issubset(capability_names)
            and rng.random() < self.netdisk_probability
        ):
            upload_step_id = f"step-{next_index}"
            steps.append(
                StoryStep(
                    step_id=upload_step_id,
                    capability="netdisk.upload_file",
                    actor_id=primary_actor,
                    payload={
                        "title": "Daily Notes Attachment",
                        "purpose": "Store a simple life-event note for anyone who wants details.",
                        "file_name": "daily_notes.txt",
                    },
                    depends_on=[steps[-1].step_id],
                    rationale="低概率附加网盘材料，保留生活主题为主。",
                )
            )
            next_index += 1

            share_step_id = f"step-{next_index}"
            steps.append(
                StoryStep(
                    step_id=share_step_id,
                    capability="netdisk.create_share_link",
                    actor_id=primary_actor,
                    payload={"resource_id": f"${upload_step_id}.output.resource_id"},
                    depends_on=[upload_step_id],
                    rationale="创建低频分享链接，供后续引用。",
                )
            )
            next_index += 1

            steps.append(
                StoryStep(
                    step_id=f"step-{next_index}",
                    capability="forum.create_thread",
                    actor_id=secondary_actor,
                    payload={
                        "board_slug": "town-square",
                        "title": "[Daily Follow-up] Details and Community Responses",
                        "content": "Follow-up summary for residents who asked for more context.",
                        "tags": ["daily", "follow-up"],
                        "netdisk_share_id": f"${share_step_id}.output.share_id",
                        "netdisk_access_code": f"${share_step_id}.output.access_code",
                    },
                    depends_on=[share_step_id],
                    rationale="将网盘引用放在后续帖，避免主流程过重。",
                )
            )
            next_index += 1

        if "news.publish_article" in capability_names and rng.random() < self.news_probability:
            news_dep = steps[-1].step_id
            related_share_ids = [f"${share_step_id}.output.share_id"] if share_step_id else []
            steps.append(
                StoryStep(
                    step_id=f"step-{next_index}",
                    capability="news.publish_article",
                    actor_id=tertiary_actor,
                    payload={
                        "title": "Community Brief: Daily Events Roundup",
                        "content": "Short daily roundup based on ongoing forum discussions.",
                        "category": "community",
                        "is_pinned": False,
                        "related_thread_ids": ["$step-1.output.thread_id"],
                        "related_share_ids": related_share_ids,
                    },
                    depends_on=[news_dep],
                    rationale="低概率生成新闻摘要，保持论坛生活流为主。",
                )
            )

        return StoryPlan(
            story_id=f"life-story-{story_number:04d}",
            goal=goal,
            steps=steps,
            planner_name="life_event_rule",
            planner_source="local_rule",
            fallback_used=False,
            planner_detail="Simple life-event planner with low netdisk/news trigger probabilities.",
        )


class OngoingLifeArcPlanner(AbstractStoryPlanner):
    def __init__(
        self,
        *,
        story_arc_service,
        reveal_after_hours: float = 1.0,
        news_resolution_probability: float = 0.35,
    ) -> None:
        self.story_arc_service = story_arc_service
        self.reveal_after_hours = max(0.0, reveal_after_hours)
        self.news_resolution_probability = max(0.0, min(1.0, news_resolution_probability))
        self._story_counter = count(1)

    def build_story_plan(
        self,
        *,
        goal: str,
        actors: list[str],
        capabilities: list[CapabilitySpec],
    ) -> StoryPlan:
        if not actors:
            actors = ["aria"]

        capability_names = {cap.name for cap in capabilities}
        arc = self.story_arc_service.get_or_create_open_arc(goal=goal, reveal_after_hours=self.reveal_after_hours)
        phase = self.story_arc_service.determine_phase(arc)
        run_no = next(self._story_counter)
        primary_actor = actors[0]
        secondary_actor = actors[1] if len(actors) > 1 else primary_actor
        tertiary_actor = actors[2] if len(actors) > 2 else secondary_actor

        steps: list[StoryStep] = []

        if "forum.create_thread" not in capability_names:
            return StoryPlan(
                story_id=f"life-arc-{arc.arc_id}-run-{run_no:04d}",
                goal=goal,
                steps=[],
                planner_name="ongoing_life_arc",
                planner_source="local_rule",
                fallback_used=False,
                planner_detail="forum.create_thread not available for ongoing arc planner.",
            )

        if phase == "discovery":
            steps.append(
                StoryStep(
                    step_id="step-1",
                    capability="forum.create_thread",
                    actor_id=primary_actor,
                    payload={
                        "board_slug": "town-square",
                        "title": "[Ongoing] Something Feels Off In Daily Routine",
                        "content": "I noticed a pattern today, but the full explanation is still missing. Sharing clues first.",
                        "tags": ["ongoing", "discovery", "daily"],
                    },
                    rationale="第一阶段只抛出问题，不给结论。",
                )
            )
            if "forum.reply_thread" in capability_names:
                steps.append(
                    StoryStep(
                        step_id="step-2",
                        capability="forum.reply_thread",
                        actor_id=secondary_actor,
                        payload={
                            "thread_id": "$step-1.output.thread_id",
                            "content": "I can confirm part of this, but we still need one more cycle of observation.",
                        },
                        depends_on=["step-1"],
                        rationale="制造第一轮讨论与悬念。",
                    )
                )

        elif phase == "investigation":
            if arc.clue_thread_id:
                if "forum.reply_thread" in capability_names:
                    steps.append(
                        StoryStep(
                            step_id="step-1",
                            capability="forum.reply_thread",
                            actor_id=secondary_actor,
                            payload={
                                "thread_id": arc.clue_thread_id,
                                "content": "New observations arrived, but they still do not fully explain what happened.",
                            },
                            rationale="中间阶段继续调查，仍不揭晓答案。",
                        )
                    )
                    steps.append(
                        StoryStep(
                            step_id="step-2",
                            capability="forum.reply_thread",
                            actor_id=tertiary_actor,
                            payload={
                                "thread_id": arc.clue_thread_id,
                                "content": "We should verify one final detail in the next cycle before making a conclusion.",
                            },
                            depends_on=["step-1"],
                            rationale="让观众在本周期仍看不到最终答案。",
                        )
                    )
            else:
                steps.append(
                    StoryStep(
                        step_id="step-1",
                        capability="forum.create_thread",
                        actor_id=primary_actor,
                        payload={
                            "board_slug": "town-square",
                            "title": "[Ongoing] Investigation Continues",
                            "content": "Previous clues exist, but we still need more time before conclusions.",
                            "tags": ["ongoing", "investigation"],
                        },
                        rationale="缺少历史线索帖时，补建调查帖。",
                    )
                )

        else:
            # resolution phase
            if arc.clue_thread_id and "forum.reply_thread" in capability_names:
                steps.append(
                    StoryStep(
                        step_id="step-1",
                        capability="forum.reply_thread",
                        actor_id=secondary_actor,
                        payload={
                            "thread_id": arc.clue_thread_id,
                            "content": "Final check complete: we can now explain the event and close the investigation.",
                        },
                        rationale="在原线索帖下给出最终解释。",
                    )
                )

            rng = random.Random(f"arc-resolution-{arc.arc_id}-{goal.strip().lower()}")
            should_publish_news = "news.publish_article" in capability_names and rng.random() < self.news_resolution_probability

            if should_publish_news and arc.clue_thread_id:
                depends = [steps[-1].step_id] if steps else []
                steps.append(
                    StoryStep(
                        step_id=f"step-{len(steps) + 1}",
                        capability="news.publish_article",
                        actor_id=tertiary_actor,
                        payload={
                            "title": "Resolution Update: Daily Incident Explained",
                            "content": "This update closes the ongoing event with verified findings and practical takeaways.",
                            "category": "community",
                            "is_pinned": False,
                            "related_thread_ids": [arc.clue_thread_id],
                            "related_share_ids": [arc.related_share_id] if arc.related_share_id else [],
                        },
                        depends_on=depends,
                        rationale="在下一调度周期发布最终结果。",
                    )
                )
            else:
                depends = [steps[-1].step_id] if steps else []
                steps.append(
                    StoryStep(
                        step_id=f"step-{len(steps) + 1}",
                        capability="forum.create_thread",
                        actor_id=tertiary_actor,
                        payload={
                            "board_slug": "town-square",
                            "title": "[Result] Follow-up Conclusion",
                            "content": "Final outcome is now available. This thread summarizes what actually happened and why.",
                            "tags": ["result", "follow-up", "ongoing"],
                        },
                        depends_on=depends,
                        rationale="不用新闻时，改为另一个角色发布结果帖。",
                    )
                )

        # Add lightweight social mirrors so arc schedulers can also use social site capabilities.
        social_post_step_id: str | None = None
        next_index = len(steps) + 1
        if "social.create_post" in capability_names:
            social_depends_on = [steps[-1].step_id] if steps else []
            social_content_map = {
                "discovery": "Something in daily life still feels unusual. Sharing the first clue and watching for more updates.",
                "investigation": "Investigation is ongoing. We found partial evidence, but one key detail is still unresolved.",
                "resolution": "Final verification is complete. Summary is now available and the ongoing issue is considered closed.",
            }
            social_post_step_id = f"step-{next_index}"
            steps.append(
                StoryStep(
                    step_id=social_post_step_id,
                    capability="social.create_post",
                    actor_id=primary_actor,
                    payload={
                        "content": social_content_map.get(phase, "Daily update posted."),
                        "tags": ["ongoing", "daily", phase],
                    },
                    depends_on=social_depends_on,
                    rationale="为持续剧情同步一条社交动态，覆盖社交网页工具链。",
                )
            )
            next_index += 1

        if social_post_step_id and "social.reply_post" in capability_names:
            steps.append(
                StoryStep(
                    step_id=f"step-{next_index}",
                    capability="social.reply_post",
                    actor_id=secondary_actor,
                    payload={
                        "post_id": f"${social_post_step_id}.output.post_id",
                        "content": "Thanks for the update. I can confirm parts of this and will keep tracking the next clue.",
                    },
                    depends_on=[social_post_step_id],
                    rationale="补充社交站点的轻量互动，确保回帖能力可被调度。",
                )
            )

        return StoryPlan(
            story_id=f"life-arc-{arc.arc_id}-phase-{phase}-run-{run_no:04d}",
            goal=goal,
            steps=steps,
            planner_name="ongoing_life_arc",
            planner_source="local_rule",
            fallback_used=False,
            planner_detail=f"Ongoing arc planner phase={phase}, reveal_after={arc.reveal_after}.",
        )


class OngoingDetectiveArcPlanner(AbstractStoryPlanner):
    def __init__(
        self,
        *,
        story_arc_service,
        reveal_after_hours: float = 1.0,
        resolution_news_probability: float = 0.55,
        netdisk_probability: float = 0.65,
    ) -> None:
        self.story_arc_service = story_arc_service
        self.reveal_after_hours = max(0.0, reveal_after_hours)
        self.resolution_news_probability = max(0.0, min(1.0, resolution_news_probability))
        self.netdisk_probability = max(0.0, min(1.0, netdisk_probability))
        self._story_counter = count(1)

    def build_story_plan(
        self,
        *,
        goal: str,
        actors: list[str],
        capabilities: list[CapabilitySpec],
    ) -> StoryPlan:
        if not actors:
            actors = ["aria"]

        normalized_goal = goal.strip() or "Unexplained town incident under investigation"
        arc_goal = normalized_goal if normalized_goal.lower().startswith("detective:") else f"detective: {normalized_goal}"

        capability_names = {cap.name for cap in capabilities}
        arc = self.story_arc_service.get_or_create_open_arc(goal=arc_goal, reveal_after_hours=self.reveal_after_hours)
        phase = self.story_arc_service.determine_phase(arc)
        run_no = next(self._story_counter)

        investigator = actors[0]
        witness = actors[1] if len(actors) > 1 else investigator
        analyst = actors[2] if len(actors) > 2 else witness

        rng = random.Random(f"detective-{arc.arc_id}-{phase}-{normalized_goal.lower()}")
        steps: list[StoryStep] = []

        can_forum = "forum.create_thread" in capability_names
        can_reply = "forum.reply_thread" in capability_names
        can_upload = "netdisk.upload_file" in capability_names
        can_share = "netdisk.create_share_link" in capability_names
        can_news = "news.publish_article" in capability_names

        if not can_forum:
            return StoryPlan(
                story_id=f"detective-arc-{arc.arc_id}-run-{run_no:04d}",
                goal=goal,
                steps=[],
                planner_name="ongoing_detective_arc",
                planner_source="local_rule",
                fallback_used=False,
                planner_detail="forum.create_thread not available for detective arc planner.",
            )

        share_step_id: str | None = None
        if phase == "discovery":
            steps.append(
                StoryStep(
                    step_id="step-1",
                    capability="forum.create_thread",
                    actor_id=investigator,
                    payload={
                        "board_slug": "town-square",
                        "title": "[Case Opened] Unresolved Clue Appeared Overnight",
                        "content": "A suspicious clue was found, but no verified explanation is available yet. Opening a structured investigation thread.",
                        "tags": ["detective", "case-open", "clue"],
                    },
                    rationale="第一轮只开案和抛线索，不给答案。",
                )
            )

            if can_upload and can_share and rng.random() < self.netdisk_probability:
                steps.append(
                    StoryStep(
                        step_id="step-2",
                        capability="netdisk.upload_file",
                        actor_id=investigator,
                        payload={
                            "title": "Case Evidence Snapshot",
                            "purpose": "Store first-round evidence notes for investigation continuity.",
                            "file_name": "case_evidence_round1.txt",
                        },
                        depends_on=["step-1"],
                        rationale="高概率附加证据文件，但仍不揭晓结论。",
                    )
                )
                steps.append(
                    StoryStep(
                        step_id="step-3",
                        capability="netdisk.create_share_link",
                        actor_id=investigator,
                        payload={"resource_id": "$step-2.output.resource_id"},
                        depends_on=["step-2"],
                        rationale="创建证据分享链接供后续讨论引用。",
                    )
                )
                share_step_id = "step-3"
                if can_reply:
                    steps.append(
                        StoryStep(
                            step_id="step-4",
                            capability="forum.reply_thread",
                            actor_id=witness,
                            payload={
                                "thread_id": "$step-1.output.thread_id",
                                "content": "I checked part of the evidence, but the timeline still has a gap. We need one more cycle.",
                            },
                            depends_on=["step-3"],
                            rationale="证人确认部分线索，保留悬念。",
                        )
                    )
            elif can_reply:
                steps.append(
                    StoryStep(
                        step_id="step-2",
                        capability="forum.reply_thread",
                        actor_id=witness,
                        payload={
                            "thread_id": "$step-1.output.thread_id",
                            "content": "I can confirm unusual activity, but nothing conclusive yet.",
                        },
                        depends_on=["step-1"],
                        rationale="无网盘时用回帖制造首轮悬念。",
                    )
                )

        elif phase == "investigation":
            if arc.clue_thread_id and can_reply:
                steps.append(
                    StoryStep(
                        step_id="step-1",
                        capability="forum.reply_thread",
                        actor_id=witness,
                        payload={
                            "thread_id": arc.clue_thread_id,
                            "content": "New witness detail reduces uncertainty, but one key contradiction remains unresolved.",
                        },
                        rationale="中段推进调查，不公布真相。",
                    )
                )
                steps.append(
                    StoryStep(
                        step_id="step-2",
                        capability="forum.reply_thread",
                        actor_id=analyst,
                        payload={
                            "thread_id": arc.clue_thread_id,
                            "content": "Cross-check complete for now. We should wait for the next cycle before final conclusion.",
                        },
                        depends_on=["step-1"],
                        rationale="把结论推迟到下一轮调度。",
                    )
                )
            else:
                steps.append(
                    StoryStep(
                        step_id="step-1",
                        capability="forum.create_thread",
                        actor_id=investigator,
                        payload={
                            "board_slug": "town-square",
                            "title": "[Case Ongoing] Investigation Progress Update",
                            "content": "The case is still open. We collected more clues, but no final answer yet.",
                            "tags": ["detective", "ongoing", "investigation"],
                        },
                        rationale="缺少线索帖时补建调查节点。",
                    )
                )

        else:
            # resolution phase
            if arc.clue_thread_id and can_reply:
                steps.append(
                    StoryStep(
                        step_id="step-1",
                        capability="forum.reply_thread",
                        actor_id=analyst,
                        payload={
                            "thread_id": arc.clue_thread_id,
                            "content": "Final verification passed. The case explanation is now complete and consistent.",
                        },
                        rationale="在原帖下给出关键结论。",
                    )
                )

            publish_news = can_news and rng.random() < self.resolution_news_probability
            depends = [steps[-1].step_id] if steps else []
            if publish_news and arc.clue_thread_id:
                steps.append(
                    StoryStep(
                        step_id=f"step-{len(steps) + 1}",
                        capability="news.publish_article",
                        actor_id=analyst,
                        payload={
                            "title": "Case Closed: Final Investigation Report",
                            "content": "This report closes the long-running case and explains the clue sequence, false leads, and verified outcome.",
                            "category": "investigation",
                            "is_pinned": False,
                            "related_thread_ids": [arc.clue_thread_id],
                            "related_share_ids": [arc.related_share_id] if arc.related_share_id else [],
                        },
                        depends_on=depends,
                        rationale="结果阶段发布新闻结案。",
                    )
                )
            else:
                steps.append(
                    StoryStep(
                        step_id=f"step-{len(steps) + 1}",
                        capability="forum.create_thread",
                        actor_id=analyst,
                        payload={
                            "board_slug": "town-square",
                            "title": "[Case Closed] Consolidated Findings",
                            "content": "The investigation is now closed. This thread records the final explanation and remaining caveats.",
                            "tags": ["detective", "case-closed", "result"],
                        },
                        depends_on=depends,
                        rationale="不用新闻时用新帖结案。",
                    )
                )

        # Mirror detective arc progress to social site so probabilistic detective schedulers
        # can use social page tools in both normal and serious-incident dispatches.
        social_post_step_id: str | None = None
        next_index = len(steps) + 1
        if "social.create_post" in capability_names:
            social_depends_on = [steps[-1].step_id] if steps else []
            social_content_map = {
                "discovery": "Case opened. We have clues, but no confirmed explanation yet.",
                "investigation": "Case update: new evidence arrived, but one contradiction remains unresolved.",
                "resolution": "Case closed. Final findings are now verified and published.",
            }
            social_post_step_id = f"step-{next_index}"
            steps.append(
                StoryStep(
                    step_id=social_post_step_id,
                    capability="social.create_post",
                    actor_id=investigator,
                    payload={
                        "content": social_content_map.get(phase, "Case update posted."),
                        "tags": ["detective", "case", phase],
                    },
                    depends_on=social_depends_on,
                    rationale="同步侦探线到社交网站，覆盖 social 发帖工具。",
                )
            )
            next_index += 1

        if social_post_step_id and "social.reply_post" in capability_names:
            steps.append(
                StoryStep(
                    step_id=f"step-{next_index}",
                    capability="social.reply_post",
                    actor_id=witness,
                    payload={
                        "post_id": f"${social_post_step_id}.output.post_id",
                        "content": "Acknowledged. I can corroborate part of this update and will share more after the next check.",
                    },
                    depends_on=[social_post_step_id],
                    rationale="同步侦探线的社交回帖能力，确保回帖工具可被调度。",
                )
            )

        return StoryPlan(
            story_id=f"detective-arc-{arc.arc_id}-phase-{phase}-run-{run_no:04d}",
            goal=goal,
            steps=steps,
            planner_name="ongoing_detective_arc",
            planner_source="local_rule",
            fallback_used=False,
            planner_detail=f"Ongoing detective arc planner phase={phase}, reveal_after={arc.reveal_after}.",
        )
