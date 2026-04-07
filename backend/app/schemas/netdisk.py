from __future__ import annotations

from pydantic import BaseModel


class NetdiskFileListItem(BaseModel):
    resource_id: str
    owner_agent_id: str
    title: str
    file_name: str
    size_bytes: int
    created_at: str


class NetdiskFileContentResponse(BaseModel):
    resource_id: str
    title: str
    file_name: str
    size_bytes: int
    content: str
    created_at: str


class NetdiskUploadRequest(BaseModel):
    actor_id: str
    title: str
    purpose: str
    file_name: str = "report.txt"


class NetdiskUploadResponse(BaseModel):
    status: str
    resource_id: str
    title: str
    file_name: str
    local_path: str
    size_bytes: int


class NetdiskCreateShareRequest(BaseModel):
    actor_id: str
    resource_id: str
    expires_hours: int | None = None


class NetdiskShareResponse(BaseModel):
    share_id: str
    resource_id: str
    access_code: str
    share_url: str
    status: str
    created_at: str
    expires_at: str | None


class NetdiskShareAccessResponse(BaseModel):
    share: NetdiskShareResponse
    file_name: str
    title: str
    purpose: str
    size_bytes: int
