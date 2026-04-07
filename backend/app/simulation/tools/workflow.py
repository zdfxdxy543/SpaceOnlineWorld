from __future__ import annotations

from abc import ABC, abstractmethod

from app.infrastructure.llm.structured_content import AbstractStructuredContentGenerator
from app.simulation.protocol import (
    ActionRequest,
    ActionResult,
    CapabilitySpec,
    ConsistencyCheckResult,
    ContentGenerationRequest,
    FactExecutionResult,
    GeneratedContent,
    PublicationResult,
)
from app.simulation.tools.base import AbstractToolExecutor


class AbstractCapabilityWorkflow(ABC):
    @property
    @abstractmethod
    def capability(self) -> CapabilitySpec:
        raise NotImplementedError

    @abstractmethod
    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        raise NotImplementedError

    def build_generation_request(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
    ) -> ContentGenerationRequest | None:
        return None

    def validate_generated_content(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        generated_content: GeneratedContent,
    ) -> ConsistencyCheckResult:
        return ConsistencyCheckResult(passed=True, normalized_fields=generated_content.fields)

    @abstractmethod
    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        raise NotImplementedError


class FiveStageToolExecutor(AbstractToolExecutor):
    def __init__(
        self,
        *,
        workflows: list[AbstractCapabilityWorkflow],
        content_generator: AbstractStructuredContentGenerator,
    ) -> None:
        self._workflows = {workflow.capability.name: workflow for workflow in workflows}
        self._content_generator = content_generator
        self._idempotency_cache: dict[str, ActionResult] = {}

    def list_capabilities(self) -> list[CapabilitySpec]:
        return [workflow.capability for workflow in self._workflows.values()]

    def execute(self, request: ActionRequest) -> ActionResult:
        if request.idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[request.idempotency_key]

        workflow = self._workflows.get(request.capability)
        if workflow is None:
            return ActionResult(
                action_id=request.action_id,
                capability=request.capability,
                status="failed",
                error_code="unsupported_capability",
                error_message=f"Unsupported capability: {request.capability}",
            )

        try:
            fact_result = workflow.execute_facts(request)
        except Exception as error:
            return ActionResult(
                action_id=request.action_id,
                capability=request.capability,
                status="failed",
                error_code="fact_execution_failed",
                error_message=str(error),
                pipeline={
                    "mode": "five_stage_write",
                    "stages_completed": [],
                    "content_generation": {"used": False, "source": "none"},
                },
            )

        events = list(fact_result.events)
        facts = list(fact_result.facts)
        pipeline = {
            "mode": "five_stage_write" if fact_result.requires_content_generation else "facts_only",
            "stages_completed": ["facts_executed"],
            "content_generation": {"used": False, "source": "none"},
            "draft": fact_result.output,
        }

        validation_result = ConsistencyCheckResult(passed=True, normalized_fields={})

        if fact_result.requires_content_generation:
            generation_request = workflow.build_generation_request(request, fact_result)
            if generation_request is None:
                return ActionResult(
                    action_id=request.action_id,
                    capability=request.capability,
                    status="failed",
                    output=fact_result.output,
                    facts=facts,
                    events=events,
                    pipeline=pipeline,
                    error_code="missing_generation_request",
                    error_message="Capability requires content generation but no generation request was built.",
                )

            try:
                generated = self._content_generator.generate(generation_request)
            except Exception as error:
                return ActionResult(
                    action_id=request.action_id,
                    capability=request.capability,
                    status="failed",
                    output=fact_result.output,
                    facts=facts,
                    events=events,
                    pipeline=pipeline,
                    error_code="content_generation_failed",
                    error_message=str(error),
                )
            pipeline["stages_completed"].append("content_generated")
            pipeline["content_generation"] = {
                "used": True,
                "source": generated.source,
                "metadata": generated.metadata,
            }
            validation_result = workflow.validate_generated_content(request, fact_result, generated)
            pipeline["stages_completed"].append("consistency_checked")
            pipeline["consistency"] = {
                "passed": validation_result.passed,
                "violations": validation_result.violations,
            }
            if not validation_result.passed:
                result = ActionResult(
                    action_id=request.action_id,
                    capability=request.capability,
                    status="failed",
                    output=fact_result.output,
                    facts=facts,
                    events=events,
                    pipeline=pipeline,
                    error_code="consistency_check_failed",
                    error_message="Generated content failed consistency validation.",
                )
                return result

        try:
            publication = workflow.publish(request, fact_result, validation_result)
        except Exception as error:
            return ActionResult(
                action_id=request.action_id,
                capability=request.capability,
                status="failed",
                output=fact_result.output,
                facts=facts,
                events=events,
                pipeline=pipeline,
                error_code="publication_failed",
                error_message=str(error),
            )
        pipeline["stages_completed"].append("published")
        pipeline["publication"] = publication.output
        result = ActionResult(
            action_id=request.action_id,
            capability=request.capability,
            status="success",
            output=publication.output,
            facts=facts + publication.facts,
            events=events + publication.events,
            pipeline=pipeline,
        )
        self._idempotency_cache[request.idempotency_key] = result
        return result
