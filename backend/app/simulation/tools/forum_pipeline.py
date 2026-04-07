from __future__ import annotations

from app.consistency.checker import ConsistencyChecker
from app.domain.events import StoryEvent
from app.infrastructure.llm.structured_content import AbstractStructuredContentGenerator
from app.repositories.forum_repository import ThreadDetail, ThreadSummary
from app.services.forum_service import ForumService
from app.services.netdisk_service import NetdiskService
from app.simulation.content_sanitizer import sanitize_forum_content, sanitize_forum_title
from app.simulation.protocol import (
    ActionRequest,
    CapabilitySpec,
    ConsistencyCheckResult,
    ContentGenerationRequest,
    FactExecutionResult,
    GeneratedContent,
    PublicationResult,
)
from app.simulation.tools.workflow import AbstractCapabilityWorkflow, FiveStageToolExecutor


def _normalize_forum_stage(stage: str) -> str:
    allowed = {"discussion", "investigation", "disclosure", "conclusion"}
    value = (stage or "").strip().lower()
    return value if value in allowed else "discussion"


def _map_thread_summary(thread: ThreadSummary) -> dict:
    return {
        "id": thread.id,
        "title": thread.title,
        "board_slug": thread.board_slug,
        "stage": thread.stage,
        "author_id": thread.author_id,
        "replies": thread.replies,
        "views": thread.views,
        "last_reply_by_id": thread.last_reply_by_id,
        "last_reply_at": thread.last_reply_at,
        "pinned": thread.pinned,
        "tags": thread.tags,
    }


def _map_thread_detail(thread: ThreadDetail) -> dict:
    return {
        **_map_thread_summary(thread),
        "posts": [
            {
                "id": post.id,
                "author_id": post.author_id,
                "created_at": post.created_at,
                "content": post.content,
            }
            for post in thread.posts
        ],
    }


class ForumWorkflowBase(AbstractCapabilityWorkflow):
    def __init__(
        self,
        forum_service: ForumService,
        consistency_checker: ConsistencyChecker,
        netdisk_service: NetdiskService,
    ) -> None:
        self.forum_service = forum_service
        self.consistency_checker = consistency_checker
        self.netdisk_service = netdisk_service

    def _available_board_slugs(self) -> list[str]:
        return [board.slug for board in self.forum_service.list_boards()]

    def _resolve_board_slug(self, raw_value: str) -> str:
        value = raw_value.strip().lower()
        if not value:
            return value

        available = {board.slug: board.slug for board in self.forum_service.list_boards()}
        for board in self.forum_service.list_boards():
            available[board.name.strip().lower()] = board.slug

        aliases = {
            "general": "town-square",
            "general-discussion": "town-square",
            "town square": "town-square",
            "main-forum": "town-square",
            "market": "bazaar",
            "shop": "bazaar",
            "dm": "whispers",
            "private": "whispers",
        }

        if value in aliases:
            return aliases[value]
        return available.get(value, value)


