from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from itertools import count

from app.infrastructure.db.session import DatabaseSessionManager
from app.repositories.forum_repository import (
    AbstractForumRepository,
    BoardSummary,
    ForumReplyDraft,
    ForumStats,
    ForumThreadDraft,
    ThreadDetail,
    ThreadPost,
    ThreadSummary,
    UserProfile,
)


class SQLiteForumRepository(AbstractForumRepository):
    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager
        self._thread_counter = count(10000)
        self._post_counter = count(20000)
        self._draft_counter = count(1)

    def initialize(self) -> None:
        self._create_tables()
        self._ensure_stage_columns()
        self._seed_if_empty()
        self._sync_counters()

    def get_stats(self) -> ForumStats:
        with self.session_manager.connect() as conn:
            stats_row = conn.execute("SELECT online_users FROM forum_stats LIMIT 1").fetchone()
            thread_count = conn.execute("SELECT COUNT(1) AS count FROM threads").fetchone()["count"]
            post_count = conn.execute("SELECT COUNT(1) AS count FROM posts").fetchone()["count"]

        return ForumStats(
            online_users=stats_row["online_users"] if stats_row else 0,
            total_threads=thread_count,
            total_posts=post_count,
        )

    def list_boards(self) -> list[BoardSummary]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    b.slug,
                    b.name,
                    b.description,
                    b.moderator,
                    (SELECT COUNT(1) FROM threads t WHERE t.board_slug = b.slug) AS thread_count,
                    (SELECT COUNT(1)
                     FROM posts p
                     JOIN threads t ON t.id = p.thread_id
                     WHERE t.board_slug = b.slug) AS post_count
                FROM boards b
                ORDER BY b.sort_order ASC
                """
            ).fetchall()

        result: list[BoardSummary] = []
        for row in rows:
            latest = self._get_latest_thread_for_board(row["slug"])
            result.append(
                BoardSummary(
                    slug=row["slug"],
                    name=row["name"],
                    description=row["description"],
                    moderator=row["moderator"],
                    threads=row["thread_count"],
                    posts=row["post_count"],
                    latest_thread=latest,
                )
            )
        return result

    def list_threads(self, board_slug: str) -> tuple[BoardSummary | None, list[ThreadSummary]]:
        with self.session_manager.connect() as conn:
            board_row = conn.execute(
                "SELECT slug, name, description, moderator FROM boards WHERE slug = ?",
                (board_slug,),
            ).fetchone()
            if board_row is None:
                return None, []

            thread_rows = conn.execute(
                """
                SELECT
                    id,
                    board_slug,
                    title,
                    stage,
                    author_id,
                    replies,
                    views,
                    last_reply_by_id,
                    last_reply_at,
                    pinned,
                    tags
                FROM threads
                WHERE board_slug = ?
                ORDER BY pinned DESC, last_reply_at DESC
                """,
                (board_slug,),
            ).fetchall()

            post_count = conn.execute(
                """
                SELECT COUNT(1) AS count
                FROM posts p
                JOIN threads t ON t.id = p.thread_id
                WHERE t.board_slug = ?
                """,
                (board_slug,),
            ).fetchone()["count"]

        threads = [self._map_thread_summary(row) for row in thread_rows]
        board = BoardSummary(
            slug=board_row["slug"],
            name=board_row["name"],
            description=board_row["description"],
            moderator=board_row["moderator"],
            threads=len(threads),
            posts=post_count,
            latest_thread=threads[0] if threads else None,
        )
        return board, threads

    def get_thread(self, thread_id: str) -> ThreadDetail | None:
        with self.session_manager.connect() as conn:
            thread_row = conn.execute(
                """
                SELECT
                    id,
                    board_slug,
                    title,
                    stage,
                    author_id,
                    replies,
                    views,
                    last_reply_by_id,
                    last_reply_at,
                    pinned,
                    tags
                FROM threads
                WHERE id = ?
                """,
                (thread_id,),
            ).fetchone()
            if thread_row is None:
                return None

            post_rows = conn.execute(
                """
                SELECT id, author_id, created_at, content
                FROM posts
                WHERE thread_id = ?
                ORDER BY created_at ASC
                """,
                (thread_id,),
            ).fetchall()

        summary = self._map_thread_summary(thread_row)
        posts = [
            ThreadPost(
                id=row["id"],
                author_id=row["author_id"],
                created_at=row["created_at"],
                content=row["content"],
            )
            for row in post_rows
        ]
        return ThreadDetail(
            id=summary.id,
            board_slug=summary.board_slug,
            title=summary.title,
            stage=summary.stage,
            author_id=summary.author_id,
            replies=summary.replies,
            views=summary.views,
            last_reply_by_id=summary.last_reply_by_id,
            last_reply_at=summary.last_reply_at,
            pinned=summary.pinned,
            tags=summary.tags,
            posts=posts,
        )

    def get_user_profile(self, user_id: str) -> UserProfile | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    name,
                    title,
                    join_date,
                    posts,
                    reputation,
                    status,
                    signature,
                    bio
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return UserProfile(
            id=row["id"],
            name=row["name"],
            title=row["title"],
            join_date=row["join_date"],
            posts=row["posts"],
            reputation=row["reputation"],
            status=row["status"],
            signature=row["signature"],
            bio=row["bio"],
        )

    def user_exists(self, user_id: str) -> bool:
        with self.session_manager.connect() as conn:
            row = conn.execute("SELECT 1 AS exists_flag FROM users WHERE id = ?", (user_id,)).fetchone()
        return row is not None

    def list_user_ids(self) -> list[str]:
        with self.session_manager.connect() as conn:
            rows = conn.execute("SELECT id FROM users ORDER BY join_date ASC, id ASC").fetchall()
        return [row["id"] for row in rows]

    def get_recent_threads_by_author(self, user_id: str, limit: int = 5) -> list[ThreadSummary]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    board_slug,
                    title,
                    stage,
                    author_id,
                    replies,
                    views,
                    last_reply_by_id,
                    last_reply_at,
                    pinned,
                    tags
                FROM threads
                WHERE author_id = ?
                ORDER BY last_reply_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [self._map_thread_summary(row) for row in rows]

    def get_hot_threads(self, limit: int = 5) -> list[ThreadSummary]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    board_slug,
                    title,
                    stage,
                    author_id,
                    replies,
                    views,
                    last_reply_by_id,
                    last_reply_at,
                    pinned,
                    tags
                FROM threads
                ORDER BY views DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._map_thread_summary(row) for row in rows]

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
        thread_id = f"t{next(self._thread_counter)}"
        post_id = f"p{next(self._post_counter)}"
        now = datetime.now(timezone.utc).isoformat()
        tags_text = ",".join(tag.strip() for tag in tags if tag.strip())

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO threads (
                    id,
                    board_slug,
                    title,
                    stage,
                    author_id,
                    replies,
                    views,
                    last_reply_by_id,
                    last_reply_at,
                    pinned,
                    tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (thread_id, board_slug, title, self._normalize_stage(stage), author_id, 0, 0, author_id, now, 0, tags_text),
            )
            conn.execute(
                """
                INSERT INTO posts (id, thread_id, author_id, created_at, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (post_id, thread_id, author_id, now, content),
            )
            conn.execute("UPDATE users SET posts = posts + 1 WHERE id = ?", (author_id,))
            conn.commit()

        thread = self.get_thread(thread_id)
        if thread is None:
            raise RuntimeError("Failed to load newly created thread")
        return thread

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
        now = datetime.now(timezone.utc).isoformat()
        draft_id = f"fd{next(self._draft_counter):05d}"
        thread_id = f"t{next(self._thread_counter)}"
        post_id = f"p{next(self._post_counter)}"
        tags_text = ",".join(tag.strip() for tag in tags if tag.strip())

        with self.session_manager.connect() as conn:
            board_row = conn.execute(
                "SELECT slug, name FROM boards WHERE slug = ?",
                (board_slug,),
            ).fetchone()
            if board_row is None:
                raise ValueError(f"Board not found: {board_slug}")

            conn.execute(
                """
                INSERT INTO thread_drafts (
                    draft_id,
                    thread_id,
                    first_post_id,
                    board_slug,
                    board_name,
                    author_id,
                    requested_title,
                    requested_content,
                    stage,
                    tags,
                    status,
                    created_at,
                    published_at,
                    final_title,
                    final_content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    thread_id,
                    post_id,
                    board_slug,
                    board_row["name"],
                    author_id,
                    requested_title,
                    requested_content,
                    self._normalize_stage(stage),
                    tags_text,
                    "pending",
                    now,
                    None,
                    None,
                    None,
                ),
            )
            conn.commit()

        return ForumThreadDraft(
            draft_id=draft_id,
            thread_id=thread_id,
            first_post_id=post_id,
            board_slug=board_slug,
            board_name=board_row["name"],
            author_id=author_id,
            requested_title=requested_title,
            requested_content=requested_content,
            stage=self._normalize_stage(stage),
            tags=[tag.strip() for tag in tags if tag.strip()],
            created_at=now,
        )

    def publish_thread_draft(self, *, draft_id: str, title: str, content: str, stage: str) -> ThreadDetail:
        with self.session_manager.connect() as conn:
            draft_row = conn.execute(
                "SELECT * FROM thread_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
            if draft_row is None:
                raise KeyError(f"Thread draft not found: {draft_id}")

            if draft_row["status"] == "published":
                existing_thread = self.get_thread(draft_row["thread_id"])
                if existing_thread is None:
                    raise RuntimeError("Published draft is missing its thread record")
                return existing_thread

            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO threads (
                    id,
                    board_slug,
                    title,
                    stage,
                    author_id,
                    replies,
                    views,
                    last_reply_by_id,
                    last_reply_at,
                    pinned,
                    tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_row["thread_id"],
                    draft_row["board_slug"],
                    title,
                    self._normalize_stage(stage),
                    draft_row["author_id"],
                    0,
                    0,
                    draft_row["author_id"],
                    now,
                    0,
                    draft_row["tags"],
                ),
            )
            conn.execute(
                """
                INSERT INTO posts (id, thread_id, author_id, created_at, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    draft_row["first_post_id"],
                    draft_row["thread_id"],
                    draft_row["author_id"],
                    now,
                    content,
                ),
            )
            conn.execute("UPDATE users SET posts = posts + 1 WHERE id = ?", (draft_row["author_id"],))
            conn.execute(
                """
                UPDATE thread_drafts
                SET status = ?,
                    published_at = ?,
                    final_title = ?,
                    final_content = ?
                WHERE draft_id = ?
                """,
                ("published", now, title, content, draft_id),
            )
            conn.commit()

        thread = self.get_thread(draft_row["thread_id"])
        if thread is None:
            raise RuntimeError("Failed to load published thread")
        return thread

    def reply_thread(self, *, thread_id: str, author_id: str, content: str) -> ThreadPost | None:
        now = datetime.now(timezone.utc).isoformat()
        post_id = f"p{next(self._post_counter)}"

        with self.session_manager.connect() as conn:
            existing = conn.execute("SELECT id FROM threads WHERE id = ?", (thread_id,)).fetchone()
            if existing is None:
                return None

            conn.execute(
                """
                INSERT INTO posts (id, thread_id, author_id, created_at, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (post_id, thread_id, author_id, now, content),
            )
            conn.execute(
                """
                UPDATE threads
                SET replies = replies + 1,
                    last_reply_by_id = ?,
                    last_reply_at = ?
                WHERE id = ?
                """,
                (author_id, now, thread_id),
            )
            conn.execute("UPDATE users SET posts = posts + 1 WHERE id = ?", (author_id,))
            conn.commit()

        return ThreadPost(
            id=post_id,
            author_id=author_id,
            created_at=now,
            content=content,
        )

    def create_reply_draft(self, *, thread_id: str, author_id: str, requested_content: str) -> ForumReplyDraft | None:
        now = datetime.now(timezone.utc).isoformat()
        draft_id = f"fd{next(self._draft_counter):05d}"
        post_id = f"p{next(self._post_counter)}"

        with self.session_manager.connect() as conn:
            thread_row = conn.execute(
                "SELECT id, title FROM threads WHERE id = ?",
                (thread_id,),
            ).fetchone()
            if thread_row is None:
                return None

            conn.execute(
                """
                INSERT INTO reply_drafts (
                    draft_id,
                    thread_id,
                    post_id,
                    author_id,
                    requested_content,
                    thread_title,
                    status,
                    created_at,
                    published_at,
                    final_content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    thread_id,
                    post_id,
                    author_id,
                    requested_content,
                    thread_row["title"],
                    "pending",
                    now,
                    None,
                    None,
                ),
            )
            conn.commit()

        return ForumReplyDraft(
            draft_id=draft_id,
            thread_id=thread_id,
            post_id=post_id,
            author_id=author_id,
            requested_content=requested_content,
            thread_title=thread_row["title"],
            created_at=now,
        )

    def publish_reply_draft(self, *, draft_id: str, content: str) -> ThreadPost | None:
        with self.session_manager.connect() as conn:
            draft_row = conn.execute(
                "SELECT * FROM reply_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
            if draft_row is None:
                return None

            if draft_row["status"] == "published":
                return ThreadPost(
                    id=draft_row["post_id"],
                    author_id=draft_row["author_id"],
                    created_at=draft_row["published_at"] or draft_row["created_at"],
                    content=draft_row["final_content"] or content,
                )

            now = datetime.now(timezone.utc).isoformat()
            existing = conn.execute("SELECT id FROM threads WHERE id = ?", (draft_row["thread_id"],)).fetchone()
            if existing is None:
                return None

            conn.execute(
                """
                INSERT INTO posts (id, thread_id, author_id, created_at, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    draft_row["post_id"],
                    draft_row["thread_id"],
                    draft_row["author_id"],
                    now,
                    content,
                ),
            )
            conn.execute(
                """
                UPDATE threads
                SET replies = replies + 1,
                    last_reply_by_id = ?,
                    last_reply_at = ?
                WHERE id = ?
                """,
                (draft_row["author_id"], now, draft_row["thread_id"]),
            )
            conn.execute("UPDATE users SET posts = posts + 1 WHERE id = ?", (draft_row["author_id"],))
            conn.execute(
                """
                UPDATE reply_drafts
                SET status = ?,
                    published_at = ?,
                    final_content = ?
                WHERE draft_id = ?
                """,
                ("published", now, content, draft_id),
            )
            conn.commit()

        return ThreadPost(
            id=draft_row["post_id"],
            author_id=draft_row["author_id"],
            created_at=now,
            content=content,
        )

    def _get_latest_thread_for_board(self, board_slug: str) -> ThreadSummary | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    board_slug,
                    title,
                    stage,
                    author_id,
                    replies,
                    views,
                    last_reply_by_id,
                    last_reply_at,
                    pinned,
                    tags
                FROM threads
                WHERE board_slug = ?
                ORDER BY pinned DESC, last_reply_at DESC
                LIMIT 1
                """,
                (board_slug,),
            ).fetchone()
        if row is None:
            return None
        return self._map_thread_summary(row)

    @staticmethod
    def _map_thread_summary(row: sqlite3.Row) -> ThreadSummary:
        tags = [value.strip() for value in (row["tags"] or "").split(",") if value.strip()]
        return ThreadSummary(
            id=row["id"],
            board_slug=row["board_slug"],
            title=row["title"],
            stage=row["stage"],
            author_id=row["author_id"],
            replies=row["replies"],
            views=row["views"],
            last_reply_by_id=row["last_reply_by_id"],
            last_reply_at=row["last_reply_at"],
            pinned=bool(row["pinned"]),
            tags=tags,
        )

    @staticmethod
    def _normalize_stage(stage: str) -> str:
        allowed = {"discussion", "investigation", "disclosure", "conclusion"}
        value = (stage or "").strip().lower()
        return value if value in allowed else "discussion"

    def _create_tables(self) -> None:
        with self.session_manager.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS forum_stats (
                    online_users INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    join_date TEXT NOT NULL,
                    posts INTEGER NOT NULL,
                    reputation INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    bio TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS boards (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    moderator TEXT NOT NULL,
                    sort_order INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    board_slug TEXT NOT NULL,
                    title TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT 'discussion',
                    author_id TEXT NOT NULL,
                    replies INTEGER NOT NULL,
                    views INTEGER NOT NULL,
                    last_reply_by_id TEXT NOT NULL,
                    last_reply_at TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    tags TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(board_slug) REFERENCES boards(slug),
                    FOREIGN KEY(author_id) REFERENCES users(id),
                    FOREIGN KEY(last_reply_by_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES threads(id),
                    FOREIGN KEY(author_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS thread_drafts (
                    draft_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    first_post_id TEXT NOT NULL,
                    board_slug TEXT NOT NULL,
                    board_name TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    requested_title TEXT NOT NULL,
                    requested_content TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT 'discussion',
                    tags TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    final_title TEXT,
                    final_content TEXT
                );

                CREATE TABLE IF NOT EXISTS reply_drafts (
                    draft_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    requested_content TEXT NOT NULL,
                    thread_title TEXT NOT NULL,
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
            user_count = conn.execute("SELECT COUNT(1) AS count FROM users").fetchone()["count"]
            if user_count > 0:
                return

            conn.execute("INSERT INTO forum_stats (online_users) VALUES (?)", (187,))

            conn.executemany(
                """
                INSERT INTO users (id, name, title, join_date, posts, reputation, status, signature, bio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "aria",
                        "Aria_Threadweaver",
                        "Senior Archivist",
                        "2000-08-21",
                        3488,
                        632,
                        "Online",
                        "Facts first. Stories second.",
                        "Tracks timeline drift and cross-site contradictions. Collects old screenshots.",
                    ),
                    (
                        "milo",
                        "Milo_Bazaar",
                        "Trusted Trader",
                        "2001-02-12",
                        1560,
                        401,
                        "Away",
                        "Every listing leaves a trail.",
                        "Maintains escrow records and flags strange transaction chains.",
                    ),
                    (
                        "eve",
                        "Eve_Observer",
                        "Rumor Hunter",
                        "2001-09-03",
                        905,
                        287,
                        "Online",
                        "Truth echoes in side channels.",
                        "Specializes in whisper network patterns and anonymous drop verification.",
                    ),
                ],
            )

            conn.executemany(
                """
                INSERT INTO boards (slug, name, description, moderator, sort_order)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        "town-square",
                        "Town Square",
                        "Public forum for world news, big stories, and daily chatter.",
                        "Mod_Nova",
                        1,
                    ),
                    (
                        "bazaar",
                        "Bazaar",
                        "Buy, sell, trade, and inspect suspicious listings.",
                        "TradeMarshal",
                        2,
                    ),
                    (
                        "whispers",
                        "Whispers",
                        "Private leaks, rumors, and detective work from the shadows.",
                        "QuietSignal",
                        3,
                    ),
                    (
                        "station-terminal",
                        "Station Terminal",
                        "System updates, patch notes, and simulation event logs.",
                        "SYS_OP",
                        4,
                    ),
                ],
            )

            conn.executemany(
                """
                INSERT INTO threads (
                    id,
                    board_slug,
                    title,
                    stage,
                    author_id,
                    replies,
                    views,
                    last_reply_by_id,
                    last_reply_at,
                    pinned,
                    tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "t1001",
                        "town-square",
                        "[Investigation] Missing courier spotted near old exchange",
                        "investigation",
                        "aria",
                        48,
                        2310,
                        "eve",
                        "2001-11-09 22:16",
                        1,
                        "investigation,timeline",
                    ),
                    (
                        "t1004",
                        "town-square",
                        "Daily World Pulse - Nov 9",
                        "discussion",
                        "milo",
                        23,
                        980,
                        "aria",
                        "2001-11-10 00:03",
                        0,
                        "news,digest",
                    ),
                    (
                        "t2003",
                        "bazaar",
                        "[For Sale] Antique console with hidden data port",
                        "discussion",
                        "milo",
                        31,
                        1702,
                        "aria",
                        "2001-11-09 21:41",
                        0,
                        "listing,hardware",
                    ),
                    (
                        "t3006",
                        "whispers",
                        "[Leak] Anonymous file drop references fake witness",
                        "investigation",
                        "eve",
                        64,
                        2910,
                        "eve",
                        "2001-11-10 01:28",
                        1,
                        "leak,evidence,rumor",
                    ),
                ],
            )

            conn.executemany(
                """
                INSERT INTO posts (id, thread_id, author_id, created_at, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        "p1",
                        "t1001",
                        "aria",
                        "2001-11-09 18:42",
                        "Witness report says the courier logged into the bazaar account at 17:58, but no valid transaction record exists. Posting structured facts below for review.",
                    ),
                    (
                        "p2",
                        "t1001",
                        "eve",
                        "2001-11-09 22:16",
                        "I found two rumor nodes repeating the same wrong locker code. Might be deliberate misinformation. Can anyone verify terminal camera logs?",
                    ),
                    (
                        "p3",
                        "t1004",
                        "milo",
                        "2001-11-09 09:00",
                        "Forum activity up 12 percent, bazaar delistings up 4 percent, and whispers are flooding with false package IDs. Keep your logs clean.",
                    ),
                    (
                        "p4",
                        "t2003",
                        "milo",
                        "2001-11-09 16:21",
                        "Listed for 240 credits. Verified serial attached in listing metadata. No off-ledger bids accepted.",
                    ),
                    (
                        "p5",
                        "t2003",
                        "aria",
                        "2001-11-09 21:41",
                        "Cross-check complete. Serial exists in maintenance archive; status is valid. Recommend trusted escrow only.",
                    ),
                    (
                        "p6",
                        "t3006",
                        "eve",
                        "2001-11-09 20:03",
                        "Drop claims witness from sector 4, but the account was created 3 hours before posting. Sharing hash and checksum for independent review.",
                    ),
                    (
                        "p7",
                        "t3006",
                        "aria",
                        "2001-11-09 22:44",
                        "Checksum does not match public mirror. Please treat as unverified until we map propagation path.",
                    ),
                    (
                        "p8",
                        "t3006",
                        "eve",
                        "2001-11-10 01:28",
                        "Updated: first appearance traced to kiosk relay B12. Escalating to station terminal moderators.",
                    ),
                ],
            )
            conn.commit()

    def _ensure_stage_columns(self) -> None:
        with self.session_manager.connect() as conn:
            thread_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(threads)").fetchall()
            }
            if "stage" not in thread_columns:
                conn.execute("ALTER TABLE threads ADD COLUMN stage TEXT NOT NULL DEFAULT 'discussion'")

            draft_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(thread_drafts)").fetchall()
            }
            if "stage" not in draft_columns:
                conn.execute("ALTER TABLE thread_drafts ADD COLUMN stage TEXT NOT NULL DEFAULT 'discussion'")
            conn.commit()

    def _sync_counters(self) -> None:
        with self.session_manager.connect() as conn:
            thread_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(id, 2) AS INTEGER)), 9999) AS max_id FROM threads"
            ).fetchone()
            post_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(id, 2) AS INTEGER)), 19999) AS max_id FROM posts"
            ).fetchone()
            draft_row = conn.execute(
                """
                SELECT COALESCE(
                    MAX(CAST(SUBSTR(draft_id, 3) AS INTEGER)),
                    0
                ) AS max_id
                FROM (
                    SELECT draft_id FROM thread_drafts
                    UNION ALL
                    SELECT draft_id FROM reply_drafts
                )
                """
            ).fetchone()

        self._thread_counter = count(int(thread_row["max_id"]) + 1)
        self._post_counter = count(int(post_row["max_id"]) + 1)
        self._draft_counter = count(int(draft_row["max_id"]) + 1)
