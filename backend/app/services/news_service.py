from __future__ import annotations

from app.repositories.news_repository import (
    AbstractNewsRepository,
    ArticleDetail,
    ArticleSummary,
    CategorySummary,
    NewsArticleDraft,
    NewsStats,
)


class NewsService:
    def __init__(self, news_repository: AbstractNewsRepository) -> None:
        self.news_repository = news_repository

    def get_stats(self) -> NewsStats:
        return self.news_repository.get_stats()

    def list_categories(self) -> list[CategorySummary]:
        return self.news_repository.list_categories()

    def get_category(self, category_slug: str) -> CategorySummary | None:
        return self.news_repository.get_category(category_slug)

    def list_articles(self, category: str | None = None, limit: int = 20) -> list[ArticleSummary]:
        return self.news_repository.list_articles(category=category, limit=limit)

    def get_article(self, article_id: str) -> ArticleDetail | None:
        article = self.news_repository.get_article(article_id)
        if article:
            self.news_repository.increment_article_views(article_id)
        return article

    def get_hot_articles(self, limit: int = 5) -> list[ArticleSummary]:
        return self.news_repository.get_hot_articles(limit)

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
        return self.news_repository.create_article(
            title=title,
            content=content,
            category=category,
            stage=stage,
            author_id=author_id,
            is_pinned=is_pinned,
            related_thread_ids=related_thread_ids,
            related_share_ids=related_share_ids,
        )

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
        return self.news_repository.update_article(
            article_id=article_id,
            title=title,
            content=content,
            category=category,
            stage=stage,
            is_pinned=is_pinned,
            related_thread_ids=related_thread_ids,
            related_share_ids=related_share_ids,
        )

    def delete_article(self, article_id: str) -> bool:
        return self.news_repository.delete_article(article_id)

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
        return self.news_repository.create_article_draft(
            category=category,
            author_id=author_id,
            requested_title=requested_title,
            requested_content=requested_content,
            requested_stage=requested_stage,
            requested_is_pinned=requested_is_pinned,
            requested_related_thread_ids=requested_related_thread_ids,
            requested_related_share_ids=requested_related_share_ids,
        )

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
        return self.news_repository.publish_article_draft(
            draft_id=draft_id,
            title=title,
            content=content,
            stage=stage,
            is_pinned=is_pinned,
            related_thread_ids=related_thread_ids,
            related_share_ids=related_share_ids,
        )
