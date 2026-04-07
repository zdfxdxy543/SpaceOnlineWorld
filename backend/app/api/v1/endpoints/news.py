from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.news import (
    ArticleDetailResponse,
    ArticlesResponse,
    CategoryDetailResponse,
    CreateArticleRequest,
    CreateArticleResponse,
    HotArticlesResponse,
    NewsStatsResponse,
    CategoryListResponse,
    CategoryResponse,
    UpdateArticleRequest,
    UpdateArticleResponse,
)

router = APIRouter()


def _map_article_summary(article):
    return {
        "article_id": article.article_id,
        "title": article.title,
        "category": article.category,
        "stage": article.stage,
        "author_id": article.author_id,
        "published_at": article.published_at,
        "views": article.views,
        "is_pinned": article.is_pinned,
        "excerpt": article.excerpt,
    }


def _map_article_detail(article):
    result = _map_article_summary(article)
    result.update({
        "content": article.content,
        "related_thread_ids": article.related_thread_ids,
        "related_share_ids": article.related_share_ids,
    })
    return result


def _map_category(category):
    return {
        "slug": category.slug,
        "name": category.name,
        "description": category.description,
        "article_count": category.article_count,
    }


@router.get("/stats", response_model=NewsStatsResponse)
def get_news_stats(request: Request) -> NewsStatsResponse:
    stats = request.app.state.container.news_service.get_stats()
    return NewsStatsResponse(
        total_articles=stats.total_articles,
        total_categories=stats.total_categories,
        online_users=stats.online_users,
    )


@router.get("/categories", response_model=CategoryListResponse)
def list_categories(request: Request) -> CategoryListResponse:
    categories = request.app.state.container.news_service.list_categories()
    return CategoryListResponse(
        categories=[_map_category(category) for category in categories]
    )


@router.get("/categories/{category_slug}", response_model=CategoryDetailResponse)
def get_category(category_slug: str, request: Request) -> CategoryDetailResponse:
    service = request.app.state.container.news_service
    category = service.get_category(category_slug)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    articles = service.list_articles(category=category_slug, limit=100)
    return CategoryDetailResponse(
        category=_map_category(category),
        articles=[_map_article_summary(article) for article in articles],
    )


@router.get("/articles", response_model=ArticlesResponse)
def list_articles(
    request: Request,
    category: str | None = Query(None, description="Filter articles by category"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of articles to return"),
) -> ArticlesResponse:
    articles = request.app.state.container.news_service.list_articles(category=category, limit=limit)
    return ArticlesResponse(
        articles=[_map_article_summary(article) for article in articles],
        total=len(articles),
        category=category,
    )


@router.get("/articles/{article_id}", response_model=ArticleDetailResponse)
def get_article(article_id: str, request: Request) -> ArticleDetailResponse:
    article = request.app.state.container.news_service.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleDetailResponse(**_map_article_detail(article))


@router.get("/hot-articles", response_model=HotArticlesResponse)
def get_hot_articles(
    request: Request,
    limit: int = Query(default=5, ge=1, le=20, description="Maximum number of hot articles to return"),
) -> HotArticlesResponse:
    articles = request.app.state.container.news_service.get_hot_articles(limit=limit)
    return HotArticlesResponse(
        articles=[_map_article_summary(article) for article in articles]
    )


@router.post("/articles", response_model=CreateArticleResponse)
def create_article(
    payload: CreateArticleRequest,
    request: Request,
) -> CreateArticleResponse:
    article = request.app.state.container.news_service.create_article(
        title=payload.title,
        content=payload.content,
        category=payload.category,
        stage=payload.stage,
        author_id=payload.author_id,
        is_pinned=payload.is_pinned,
        related_thread_ids=payload.related_thread_ids,
        related_share_ids=payload.related_share_ids,
    )
    return CreateArticleResponse(article=ArticleDetailResponse(**_map_article_detail(article)))


@router.put("/articles/{article_id}", response_model=UpdateArticleResponse)
def update_article(
    article_id: str,
    payload: UpdateArticleRequest,
    request: Request,
) -> UpdateArticleResponse:
    article = request.app.state.container.news_service.update_article(
        article_id=article_id,
        title=payload.title,
        content=payload.content,
        category=payload.category,
        stage=payload.stage,
        is_pinned=payload.is_pinned,
        related_thread_ids=payload.related_thread_ids,
        related_share_ids=payload.related_share_ids,
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return UpdateArticleResponse(article=ArticleDetailResponse(**_map_article_detail(article)))


@router.delete("/articles/{article_id}")
def delete_article(article_id: str, request: Request):
    success = request.app.state.container.news_service.delete_article(article_id)
    if not success:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"status": "success", "message": "Article deleted successfully"}
