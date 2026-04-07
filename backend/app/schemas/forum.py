from __future__ import annotations

from pydantic import BaseModel, Field


class ThreadSummaryResponse(BaseModel):
    id: str
    board_slug: str
    title: str
    stage: str
    author_id: str
    replies: int
    views: int
    last_reply_by_id: str
    last_reply_at: str
    pinned: bool
    tags: list[str]


class BoardSummaryResponse(BaseModel):
    slug: str
    name: str
    description: str
    moderator: str
    threads: int
    posts: int
    latest_thread: ThreadSummaryResponse | None


class ForumStatsResponse(BaseModel):
    online_users: int
    total_threads: int
    total_posts: int


class ThreadPostResponse(BaseModel):
    id: str
    author_id: str
    created_at: str
    content: str


class ThreadDetailResponse(ThreadSummaryResponse):
    posts: list[ThreadPostResponse]


class BoardThreadsResponse(BaseModel):
    board: BoardSummaryResponse
    threads: list[ThreadSummaryResponse]


class UserProfileResponse(BaseModel):
    id: str
    name: str
    title: str
    join_date: str
    posts: int
    reputation: int
    status: str
    signature: str
    bio: str


class UserProfileWithThreadsResponse(BaseModel):
    user: UserProfileResponse
    recent_threads: list[ThreadSummaryResponse]


class CreateThreadRequest(BaseModel):
    board_slug: str
    author_id: str
    title: str
    content: str
    stage: str = "discussion"
    tags: list[str] = Field(default_factory=list)


class ReplyThreadRequest(BaseModel):
    author_id: str
    content: str


class CreateThreadResponse(BaseModel):
    thread: ThreadDetailResponse


class ReplyThreadResponse(BaseModel):
    post: ThreadPostResponse
