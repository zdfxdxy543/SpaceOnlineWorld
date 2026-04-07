from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import DraftPostPlan


class AbstractLLMClient(ABC):
    @abstractmethod
    def generate_forum_post(self, plan: DraftPostPlan) -> str:
        raise NotImplementedError
