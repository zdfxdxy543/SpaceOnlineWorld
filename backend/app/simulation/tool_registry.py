from __future__ import annotations

from app.simulation.protocol import ActionRequest, ActionResult, CapabilitySpec
from app.simulation.tools.base import AbstractToolExecutor


class ToolRegistry:
    def __init__(self, executors: list[AbstractToolExecutor]) -> None:
        self._executors = executors
        self._capability_map: dict[str, AbstractToolExecutor] = {}
        for executor in executors:
            for capability in executor.list_capabilities():
                self._capability_map[capability.name] = executor

    def list_capabilities(self) -> list[CapabilitySpec]:
        all_items: list[CapabilitySpec] = []
        for executor in self._executors:
            all_items.extend(executor.list_capabilities())
        return all_items

    def execute(self, request: ActionRequest) -> ActionResult:
        executor = self._capability_map.get(request.capability)
        if executor is None:
            return ActionResult(
                action_id=request.action_id,
                capability=request.capability,
                status="failed",
                error_code="capability_not_found",
                error_message=f"Capability not found: {request.capability}",
            )
        return executor.execute(request)
