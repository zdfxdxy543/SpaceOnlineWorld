from __future__ import annotations

from itertools import count

from fastapi import APIRouter, HTTPException, Query, Request

from fastapi.responses import PlainTextResponse

from app.schemas.netdisk import (
    NetdiskCreateShareRequest,
    NetdiskFileContentResponse,
    NetdiskFileListItem,
    NetdiskShareAccessResponse,
    NetdiskShareResponse,
    NetdiskUploadRequest,
    NetdiskUploadResponse,
)
from app.simulation.protocol import ActionRequest

router = APIRouter()
_action_counter = count(1)


def _map_share(item) -> NetdiskShareResponse:
    return NetdiskShareResponse(
        share_id=item.share_id,
        resource_id=item.resource_id,
        access_code=item.access_code,
        share_url=item.share_url,
        status=item.status,
        created_at=item.created_at,
        expires_at=item.expires_at,
    )


@router.post("/upload-generate", response_model=NetdiskUploadResponse)
def upload_generate(payload: NetdiskUploadRequest, request: Request) -> NetdiskUploadResponse:
    world_service = request.app.state.container.world_service
    if not world_service.agent_exists(payload.actor_id):
        raise HTTPException(status_code=404, detail=f"Actor not found: {payload.actor_id}")

    action_request = ActionRequest(
        action_id=f"manual-action-{next(_action_counter):05d}",
        capability="netdisk.upload_file",
        actor_id=payload.actor_id,
        payload={
            "title": payload.title,
            "purpose": payload.purpose,
            "file_name": payload.file_name,
        },
        idempotency_key=f"manual-netdisk-upload:{payload.actor_id}:{payload.title}:{payload.file_name}:{next(_action_counter):05d}",
    )
    result = request.app.state.container.tool_registry.execute(action_request)
    if result.status != "success":
        raise HTTPException(status_code=400, detail=result.error_message or result.error_code or "upload_failed")

    output = result.output
    return NetdiskUploadResponse(
        status="uploaded",
        resource_id=str(output.get("resource_id", "")),
        title=str(output.get("title", "")),
        file_name=str(output.get("file_name", "")),
        local_path=str(output.get("local_path", "")),
        size_bytes=int(output.get("size_bytes", 0)),
    )


@router.post("/shares", response_model=NetdiskShareResponse)
def create_share(payload: NetdiskCreateShareRequest, request: Request) -> NetdiskShareResponse:
    service = request.app.state.container.netdisk_service
    share = service.create_share_link(
        resource_id=payload.resource_id,
        creator_agent_id=payload.actor_id,
        expires_hours=payload.expires_hours,
    )
    return _map_share(share)


@router.get("/shares/{share_id}", response_model=NetdiskShareAccessResponse)
def get_share(share_id: str, request: Request, access_code: str = Query(...)) -> NetdiskShareAccessResponse:
    service = request.app.state.container.netdisk_service
    share = service.validate_share_reference(share_id=share_id, access_code=access_code)
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found or access code invalid")

    file_item = service.get_file(resource_id=share.resource_id)
    if file_item is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    return NetdiskShareAccessResponse(
        share=_map_share(share),
        file_name=file_item.file_name,
        title=file_item.title,
        purpose=file_item.purpose,
        size_bytes=file_item.size_bytes,
    )


@router.get("/files", response_model=list[NetdiskFileListItem])
def list_files(request: Request, limit: int = Query(default=100, ge=1, le=500)) -> list[NetdiskFileListItem]:
    service = request.app.state.container.netdisk_service
    records = service.list_files(limit=limit)
    return [
        NetdiskFileListItem(
            resource_id=r.resource_id,
            owner_agent_id=r.owner_agent_id,
            title=r.title,
            file_name=r.file_name,
            size_bytes=r.size_bytes,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/files/{resource_id}", response_model=NetdiskFileContentResponse)
def get_file_content(
    resource_id: str,
    request: Request,
    access_code: str = Query(...),
) -> NetdiskFileContentResponse:
    service = request.app.state.container.netdisk_service
    # Prefer share_id lookup for user-facing file IDs, then fallback to raw resource_id.
    share = service.validate_share_reference(share_id=resource_id, access_code=access_code)
    resolved_resource_id = share.resource_id if share is not None else resource_id
    if share is None:
        share = service.validate_file_access(resource_id=resource_id, access_code=access_code)
        if share is None:
            raise HTTPException(status_code=404, detail="File not found or access code invalid")
        resolved_resource_id = share.resource_id

    item = service.get_file(resource_id=resolved_resource_id)
    if item is None:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = open(item.local_path, encoding="utf-8").read()
    except OSError:
        content = "[File content unavailable]"
    return NetdiskFileContentResponse(
        resource_id=item.resource_id,
        title=item.title,
        file_name=item.file_name,
        size_bytes=item.size_bytes,
        content=content,
        created_at=item.created_at,
    )


@router.get("/files/{resource_id}/download")
def download_file(
    resource_id: str,
    request: Request,
    access_code: str = Query(...),
) -> PlainTextResponse:
    service = request.app.state.container.netdisk_service
    # Prefer share_id lookup for user-facing file IDs, then fallback to raw resource_id.
    share = service.validate_share_reference(share_id=resource_id, access_code=access_code)
    resolved_resource_id = share.resource_id if share is not None else resource_id
    if share is None:
        share = service.validate_file_access(resource_id=resource_id, access_code=access_code)
        if share is None:
            raise HTTPException(status_code=404, detail="File not found or access code invalid")
        resolved_resource_id = share.resource_id

    item = service.get_file(resource_id=resolved_resource_id)
    if item is None:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = open(item.local_path, encoding="utf-8").read()
    except OSError:
        raise HTTPException(status_code=500, detail="File content unavailable on disk")
    return PlainTextResponse(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{item.file_name}"'},
    )
