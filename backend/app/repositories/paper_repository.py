from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class PaperStats:
    total_papers: int
    total_journals: int


@dataclass(slots=True)
class CategorySummary:
    id: str
    name: str
    paper_count: int


@dataclass(slots=True)
class PaperSummary:
    paper_id: str
    title: str
    authors: list[str]
    institution: str
    journal: str
    publish_date: str
    keywords: list[str]
    downloads: int
    pages: int
    file_size: int
    file_name: str


@dataclass(slots=True)
class PaperDetail(PaperSummary):
    abstract: str


@dataclass(slots=True)
class PaperDraft:
    draft_id: str
    paper_id: str
    requested_title: str
    requested_authors: list[str]
    requested_institution: str
    requested_journal: str
    requested_publish_date: str
    requested_keywords: list[str]
    requested_abstract: str
    requested_pages: int
    created_at: str


class AbstractPaperRepository(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_stats(self) -> PaperStats:
        raise NotImplementedError

    @abstractmethod
    def list_categories(self) -> list[CategorySummary]:
        raise NotImplementedError

    @abstractmethod
    def list_papers(self, category: str | None = None, limit: int = 20) -> list[PaperSummary]:
        raise NotImplementedError

    @abstractmethod
    def get_paper(self, paper_id: str) -> PaperDetail | None:
        raise NotImplementedError

    @abstractmethod
    def get_hot_papers(self, limit: int = 5) -> list[PaperSummary]:
        raise NotImplementedError

    @abstractmethod
    def search_papers(
        self,
        query: str | None = None,
        field: str | None = None,
        category: str | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[PaperSummary]:
        raise NotImplementedError

    @abstractmethod
    def create_paper(
        self,
        *,
        title: str,
        authors: list[str],
        institution: str,
        journal: str,
        publish_date: str,
        keywords: list[str],
        abstract: str,
        pages: int,
        file_name: str,
        file_size: int,
    ) -> PaperDetail:
        raise NotImplementedError

    @abstractmethod
    def increment_downloads(self, paper_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def create_paper_draft(
        self,
        *,
        requested_title: str,
        requested_authors: list[str],
        requested_institution: str,
        requested_journal: str,
        requested_publish_date: str,
        requested_keywords: list[str],
        requested_abstract: str,
        requested_pages: int,
    ) -> PaperDraft:
        raise NotImplementedError

    @abstractmethod
    def publish_paper_draft(
        self,
        *,
        draft_id: str,
        title: str,
        authors: list[str],
        institution: str,
        journal: str,
        publish_date: str,
        keywords: list[str],
        abstract: str,
        pages: int,
        file_name: str,
        file_size: int,
    ) -> PaperDetail:
        raise NotImplementedError
