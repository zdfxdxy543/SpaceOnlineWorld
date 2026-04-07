from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class NetdiskUploadDraft:
    draft_id: str
    resource_id: str
    owner_agent_id: str
    title: str
    purpose: str
    requested_file_name: str
    created_at: str


@dataclass(slots=True)
class NetdiskFileRecord:
    resource_id: str
    owner_agent_id: str
    title: str
    purpose: str
    file_name: str
    local_path: str
    size_bytes: int
    content_hash: str
    created_at: str


@dataclass(slots=True)
class NetdiskShareRecord:
    share_id: str
    resource_id: str
    access_code: str
    share_url: str
    status: str
    created_at: str
    expires_at: str | None
    creator_agent_id: str


class AbstractNetdiskRepository(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_upload_draft(
        self,
        *,
        owner_agent_id: str,
        title: str,
        purpose: str,
        requested_file_name: str,
    ) -> NetdiskUploadDraft:
        raise NotImplementedError

    @abstractmethod
    def publish_upload_draft(
        self,
        *,
        draft_id: str,
        file_name: str,
        local_path: str,
        size_bytes: int,
        content_hash: str,
    ) -> NetdiskFileRecord:
        raise NotImplementedError

    @abstractmethod
    def get_upload_draft(self, *, draft_id: str) -> NetdiskUploadDraft | None:
        raise NotImplementedError

    @abstractmethod
    def create_share(
        self,
        *,
        resource_id: str,
        creator_agent_id: str,
        access_code: str,
        expires_at: str | None,
    ) -> NetdiskShareRecord:
        raise NotImplementedError

    @abstractmethod
    def get_share(self, *, share_id: str) -> NetdiskShareRecord | None:
        raise NotImplementedError

    @abstractmethod
    def get_share_by_resource_access(
        self,
        *,
        resource_id: str,
        access_code: str,
    ) -> NetdiskShareRecord | None:
        raise NotImplementedError

    @abstractmethod
    def get_file(self, *, resource_id: str) -> NetdiskFileRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_files(self, *, limit: int = 100) -> list[NetdiskFileRecord]:
        raise NotImplementedError
