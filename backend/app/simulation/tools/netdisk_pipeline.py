from __future__ import annotations

from app.domain.events import StoryEvent
from app.infrastructure.llm.structured_content import AbstractStructuredContentGenerator
from app.services.netdisk_service import NetdiskService
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


class NetdiskUploadWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, netdisk_service: NetdiskService) -> None:
        self.netdisk_service = netdisk_service

    @staticmethod
    def _select_document_type(*, title: str, purpose: str, file_name: str) -> str:
        combined = f"{title} {purpose} {file_name}".lower()
        if any(token in combined for token in ["timeline", "sequence", "chronology", "log"]):
            return "timeline_note"
        if any(token in combined for token in ["witness", "statement", "testimony", "memo"]):
            return "witness_memo"
        return "incident_report"

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="netdisk.upload_file",
            site="netdisk",
            description="Generate file content via LLM and persist file locally.",
            input_schema={
                "title": "string",
                "purpose": "string",
                "file_name": "string optional",
            },
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        title = str(request.payload.get("title", "Untitled File")).strip() or "Untitled File"
        purpose = str(request.payload.get("purpose", "General upload")).strip() or "General upload"
        file_name = str(request.payload.get("file_name", "report.txt")).strip() or "report.txt"

        draft = self.netdisk_service.create_upload_draft(
            owner_agent_id=request.actor_id,
            title=title,
            purpose=purpose,
            requested_file_name=file_name,
        )
        document_type = self._select_document_type(title=title, purpose=purpose, file_name=file_name)

        return FactExecutionResult(
            capability=request.capability,
            site="netdisk",
            actor_id=request.actor_id,
            facts=[f"网盘草稿={draft.draft_id}", f"保留资源ID={draft.resource_id}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="网盘上传草稿已创建，等待内容生成。",
                    metadata={"draft_id": draft.draft_id, "resource_id": draft.resource_id},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="网盘上传草稿已持久化到数据库。",
                    metadata={"draft_id": draft.draft_id},
                ),
            ],
            output={"draft_id": draft.draft_id, "resource_id": draft.resource_id, "status": "draft_created"},
            generation_context={
                "draft_id": draft.draft_id,
                "resource_id": draft.resource_id,
                "title": draft.title,
                "purpose": draft.purpose,
                "file_name": draft.requested_file_name,
                "document_type": document_type,
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
            site="netdisk",
            actor_id=request.actor_id,
            instruction=(
                "Generate English plain-text evidence file content based on title, purpose, and document_type. "
                "Return realistic in-world file text, not instructions."
            ),
            desired_fields=["file_content", "file_name"],
            fact_context=fact_result.generation_context,
            style_context={
                "tone": "evidence_file",
                "language": "en",
                "format": "plain_text",
                "document_type": fact_result.generation_context.get("document_type", "incident_report"),
            },
        )

    # Aliases the LLM may return instead of the canonical field names
    _FILE_CONTENT_ALIASES = ("file_content", "content", "text", "body", "file_body", "document", "file_text")
    _FILE_NAME_ALIASES = ("file_name", "filename", "name", "file")

    def validate_generated_content(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        generated_content: GeneratedContent,
    ) -> ConsistencyCheckResult:
        fields = generated_content.fields

        # Resolve file_content from aliases
        file_content = ""
        for alias in self._FILE_CONTENT_ALIASES:
            candidate = str(fields.get(alias, "")).strip()
            if candidate:
                file_content = candidate
                break

        # Resolve file_name from aliases
        file_name = ""
        for alias in self._FILE_NAME_ALIASES:
            candidate = str(fields.get(alias, "")).strip()
            if candidate:
                file_name = candidate
                break
        if not file_name:
            file_name = str(fact_result.generation_context.get("file_name", "report.txt")).strip() or "report.txt"

        violations: list[str] = []
        if not file_content:
            returned_keys = ", ".join(fields.keys()) if fields else "<none>"
            violations.append(f"missing-field:file_content (returned keys: {returned_keys})")
        if not file_name:
            violations.append("missing-field:file_name")

        lowered_content = file_content.lower()
        _PROMPT_LEAK_SUBSTRINGS = (
            "generate english plain-text evidence file content",
            "generate english plain-text file content based on title and purpose",
            "return realistic in-world file text, not instructions",
            "return concise but realistic content",
        )
        if any(s in lowered_content for s in _PROMPT_LEAK_SUBSTRINGS):
            violations.append("prompt-leak:file_content")

        return ConsistencyCheckResult(
            passed=not violations,
            violations=violations,
            normalized_fields={"file_content": file_content, "file_name": file_name},
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        draft_id = str(fact_result.output["draft_id"])
        published = self.netdisk_service.publish_upload_draft(
            draft_id=draft_id,
            file_name=validation_result.normalized_fields["file_name"],
            file_content=validation_result.normalized_fields["file_content"],
        )
        return PublicationResult(
            output={
                "draft_id": draft_id,
                "resource_id": published.resource_id,
                "title": published.title,
                "file_name": published.file_name,
                "local_path": published.local_path,
                "size_bytes": published.size_bytes,
                "content_hash": published.content_hash,
                "publication_status": "published",
            },
            facts=[f"已上传网盘文件={published.resource_id}"],
            events=[
                StoryEvent(
                    name="ContentPublished",
                    detail="网盘文件已生成并保存到本地。",
                    metadata={"resource_id": published.resource_id, "draft_id": draft_id},
                )
            ],
        )


class NetdiskCreateShareWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, netdisk_service: NetdiskService) -> None:
        self.netdisk_service = netdisk_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="netdisk.create_share_link",
            site="netdisk",
            description="Create share link and access code for a netdisk resource.",
            input_schema={"resource_id": "string", "expires_hours": "integer optional"},
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        resource_id = str(request.payload.get("resource_id", "")).strip()
        if not resource_id:
            raise ValueError("resource_id is required")
        expires_hours_raw = request.payload.get("expires_hours")
        expires_hours = None
        if expires_hours_raw is not None:
            expires_hours = int(expires_hours_raw)

        share = self.netdisk_service.create_share_link(
            resource_id=resource_id,
            creator_agent_id=request.actor_id,
            expires_hours=expires_hours,
        )
        return FactExecutionResult(
            capability=request.capability,
            site="netdisk",
            actor_id=request.actor_id,
            facts=[f"分享链接={share.share_id}", f"网盘资源={share.resource_id}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="网盘分享链接已创建。",
                    metadata={"share_id": share.share_id, "resource_id": share.resource_id},
                )
            ],
            output={
                "share_id": share.share_id,
                "resource_id": share.resource_id,
                "access_code": share.access_code,
                "share_url": share.share_url,
                "expires_at": share.expires_at,
            },
            generation_context={"share_id": share.share_id},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class NetdiskReadShareWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, netdisk_service: NetdiskService) -> None:
        self.netdisk_service = netdisk_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="netdisk.read_share_info",
            site="netdisk",
            description="Read share info by share_id and access_code.",
            input_schema={"share_id": "string", "access_code": "string"},
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        share_id = str(request.payload.get("share_id", "")).strip()
        access_code = str(request.payload.get("access_code", "")).strip()
        if not share_id or not access_code:
            raise ValueError("share_id and access_code are required")

        share = self.netdisk_service.validate_share_reference(share_id=share_id, access_code=access_code)
        if share is None:
            raise ValueError("Share not found or access code invalid")

        file_item = self.netdisk_service.get_file(resource_id=share.resource_id)
        if file_item is None:
            raise ValueError("Referenced netdisk file not found")

        return FactExecutionResult(
            capability=request.capability,
            site="netdisk",
            actor_id=request.actor_id,
            facts=[f"读取分享={share.share_id}", f"读取资源={share.resource_id}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="网盘分享信息读取完成。",
                    metadata={"share_id": share.share_id},
                )
            ],
            output={
                "share_id": share.share_id,
                "resource_id": share.resource_id,
                "share_url": share.share_url,
                "access_code": share.access_code,
                "file_name": file_item.file_name,
                "title": file_item.title,
                "purpose": file_item.purpose,
            },
            generation_context={"share_id": share.share_id},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class NetdiskPipelineToolExecutor(FiveStageToolExecutor):
    def __init__(
        self,
        netdisk_service: NetdiskService,
        content_generator: AbstractStructuredContentGenerator,
    ) -> None:
        workflows = [
            NetdiskUploadWorkflow(netdisk_service),
            NetdiskCreateShareWorkflow(netdisk_service),
            NetdiskReadShareWorkflow(netdisk_service),
        ]
        super().__init__(workflows=workflows, content_generator=content_generator)
