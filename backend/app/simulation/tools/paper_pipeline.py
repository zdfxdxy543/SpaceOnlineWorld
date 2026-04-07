from __future__ import annotations

from app.consistency.checker import ConsistencyChecker
from app.domain.events import StoryEvent
from app.infrastructure.llm.structured_content import AbstractStructuredContentGenerator
from app.services.forum_service import ForumService
from app.services.netdisk_service import NetdiskService
from app.services.paper_service import PaperService
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


class PaperReadPapersWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, paper_service: PaperService) -> None:
        self.paper_service = paper_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="academic.read_papers",
            site="academic",
            description="Read academic papers with optional filters.",
            input_schema={
                "category": "string optional",
                "limit": "integer optional",
            },
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        category = request.payload.get("category")
        limit = int(request.payload.get("limit", 20))
        papers = self.paper_service.list_papers(category=category, limit=limit)

        return FactExecutionResult(
            capability=request.capability,
            site="academic",
            actor_id=request.actor_id,
            facts=[
                f"读取分类={category or 'all'}",
                f"读取论文数量={len(papers)}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="学术论文读取完成。",
                    metadata={"category": category},
                ),
            ],
            output={
                "papers": [
                    {
                        "paper_id": paper.paper_id,
                        "title": paper.title,
                        "authors": paper.authors,
                        "institution": paper.institution,
                        "journal": paper.journal,
                        "publish_date": paper.publish_date,
                        "keywords": paper.keywords,
                        "downloads": paper.downloads,
                        "pages": paper.pages,
                        "file_size": paper.file_size,
                        "file_name": paper.file_name,
                    }
                    for paper in papers
                ],
                "total": len(papers),
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


class PaperReadPaperWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, paper_service: PaperService) -> None:
        self.paper_service = paper_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="academic.read_paper",
            site="academic",
            description="Read academic paper detail by ID.",
            input_schema={"paper_id": "string"},
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        paper_id = str(request.payload.get("paper_id", ""))
        paper = self.paper_service.get_paper(paper_id)

        if paper is None:
            raise ValueError(f"Paper not found: {paper_id}")

        return FactExecutionResult(
            capability=request.capability,
            site="academic",
            actor_id=request.actor_id,
            facts=[
                f"论文ID={paper_id}",
                f"论文标题={paper.title}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="学术论文详情读取完成。",
                    metadata={"paper_id": paper_id},
                ),
            ],
            output={
                "paper": {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "institution": paper.institution,
                    "journal": paper.journal,
                    "publish_date": paper.publish_date,
                    "keywords": paper.keywords,
                    "abstract": paper.abstract,
                    "downloads": paper.downloads,
                    "pages": paper.pages,
                    "file_size": paper.file_size,
                    "file_name": paper.file_name,
                },
            },
            generation_context={"paper_id": paper_id},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class PaperSearchWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, paper_service: PaperService) -> None:
        self.paper_service = paper_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="academic.search_papers",
            site="academic",
            description="Search academic papers by query and filters.",
            input_schema={
                "query": "string optional",
                "field": "string optional",
                "year_start": "integer optional",
                "year_end": "integer optional",
            },
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        query = request.payload.get("query")
        field = request.payload.get("field")
        year_start = request.payload.get("year_start")
        year_end = request.payload.get("year_end")

        papers = self.paper_service.search_papers(
            query=query,
            field=field,
            year_start=year_start,
            year_end=year_end,
        )

        return FactExecutionResult(
            capability=request.capability,
            site="academic",
            actor_id=request.actor_id,
            facts=[
                f"搜索关键词={query or 'all'}",
                f"搜索结果数量={len(papers)}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="学术论文搜索完成。",
                    metadata={"query": query},
                ),
            ],
            output={
                "papers": [
                    {
                        "paper_id": paper.paper_id,
                        "title": paper.title,
                        "authors": paper.authors,
                        "institution": paper.institution,
                        "journal": paper.journal,
                        "publish_date": paper.publish_date,
                        "keywords": paper.keywords,
                        "downloads": paper.downloads,
                        "pages": paper.pages,
                        "file_size": paper.file_size,
                        "file_name": paper.file_name,
                    }
                    for paper in papers
                ],
                "total": len(papers),
                "query": query,
            },
            generation_context={"query": query},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class PaperPublishWorkflow(AbstractCapabilityWorkflow):
    def __init__(
        self,
        paper_service: PaperService,
        consistency_checker: ConsistencyChecker,
        content_generator: AbstractStructuredContentGenerator,
        forum_service: ForumService,
        netdisk_service: NetdiskService,
    ) -> None:
        self.paper_service = paper_service
        self.consistency_checker = consistency_checker
        self.content_generator = content_generator
        self.forum_service = forum_service
        self.netdisk_service = netdisk_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="academic.publish_paper",
            site="academic",
            description="Publish an academic paper through the fact-first pipeline.",
            input_schema={
                "title": "string",
                "authors": "string[]",
                "institution": "string",
                "journal": "string",
                "publish_date": "string",
                "keywords": "string[]",
                "abstract": "string",
                "pages": "integer",
                "file_name": "string",
                "file_size": "integer optional",
                "related_thread_ids": "string[] optional",
                "related_share_ids": "string[] optional",
            },
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        title = str(request.payload.get("title", ""))
        authors_raw = request.payload.get("authors", [])
        institution = str(request.payload.get("institution", ""))
        journal = str(request.payload.get("journal", ""))
        publish_date = str(request.payload.get("publish_date", ""))
        keywords_raw = request.payload.get("keywords", [])
        abstract = str(request.payload.get("abstract", ""))
        pages = int(request.payload.get("pages", 10))
        file_name = str(request.payload.get("file_name", ""))
        file_size = int(request.payload.get("file_size", 0))
        related_thread_ids_raw = request.payload.get("related_thread_ids", [])
        related_share_ids_raw = request.payload.get("related_share_ids", [])

        if not isinstance(authors_raw, list):
            raise ValueError("authors must be a list")
        if not isinstance(keywords_raw, list):
            raise ValueError("keywords must be a list")
        if not isinstance(related_thread_ids_raw, list):
            raise ValueError("related_thread_ids must be a list")
        if not isinstance(related_share_ids_raw, list):
            raise ValueError("related_share_ids must be a list")

        authors = [str(item).strip() for item in authors_raw if str(item).strip()]
        keywords = [str(item).strip() for item in keywords_raw if str(item).strip()]
        related_thread_ids = [str(item).strip() for item in related_thread_ids_raw if str(item).strip()]
        related_share_ids = [str(item).strip() for item in related_share_ids_raw if str(item).strip()]

        for thread_id in related_thread_ids:
            if self.forum_service.get_thread(thread_id) is None:
                raise ValueError(f"Related forum thread not found: {thread_id}")

        for share_id in related_share_ids:
            if self.netdisk_service.get_share(share_id=share_id) is None:
                raise ValueError(f"Related netdisk share not found: {share_id}")

        if not journal:
            journal = "Academic Journal"

        if not publish_date:
            from datetime import datetime
            publish_date = datetime.now().strftime("%Y-%m-%d")

        if not file_name:
            first_author = authors[0] if authors else "author"
            year = publish_date[:4] if len(publish_date) >= 4 else "unknown"
            file_name = f"{first_author}_{title[:20].replace(' ', '_')}_{year}.pdf".lower()

        draft = self.paper_service.create_paper_draft(
            requested_title=title,
            requested_authors=authors,
            requested_institution=institution,
            requested_journal=journal,
            requested_publish_date=publish_date,
            requested_keywords=keywords,
            requested_abstract=abstract,
            requested_pages=pages,
        )

        return FactExecutionResult(
            capability=request.capability,
            site="academic",
            actor_id=request.actor_id,
            facts=[
                f"论文草稿={draft.draft_id}",
                f"论文ID={draft.paper_id}",
                f"目标期刊={draft.requested_journal}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="学术论文草稿事实已创建，等待内容生成。",
                    metadata={"draft_id": draft.draft_id, "paper_id": draft.paper_id},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="学术论文草稿已持久化到数据库。",
                    metadata={"draft_id": draft.draft_id},
                ),
            ],
            output={
                "draft_id": draft.draft_id,
                "paper_id": draft.paper_id,
                "status": "draft_created",
            },
            generation_context={
                "draft_id": draft.draft_id,
                "paper_id": draft.paper_id,
                "requested_title": draft.requested_title,
                "requested_authors": draft.requested_authors,
                "requested_institution": draft.requested_institution,
                "requested_journal": draft.requested_journal,
                "requested_publish_date": draft.requested_publish_date,
                "requested_keywords": draft.requested_keywords,
                "requested_abstract": draft.requested_abstract,
                "requested_pages": draft.requested_pages,
                "file_name": file_name,
                "file_size": file_size,
                "related_thread_ids": related_thread_ids,
                "related_share_ids": related_share_ids,
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
            site="academic",
            actor_id=request.actor_id,
            instruction=(
                "Based on the created academic paper draft and fact context, generate a complete academic paper. "
                "The paper should have a proper academic title, authors, institution, abstract, and content structure. "
                "Generate realistic academic content that matches the specified field and topic. "
                "If related_thread_ids or related_share_ids are present, reference them appropriately."
            ),
            desired_fields=["title", "abstract", "keywords", "content"],
            fact_context=fact_result.generation_context,
            style_context={"tone": "academic_paper", "avoid_meta_prompt": True, "language": "en"},
        )

    def validate_generated_content(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        generated_content: GeneratedContent,
    ) -> ConsistencyCheckResult:
        title = str(generated_content.fields.get("title", ""))
        abstract = str(generated_content.fields.get("abstract", ""))
        keywords_raw = generated_content.fields.get("keywords", [])
        content = str(generated_content.fields.get("content", ""))

        if isinstance(keywords_raw, list):
            keywords = [str(k).strip() for k in keywords_raw if str(k).strip()]
        elif isinstance(keywords_raw, str):
            keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        else:
            keywords = []

        normalized_fields = {
            "title": title,
            "abstract": abstract,
            "keywords": keywords,
            "content": content,
        }
        violations = []
        violations.extend(self.consistency_checker.validate_required_fields(normalized_fields, ["title", "abstract"]))
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
        file_name = str(fact_result.generation_context.get("file_name", ""))
        file_size = int(fact_result.generation_context.get("file_size", 0))

        paper = self.paper_service.publish_paper_draft(
            draft_id=draft_id,
            title=validation_result.normalized_fields["title"],
            authors=fact_result.generation_context.get("requested_authors", []),
            institution=fact_result.generation_context.get("requested_institution", ""),
            journal=fact_result.generation_context.get("requested_journal", ""),
            publish_date=fact_result.generation_context.get("requested_publish_date", ""),
            keywords=validation_result.normalized_fields.get("keywords", []),
            abstract=validation_result.normalized_fields["abstract"],
            pages=fact_result.generation_context.get("requested_pages", 10),
            file_name=file_name,
            file_size=file_size,
        )

        return PublicationResult(
            output={
                "draft_id": draft_id,
                "paper_id": paper.paper_id,
                "paper": {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "institution": paper.institution,
                    "journal": paper.journal,
                    "publish_date": paper.publish_date,
                    "keywords": paper.keywords,
                    "abstract": paper.abstract,
                    "pages": paper.pages,
                    "file_name": paper.file_name,
                    "file_size": paper.file_size,
                    "downloads": paper.downloads,
                },
            },
            facts=[
                f"论文已发布={paper.paper_id}",
                f"标题={paper.title}",
            ],
            events=[
                StoryEvent(
                    name="PublicationCompleted",
                    detail=f"学术论文已发布: {paper.title}",
                    metadata={"paper_id": paper.paper_id},
                ),
            ],
        )


class PaperPipelineToolExecutor(FiveStageToolExecutor):
    def __init__(
        self,
        paper_service: PaperService,
        consistency_checker: ConsistencyChecker,
        content_generator: AbstractStructuredContentGenerator,
        forum_service: ForumService,
        netdisk_service: NetdiskService,
    ) -> None:
        workflows = [
            PaperReadPapersWorkflow(paper_service),
            PaperReadPaperWorkflow(paper_service),
            PaperSearchWorkflow(paper_service),
            PaperPublishWorkflow(paper_service, consistency_checker, content_generator, forum_service, netdisk_service),
        ]
        super().__init__(workflows=workflows, content_generator=content_generator)
