from __future__ import annotations

from app.repositories.paper_repository import (
    AbstractPaperRepository,
    CategorySummary,
    PaperDetail,
    PaperDraft,
    PaperStats,
    PaperSummary,
)


class PaperService:
    def __init__(self, paper_repository: AbstractPaperRepository) -> None:
        self.paper_repository = paper_repository

    def get_stats(self) -> PaperStats:
        return self.paper_repository.get_stats()

    def list_categories(self) -> list[CategorySummary]:
        return self.paper_repository.list_categories()

    def list_papers(self, category: str | None = None, limit: int = 20) -> list[PaperSummary]:
        return self.paper_repository.list_papers(category=category, limit=limit)

    def get_paper(self, paper_id: str) -> PaperDetail | None:
        paper = self.paper_repository.get_paper(paper_id)
        return paper

    def get_hot_papers(self, limit: int = 5) -> list[PaperSummary]:
        return self.paper_repository.get_hot_papers(limit)

    def search_papers(
        self,
        query: str | None = None,
        field: str | None = None,
        category: str | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[PaperSummary]:
        return self.paper_repository.search_papers(
            query=query,
            field=field,
            category=category,
            year_start=year_start,
            year_end=year_end,
        )

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
        return self.paper_repository.create_paper(
            title=title,
            authors=authors,
            institution=institution,
            journal=journal,
            publish_date=publish_date,
            keywords=keywords,
            abstract=abstract,
            pages=pages,
            file_name=file_name,
            file_size=file_size,
        )

    def increment_downloads(self, paper_id: str) -> bool:
        return self.paper_repository.increment_downloads(paper_id)

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
        return self.paper_repository.create_paper_draft(
            requested_title=requested_title,
            requested_authors=requested_authors,
            requested_institution=requested_institution,
            requested_journal=requested_journal,
            requested_publish_date=requested_publish_date,
            requested_keywords=requested_keywords,
            requested_abstract=requested_abstract,
            requested_pages=requested_pages,
        )

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
        return self.paper_repository.publish_paper_draft(
            draft_id=draft_id,
            title=title,
            authors=authors,
            institution=institution,
            journal=journal,
            publish_date=publish_date,
            keywords=keywords,
            abstract=abstract,
            pages=pages,
            file_name=file_name,
            file_size=file_size,
        )
