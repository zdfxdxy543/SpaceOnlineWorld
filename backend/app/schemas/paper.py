from __future__ import annotations

from pydantic import BaseModel, Field


class PaperStatsResponse(BaseModel):
    total_papers: int
    total_journals: int


class CategoryResponse(BaseModel):
    id: str
    name: str
    paper_count: int


class PaperSummaryResponse(BaseModel):
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


class PaperDetailResponse(PaperSummaryResponse):
    abstract: str


class HotPapersResponse(BaseModel):
    papers: list[PaperSummaryResponse]


class CategoryListResponse(BaseModel):
    categories: list[CategoryResponse]


class PapersResponse(BaseModel):
    papers: list[PaperSummaryResponse]
    total: int


class SearchPapersRequest(BaseModel):
    query: str | None = None
    field: str | None = None
    category: str | None = None
    year_start: int | None = None
    year_end: int | None = None


class SearchPapersResponse(BaseModel):
    papers: list[PaperSummaryResponse]
    total: int
    query: str | None = None


class CreatePaperRequest(BaseModel):
    title: str
    authors: list[str]
    institution: str
    journal: str
    publish_date: str
    keywords: list[str]
    abstract: str
    pages: int
    file_name: str
    file_size: int


class CreatePaperResponse(BaseModel):
    paper: PaperDetailResponse


class DownloadPaperResponse(BaseModel):
    paper_id: str
    file_name: str
    download_url: str
