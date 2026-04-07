from __future__ import annotations

from abc import ABC, abstractmethod

from app.simulation.protocol import ActionRequest, ActionResult, CapabilitySpec


class AbstractToolExecutor(ABC):
    @abstractmethod
    def list_capabilities(self) -> list[CapabilitySpec]:
        raise NotImplementedError

    @abstractmethod
    def execute(self, request: ActionRequest) -> ActionResult:
        raise NotImplementedError
