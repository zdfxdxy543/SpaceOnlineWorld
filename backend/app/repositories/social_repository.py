from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class SocialPost:
    id: str
    content: str
    author_id: str
    created_at: str
    likes: int
    tags: list[str]


@dataclass(slots=True)
class SocialReply:
    id: str
    post_id: str
    content: str
    author_id: str
    created_at: str


@dataclass(slots=True)
class SocialPostDetail:
    id: str
    content: str
    author_id: str
    created_at: str
    likes: int
    tags: list[str]
    replies: list[SocialReply]


@dataclass(slots=True)
class SocialPostSummary:
    id: str
    content: str
    author_id: str
    created_at: str
    likes: int
    replies_count: int
    tags: list[str]


@dataclass(slots=True)
class SocialPostDraft:
    id: str
    post_id: str
    author_id: str
    requested_content: str
    tags: list[str]
    created_at: str


@dataclass(slots=True)
class SocialReplyDraft:
    id: str
    post_id: str
    author_id: str
    requested_content: str
    created_at: str


class AbstractSocialRepository(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_posts(self, limit: int = 10, cursor: Optional[str] = None) -> Tuple[List[SocialPostSummary], Optional[str]]:
        raise NotImplementedError

    @abstractmethod
    def get_post(self, post_id: str) -> Optional[SocialPostDetail]:
        raise NotImplementedError

    @abstractmethod
    def create_post(self, content: str, author_id: str, tags: List[str]) -> SocialPostDetail:
        raise NotImplementedError

    @abstractmethod
    def reply_post(self, post_id: str, author_id: str, content: str) -> Optional[SocialReply]:
        raise NotImplementedError

    @abstractmethod
    def like_post(self, post_id: str) -> Optional[SocialPost]:
        raise NotImplementedError

    @abstractmethod
    def create_post_draft(self, author_id: str, requested_content: str, tags: List[str]) -> SocialPostDraft:
        raise NotImplementedError

    @abstractmethod
    def publish_post_draft(self, draft_id: str, content: str) -> SocialPostDetail:
        raise NotImplementedError

    @abstractmethod
    def create_reply_draft(self, post_id: str, author_id: str, requested_content: str) -> Optional[SocialReplyDraft]:
        raise NotImplementedError

    @abstractmethod
    def publish_reply_draft(self, draft_id: str, content: str) -> Optional[SocialReply]:
        raise NotImplementedError
