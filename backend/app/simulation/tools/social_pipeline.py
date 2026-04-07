from __future__ import annotations

from app.consistency.checker import ConsistencyChecker
from app.domain.events import StoryEvent
from app.infrastructure.llm.structured_content import AbstractStructuredContentGenerator
from app.services.social_service import SocialService
from app.simulation.content_sanitizer import sanitize_forum_content
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


class SocialWorkflowBase(AbstractCapabilityWorkflow):
    def __init__(
        self,
        social_service: SocialService,
        consistency_checker: ConsistencyChecker,
    ) -> None:
        self.social_service = social_service
        self.consistency_checker = consistency_checker


class SocialCreatePostWorkflow(SocialWorkflowBase):
    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="social.create_post",
            site="social",
            description="Create a new social media post with optional tags",
            input_schema={
                "content": "string",
                "tags": "string[] optional",
            },
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        requested_content = str(request.payload.get("content", "")).strip()
        tags = request.payload.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        draft = self.social_service.create_post_draft(
            author_id=request.actor_id,
            requested_content=requested_content,
            tags=[str(tag) for tag in tags],
        )

        return FactExecutionResult(
            capability=request.capability,
            site="social",
            actor_id=request.actor_id,
            facts=[
                f"帖子草稿={draft.id}",
                f"作者={request.actor_id}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="社交媒体帖子草稿事实已创建，等待内容生成。",
                    metadata={"draft_id": draft.id},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="社交媒体帖子草稿已持久化到数据库。",
                    metadata={"draft_id": draft.id},
                ),
            ],
            output={
                "draft_id": draft.id,
                "status": "draft_created",
            },
            generation_context={
                "draft_id": draft.id,
                "requested_content": draft.requested_content,
                "tags": draft.tags,
            },
            requires_content_generation=True,
        )

    def build_generation_request(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
    ) -> ContentGenerationRequest:
        recent_posts, _ = self.social_service.list_posts(limit=3, cursor=None, tag=None)
        recent_social_context = [
            {
                "author_id": post.author_id,
                "content": post.content,
                "tags": post.tags,
            }
            for post in recent_posts
        ]

        fact_context = dict(fact_result.generation_context)
        fact_context["recent_social_context"] = recent_social_context

        return ContentGenerationRequest(
            capability=request.capability,
            site="social",
            actor_id=request.actor_id,
            instruction=(
                "Based on the created social media post draft and fact context, generate a short social media post (1-2 sentences) that is ready to publish. "
                "Read the recent social feed context to match style and avoid repeating the same idea. "
                "The post should be casual, conversational, and fit the 2000s web style. "
                "Avoid using modern social media features or terminology."
            ),
            desired_fields=["content"],
            fact_context=fact_context,
            style_context={"tone": "social_post", "avoid_meta_prompt": True, "language": "en"},
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
        post = self.social_service.publish_post_draft(
            draft_id=draft_id,
            content=validation_result.normalized_fields["content"],
        )
        return PublicationResult(
            output={
                "draft_id": draft_id,
                "post_id": post.id,
                "content": post.content,
                "author_id": post.author_id,
                "created_at": post.created_at,
                "publication_status": "published",
            },
            facts=[f"已发布帖子={post.id}"],
            events=[
                StoryEvent(
                    name="ContentPublished",
                    detail="社交媒体帖子已通过五步骤链正式发布。",
                    metadata={"post_id": post.id, "draft_id": draft_id},
                )
            ],
        )


class SocialReplyPostWorkflow(SocialWorkflowBase):
    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="social.reply_post",
            site="social",
            description="Reply to an existing social media post",
            input_schema={
                "post_id": "string",
                "content": "string",
            },
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        post_id = str(request.payload.get("post_id", "")).strip()
        requested_content = str(request.payload.get("content", "")).strip()
        draft = self.social_service.create_reply_draft(
            post_id=post_id,
            author_id=request.actor_id,
            requested_content=requested_content,
        )
        if draft is None:
            raise ValueError(f"Post not found: {post_id}")

        return FactExecutionResult(
            capability=request.capability,
            site="social",
            actor_id=request.actor_id,
            facts=[
                f"回复草稿={draft.id}",
                f"目标帖子={draft.post_id}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="社交媒体回复草稿事实已创建，等待内容生成。",
                    metadata={"draft_id": draft.id, "post_id": draft.post_id},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="社交媒体回复草稿已持久化到数据库。",
                    metadata={"draft_id": draft.id},
                ),
            ],
            output={
                "draft_id": draft.id,
                "post_id": draft.post_id,
                "status": "draft_created",
            },
            generation_context={
                "draft_id": draft.id,
                "post_id": draft.post_id,
                "requested_content": draft.requested_content,
            },
            requires_content_generation=True,
        )

    def build_generation_request(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
    ) -> ContentGenerationRequest:
        post_id = fact_result.generation_context.get("post_id")
        post = self.social_service.get_post(post_id)
        post_content = post.content if post else ""

        return ContentGenerationRequest(
            capability=request.capability,
            site="social",
            actor_id=request.actor_id,
            instruction=(
                f"Based on the created social media reply draft and post context, generate a short reply (1-2 sentences) that is ready to publish. "
                f"Original post: {post_content}"
                "The reply should be casual, conversational, and fit the 2000s web style. "
                "Avoid using modern social media features or terminology."
            ),
            desired_fields=["content"],
            fact_context=fact_result.generation_context,
            style_context={"tone": "social_reply", "avoid_meta_prompt": True, "language": "en"},
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
        reply = self.social_service.publish_reply_draft(
            draft_id=draft_id,
            content=validation_result.normalized_fields["content"],
        )
        if reply is None:
            raise ValueError(f"Unable to publish reply draft: {draft_id}")
        return PublicationResult(
            output={
                "draft_id": draft_id,
                "post_id": fact_result.output["post_id"],
                "reply_id": reply.id,
                "content": reply.content,
                "author_id": reply.author_id,
                "created_at": reply.created_at,
                "publication_status": "published",
            },
            facts=[f"已发布回复={reply.id}"],
            events=[
                StoryEvent(
                    name="ContentPublished",
                    detail="社交媒体回复已通过五步骤链正式发布。",
                    metadata={"reply_id": reply.id, "draft_id": draft_id},
                )
            ],
        )


class SocialPipelineToolExecutor(FiveStageToolExecutor):
    def __init__(
        self,
        social_service: SocialService,
        consistency_checker: ConsistencyChecker,
        content_generator: AbstractStructuredContentGenerator,
    ) -> None:
        workflows = [
            SocialCreatePostWorkflow(social_service, consistency_checker),
            SocialReplyPostWorkflow(social_service, consistency_checker),
        ]
        super().__init__(workflows=workflows, content_generator=content_generator)
