from __future__ import annotations

from app.consistency.checker import ConsistencyChecker
from app.domain.events import StoryEvent
from app.infrastructure.llm.structured_content import AbstractStructuredContentGenerator
from app.services.forum_service import ForumService
from app.services.netdisk_service import NetdiskService
from app.services.news_service import NewsService
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


def _normalize_news_stage(stage: str) -> str:
    allowed = {"breaking", "investigation", "disclosure", "conclusion"}
    value = (stage or "").strip().lower()
    return value if value in allowed else "breaking"


class NewsPublishArticleWorkflow(AbstractCapabilityWorkflow):
    def __init__(
        self,
        news_service: NewsService,
        consistency_checker: ConsistencyChecker,
        forum_service: ForumService,
        netdisk_service: NetdiskService,
    ) -> None:
        self.news_service = news_service
        self.consistency_checker = consistency_checker
        self.forum_service = forum_service
        self.netdisk_service = netdisk_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="news.publish_article",
            site="news",
            description="Publish a news article through the fact-first pipeline.",
            input_schema={
                "title": "string",
                "content": "string",
                "category": "string",
                "stage": "string optional",
                "is_pinned": "boolean optional",
                "related_thread_ids": "string[] optional",
                "related_share_ids": "string[] optional",
            },
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        title = str(request.payload.get("title", ""))
        content = str(request.payload.get("content", ""))
        category = str(request.payload.get("category", ""))
        stage = _normalize_news_stage(str(request.payload.get("stage", "breaking")))
        is_pinned = bool(request.payload.get("is_pinned", False))
        related_thread_ids_raw = request.payload.get("related_thread_ids", [])
        related_share_ids_raw = request.payload.get("related_share_ids", [])

        if not isinstance(related_thread_ids_raw, list):
            raise ValueError("related_thread_ids must be a list")
        if not isinstance(related_share_ids_raw, list):
            raise ValueError("related_share_ids must be a list")

        related_thread_ids = [str(item).strip() for item in related_thread_ids_raw if str(item).strip()]
        related_share_ids = [str(item).strip() for item in related_share_ids_raw if str(item).strip()]

        for thread_id in related_thread_ids:
            if self.forum_service.get_thread(thread_id) is None:
                raise ValueError(f"Related forum thread not found: {thread_id}")

        for share_id in related_share_ids:
            if self.netdisk_service.get_share(share_id=share_id) is None:
                raise ValueError(f"Related netdisk share not found: {share_id}")

        if not category:
            category = "community"

        draft = self.news_service.create_article_draft(
            category=category,
            author_id=request.actor_id,
            requested_title=title,
            requested_content=content,
            requested_stage=stage,
            requested_is_pinned=is_pinned,
            requested_related_thread_ids=related_thread_ids,
            requested_related_share_ids=related_share_ids,
        )

        return FactExecutionResult(
            capability=request.capability,
            site="news",
            actor_id=request.actor_id,
            facts=[
                f"新闻草稿={draft.draft_id}",
                f"保留文章ID={draft.article_id}",
                f"目标分类={draft.category}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="新闻文章草稿事实已创建，等待内容生成。",
                    metadata={"draft_id": draft.draft_id, "article_id": draft.article_id},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="新闻文章草稿已持久化到数据库。",
                    metadata={"draft_id": draft.draft_id},
                ),
            ],
            output={
                "draft_id": draft.draft_id,
                "article_id": draft.article_id,
                "status": "draft_created",
            },
            generation_context={
                "draft_id": draft.draft_id,
                "article_id": draft.article_id,
                "category": draft.category,
                "requested_title": draft.requested_title,
                "requested_content": draft.requested_content,
                "requested_stage": draft.requested_stage,
                "requested_is_pinned": draft.requested_is_pinned,
                "requested_related_thread_ids": draft.requested_related_thread_ids,
                "requested_related_share_ids": draft.requested_related_share_ids,
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
            site="news",
            actor_id=request.actor_id,
            instruction=(
                "Based on the created news article draft and fact context, generate a professional news article. "
                "The article should have a clear title and body that is ready to publish. "
                "If related_thread_ids or related_share_ids are present, include references to them in the article."
            ),
            desired_fields=["title", "content"],
            fact_context=fact_result.generation_context,
            style_context={"tone": "news_article", "avoid_meta_prompt": True, "language": "en"},
        )

    def validate_generated_content(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        generated_content: GeneratedContent,
    ) -> ConsistencyCheckResult:
        title = str(generated_content.fields.get("title", ""))
        content = str(generated_content.fields.get("content", ""))
        normalized_fields = {"title": title, "content": content}
        violations = []
        violations.extend(self.consistency_checker.validate_required_fields(normalized_fields, ["title", "content"]))
        violations.extend(
            self.consistency_checker.validate_minimum_length(
                field_name="title",
                value=title,
                minimum_length=12,
            )
        )
        violations.extend(
            self.consistency_checker.validate_minimum_length(
                field_name="content",
                value=content,
                minimum_length=160,
            )
        )
        violations.extend(
            self.consistency_checker.validate_against_placeholders(
                field_name="title",
                value=title,
                placeholders=["News Brief", "Breaking Update", "Generated News", "News Update"],
            )
        )
        violations.extend(self.consistency_checker.detect_unresolved_references(normalized_fields))
        violations.extend(
            self.consistency_checker.validate_news_references(
                content=content,
                related_thread_ids=[
                    str(item)
                    for item in fact_result.generation_context.get("requested_related_thread_ids", [])
                    if str(item).strip()
                ],
                related_share_ids=[
                    str(item)
                    for item in fact_result.generation_context.get("requested_related_share_ids", [])
                    if str(item).strip()
                ],
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
        article = self.news_service.publish_article_draft(
            draft_id=draft_id,
            title=validation_result.normalized_fields["title"],
            content=validation_result.normalized_fields["content"],
            stage=str(fact_result.generation_context.get("requested_stage", "breaking")),
            is_pinned=bool(fact_result.generation_context.get("requested_is_pinned", False)),
            related_thread_ids=fact_result.generation_context.get("requested_related_thread_ids", []),
            related_share_ids=fact_result.generation_context.get("requested_related_share_ids", []),
        )
        return PublicationResult(
            output={
                "draft_id": draft_id,
                "article_id": article.article_id,
                "article": {
                    "article_id": article.article_id,
                    "title": article.title,
                    "category": article.category,
                    "stage": article.stage,
                    "author_id": article.author_id,
                    "published_at": article.published_at,
                    "views": article.views,
                    "is_pinned": article.is_pinned,
                    "excerpt": article.excerpt,
                    "content": article.content,
                    "related_thread_ids": article.related_thread_ids,
                    "related_share_ids": article.related_share_ids,
                },
                "publication_status": "published",
            },
            facts=[f"已发布新闻={article.article_id}"],
            events=[
                StoryEvent(
                    name="ContentPublished",
                    detail="新闻文章已通过五步骤链正式发布。",
                    metadata={"article_id": article.article_id, "draft_id": draft_id},
                )
            ],
        )


class NewsReadArticlesWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, news_service: NewsService) -> None:
        self.news_service = news_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="news.read_articles",
            site="news",
            description="Read news articles with optional category filter.",
            input_schema={
                "category": "string optional",
                "limit": "integer optional",
            },
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        category = request.payload.get("category")
        limit = int(request.payload.get("limit", 20))
        articles = self.news_service.list_articles(category=category, limit=limit)

        return FactExecutionResult(
            capability=request.capability,
            site="news",
            actor_id=request.actor_id,
            facts=[
                f"读取分类={category or 'all'}",
                f"读取文章数量={len(articles)}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="新闻文章读取完成。",
                    metadata={"category": category},
                ),
            ],
            output={
                "articles": [
                    {
                        "article_id": article.article_id,
                        "title": article.title,
                        "category": article.category,
                        "stage": article.stage,
                        "author_id": article.author_id,
                        "published_at": article.published_at,
                        "views": article.views,
                        "is_pinned": article.is_pinned,
                        "excerpt": article.excerpt,
                    }
                    for article in articles
                ],
                "total": len(articles),
                "category": category,
            },
            generation_context={"category": category},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class NewsReadArticleWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, news_service: NewsService) -> None:
        self.news_service = news_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="news.read_article",
            site="news",
            description="Read news article detail by ID.",
            input_schema={"article_id": "string"},
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        article_id = str(request.payload.get("article_id", ""))
        article = self.news_service.get_article(article_id)
        if article is None:
            raise ValueError(f"Article not found: {article_id}")

        return FactExecutionResult(
            capability=request.capability,
            site="news",
            actor_id=request.actor_id,
            facts=[
                f"读取文章={article.article_id}",
                f"文章分类={article.category}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="新闻文章详情读取完成。",
                    metadata={"article_id": article.article_id},
                ),
            ],
            output={
                "article": {
                    "article_id": article.article_id,
                    "title": article.title,
                    "category": article.category,
                    "stage": article.stage,
                    "author_id": article.author_id,
                    "published_at": article.published_at,
                    "views": article.views,
                    "is_pinned": article.is_pinned,
                    "excerpt": article.excerpt,
                    "content": article.content,
                    "related_thread_ids": article.related_thread_ids,
                    "related_share_ids": article.related_share_ids,
                },
            },
            generation_context={"article_id": article.article_id},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class NewsPipelineToolExecutor(FiveStageToolExecutor):
    def __init__(
        self,
        news_service: NewsService,
        consistency_checker: ConsistencyChecker,
        content_generator: AbstractStructuredContentGenerator,
        forum_service: ForumService,
        netdisk_service: NetdiskService,
    ) -> None:
        workflows = [
            NewsReadArticlesWorkflow(news_service),
            NewsReadArticleWorkflow(news_service),
            NewsPublishArticleWorkflow(news_service, consistency_checker, forum_service, netdisk_service),
        ]
        super().__init__(workflows=workflows, content_generator=content_generator)
