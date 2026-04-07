from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.infrastructure.db.forum_repository import SQLiteForumRepository
from app.infrastructure.db.mainpage_repository import SQLiteMainPageRepository
from app.infrastructure.db.netdisk_repository import SQLiteNetdiskRepository
from app.infrastructure.db.news_repository import SQLiteNewsRepository
from app.infrastructure.db.paper_repository import SQLitePaperRepository
from app.infrastructure.db.p2pstore_repository import SQLiteP2PStoreRepository
from app.infrastructure.db.session import DatabaseSessionManager
from app.infrastructure.db.social_repository import SQLiteSocialRepository
from app.infrastructure.db.world_repository import SQLiteWorldRepository


def remove_existing_database(session_manager: DatabaseSessionManager) -> None:
    database_path = session_manager.sqlite_path()
    if database_path.exists():
        database_path.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(database_path) + suffix)
        if sidecar.exists():
            sidecar.unlink()


def initialize_repositories(session_manager: DatabaseSessionManager) -> None:
    repositories = [
        SQLiteForumRepository(session_manager),
        SQLiteWorldRepository(session_manager),
        SQLiteNetdiskRepository(session_manager),
        SQLiteNewsRepository(session_manager),
        SQLitePaperRepository(session_manager),
        SQLiteP2PStoreRepository(session_manager),
        SQLiteMainPageRepository(session_manager),
        SQLiteSocialRepository(session_manager),
    ]
    for repository in repositories:
        repository.initialize()


def seed_demo_forum_content(session_manager: DatabaseSessionManager) -> None:
    with session_manager.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO threads (
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
                "t9001",
                "town-square",
                "[Demo] Welcome to OnlineWorld API forum",
                "discussion",
                "aria",
                1,
                42,
                "milo",
                "2001-11-11 10:08",
                0,
                "demo,announcement",
            ),
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO posts (id, thread_id, author_id, created_at, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "p9001",
                "t9001",
                "aria",
                "2001-11-11 10:05",
                "Forum API has been initialized. This post is inserted by scripts/init_db.py.",
            ),
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO posts (id, thread_id, author_id, created_at, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "p9002",
                "t9001",
                "milo",
                "2001-11-11 10:08",
                "Acknowledged. Data path verified from database to API to frontend.",
            ),
        )

        conn.commit()


def main() -> None:
    settings = get_settings()
    session_manager = DatabaseSessionManager(settings.database_url)

    remove_existing_database(session_manager)
    initialize_repositories(session_manager)
    seed_demo_forum_content(session_manager)
    session_manager.mark_initialized()

    repository = SQLiteForumRepository(session_manager)
    stats = repository.get_stats()
    print("Database initialized successfully.")
    print(f"database_url: {settings.database_url}")
    print(f"online_users: {stats.online_users}")
    print(f"total_threads: {stats.total_threads}")
    print(f"total_posts: {stats.total_posts}")


if __name__ == "__main__":
    main()
