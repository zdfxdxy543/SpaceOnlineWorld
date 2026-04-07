from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class NewsStats:
    total_articles: int
    total_categories: int
    online_users: int


@dataclass(slots=True)
class CategorySummary:
    slug: str
    name: str
    description: str
    article_count: int


@dataclass(slots=True)
class ArticleSummary:
    article_id: str
    title: str
    category: str
    stage: str
    author_id: str
    published_at: str
    views: int
    is_pinned: bool
    excerpt: str


@dataclass(slots=True)
class ArticleDetail(ArticleSummary):
    content: str
    related_thread_ids: list[str]
    related_share_ids: list[str]


@dataclass(slots=True)
class NewsArticleDraft:
    draft_id: str
    article_id: str
    author_id: str
    category: str
    requested_title: str
    requested_content: str
    requested_stage: str
    requested_is_pinned: bool
    requested_related_thread_ids: list[str]
    requested_related_share_ids: list[str]
    created_at: str


class AbstractNewsRepository(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_stats(self) -> NewsStats:
        raise NotImplementedError

    @abstractmethod
    def list_categories(self) -> list[CategorySummary]:
        raise NotImplementedError

    @abstractmethod
    def get_category(self, category_slug: str) -> CategorySummary | None:
        raise NotImplementedError

    @abstractmethod
    def list_articles(self, category: str | None = None, limit: int = 20) -> list[ArticleSummary]:
        raise NotImplementedError

    @abstractmethod
    def get_article(self, article_id: str) -> ArticleDetail | None:
        raise NotImplementedError

    @abstractmethod
    def get_hot_articles(self, limit: int = 5) -> list[ArticleSummary]:
        raise NotImplementedError

    @abstractmethod
    def create_article(
        self,
        *,
        title: str,
        content: str,
        category: str,
        stage: str,
        author_id: str,
        is_pinned: bool = False,
        related_thread_ids: list[str] = None,
        related_share_ids: list[str] = None,
    ) -> ArticleDetail:
        raise NotImplementedError

    @abstractmethod
    def update_article(
        self,
        *,
        article_id: str,
        title: str | None = None,
        content: str | None = None,
        category: str | None = None,
        stage: str | None = None,
        is_pinned: bool | None = None,
        related_thread_ids: list[str] | None = None,
        related_share_ids: list[str] | None = None,
    ) -> ArticleDetail | None:
        raise NotImplementedError

    @abstractmethod
    def delete_article(self, article_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def increment_article_views(self, article_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def create_article_draft(
        self,
        *,
        category: str,
        author_id: str,
        requested_title: str,
        requested_content: str,
        requested_stage: str,
        requested_is_pinned: bool = False,
        requested_related_thread_ids: list[str] = None,
        requested_related_share_ids: list[str] = None,
    ) -> NewsArticleDraft:
        raise NotImplementedError

    @abstractmethod
    def publish_article_draft(
        self,
        *,
        draft_id: str,
        title: str,
        content: str,
        stage: str,
        is_pinned: bool = False,
        related_thread_ids: list[str] = None,
        related_share_ids: list[str] = None,
    ) -> ArticleDetail:
        raise NotImplementedError
