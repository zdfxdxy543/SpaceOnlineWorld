from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import count

from app.infrastructure.db.session import DatabaseSessionManager
from app.repositories.netdisk_repository import (
    AbstractNetdiskRepository,
    NetdiskFileRecord,
    NetdiskShareRecord,
    NetdiskUploadDraft,
)


class SQLiteNetdiskRepository(AbstractNetdiskRepository):
    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager
        self._resource_counter = count(1)
        self._share_counter = count(1)
        self._draft_counter = count(1)

    def initialize(self) -> None:
        with self.session_manager.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS netdisk_upload_drafts (
                    draft_id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    owner_agent_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    requested_file_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    final_file_name TEXT,
                    local_path TEXT,
                    size_bytes INTEGER,
                    content_hash TEXT
                );

                CREATE TABLE IF NOT EXISTS netdisk_files (
                    resource_id TEXT PRIMARY KEY,
                    owner_agent_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS netdisk_shares (
                    share_id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    access_code TEXT NOT NULL,
                    share_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    creator_agent_id TEXT NOT NULL,
                    FOREIGN KEY(resource_id) REFERENCES netdisk_files(resource_id)
                );

                CREATE TABLE IF NOT EXISTS netdisk_access_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    share_id TEXT NOT NULL,
                    access_result TEXT NOT NULL,
                    detail TEXT,
                    occurred_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS world_resources (
                    resource_id TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    access_code TEXT NOT NULL,
                    owner_agent_id TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                """
            )

            resource_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(resource_id, 4) AS INTEGER)), 0) AS max_id FROM netdisk_files WHERE resource_id LIKE 'nd-%'"
            ).fetchone()
            share_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(share_id, 4) AS INTEGER)), 0) AS max_id FROM netdisk_shares WHERE share_id LIKE 'sh-%'"
            ).fetchone()
            draft_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(draft_id, 5) AS INTEGER)), 0) AS max_id FROM netdisk_upload_drafts WHERE draft_id LIKE 'ndd-%'"
            ).fetchone()

            self._resource_counter = count(int(resource_row["max_id"]) + 1)
            self._share_counter = count(int(share_row["max_id"]) + 1)
            self._draft_counter = count(int(draft_row["max_id"]) + 1)
            conn.commit()

    def create_upload_draft(
        self,
        *,
        owner_agent_id: str,
        title: str,
        purpose: str,
        requested_file_name: str,
    ) -> NetdiskUploadDraft:
        draft_id = f"ndd-{next(self._draft_counter):05d}"
        resource_id = f"nd-{next(self._resource_counter):05d}"
        now = datetime.now(timezone.utc).isoformat()

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO netdisk_upload_drafts (
                    draft_id,
                    resource_id,
                    owner_agent_id,
                    title,
                    purpose,
                    requested_file_name,
                    status,
                    created_at,
                    published_at,
                    final_file_name,
                    local_path,
                    size_bytes,
                    content_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    resource_id,
                    owner_agent_id,
                    title,
                    purpose,
                    requested_file_name,
                    "pending",
                    now,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            conn.commit()

        return NetdiskUploadDraft(
            draft_id=draft_id,
            resource_id=resource_id,
            owner_agent_id=owner_agent_id,
            title=title,
            purpose=purpose,
            requested_file_name=requested_file_name,
            created_at=now,
        )

    def publish_upload_draft(
        self,
        *,
        draft_id: str,
        file_name: str,
        local_path: str,
        size_bytes: int,
        content_hash: str,
    ) -> NetdiskFileRecord:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                "SELECT * FROM netdisk_upload_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Netdisk draft not found: {draft_id}")

            if row["status"] == "published":
                existing = self.get_file(resource_id=row["resource_id"])
                if existing is None:
                    raise RuntimeError("Published draft missing file record")
                return existing

            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO netdisk_files (
                    resource_id,
                    owner_agent_id,
                    title,
                    purpose,
                    file_name,
                    local_path,
                    size_bytes,
                    content_hash,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["resource_id"],
                    row["owner_agent_id"],
                    row["title"],
                    row["purpose"],
                    file_name,
                    local_path,
                    size_bytes,
                    content_hash,
                    now,
                ),
            )

            metadata = {
                "local_path": local_path,
                "content_hash": content_hash,
                "size_bytes": size_bytes,
                "purpose": row["purpose"],
            }
            conn.execute(
                """
                INSERT INTO world_resources (
                    resource_id,
                    resource_type,
                    title,
                    access_code,
                    owner_agent_id,
                    site_id,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["resource_id"],
                    "netdisk_file",
                    row["title"],
                    "",
                    row["owner_agent_id"],
                    "netdisk.main",
                    json.dumps(metadata, ensure_ascii=True),
                ),
            )

            conn.execute(
                """
                UPDATE netdisk_upload_drafts
                SET status = ?,
                    published_at = ?,
                    final_file_name = ?,
                    local_path = ?,
                    size_bytes = ?,
                    content_hash = ?
                WHERE draft_id = ?
                """,
                (
                    "published",
                    now,
                    file_name,
                    local_path,
                    size_bytes,
                    content_hash,
                    draft_id,
                ),
            )
            conn.commit()

        created = self.get_file(resource_id=row["resource_id"])
        if created is None:
            raise RuntimeError("Failed to load published netdisk file")
        return created

    def create_share(
        self,
        *,
        resource_id: str,
        creator_agent_id: str,
        access_code: str,
        expires_at: str | None,
    ) -> NetdiskShareRecord:
        share_id = f"sh-{next(self._share_counter):05d}"
        share_url = f"/api/v1/netdisk/shares/{share_id}"
        now = datetime.now(timezone.utc).isoformat()

        with self.session_manager.connect() as conn:
            file_row = conn.execute(
                "SELECT resource_id FROM netdisk_files WHERE resource_id = ?",
                (resource_id,),
            ).fetchone()
            if file_row is None:
                raise KeyError(f"Netdisk resource not found: {resource_id}")

            conn.execute(
                """
                INSERT INTO netdisk_shares (
                    share_id,
                    resource_id,
                    access_code,
                    share_url,
                    status,
                    created_at,
                    expires_at,
                    creator_agent_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    share_id,
                    resource_id,
                    access_code,
                    share_url,
                    "active",
                    now,
                    expires_at,
                    creator_agent_id,
                ),
            )

            world_row = conn.execute(
                "SELECT metadata_json FROM world_resources WHERE resource_id = ?",
                (resource_id,),
            ).fetchone()
            metadata = {}
            if world_row is not None:
                try:
                    metadata = json.loads(world_row["metadata_json"])
                except json.JSONDecodeError:
                    metadata = {}
            metadata["last_share_id"] = share_id
            metadata["last_share_url"] = share_url

            conn.execute(
                """
                UPDATE world_resources
                SET access_code = ?, metadata_json = ?
                WHERE resource_id = ?
                """,
                (
                    access_code,
                    json.dumps(metadata, ensure_ascii=True),
                    resource_id,
                ),
            )
            conn.commit()

        created = self.get_share(share_id=share_id)
        if created is None:
            raise RuntimeError("Failed to load created netdisk share")
        return created

    def get_upload_draft(self, *, draft_id: str) -> NetdiskUploadDraft | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT draft_id, resource_id, owner_agent_id, title, purpose, requested_file_name, created_at
                FROM netdisk_upload_drafts
                WHERE draft_id = ?
                """,
                (draft_id,),
            ).fetchone()
        if row is None:
            return None
        return NetdiskUploadDraft(
            draft_id=row["draft_id"],
            resource_id=row["resource_id"],
            owner_agent_id=row["owner_agent_id"],
            title=row["title"],
            purpose=row["purpose"],
            requested_file_name=row["requested_file_name"],
            created_at=row["created_at"],
        )

    def get_share(self, *, share_id: str) -> NetdiskShareRecord | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                "SELECT * FROM netdisk_shares WHERE share_id = ?",
                (share_id,),
            ).fetchone()
        if row is None:
            return None
        return NetdiskShareRecord(
            share_id=row["share_id"],
            resource_id=row["resource_id"],
            access_code=row["access_code"],
            share_url=row["share_url"],
            status=row["status"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            creator_agent_id=row["creator_agent_id"],
        )

    def get_share_by_resource_access(
        self,
        *,
        resource_id: str,
        access_code: str,
    ) -> NetdiskShareRecord | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM netdisk_shares
                WHERE resource_id = ? AND access_code = ? AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (resource_id, access_code),
            ).fetchone()
        if row is None:
            return None
        return NetdiskShareRecord(
            share_id=row["share_id"],
            resource_id=row["resource_id"],
            access_code=row["access_code"],
            share_url=row["share_url"],
            status=row["status"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            creator_agent_id=row["creator_agent_id"],
        )

    def get_file(self, *, resource_id: str) -> NetdiskFileRecord | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                "SELECT * FROM netdisk_files WHERE resource_id = ?",
                (resource_id,),
            ).fetchone()
        if row is None:
            return None
        return NetdiskFileRecord(
            resource_id=row["resource_id"],
            owner_agent_id=row["owner_agent_id"],
            title=row["title"],
            purpose=row["purpose"],
            file_name=row["file_name"],
            local_path=row["local_path"],
            size_bytes=row["size_bytes"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
        )

    def list_files(self, *, limit: int = 100) -> list[NetdiskFileRecord]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM netdisk_files ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            NetdiskFileRecord(
                resource_id=row["resource_id"],
                owner_agent_id=row["owner_agent_id"],
                title=row["title"],
                purpose=row["purpose"],
                file_name=row["file_name"],
                local_path=row["local_path"],
                size_bytes=row["size_bytes"],
                content_hash=row["content_hash"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