class ForumReadBoardWorkflow(ForumWorkflowBase):
    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="forum.read_board",
            site="forum",
            description="Read threads under a board.",
            input_schema={
                "board_slug": "string",
                "limit": "integer optional",
                "allowed_board_slugs": self._available_board_slugs(),
            },
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        board_slug = self._resolve_board_slug(str(request.payload.get("board_slug", "")).strip())
        limit = int(request.payload.get("limit", 10))
        board, threads = self.forum_service.list_board_threads(board_slug)
        if board is None:
            raise ValueError(f"Board not found: {board_slug}")

        trimmed_threads = threads[: max(1, limit)]
        return FactExecutionResult(
            capability=request.capability,
            site="forum",
            actor_id=request.actor_id,
            facts=[f"读取版块={board_slug}", f"读取主题数量={len(trimmed_threads)}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="论坛版块读取完成。",
                    metadata={"board_slug": board_slug},
                )
            ],
            output={
                "board": {
                    "slug": board.slug,
                    "name": board.name,
                    "description": board.description,
                },
                "threads": [_map_thread_summary(thread) for thread in trimmed_threads],
            },
            generation_context={"board_slug": board_slug},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class ForumReadThreadWorkflow(ForumWorkflowBase):
    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="forum.read_thread",
            site="forum",
            description="Read thread detail with post list.",
            input_schema={"thread_id": "string"},
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        thread_id = str(request.payload.get("thread_id", "")).strip()
        thread = self.forum_service.get_thread(thread_id)
        if thread is None:
            raise ValueError(f"Thread not found: {thread_id}")

        return FactExecutionResult(
            capability=request.capability,
            site="forum",
            actor_id=request.actor_id,
            facts=[f"读取帖子={thread.id}", f"帖子内容数量={len(thread.posts)}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="论坛帖子读取完成。",
                    metadata={"thread_id": thread.id},
                )
            ],
            output={"thread": _map_thread_detail(thread)},
            generation_context={"thread_id": thread.id},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class ForumCreateThreadWorkflow(ForumWorkflowBase):
    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="forum.create_thread",
            site="forum",
            description="Create a thread in board with first post through the fact-first pipeline.",
            input_schema={
                "board_slug": "string",
                "title": "string",
                "content": "string",
                "stage": "string optional",
                "tags": "string[] optional",
                "image_url": "string optional",
                "netdisk_share_id": "string optional",
                "netdisk_access_code": "string optional",
                "allowed_board_slugs": self._available_board_slugs(),
            },
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        board_slug = self._resolve_board_slug(str(request.payload.get("board_slug", "")).strip())
        requested_title = str(request.payload.get("title", "")).strip()
        requested_content = str(request.payload.get("content", "")).strip()
        image_url = str(request.payload.get("image_url", "")).strip()
        netdisk_share_id = str(request.payload.get("netdisk_share_id", "")).strip()
        netdisk_access_code = str(request.payload.get("netdisk_access_code", "")).strip()
        tags = request.payload.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        stage = _normalize_forum_stage(str(request.payload.get("stage", "discussion")))

        netdisk_share = None
        if netdisk_share_id or netdisk_access_code:
            if not netdisk_share_id or not netdisk_access_code:
                raise ValueError("netdisk_share_id and netdisk_access_code must be provided together")
            netdisk_share = self.netdisk_service.validate_share_reference(
                share_id=netdisk_share_id,
                access_code=netdisk_access_code,
            )
            if netdisk_share is None:
                raise ValueError("Referenced netdisk share is invalid or expired")

        draft = self.forum_service.create_thread_draft(
            board_slug=board_slug,
            author_id=request.actor_id,
            requested_title=requested_title,
            requested_content=requested_content,
            stage=stage,
            tags=[str(tag) for tag in tags],
        )

        return FactExecutionResult(
            capability=request.capability,
            site="forum",
            actor_id=request.actor_id,
            facts=[
                f"线程草稿={draft.draft_id}",
                f"保留主题ID={draft.thread_id}",
                f"保留首帖ID={draft.first_post_id}",
                f"目标版块={draft.board_slug}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="论坛主题草稿事实已创建，等待内容生成。",
                    metadata={"draft_id": draft.draft_id, "thread_id": draft.thread_id},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="论坛主题草稿已持久化到数据库。",
                    metadata={"draft_id": draft.draft_id},
                ),
            ],
            output={
                "draft_id": draft.draft_id,
                "thread_id": draft.thread_id,
                "first_post_id": draft.first_post_id,
                "board_slug": draft.board_slug,
                "status": "draft_created",
            },
            generation_context={
                "draft_id": draft.draft_id,
                "thread_id": draft.thread_id,
                "first_post_id": draft.first_post_id,
                "board_slug": draft.board_slug,
                "board_name": draft.board_name,
                "requested_title": draft.requested_title,
                "requested_content": draft.requested_content,
                "stage": draft.stage,
                "image_url": image_url,
                "tags": draft.tags,
                "netdisk_share_id": netdisk_share.share_id if netdisk_share else "",
                "netdisk_access_code": netdisk_share.access_code if netdisk_share else "",
                "netdisk_share_url": netdisk_share.share_url if netdisk_share else "",
                "netdisk_resource_id": netdisk_share.resource_id if netdisk_share else "",
            },
            requires_content_generation=True,
        )

    def build_generation_request(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
    ) -> ContentGenerationRequest:
        return ContentGenerationRequest(
            capability=request.capability,
            site="forum",
            actor_id=request.actor_id,
            instruction=(
                "Based on the created forum thread draft and fact context, generate an English forum title and an "
                "English first post body that are ready to publish. If netdisk_share_id and netdisk_access_code are "
                "present in fact_context, include both values in the post body exactly."
            ),
            desired_fields=["title", "content"],
            fact_context=fact_result.generation_context,
            style_context={"tone": "forum_post", "avoid_meta_prompt": True, "language": "en"},
        )

    def validate_generated_content(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        generated_content: GeneratedContent,
    ) -> ConsistencyCheckResult:
        title = sanitize_forum_title(str(generated_content.fields.get("title", "")))
        content = sanitize_forum_content(str(generated_content.fields.get("content", "")))
        image_url = str(fact_result.generation_context.get("image_url", "")).strip()
        if image_url and image_url not in content:
            content = f"{content}\n\n![Generated scene]({image_url})"
        normalized_fields = {"title": title, "content": content}
        violations = []
        violations.extend(self.consistency_checker.validate_required_fields(normalized_fields, ["title", "content"]))
        violations.extend(
            self.consistency_checker.validate_minimum_length(
                field_name="title",
                value=title,
                minimum_length=8,
            )
        )
        violations.extend(
            self.consistency_checker.validate_minimum_length(
                field_name="content",
                value=content,
                minimum_length=80,
            )
        )
        violations.extend(
            self.consistency_checker.validate_against_placeholders(
                field_name="title",
                value=title,
                placeholders=["Forum Update", "Thread Update", "Generated Thread"],
            )
        )
        violations.extend(self.consistency_checker.detect_unresolved_references(normalized_fields))
        violations.extend(
            self.consistency_checker.validate_netdisk_reference(
                content=content,
                share_id=str(fact_result.generation_context.get("netdisk_share_id", "")),
                access_code=str(fact_result.generation_context.get("netdisk_access_code", "")),
            )
        )
        return ConsistencyCheckResult(
            passed=not violations,
            violations=violations,
            normalized_fields=normalized_fields,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        draft_id = str(fact_result.output["draft_id"])
        thread = self.forum_service.publish_thread_draft(
            draft_id=draft_id,
            title=validation_result.normalized_fields["title"],
            content=validation_result.normalized_fields["content"],
            stage=str(fact_result.generation_context.get("stage", "discussion")),
        )
        return PublicationResult(
            output={
                "draft_id": draft_id,
                "thread_id": thread.id,
                "thread": _map_thread_detail(thread),
                "publication_status": "published",
            },
            facts=[f"已发布主题={thread.id}"],
            events=[
                StoryEvent(
                    name="ContentPublished",
                    detail="论坛主题已通过五步骤链正式发布。",
                    metadata={"thread_id": thread.id, "draft_id": draft_id},
                )
            ],
        )


class ForumReplyThreadWorkflow(ForumWorkflowBase):
    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="forum.reply_thread",
            site="forum",
            description="Reply to an existing thread through the fact-first pipeline.",
            input_schema={"thread_id": "string", "content": "string"},
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        thread_id = str(request.payload.get("thread_id", "")).strip()
        requested_content = str(request.payload.get("content", "")).strip()
        draft = self.forum_service.create_reply_draft(
            thread_id=thread_id,
            author_id=request.actor_id,
            requested_content=requested_content,
        )
        if draft is None:
            raise ValueError(f"Thread not found: {thread_id}")

        return FactExecutionResult(
            capability=request.capability,
            site="forum",
            actor_id=request.actor_id,
            facts=[
                f"回复草稿={draft.draft_id}",
                f"目标主题={draft.thread_id}",
                f"保留回复ID={draft.post_id}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="论坛回复草稿事实已创建，等待内容生成。",
                    metadata={"draft_id": draft.draft_id, "thread_id": draft.thread_id},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="论坛回复草稿已持久化到数据库。",
                    metadata={"draft_id": draft.draft_id},
                ),
            ],
            output={
                "draft_id": draft.draft_id,
                "thread_id": draft.thread_id,
                "post_id": draft.post_id,
                "status": "draft_created",
            },
            generation_context={
                "draft_id": draft.draft_id,
                "thread_id": draft.thread_id,
                "post_id": draft.post_id,
                "thread_title": draft.thread_title,
                "requested_content": draft.requested_content,
            },
            requires_content_generation=True,
        )

    def build_generation_request(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
    ) -> ContentGenerationRequest:
        return ContentGenerationRequest(
            capability=request.capability,
            site="forum",
            actor_id=request.actor_id,
            instruction="Based on the created forum reply draft and thread context, generate an English reply body that is ready to publish.",
            desired_fields=["content"],
            fact_context=fact_result.generation_context,
            style_context={"tone": "forum_reply", "avoid_meta_prompt": True, "language": "en"},
        )

    def validate_generated_content(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        generated_content: GeneratedContent,
    ) -> ConsistencyCheckResult:
        content = sanitize_forum_content(str(generated_content.fields.get("content", "")))
        normalized_fields = {"content": content}
        violations = []
        violations.extend(self.consistency_checker.validate_required_fields(normalized_fields, ["content"]))
        violations.extend(self.consistency_checker.detect_unresolved_references(normalized_fields))
        return ConsistencyCheckResult(
            passed=not violations,
            violations=violations,
            normalized_fields=normalized_fields,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        draft_id = str(fact_result.output["draft_id"])
        post = self.forum_service.publish_reply_draft(
            draft_id=draft_id,
            content=validation_result.normalized_fields["content"],
        )
        if post is None:
            raise ValueError(f"Unable to publish reply draft: {draft_id}")
        return PublicationResult(
            output={
                "draft_id": draft_id,
                "thread_id": fact_result.output["thread_id"],
                "post": {
                    "id": post.id,
                    "author_id": post.author_id,
                    "created_at": post.created_at,
                    "content": post.content,
                },
                "publication_status": "published",
            },
            facts=[f"已发布回复={post.id}"],
            events=[
                StoryEvent(
                    name="ContentPublished",
                    detail="论坛回复已通过五步骤链正式发布。",
                    metadata={"post_id": post.id, "draft_id": draft_id},
                )
            ],
        )


class ForumPipelineToolExecutor(FiveStageToolExecutor):
    def __init__(
        self,
        forum_service: ForumService,
        consistency_checker: ConsistencyChecker,
        netdisk_service: NetdiskService,
        content_generator: AbstractStructuredContentGenerator,
    ) -> None:
        workflows = [
            ForumReadBoardWorkflow(forum_service, consistency_checker, netdisk_service),
            ForumReadThreadWorkflow(forum_service, consistency_checker, netdisk_service),
            ForumCreateThreadWorkflow(forum_service, consistency_checker, netdisk_service),
            ForumReplyThreadWorkflow(forum_service, consistency_checker, netdisk_service),
        ]
        super().__init__(workflows=workflows, content_generator=content_generator)
