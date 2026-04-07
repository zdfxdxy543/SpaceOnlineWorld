from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class ForumStats:
    online_users: int
    total_threads: int
    total_posts: int


@dataclass(slots=True)
class ThreadSummary:
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


@dataclass(slots=True)
class BoardSummary:
    slug: str
    name: str
    description: str
    moderator: str
    threads: int
    posts: int
    latest_thread: ThreadSummary | None


@dataclass(slots=True)
class ThreadPost:
    id: str
    author_id: str
    created_at: str
    content: str


@dataclass(slots=True)
class ThreadDetail(ThreadSummary):
    posts: list[ThreadPost]


@dataclass(slots=True)
class ForumThreadDraft:
    draft_id: str
    thread_id: str
    first_post_id: str
    board_slug: str
    board_name: str
    author_id: str
    requested_title: str
    requested_content: str
    stage: str
    tags: list[str]
    created_at: str


@dataclass(slots=True)
class ForumReplyDraft:
    draft_id: str
    thread_id: str
    post_id: str
    author_id: str
    requested_content: str
    thread_title: str
    created_at: str


@dataclass(slots=True)
class UserProfile:
    id: str
    name: str
    title: str
    join_date: str
    posts: int
    reputation: int
    status: str
    signature: str
    bio: str


class AbstractForumRepository(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_stats(self) -> ForumStats:
        raise NotImplementedError

    @abstractmethod
    def list_boards(self) -> list[BoardSummary]:
        raise NotImplementedError

    @abstractmethod
    def list_threads(self, board_slug: str) -> tuple[BoardSummary | None, list[ThreadSummary]]:
        raise NotImplementedError

    @abstractmethod
    def get_thread(self, thread_id: str) -> ThreadDetail | None:
        raise NotImplementedError

    @abstractmethod
    def get_user_profile(self, user_id: str) -> UserProfile | None:
        raise NotImplementedError

    @abstractmethod
    def user_exists(self, user_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_user_ids(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_recent_threads_by_author(self, user_id: str, limit: int = 5) -> list[ThreadSummary]:
        raise NotImplementedError

    @abstractmethod
    def get_hot_threads(self, limit: int = 5) -> list[ThreadSummary]:
        raise NotImplementedError

    @abstractmethod
    def create_thread(
        self,
        *,
        board_slug: str,
        author_id: str,
        title: str,
        content: str,
        stage: str,
        tags: list[str],
    ) -> ThreadDetail:
        raise NotImplementedError

    @abstractmethod
    def reply_thread(self, *, thread_id: str, author_id: str, content: str) -> ThreadPost | None:
        raise NotImplementedError

    @abstractmethod
    def create_thread_draft(
        self,
        *,
        board_slug: str,
        author_id: str,
        requested_title: str,
        requested_content: str,
        stage: str,
        tags: list[str],
    ) -> ForumThreadDraft:
        raise NotImplementedError

    @abstractmethod
    def publish_thread_draft(self, *, draft_id: str, title: str, content: str, stage: str) -> ThreadDetail:
        raise NotImplementedError

    @abstractmethod
    def create_reply_draft(self, *, thread_id: str, author_id: str, requested_content: str) -> ForumReplyDraft | None:
        raise NotImplementedError

    @abstractmethod
    def publish_reply_draft(self, *, draft_id: str, content: str) -> ThreadPost | None:
        raise NotImplementedError
