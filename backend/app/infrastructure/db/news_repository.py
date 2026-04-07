from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from itertools import count

from app.infrastructure.db.session import DatabaseSessionManager
from app.repositories.news_repository import (
    AbstractNewsRepository,
    ArticleDetail,
    ArticleSummary,
    CategorySummary,
    NewsArticleDraft,
    NewsStats,
)


class SQLiteNewsRepository(AbstractNewsRepository):
    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager
        self._article_counter = count(10000)
        self._draft_counter = count(1)

    def initialize(self) -> None:
        self._create_tables()
        self._ensure_stage_columns()
        self._seed_if_empty()
        self._sync_counters()

    def get_stats(self) -> NewsStats:
        with self.session_manager.connect() as conn:
            stats_row = conn.execute("SELECT online_users FROM news_stats LIMIT 1").fetchone()
            article_count = conn.execute("SELECT COUNT(1) AS count FROM news_articles").fetchone()["count"]
            category_count = conn.execute("SELECT COUNT(1) AS count FROM news_categories").fetchone()["count"]

        return NewsStats(
            total_articles=article_count,
            total_categories=category_count,
            online_users=stats_row["online_users"] if stats_row else 0,
        )

    def list_categories(self) -> list[CategorySummary]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.slug,
                    c.name,
                    c.description,
                    (SELECT COUNT(1) FROM news_articles a WHERE a.category = c.slug) AS article_count
                FROM news_categories c
                ORDER BY c.sort_order ASC
                """
            ).fetchall()

        return [
            CategorySummary(
                slug=row["slug"],
                name=row["name"],
                description=row["description"],
                article_count=row["article_count"],
            )
            for row in rows
        ]

    def get_category(self, category_slug: str) -> CategorySummary | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    c.slug,
                    c.name,
                    c.description,
                    (SELECT COUNT(1) FROM news_articles a WHERE a.category = c.slug) AS article_count
                FROM news_categories c
                WHERE c.slug = ?
                """,
                (category_slug,),
            ).fetchone()

        if row is None:
            return None

        return CategorySummary(
            slug=row["slug"],
            name=row["name"],
            description=row["description"],
            article_count=row["article_count"],
        )

    def list_articles(self, category: str | None = None, limit: int = 20) -> list[ArticleSummary]:
        query = """
        SELECT
            id, title, category, stage, author_id, published_at, views, is_pinned, excerpt
        FROM news_articles
        """
        params = []

        if category:
            query += " WHERE category = ?"
            params.append(category)

        query += " ORDER BY is_pinned DESC, published_at DESC LIMIT ?"
        params.append(limit)

        with self.session_manager.connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._map_article_summary(row) for row in rows]

    def get_article(self, article_id: str) -> ArticleDetail | None:
        with self.session_manager.connect() as conn:
            article_row = conn.execute(
                """
                SELECT
                    id, title, category, stage, author_id, published_at, views, is_pinned, excerpt, content
                FROM news_articles
                WHERE id = ?
                """,
                (article_id,),
            ).fetchone()

            if article_row is None:
                return None

            related_threads = conn.execute(
                "SELECT thread_id FROM news_article_related_threads WHERE article_id = ?",
                (article_id,),
            ).fetchall()

            related_shares = conn.execute(
                "SELECT share_id FROM news_article_related_shares WHERE article_id = ?",
                (article_id,),
            ).fetchall()

        summary = self._map_article_summary(article_row)
        related_thread_ids = [row["thread_id"] for row in related_threads]
        related_share_ids = [row["share_id"] for row in related_shares]

        return ArticleDetail(
            article_id=summary.article_id,
            title=summary.title,
            category=summary.category,
            stage=summary.stage,
            author_id=summary.author_id,
            published_at=summary.published_at,
            views=summary.views,
            is_pinned=summary.is_pinned,
            excerpt=summary.excerpt,
            content=article_row["content"],
            related_thread_ids=related_thread_ids,
            related_share_ids=related_share_ids,
        )

    def get_hot_articles(self, limit: int = 5) -> list[ArticleSummary]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, title, category, stage, author_id, published_at, views, is_pinned, excerpt
                FROM news_articles
                ORDER BY views DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._map_article_summary(row) for row in rows]

    def create_article(
        self,
        *,
        title: str,
        content: str,
        category: str,
        stage: str,
        author_id: str,
        is_pinned: bool = False,
        related_thread_ids: list[str] = None,
        related_share_ids: list[str] = None,
    ) -> ArticleDetail:
        article_id = f"n{next(self._article_counter)}"
        now = datetime.now(timezone.utc).isoformat()
        excerpt = self._generate_excerpt(content)

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO news_articles (
                    id,
                    title,
                    content,
                    excerpt,
                    category,
                    stage,
                    author_id,
                    published_at,
                    views,
                    is_pinned
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (article_id, title, content, excerpt, category, self._normalize_stage(stage), author_id, now, 0, 1 if is_pinned else 0),
            )

            if related_thread_ids:
                for thread_id in related_thread_ids:
                    conn.execute(
                        """
                        INSERT INTO news_article_related_threads (article_id, thread_id)
                        VALUES (?, ?)
                        """,
                        (article_id, thread_id),
                    )

            if related_share_ids:
                for share_id in related_share_ids:
                    conn.execute(
                        """
                        INSERT INTO news_article_related_shares (article_id, share_id)
                        VALUES (?, ?)
                        """,
                        (article_id, share_id),
                    )

            conn.commit()

        article = self.get_article(article_id)
        if article is None:
            raise RuntimeError("Failed to load newly created article")
        return article

    def update_article(
        self,
        *,
        article_id: str,
        title: str | None = None,
        content: str | None = None,
        category: str | None = None,
        stage: str | None = None,
        is_pinned: bool | None = None,
        related_thread_ids: list[str] | None = None,
        related_share_ids: list[str] | None = None,
    ) -> ArticleDetail | None:
        with self.session_manager.connect() as conn:
            article_row = conn.execute(
                "SELECT id FROM news_articles WHERE id = ?",
                (article_id,),
            ).fetchone()

            if article_row is None:
                return None

            updates = []
            params = []

            if title is not None:
                updates.append("title = ?")
                params.append(title)

            if content is not None:
                updates.append("content = ?")
                updates.append("excerpt = ?")
                params.extend([content, self._generate_excerpt(content)])

            if category is not None:
                updates.append("category = ?")
                params.append(category)

            if stage is not None:
                updates.append("stage = ?")
                params.append(self._normalize_stage(stage))

            if is_pinned is not None:
                updates.append("is_pinned = ?")
                params.append(1 if is_pinned else 0)

            if updates:
                query = f"UPDATE news_articles SET {', '.join(updates)} WHERE id = ?"
                params.append(article_id)
                conn.execute(query, params)

            if related_thread_ids is not None:
                conn.execute("DELETE FROM news_article_related_threads WHERE article_id = ?", (article_id,))
                for thread_id in related_thread_ids:
                    conn.execute(
                        "INSERT INTO news_article_related_threads (article_id, thread_id) VALUES (?, ?)",
                        (article_id, thread_id),
                    )

            if related_share_ids is not None:
                conn.execute("DELETE FROM news_article_related_shares WHERE article_id = ?", (article_id,))
                for share_id in related_share_ids:
                    conn.execute(
                        "INSERT INTO news_article_related_shares (article_id, share_id) VALUES (?, ?)",
                        (article_id, share_id),
                    )

            conn.commit()

        return self.get_article(article_id)

    def delete_article(self, article_id: str) -> bool:
        with self.session_manager.connect() as conn:
            result = conn.execute("DELETE FROM news_articles WHERE id = ?", (article_id,))
            conn.execute("DELETE FROM news_article_related_threads WHERE article_id = ?", (article_id,))
            conn.execute("DELETE FROM news_article_related_shares WHERE article_id = ?", (article_id,))
            conn.commit()

        return result.rowcount > 0

    def increment_article_views(self, article_id: str) -> bool:
        with self.session_manager.connect() as conn:
            result = conn.execute(
                "UPDATE news_articles SET views = views + 1 WHERE id = ?",
                (article_id,),
            )
            conn.commit()

        return result.rowcount > 0

    def create_article_draft(
        self,
        *,
        category: str,
        author_id: str,
        requested_title: str,
        requested_content: str,
        requested_stage: str,
        requested_is_pinned: bool = False,
        requested_related_thread_ids: list[str] = None,
        requested_related_share_ids: list[str] = None,
    ) -> NewsArticleDraft:
        now = datetime.now(timezone.utc).isoformat()
        draft_id = f"nd{next(self._draft_counter):05d}"
        article_id = f"n{next(self._article_counter)}"

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO news_article_drafts (
                    draft_id,
                    article_id,
                    author_id,
                    category,
                    requested_title,
                    requested_content,
                    requested_stage,
                    requested_is_pinned,
                    status,
                    created_at,
                    published_at,
                    final_title,
                    final_content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    article_id,
                    author_id,
                    category,
                    requested_title,
                    requested_content,
                    self._normalize_stage(requested_stage),
                    1 if requested_is_pinned else 0,
                    "pending",
                    now,
                    None,
                    None,
                    None,
                ),
            )

            if requested_related_thread_ids:
                for thread_id in requested_related_thread_ids:
                    conn.execute(
                        """
                        INSERT INTO news_article_draft_related_threads (draft_id, thread_id)
                        VALUES (?, ?)
                        """,
                        (draft_id, thread_id),
                    )

            if requested_related_share_ids:
                for share_id in requested_related_share_ids:
                    conn.execute(
                        """
                        INSERT INTO news_article_draft_related_shares (draft_id, share_id)
                        VALUES (?, ?)
                        """,
                        (draft_id, share_id),
                    )

            conn.commit()

        return NewsArticleDraft(
            draft_id=draft_id,
            article_id=article_id,
            author_id=author_id,
            category=category,
            requested_title=requested_title,
            requested_content=requested_content,
            requested_stage=self._normalize_stage(requested_stage),
            requested_is_pinned=requested_is_pinned,
            requested_related_thread_ids=requested_related_thread_ids or [],
            requested_related_share_ids=requested_related_share_ids or [],
            created_at=now,
        )

    def publish_article_draft(
        self,
        *,
        draft_id: str,
        title: str,
        content: str,
        stage: str,
        is_pinned: bool = False,
        related_thread_ids: list[str] = None,
        related_share_ids: list[str] = None,
    ) -> ArticleDetail:
        with self.session_manager.connect() as conn:
            draft_row = conn.execute(
                "SELECT * FROM news_article_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()

            if draft_row is None:
                raise KeyError(f"Article draft not found: {draft_id}")

            if draft_row["status"] == "published":
                existing_article = self.get_article(draft_row["article_id"])
                if existing_article is None:
                    raise RuntimeError("Published draft is missing its article record")
                return existing_article

            now = datetime.now(timezone.utc).isoformat()
            excerpt = self._generate_excerpt(content)

            conn.execute(
                """
                INSERT INTO news_articles (
                    id,
                    title,
                    content,
                    excerpt,
                    stage,
                    category,
                    author_id,
                    published_at,
                    views,
                    is_pinned
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_row["article_id"],
                    title,
                    content,
                    excerpt,
                    self._normalize_stage(stage),
                    draft_row["category"],
                    draft_row["author_id"],
                    now,
                    0,
                    1 if is_pinned else 0,
                ),
            )

            if related_thread_ids:
                for thread_id in related_thread_ids:
                    conn.execute(
                        "INSERT INTO news_article_related_threads (article_id, thread_id) VALUES (?, ?)",
                        (draft_row["article_id"], thread_id),
                    )

            if related_share_ids:
                for share_id in related_share_ids:
                    conn.execute(
                        "INSERT INTO news_article_related_shares (article_id, share_id) VALUES (?, ?)",
                        (draft_row["article_id"], share_id),
                    )

            conn.execute(
                """
                UPDATE news_article_drafts
                SET status = ?, published_at = ?, final_title = ?, final_content = ?
                WHERE draft_id = ?
                """,
                ("published", now, title, content, draft_id),
            )

            conn.commit()

        article = self.get_article(draft_row["article_id"])
        if article is None:
            raise RuntimeError("Failed to load published article")
        return article

    def _map_article_summary(self, row: sqlite3.Row) -> ArticleSummary:
        return ArticleSummary(
            article_id=row["id"],
            title=row["title"],
            category=row["category"],
            stage=row["stage"],
            author_id=row["author_id"],
            published_at=row["published_at"],
            views=row["views"],
            is_pinned=bool(row["is_pinned"]),
            excerpt=row["excerpt"],
        )

    @staticmethod
    def _normalize_stage(stage: str) -> str:
        allowed = {"breaking", "investigation", "disclosure", "conclusion"}
        value = (stage or "").strip().lower()
        return value if value in allowed else "breaking"

    def _generate_excerpt(self, content: str, max_length: int = 150) -> str:
        # 简单的摘要生成逻辑
        content = content.replace("\n", " ").strip()
        if len(content) <= max_length:
            return content
        return content[:max_length].rsplit(" ", 1)[0] + "..."

    def _create_tables(self) -> None:
        with self.session_manager.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS news_stats (
                    online_users INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS news_categories (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    sort_order INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS news_articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    category TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT 'breaking',
                    author_id TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    views INTEGER NOT NULL DEFAULT 0,
                    is_pinned INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(category) REFERENCES news_categories(slug)
                );

                CREATE TABLE IF NOT EXISTS news_article_related_threads (
                    article_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    PRIMARY KEY (article_id, thread_id),
                    FOREIGN KEY(article_id) REFERENCES news_articles(id)
                );

                CREATE TABLE IF NOT EXISTS news_article_related_shares (
                    article_id TEXT NOT NULL,
                    share_id TEXT NOT NULL,
                    PRIMARY KEY (article_id, share_id),
                    FOREIGN KEY(article_id) REFERENCES news_articles(id)
                );

                CREATE TABLE IF NOT EXISTS news_article_drafts (
                    draft_id TEXT PRIMARY KEY,
                    article_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    requested_title TEXT NOT NULL,
                    requested_content TEXT NOT NULL,
                    requested_stage TEXT NOT NULL DEFAULT 'breaking',
                    requested_is_pinned INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    final_title TEXT,
                    final_content TEXT,
                    FOREIGN KEY(category) REFERENCES news_categories(slug)
                );

                CREATE TABLE IF NOT EXISTS news_article_draft_related_threads (
                    draft_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    PRIMARY KEY (draft_id, thread_id),
                    FOREIGN KEY(draft_id) REFERENCES news_article_drafts(draft_id)
                );

                CREATE TABLE IF NOT EXISTS news_article_draft_related_shares (
                    draft_id TEXT NOT NULL,
                    share_id TEXT NOT NULL,
                    PRIMARY KEY (draft_id, share_id),
                    FOREIGN KEY(draft_id) REFERENCES news_article_drafts(draft_id)
                );
                """
            )
            conn.commit()

    def _seed_if_empty(self) -> None:
        with self.session_manager.connect() as conn:
            category_count = conn.execute("SELECT COUNT(1) AS count FROM news_categories").fetchone()["count"]
            if category_count > 0:
                return

            conn.execute("INSERT INTO news_stats (online_users) VALUES (75)")

            conn.executemany(
                """
                INSERT INTO news_categories (slug, name, description, sort_order)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        "official",
                        "Official Announcements",
                        "Official statements and system updates from the administration.",
                        1,
                    ),
                    (
                        "breaking",
                        "Breaking News",
                        "Urgent and developing stories as they happen.",
                        2,
                    ),
                    (
                        "community",
                        "Community News",
                        "Local events and community activities.",
                        3,
                    ),
                    (
                        "investigation",
                        "Investigation Updates",
                        "Progress reports on ongoing investigations.",
                        4,
                    ),
                ],
            )

            conn.executemany(
                """
                INSERT INTO news_articles (
                    id,
                    title,
                    content,
                    excerpt,
                    category,
                    stage,
                    author_id,
                    published_at,
                    views,
                    is_pinned
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "n1001",
                        "Official Statement: System Maintenance Scheduled",
                        "The administration has announced scheduled system maintenance for this weekend. All services will be temporarily unavailable from 2:00 AM to 6:00 AM on Sunday. We apologize for any inconvenience this may cause.",
                        "The administration has announced scheduled system maintenance for this weekend.",
                        "official",
                        "disclosure",
                        "aria",
                        "2001-11-09 09:00:00",
                        342,
                        1,
                    ),
                    (
                        "n1002",
                        "Breaking: Courier Missing Near Old Exchange",
                        "A courier has been reported missing near the old exchange district. Witnesses report seeing someone matching the courier's description at 17:58, but no transaction records exist. The investigation is ongoing.",
                        "A courier has been reported missing near the old exchange district.",
                        "breaking",
                        "breaking",
                        "eve",
                        "2001-11-09 18:42:00",
                        1256,
                        1,
                    ),
                    (
                        "n1003",
                        "Community Market Day This Saturday",
                        "The monthly community market will be held this Saturday from 10:00 AM to 4:00 PM. Local vendors will be selling various goods and services. All are welcome to attend.",
                        "The monthly community market will be held this Saturday from 10:00 AM to 4:00 PM.",
                        "community",
                        "breaking",
                        "milo",
                        "2001-11-08 14:30:00",
                        289,
                        0,
                    ),
                    (
                        "n1004",
                        "Investigation Update: Fake Witness Account",
                        "Investigators have identified a fake witness account that was created 3 hours before a recent file drop. The account's claims are being treated as unverified until further evidence can be gathered.",
                        "Investigators have identified a fake witness account that was created 3 hours before a recent file drop.",
                        "investigation",
                        "investigation",
                        "aria",
                        "2001-11-09 22:44:00",
                        987,
                        0,
                    ),
                ],
            )

            conn.commit()

    def _ensure_stage_columns(self) -> None:
        with self.session_manager.connect() as conn:
            article_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(news_articles)").fetchall()
            }
            if "stage" not in article_columns:
                conn.execute("ALTER TABLE news_articles ADD COLUMN stage TEXT NOT NULL DEFAULT 'breaking'")

            draft_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(news_article_drafts)").fetchall()
            }
            if "requested_stage" not in draft_columns:
                conn.execute(
                    "ALTER TABLE news_article_drafts ADD COLUMN requested_stage TEXT NOT NULL DEFAULT 'breaking'"
                )
            conn.commit()

    def _sync_counters(self) -> None:
        with self.session_manager.connect() as conn:
            article_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(id, 2) AS INTEGER)), 9999) AS max_id FROM news_articles"
            ).fetchone()
            draft_row = conn.execute(
                """
                SELECT COALESCE(
                    MAX(CAST(SUBSTR(draft_id, 3) AS INTEGER)),
                    0
                ) AS max_id
                FROM news_article_drafts
                """
            ).fetchone()

        self._article_counter = count(int(article_row["max_id"]) + 1)
        self._draft_counter = count(int(draft_row["max_id"]) + 1)
