from __future__ import annotations

import json

from app.consistency.checker import ConsistencyChecker
from app.domain.events import StoryEvent
from app.infrastructure.llm.structured_content import AbstractStructuredContentGenerator
from app.services.mainpage_service import MainPageService
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


class MainGeneratePageWorkflow(AbstractCapabilityWorkflow):
    _TITLE_ALIASES = ("title", "page_title", "name")
    _HTML_ALIASES = ("html_content", "html", "page_html", "body", "content")
    _ASSET_ALIASES = ("assets", "resources", "asset_list")

    def __init__(self, mainpage_service: MainPageService, consistency_checker: ConsistencyChecker) -> None:
        self.mainpage_service = mainpage_service
        self.consistency_checker = consistency_checker

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="main.generate_page",
            site="main",
            description="Generate and publish an AI webpage, available at /main/{slug}.",
            input_schema={
                "title": "string",
                "description": "string",
                "slug": "string optional",
                "style": "string optional",
            },
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        title = str(request.payload.get("title", "")).strip()
        description = str(request.payload.get("description", "")).strip()
        slug = str(request.payload.get("slug", "")).strip() or None
        style = str(request.payload.get("style", "world_website")).strip() or "world_website"

        draft = self.mainpage_service.create_page_draft(
            author_id=request.actor_id,
            title=title,
            description=description,
            slug=slug,
            style=style,
        )

        return FactExecutionResult(
            capability=request.capability,
            site="main",
            actor_id=request.actor_id,
            facts=[
                f"网页草稿={draft.draft_id}",
                f"预留页面ID={draft.page_id}",
                f"预留路径=/main/{draft.slug}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="网页草稿事实已创建，等待内容生成。",
                    metadata={"draft_id": draft.draft_id, "page_id": draft.page_id, "slug": draft.slug},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="网页草稿已持久化到数据库。",
                    metadata={"draft_id": draft.draft_id},
                ),
            ],
            output={
                "draft_id": draft.draft_id,
                "page_id": draft.page_id,
                "slug": draft.slug,
                "status": "draft_created",
            },
            generation_context={
                "draft_id": draft.draft_id,
                "page_id": draft.page_id,
                "slug": draft.slug,
                "requested_title": draft.requested_title,
                "requested_description": draft.requested_description,
                "requested_style": draft.requested_style,
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
            site="main",
            actor_id=request.actor_id,
            instruction=(
                "Generate a complete HTML page and optional assets based on the page draft. "
                "Output should be publish-ready for /main/{slug}. "
                "The webpage should strongly reflect an early-2000s internet style."
            ),
            desired_fields=["title", "html_content", "assets"],
            fact_context=fact_result.generation_context,
            style_context={
                "tone": "website",
                "language": "zh-CN",
                "era": "early_2000s_web",
                "avoid_meta_prompt": True,
            },
        )

    def validate_generated_content(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        generated_content: GeneratedContent,
    ) -> ConsistencyCheckResult:
        fields = generated_content.fields
        title = self._first_non_empty(fields, self._TITLE_ALIASES)
        html_content = self._first_non_empty(fields, self._HTML_ALIASES)
        assets_raw = self._first_raw(fields, self._ASSET_ALIASES)

        if not title:
            title = str(fact_result.generation_context.get("requested_title", "Generated Page")).strip() or "Generated Page"

        normalized_assets = self._normalize_assets(assets_raw)
        normalized_fields = {
            "title": title,
            "html_content": html_content,
            "assets": normalized_assets,
        }

        violations = []
        violations.extend(self.consistency_checker.validate_required_fields(normalized_fields, ["title", "html_content"]))
        violations.extend(
            self.consistency_checker.detect_unresolved_references(
                {"title": title, "html_content": html_content}
            )
        )

        lowered_html = html_content.lower()
        if "<script" in lowered_html:
            violations.append("unsafe-html:script-tag")
        if "javascript:" in lowered_html:
            violations.append("unsafe-html:javascript-url")

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
        page = self.mainpage_service.publish_page_draft(
            draft_id=draft_id,
            title=str(validation_result.normalized_fields.get("title", "Generated Page")),
            html_content=str(validation_result.normalized_fields.get("html_content", "")),
            assets=validation_result.normalized_fields.get("assets", []),
        )
        return PublicationResult(
            output={
                "draft_id": draft_id,
                "page_id": page.page_id,
                "slug": page.slug,
                "url": f"/main/{page.slug}",
                "title": page.title,
                "publication_status": "published",
            },
            facts=[f"已发布网页={page.page_id}", f"网页路径=/main/{page.slug}"],
            events=[
                StoryEvent(
                    name="ContentPublished",
                    detail="网页已通过五步骤链正式发布。",
                    metadata={"page_id": page.page_id, "draft_id": draft_id, "slug": page.slug},
                )
            ],
        )

    @staticmethod
    def _first_non_empty(fields: dict[str, object], aliases: tuple[str, ...]) -> str:
        for alias in aliases:
            value = str(fields.get(alias, "")).strip()
            if value:
                return value
        return ""

    @staticmethod
    def _first_raw(fields: dict[str, object], aliases: tuple[str, ...]) -> object:
        for alias in aliases:
            if alias in fields:
                return fields.get(alias)
        return []

    @staticmethod
    def _normalize_assets(raw_assets: object) -> list[dict[str, str]]:
        if isinstance(raw_assets, str):
            try:
                parsed = json.loads(raw_assets)
            except json.JSONDecodeError:
                parsed = []
        else:
            parsed = raw_assets

        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in parsed[:20]:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            content = str(item.get("content", "")).strip()
            content_type = str(item.get("content_type", "text/plain")).strip() or "text/plain"
            if not path or not content:
                continue
            normalized.append(
                {
                    "path": path[:200],
                    "content": content[:20000],
                    "content_type": content_type[:80],
                }
            )
        return normalized


class MainReadPageWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, mainpage_service: MainPageService) -> None:
        self.mainpage_service = mainpage_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="main.read_page",
            site="main",
            description="Read a published main page by slug.",
            input_schema={"slug": "string"},
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        slug = str(request.payload.get("slug", "")).strip()
        if not slug:
            raise ValueError("slug is required")

        page = self.mainpage_service.get_page_by_slug(slug=slug)
        if page is None:
            raise ValueError(f"Main page not found: {slug}")

        return FactExecutionResult(
            capability=request.capability,
            site="main",
            actor_id=request.actor_id,
            facts=[f"读取网页={page.page_id}", f"网页路径=/main/{page.slug}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="网页读取完成。",
                    metadata={"page_id": page.page_id, "slug": page.slug},
                )
            ],
            output={
                "page_id": page.page_id,
                "slug": page.slug,
                "title": page.title,
                "url": f"/main/{page.slug}",
                "published_at": page.published_at,
            },
            generation_context={"slug": page.slug},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class MainPagePipelineToolExecutor(FiveStageToolExecutor):
    def __init__(
        self,
        mainpage_service: MainPageService,
        consistency_checker: ConsistencyChecker,
        content_generator: AbstractStructuredContentGenerator,
    ) -> None:
        workflows = [
            MainGeneratePageWorkflow(mainpage_service, consistency_checker),
            MainReadPageWorkflow(mainpage_service),
        ]
        super().__init__(workflows=workflows, content_generator=content_generator)
