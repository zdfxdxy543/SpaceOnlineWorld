from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.repositories.social_repository import SocialPostDetail, SocialPostSummary, SocialReply
from app.schemas.social import (
    CreatePostRequest,
    CreateReplyRequest,
    SocialPostResponse,
    SocialPostsResponse,
    SocialReplyResponse,
)

router = APIRouter()


def _map_post_summary(post: SocialPostSummary) -> dict:
    return {
        "id": post.id,
        "content": post.content,
        "author_id": post.author_id,
        "created_at": post.created_at,
        "likes": post.likes,
        "replies_count": post.replies_count,
        "tags": post.tags,
    }


def _map_reply(reply: SocialReply) -> SocialReplyResponse:
    return SocialReplyResponse(
        id=reply.id,
        post_id=reply.post_id,
        content=reply.content,
        author_id=reply.author_id,
        created_at=reply.created_at,
    )


def _map_post_detail(post: SocialPostDetail) -> SocialPostResponse:
    return SocialPostResponse(
        id=post.id,
        content=post.content,
        author_id=post.author_id,
        created_at=post.created_at,
        likes=post.likes,
        tags=post.tags,
        replies=[_map_reply(reply) for reply in post.replies],
    )


@router.get("/posts", response_model=SocialPostsResponse)
def list_posts(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    tag: Optional[str] = Query(None, description="Optional tag filter"),
) -> SocialPostsResponse:
    posts, next_cursor = request.app.state.container.social_service.list_posts(limit, cursor, tag)
    return SocialPostsResponse(
        posts=[_map_post_summary(post) for post in posts],
        next_cursor=next_cursor,
    )


@router.get("/posts/{post_id}", response_model=SocialPostResponse)
def get_post(post_id: str, request: Request) -> SocialPostResponse:
    post = request.app.state.container.social_service.get_post(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return _map_post_detail(post)


@router.post("/posts", response_model=SocialPostResponse)
def create_post(payload: CreatePostRequest, request: Request) -> SocialPostResponse:
    post = request.app.state.container.social_service.create_post(
        content=payload.content,
        author_id=payload.author_id,
        tags=payload.tags or [],
    )
    return _map_post_detail(post)


@router.post("/replies", response_model=SocialReplyResponse)
def create_reply(payload: CreateReplyRequest, request: Request) -> SocialReplyResponse:
    reply = request.app.state.container.social_service.reply_post(
        post_id=payload.post_id,
        author_id=payload.author_id,
        content=payload.content,
    )
    if reply is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return _map_reply(reply)


@router.post("/posts/{post_id}/like")
def like_post(post_id: str, request: Request):
    post = request.app.state.container.social_service.like_post(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"status": "success", "likes": post.likes}
