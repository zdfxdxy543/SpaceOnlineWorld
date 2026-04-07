from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
import re

from app.infrastructure.db.session import DatabaseSessionManager
from app.repositories.mainpage_repository import AbstractMainPageRepository, MainPageDraft, MainPageRecord


class SQLiteMainPageRepository(AbstractMainPageRepository):
    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager
        self._page_counter = count(1)
        self._draft_counter = count(1)

    def initialize(self) -> None:
        with self.session_manager.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS main_page_drafts (
                    draft_id TEXT PRIMARY KEY,
                    page_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    requested_title TEXT NOT NULL,
                    requested_description TEXT NOT NULL,
                    requested_style TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    final_title TEXT,
                    final_html_content TEXT,
                    final_assets_json TEXT
                );

                CREATE TABLE IF NOT EXISTS main_pages (
                    page_id TEXT PRIMARY KEY,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    html_content TEXT NOT NULL,
                    assets_json TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_main_pages_slug ON main_pages(slug);
                CREATE INDEX IF NOT EXISTS idx_main_page_drafts_slug ON main_page_drafts(slug);
                """
            )

            page_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(page_id, 4) AS INTEGER)), 0) AS max_id FROM main_pages WHERE page_id LIKE 'mp-%'"
            ).fetchone()
            draft_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(draft_id, 5) AS INTEGER)), 0) AS max_id FROM main_page_drafts WHERE draft_id LIKE 'mpd-%'"
            ).fetchone()

            self._page_counter = count(int(page_row["max_id"]) + 1)
            self._draft_counter = count(int(draft_row["max_id"]) + 1)
            conn.commit()

    def create_page_draft(
        self,
        *,
        author_id: str,
        slug_hint: str,
        requested_title: str,
        requested_description: str,
        requested_style: str,
    ) -> MainPageDraft:
        draft_id = f"mpd-{next(self._draft_counter):05d}"
        page_id = f"mp-{next(self._page_counter):05d}"
        now = datetime.now(timezone.utc).isoformat()
        slug = self._allocate_unique_slug(slug_hint)

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO main_page_drafts (
                    draft_id,
                    page_id,
                    author_id,
                    slug,
                    requested_title,
                    requested_description,
                    requested_style,
                    status,
                    created_at,
                    published_at,
                    final_title,
                    final_html_content,
                    final_assets_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    page_id,
                    author_id,
                    slug,
                    requested_title,
                    requested_description,
                    requested_style,
                    "pending",
                    now,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            conn.commit()

        return MainPageDraft(
            draft_id=draft_id,
            page_id=page_id,
            author_id=author_id,
            slug=slug,
            requested_title=requested_title,
            requested_description=requested_description,
            requested_style=requested_style,
            created_at=now,
        )

    def get_page_draft(self, *, draft_id: str) -> MainPageDraft | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    draft_id,
                    page_id,
                    author_id,
                    slug,
                    requested_title,
                    requested_description,
                    requested_style,
                    created_at
                FROM main_page_drafts
                WHERE draft_id = ?
                """,
                (draft_id,),
            ).fetchone()
        if row is None:
            return None
        return MainPageDraft(
            draft_id=row["draft_id"],
            page_id=row["page_id"],
            author_id=row["author_id"],
            slug=row["slug"],
            requested_title=row["requested_title"],
            requested_description=row["requested_description"],
            requested_style=row["requested_style"],
            created_at=row["created_at"],
        )

    def publish_page_draft(
        self,
        *,
        draft_id: str,
        title: str,
        html_content: str,
        assets_json: str,
    ) -> MainPageRecord:
        with self.session_manager.connect() as conn:
            draft_row = conn.execute(
                "SELECT * FROM main_page_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
            if draft_row is None:
                raise KeyError(f"Main page draft not found: {draft_id}")

            if draft_row["status"] == "published":
                existing = self.get_page_by_slug(slug=draft_row["slug"])
                if existing is None:
                    raise RuntimeError("Published draft is missing page record")
                return existing

            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO main_pages (
                    page_id,
                    slug,
                    title,
                    html_content,
                    assets_json,
                    author_id,
                    published_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_row["page_id"],
                    draft_row["slug"],
                    title,
                    html_content,
                    assets_json,
                    draft_row["author_id"],
                    now,
                    now,
                ),
            )

            conn.execute(
                """
                UPDATE main_page_drafts
                SET status = ?,
                    published_at = ?,
                    final_title = ?,
                    final_html_content = ?,
                    final_assets_json = ?
                WHERE draft_id = ?
                """,
                (
                    "published",
                    now,
                    title,
                    html_content,
                    assets_json,
                    draft_id,
                ),
            )
            conn.commit()

        created = self.get_page_by_slug(slug=draft_row["slug"])
        if created is None:
            raise RuntimeError("Failed to load published page")
        return created

    def get_page_by_slug(self, *, slug: str) -> MainPageRecord | None:
        with self.session_manager.connect() as conn:
            row = conn.execute("SELECT * FROM main_pages WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return None
        return MainPageRecord(
            page_id=row["page_id"],
            slug=row["slug"],
            title=row["title"],
            html_content=row["html_content"],
            assets_json=row["assets_json"],
            author_id=row["author_id"],
            published_at=row["published_at"],
            updated_at=row["updated_at"],
        )

    def list_pages(self, *, limit: int = 50) -> list[MainPageRecord]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM main_pages ORDER BY published_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            MainPageRecord(
                page_id=row["page_id"],
                slug=row["slug"],
                title=row["title"],
                html_content=row["html_content"],
                assets_json=row["assets_json"],
                author_id=row["author_id"],
                published_at=row["published_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def _allocate_unique_slug(self, slug_hint: str) -> str:
        base = self._normalize_slug(slug_hint)
        candidate = base
        suffix = 2

        with self.session_manager.connect() as conn:
            while True:
                exists = conn.execute(
                    "SELECT 1 FROM main_pages WHERE slug = ? UNION SELECT 1 FROM main_page_drafts WHERE slug = ? LIMIT 1",
                    (candidate, candidate),
                ).fetchone()
                if exists is None:
                    return candidate
                candidate = f"{base}-{suffix}"
                suffix += 1

    @staticmethod
    def _normalize_slug(value: str) -> str:
        raw = re.sub(r"[^a-z0-9_-]", "-", value.strip().lower())
        raw = re.sub(r"-+", "-", raw).strip("-")
        if not raw:
            raw = "generated-page"
        return raw[:64]
