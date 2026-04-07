from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.repositories.netdisk_repository import (
    AbstractNetdiskRepository,
    NetdiskFileRecord,
    NetdiskShareRecord,
    NetdiskUploadDraft,
)


class NetdiskService:
    def __init__(self, repository: AbstractNetdiskRepository, *, storage_dir: str) -> None:
        self.repository = repository
        self.storage_root = Path(storage_dir)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def create_upload_draft(
        self,
        *,
        owner_agent_id: str,
        title: str,
        purpose: str,
        requested_file_name: str,
    ) -> NetdiskUploadDraft:
        file_name = self._normalize_file_name(requested_file_name)
        return self.repository.create_upload_draft(
            owner_agent_id=owner_agent_id,
            title=title.strip() or "Untitled File",
            purpose=purpose.strip() or "General upload",
            requested_file_name=file_name,
        )

    def publish_upload_draft(
        self,
        *,
        draft_id: str,
        file_name: str,
        file_content: str,
    ) -> NetdiskFileRecord:
        normalized_file_name = self._normalize_file_name(file_name)
        content = file_content.strip()
        if not content:
            raise ValueError("Generated file content is empty")

        file_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
        draft_record = self._get_draft_record(draft_id)
        local_dir = self.storage_root / draft_record.owner_agent_id / draft_record.resource_id
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / normalized_file_name
        local_path.write_text(content, encoding="utf-8")
        size_bytes = local_path.stat().st_size

        return self.repository.publish_upload_draft(
            draft_id=draft_id,
            file_name=normalized_file_name,
            local_path=str(local_path),
            size_bytes=size_bytes,
            content_hash=file_hash,
        )

    def create_share_link(
        self,
        *,
        resource_id: str,
        creator_agent_id: str,
        expires_hours: int | None = None,
    ) -> NetdiskShareRecord:
        access_code = self._generate_access_code()
        expires_at: str | None = None
        if expires_hours is not None and expires_hours > 0:
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
        return self.repository.create_share(
            resource_id=resource_id,
            creator_agent_id=creator_agent_id,
            access_code=access_code,
            expires_at=expires_at,
        )

    def get_share(self, *, share_id: str) -> NetdiskShareRecord | None:
        return self.repository.get_share(share_id=share_id)

    def validate_share_reference(self, *, share_id: str, access_code: str) -> NetdiskShareRecord | None:
        share = self.repository.get_share(share_id=share_id)
        if share is None:
            return None
        if share.status != "active":
            return None
        if share.access_code != access_code:
            return None
        if share.expires_at:
            expires_at = datetime.fromisoformat(share.expires_at)
            if expires_at < datetime.now(timezone.utc):
                return None
        return share

    def validate_file_access(self, *, resource_id: str, access_code: str) -> NetdiskShareRecord | None:
        share = self.repository.get_share_by_resource_access(
            resource_id=resource_id,
            access_code=access_code,
        )
        if share is None:
            return None
        if share.expires_at:
            expires_at = datetime.fromisoformat(share.expires_at)
            if expires_at < datetime.now(timezone.utc):
                return None
        return share

    def get_file(self, *, resource_id: str) -> NetdiskFileRecord | None:
        return self.repository.get_file(resource_id=resource_id)

    def list_files(self, *, limit: int = 100) -> list[NetdiskFileRecord]:
        return self.repository.list_files(limit=limit)

    def _get_draft_record(self, draft_id: str) -> NetdiskUploadDraft:
        draft = self.repository.get_upload_draft(draft_id=draft_id)
        if draft is None:
            raise KeyError(f"Netdisk draft not found: {draft_id}")
        return draft

    @staticmethod
    def _generate_access_code() -> str:
        return secrets.token_hex(3).upper()

    @staticmethod
    def _normalize_file_name(value: str) -> str:
        raw = value.strip() or "report.txt"
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", raw)
        if "." not in safe:
            safe = f"{safe}.txt"
        return safe[:120]
