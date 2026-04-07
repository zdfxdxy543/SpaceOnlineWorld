from __future__ import annotations

from pydantic import BaseModel, Field


class NewsStatsResponse(BaseModel):
    total_articles: int
    total_categories: int
    online_users: int


class CategoryResponse(BaseModel):
    slug: str
    name: str
    description: str
    article_count: int


class ArticleSummaryResponse(BaseModel):
    article_id: str
    title: str
    category: str
    stage: str
    author_id: str
    published_at: str
    views: int
    is_pinned: bool
    excerpt: str


class ArticleDetailResponse(ArticleSummaryResponse):
    content: str
    related_thread_ids: list[str] = Field(default_factory=list)
    related_share_ids: list[str] = Field(default_factory=list)


class HotArticlesResponse(BaseModel):
    articles: list[ArticleSummaryResponse]


class CategoryListResponse(BaseModel):
    categories: list[CategoryResponse]


class CategoryDetailResponse(BaseModel):
    category: CategoryResponse
    articles: list[ArticleSummaryResponse]


class ArticlesResponse(BaseModel):
    articles: list[ArticleSummaryResponse]
    total: int
    category: str | None = None


class CreateArticleRequest(BaseModel):
    title: str
    content: str
    category: str
    stage: str = "breaking"
    author_id: str
    is_pinned: bool = False
    related_thread_ids: list[str] = Field(default_factory=list)
    related_share_ids: list[str] = Field(default_factory=list)


class CreateArticleResponse(BaseModel):
    article: ArticleDetailResponse


class UpdateArticleRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    stage: str | None = None
    is_pinned: bool | None = None
    related_thread_ids: list[str] | None = None
    related_share_ids: list[str] | None = None


class UpdateArticleResponse(BaseModel):
    article: ArticleDetailResponse
