from __future__ import annotations

from typing import List, Optional, Tuple

from app.repositories.social_repository import (
    AbstractSocialRepository,
    SocialPostDetail,
    SocialPostDraft,
    SocialPostSummary,
    SocialReply,
    SocialReplyDraft,
)


class SocialService:
    def __init__(self, social_repository: AbstractSocialRepository) -> None:
        self.social_repository = social_repository

    def list_posts(
        self,
        limit: int = 10,
        cursor: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> Tuple[List[SocialPostSummary], Optional[str]]:
        return self.social_repository.list_posts(limit, cursor, tag)

    def get_post(self, post_id: str) -> Optional[SocialPostDetail]:
        return self.social_repository.get_post(post_id)

    def create_post(self, content: str, author_id: str, tags: List[str]) -> SocialPostDetail:
        return self.social_repository.create_post(content, author_id, tags)

    def reply_post(self, post_id: str, author_id: str, content: str) -> Optional[SocialReply]:
        return self.social_repository.reply_post(post_id, author_id, content)

    def like_post(self, post_id: str) -> Optional[SocialPostDetail]:
        post = self.social_repository.like_post(post_id)
        if post:
            return self.social_repository.get_post(post.id)
        return None

    def create_post_draft(self, author_id: str, requested_content: str, tags: List[str]) -> SocialPostDraft:
        return self.social_repository.create_post_draft(author_id, requested_content, tags)

    def publish_post_draft(self, draft_id: str, content: str) -> SocialPostDetail:
        return self.social_repository.publish_post_draft(draft_id, content)

    def create_reply_draft(self, post_id: str, author_id: str, requested_content: str) -> Optional[SocialReplyDraft]:
        return self.social_repository.create_reply_draft(post_id, author_id, requested_content)

    def publish_reply_draft(self, draft_id: str, content: str) -> Optional[SocialReply]:
        return self.social_repository.publish_reply_draft(draft_id, content)
