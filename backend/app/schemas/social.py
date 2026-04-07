from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SocialPostBase(BaseModel):
    content: str
    author_id: str
    tags: Optional[List[str]] = None


class CreatePostRequest(SocialPostBase):
    pass


class SocialPostResponse(BaseModel):
    id: str
    content: str
    author_id: str
    created_at: datetime
    likes: int
    tags: List[str]
    replies: List[SocialReplyResponse]


class SocialReplyBase(BaseModel):
    content: str
    author_id: str


class CreateReplyRequest(SocialReplyBase):
    post_id: str


class SocialReplyResponse(BaseModel):
    id: str
    post_id: str
    content: str
    author_id: str
    created_at: datetime


class SocialPostSummary(BaseModel):
    id: str
    content: str
    author_id: str
    created_at: datetime
    likes: int
    replies_count: int
    tags: List[str]


class SocialPostsResponse(BaseModel):
    posts: List[SocialPostSummary]
    next_cursor: Optional[str] = None
