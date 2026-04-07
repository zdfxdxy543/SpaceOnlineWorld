from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class MainPageDraft:
    draft_id: str
    page_id: str
    author_id: str
    slug: str
    requested_title: str
    requested_description: str
    requested_style: str
    created_at: str


@dataclass(slots=True)
class MainPageRecord:
    page_id: str
    slug: str
    title: str
    html_content: str
    assets_json: str
    author_id: str
    published_at: str
    updated_at: str


class AbstractMainPageRepository(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_page_draft(
        self,
        *,
        author_id: str,
        slug_hint: str,
        requested_title: str,
        requested_description: str,
        requested_style: str,
    ) -> MainPageDraft:
        raise NotImplementedError

    @abstractmethod
    def get_page_draft(self, *, draft_id: str) -> MainPageDraft | None:
        raise NotImplementedError

    @abstractmethod
    def publish_page_draft(
        self,
        *,
        draft_id: str,
        title: str,
        html_content: str,
        assets_json: str,
    ) -> MainPageRecord:
        raise NotImplementedError

    @abstractmethod
    def get_page_by_slug(self, *, slug: str) -> MainPageRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_pages(self, *, limit: int = 50) -> list[MainPageRecord]:
        raise NotImplementedError
