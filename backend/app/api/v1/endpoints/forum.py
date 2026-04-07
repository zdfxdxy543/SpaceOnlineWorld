from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.repositories.forum_repository import BoardSummary, ThreadDetail, ThreadSummary, UserProfile
from app.schemas.forum import (
    BoardSummaryResponse,
    BoardThreadsResponse,
    CreateThreadRequest,
    CreateThreadResponse,
    ForumStatsResponse,
    ReplyThreadRequest,
    ReplyThreadResponse,
    ThreadDetailResponse,
    ThreadPostResponse,
    ThreadSummaryResponse,
    UserProfileResponse,
    UserProfileWithThreadsResponse,
)

router = APIRouter()


def _map_thread_summary(thread: ThreadSummary) -> ThreadSummaryResponse:
    return ThreadSummaryResponse(
        id=thread.id,
        board_slug=thread.board_slug,
        title=thread.title,
        stage=thread.stage,
        author_id=thread.author_id,
        replies=thread.replies,
        views=thread.views,
        last_reply_by_id=thread.last_reply_by_id,
        last_reply_at=thread.last_reply_at,
        pinned=thread.pinned,
        tags=thread.tags,
    )


def _map_board(board: BoardSummary) -> BoardSummaryResponse:
    return BoardSummaryResponse(
        slug=board.slug,
        name=board.name,
        description=board.description,
        moderator=board.moderator,
        threads=board.threads,
        posts=board.posts,
        latest_thread=_map_thread_summary(board.latest_thread) if board.latest_thread else None,
    )


def _map_thread_detail(thread: ThreadDetail) -> ThreadDetailResponse:
    return ThreadDetailResponse(
        id=thread.id,
        board_slug=thread.board_slug,
        title=thread.title,
        stage=thread.stage,
        author_id=thread.author_id,
        replies=thread.replies,
        views=thread.views,
        last_reply_by_id=thread.last_reply_by_id,
        last_reply_at=thread.last_reply_at,
        pinned=thread.pinned,
        tags=thread.tags,
        posts=[
            ThreadPostResponse(
                id=post.id,
                author_id=post.author_id,
                created_at=post.created_at,
                content=post.content,
            )
            for post in thread.posts
        ],
    )


def _map_user(user: UserProfile) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        name=user.name,
        title=user.title,
        join_date=user.join_date,
        posts=user.posts,
        reputation=user.reputation,
        status=user.status,
        signature=user.signature,
        bio=user.bio,
    )


@router.get("/stats", response_model=ForumStatsResponse)
def get_forum_stats(request: Request) -> ForumStatsResponse:
    stats = request.app.state.container.forum_service.get_stats()
    return ForumStatsResponse(
        online_users=stats.online_users,
        total_threads=stats.total_threads,
        total_posts=stats.total_posts,
    )


@router.get("/boards", response_model=list[BoardSummaryResponse])
def list_boards(request: Request) -> list[BoardSummaryResponse]:
    boards = request.app.state.container.forum_service.list_boards()
    return [_map_board(board) for board in boards]


@router.get("/boards/{board_slug}/threads", response_model=BoardThreadsResponse)
def list_board_threads(board_slug: str, request: Request) -> BoardThreadsResponse:
    board, threads = request.app.state.container.forum_service.list_board_threads(board_slug)
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found")
    return BoardThreadsResponse(board=_map_board(board), threads=[_map_thread_summary(item) for item in threads])


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
def get_thread(thread_id: str, request: Request) -> ThreadDetailResponse:
    thread = request.app.state.container.forum_service.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return _map_thread_detail(thread)


@router.get("/users/{user_id}", response_model=UserProfileWithThreadsResponse)
def get_user(user_id: str, request: Request) -> UserProfileWithThreadsResponse:
    service = request.app.state.container.forum_service
    user = service.get_user_profile(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    recent_threads = service.get_user_recent_threads(user_id)
    return UserProfileWithThreadsResponse(
        user=_map_user(user),
        recent_threads=[_map_thread_summary(thread) for thread in recent_threads],
    )


@router.get("/hot-threads", response_model=list[ThreadSummaryResponse])
def get_hot_threads(
    request: Request,
    limit: int = Query(default=5, ge=1, le=20),
) -> list[ThreadSummaryResponse]:
    threads = request.app.state.container.forum_service.get_hot_threads(limit)
    return [_map_thread_summary(thread) for thread in threads]


@router.post("/threads", response_model=CreateThreadResponse)
def create_thread(payload: CreateThreadRequest, request: Request) -> CreateThreadResponse:
    thread = request.app.state.container.forum_service.create_thread(
        board_slug=payload.board_slug,
        author_id=payload.author_id,
        title=payload.title,
        content=payload.content,
        stage=payload.stage,
        tags=payload.tags,
    )
    return CreateThreadResponse(thread=_map_thread_detail(thread))


@router.post("/threads/{thread_id}/replies", response_model=ReplyThreadResponse)
def reply_thread(thread_id: str, payload: ReplyThreadRequest, request: Request) -> ReplyThreadResponse:
    post = request.app.state.container.forum_service.reply_thread(
        thread_id=thread_id,
        author_id=payload.author_id,
        content=payload.content,
    )
    if post is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ReplyThreadResponse(
        post=ThreadPostResponse(
            id=post.id,
            author_id=post.author_id,
            created_at=post.created_at,
            content=post.content,
        )
    )
