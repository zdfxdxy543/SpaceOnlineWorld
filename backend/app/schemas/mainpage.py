from __future__ import annotations

from pydantic import BaseModel


class MainPageGenerateRequest(BaseModel):
    actor_id: str
    title: str
    description: str
    slug: str | None = None
    style: str = "world_website"


class MainPageGenerateResponse(BaseModel):
    status: str
    page_id: str
    slug: str
    url: str
    title: str


class MainPageSummary(BaseModel):
    page_id: str
    slug: str
    title: str
    url: str
    published_at: str


class MainPageDetail(MainPageSummary):
    html_content: str
    assets: list[dict[str, str]]
    author_id: str
    updated_at: str
