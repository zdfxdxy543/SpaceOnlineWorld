from __future__ import annotations
from datetime import datetime, timezone
from itertools import count

from app.infrastructure.db.session import DatabaseSessionManager
from app.repositories.social_repository import (
    AbstractSocialRepository,
    SocialPost,
    SocialPostDetail,
    SocialPostDraft,
    SocialPostSummary,
    SocialReply,
    SocialReplyDraft,
)


class SQLiteSocialRepository(AbstractSocialRepository):
    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager
        self._post_counter = count(10000)
        self._reply_counter = count(20000)
        self._draft_counter = count(1)

    def initialize(self) -> None:
        self._create_tables()
        self._seed_if_empty()
        self._sync_counters()

    def _init_tables(self) -> None:
        self._create_tables()

    def list_posts(
        self,
        limit: int,
        cursor: str | None = None,
        tag: str | None = None,
    ) -> tuple[list[SocialPostSummary], str | None]:
        conditions: list[str] = []
        parameters: list[object] = []
        if cursor:
            conditions.append("p.created_at < ?")
            parameters.append(cursor)
        if tag:
            conditions.append("instr(',' || p.tags || ',', ',' || ? || ',') > 0")
            parameters.append(tag.strip())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    p.id,
                    p.content,
                    p.author_id,
                    p.created_at,
                    p.likes,
                    p.tags,
                    COALESCE((
                        SELECT COUNT(1)
                        FROM social_replies r
                        WHERE r.post_id = p.id
                    ), 0) AS replies_count
                FROM social_posts p
                {where_clause}
                ORDER BY p.created_at DESC
                LIMIT ?
                """,
                (*parameters, limit + 1),
            ).fetchall()

        posts = []
        for row in rows[:limit]:
            tags = [tag.strip() for tag in (row["tags"] or "").split(",") if tag.strip()]
            posts.append(
                SocialPostSummary(
                    id=row["id"],
                    content=row["content"],
                    author_id=row["author_id"],
                    created_at=row["created_at"],
                    likes=row["likes"],
                    replies_count=row["replies_count"],
                    tags=tags,
                )
            )

        next_cursor = rows[limit]["created_at"] if len(rows) > limit else None
        return posts, next_cursor

    def get_post(self, post_id: str) -> SocialPostDetail | None:
        with self.session_manager.connect() as conn:
            post_row = conn.execute(
                """
                SELECT id, content, author_id, created_at, likes, tags
                FROM social_posts
                WHERE id = ?
                """,
                (post_id,),
            ).fetchone()
            if post_row is None:
                return None

            reply_rows = conn.execute(
                """
                SELECT id, post_id, author_id, content, created_at
                FROM social_replies
                WHERE post_id = ?
                ORDER BY created_at ASC
                """,
                (post_id,),
            ).fetchall()

        tags = [tag.strip() for tag in (post_row["tags"] or "").split(",") if tag.strip()]
        replies = [
            SocialReply(
                id=row["id"],
                post_id=row["post_id"],
                author_id=row["author_id"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in reply_rows
        ]

        return SocialPostDetail(
            id=post_row["id"],
            content=post_row["content"],
            author_id=post_row["author_id"],
            created_at=post_row["created_at"],
            likes=post_row["likes"],
            tags=tags,
            replies=replies,
        )

    def create_post(self, content: str, author_id: str, tags: list[str]) -> SocialPostDetail:
        post_id = f"sp{next(self._post_counter)}"
        now = datetime.now(timezone.utc).isoformat()
        tags_text = ",".join(tag.strip() for tag in tags if tag.strip())

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO social_posts (id, content, author_id, created_at, likes, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (post_id, content, author_id, now, 0, tags_text),
            )
            conn.commit()

        post = self.get_post(post_id)
        if post is None:
            raise RuntimeError("Failed to load newly created post")
        return post

    def create_post_draft(self, author_id: str, requested_content: str, tags: list[str]) -> SocialPostDraft:
        now = datetime.now(timezone.utc).isoformat()
        draft_id = f"sd{next(self._draft_counter):05d}"
        post_id = f"sp{next(self._post_counter)}"
        tags_text = ",".join(tag.strip() for tag in tags if tag.strip())

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO social_post_drafts (
                    draft_id,
                    post_id,
                    author_id,
                    requested_content,
                    tags,
                    status,
                    created_at,
                    published_at,
                    final_content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    post_id,
                    author_id,
                    requested_content,
                    tags_text,
                    "pending",
                    now,
                    None,
                    None,
                ),
            )
            conn.commit()

        return SocialPostDraft(
            id=draft_id,
            post_id=post_id,
            author_id=author_id,
            requested_content=requested_content,
            tags=[tag.strip() for tag in tags if tag.strip()],
            created_at=now,
        )

    def publish_post_draft(self, draft_id: str, content: str) -> SocialPostDetail:
        with self.session_manager.connect() as conn:
            draft_row = conn.execute(
                "SELECT * FROM social_post_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
            if draft_row is None:
                raise KeyError(f"Post draft not found: {draft_id}")

            if draft_row["status"] == "published":
                existing_post = self.get_post(draft_row["post_id"])
                if existing_post is None:
                    raise RuntimeError("Published draft is missing its post record")
                return existing_post

            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO social_posts (id, content, author_id, created_at, likes, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_row["post_id"],
                    content,
                    draft_row["author_id"],
                    now,
                    0,
                    draft_row["tags"],
                ),
            )
            conn.execute(
                """
                UPDATE social_post_drafts
                SET status = ?, published_at = ?, final_content = ?
                WHERE draft_id = ?
                """,
                ("published", now, content, draft_id),
            )
            conn.commit()

        post = self.get_post(draft_row["post_id"])
        if post is None:
            raise RuntimeError("Failed to load published post")
        return post

    def reply_post(self, post_id: str, author_id: str, content: str) -> SocialReply | None:
        with self.session_manager.connect() as conn:
            existing = conn.execute("SELECT id FROM social_posts WHERE id = ?", (post_id,)).fetchone()
            if existing is None:
                return None

            reply_id = f"sr{next(self._reply_counter)}"
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO social_replies (id, post_id, author_id, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (reply_id, post_id, author_id, content, now),
            )
            conn.commit()

        return SocialReply(
            id=reply_id,
            post_id=post_id,
            author_id=author_id,
            content=content,
            created_at=now,
        )

    def create_reply(self, post_id: str, author_id: str, content: str) -> SocialReply | None:
        return self.reply_post(post_id, author_id, content)

    def like_post(self, post_id: str) -> SocialPost | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT id, content, author_id, created_at, likes, tags
                FROM social_posts
                WHERE id = ?
                """,
                (post_id,),
            ).fetchone()
            if row is None:
                return None

            updated_likes = int(row["likes"]) + 1
            conn.execute(
                "UPDATE social_posts SET likes = ? WHERE id = ?",
                (updated_likes, post_id),
            )
            conn.commit()

        tags = [tag.strip() for tag in (row["tags"] or "").split(",") if tag.strip()]
        return SocialPost(
            id=row["id"],
            content=row["content"],
            author_id=row["author_id"],
            created_at=row["created_at"],
            likes=updated_likes,
            tags=tags,
        )

    def create_reply_draft(self, post_id: str, author_id: str, requested_content: str) -> SocialReplyDraft | None:
        with self.session_manager.connect() as conn:
            post_row = conn.execute(
                "SELECT id, content FROM social_posts WHERE id = ?",
                (post_id,),
            ).fetchone()
            if post_row is None:
                return None

            now = datetime.now(timezone.utc).isoformat()
            draft_id = f"sd{next(self._draft_counter):05d}"
            reply_id = f"sr{next(self._reply_counter)}"
            conn.execute(
                """
                INSERT INTO social_reply_drafts (
                    draft_id,
                    reply_id,
                    post_id,
                    author_id,
                    requested_content,
                    post_content,
                    status,
                    created_at,
                    published_at,
                    final_content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    reply_id,
                    post_id,
                    author_id,
                    requested_content,
                    post_row["content"],
                    "pending",
                    now,
                    None,
                    None,
                ),
            )
            conn.commit()

        return SocialReplyDraft(
            id=draft_id,
            post_id=post_id,
            author_id=author_id,
            requested_content=requested_content,
            created_at=now,
        )

    def publish_reply_draft(self, draft_id: str, content: str) -> SocialReply | None:
        with self.session_manager.connect() as conn:
            draft_row = conn.execute(
                "SELECT * FROM social_reply_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
            if draft_row is None:
                return None

            if draft_row["status"] == "published":
                return SocialReply(
                    id=draft_row["reply_id"],
                    post_id=draft_row["post_id"],
                    author_id=draft_row["author_id"],
                    content=draft_row["final_content"] or content,
                    created_at=draft_row["published_at"] or draft_row["created_at"],
                )

            now = datetime.now(timezone.utc).isoformat()
            existing = conn.execute("SELECT id FROM social_posts WHERE id = ?", (draft_row["post_id"],)).fetchone()
            if existing is None:
                return None

            conn.execute(
                """
                INSERT INTO social_replies (id, post_id, author_id, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    draft_row["reply_id"],
                    draft_row["post_id"],
                    draft_row["author_id"],
                    content,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE social_reply_drafts
                SET status = ?, published_at = ?, final_content = ?
                WHERE draft_id = ?
                """,
                ("published", now, content, draft_id),
            )
            conn.commit()

        return SocialReply(
            id=draft_row["reply_id"],
            post_id=draft_row["post_id"],
            author_id=draft_row["author_id"],
            content=content,
            created_at=now,
        )

    def _create_tables(self) -> None:
        with self.session_manager.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS social_posts (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    likes INTEGER NOT NULL DEFAULT 0,
                    tags TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS social_replies (
                    id TEXT PRIMARY KEY,
                    post_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(post_id) REFERENCES social_posts(id)
                );

                CREATE TABLE IF NOT EXISTS social_post_drafts (
                    draft_id TEXT PRIMARY KEY,
                    post_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    requested_content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    final_content TEXT
                );

                CREATE TABLE IF NOT EXISTS social_reply_drafts (
                    draft_id TEXT PRIMARY KEY,
                    reply_id TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    requested_content TEXT NOT NULL,
                    post_content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    final_content TEXT
                );
                """
            )
            conn.commit()

    def _seed_if_empty(self) -> None:
        with self.session_manager.connect() as conn:
            post_count = conn.execute("SELECT COUNT(1) AS count FROM social_posts").fetchone()["count"]
            if post_count > 0:
                return

            now = datetime.now(timezone.utc).isoformat()
            conn.executemany(
                """
                INSERT INTO social_posts (id, content, author_id, created_at, likes, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "sp10001",
                        "Just had the best coffee at the new café downtown!",
                        "aria",
                        now,
                        12,
                        "coffee,food",
                    ),
                    (
                        "sp10002",
                        "Found a strange key in the park today. Wonder what it unlocks?",
                        "milo",
                        now,
                        8,
                        "mystery,find",
                    ),
                    (
                        "sp10003",
                        "The library is having a book sale this weekend. Can't wait!",
                        "eve",
                        now,
                        5,
                        "books,event",
                    ),
                ],
            )
            conn.commit()

    def _sync_counters(self) -> None:
        with self.session_manager.connect() as conn:
            post_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(id, 3) AS INTEGER)), 9999) AS max_id FROM social_posts"
            ).fetchone()
            reply_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(id, 3) AS INTEGER)), 19999) AS max_id FROM social_replies"
            ).fetchone()
            draft_row = conn.execute(
                """
                SELECT COALESCE(
                    MAX(CAST(SUBSTR(draft_id, 3) AS INTEGER)),
                    0
                ) AS max_id
                FROM (
                    SELECT draft_id FROM social_post_drafts
                    UNION ALL
                    SELECT draft_id FROM social_reply_drafts
                )
                """
            ).fetchone()

        self._post_counter = count(int(post_row["max_id"]) + 1)
        self._reply_counter = count(int(reply_row["max_id"]) + 1)
        self._draft_counter = count(int(draft_row["max_id"]) + 1)
