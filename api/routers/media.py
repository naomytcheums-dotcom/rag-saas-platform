"""Partie 22 -- multi-modal media endpoints. Org-scoped upload/list
routes reuse `require_org_member`/`require_org_admin` directly (same
convention as every other org-scoped router); single-resource routes
use the new `require_media_member`/`require_media_admin`
(api/security/media.py), a flat `/media/{id}` path -- this part's own
literal spec never nests these under `{org_id}`, the same real,
documented access-level adaptation already applied for Parties 19/20/21.

**`POST /media/search`, real, single, consolidated endpoint** -- this
part's own literal spec additionally names `/media/search/visual` and
`/media/search/audio`, but the real underlying search
(`api.services.media.search_media`) is ONE real function over ONE real
chunk table, filterable by `media_type` -- 3 separate routes for the
same real query with a different default filter would be redundant
surface, not a real functional difference (this session's own standing
"correct DeepSeek's own incoherent/duplicate asks" instruction). One
route, one real optional `media_type` filter."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.media import MediaAsset
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.media import (
    MediaAssetListResponse, MediaAssetResponse, MediaFrameResponse, MediaSearchRequest, MediaSearchResponse,
    MediaTranscriptResponse,
)
from api.security.media import require_media_admin, require_media_member
from api.security.organizations import require_org_member
from api.services import media as media_service
from api.services.document_storage import stream_document_file
from api.tasks.media import schedule_media_processing

router = APIRouter(tags=["media"])


@router.post("/organizations/{org_id}/media", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_media_endpoint(
    org_id: uuid.UUID, file: UploadFile = File(...), _caller: OrganizationMember = Depends(require_org_member),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        asset = await media_service.upload_media(
            db, org_id, current_user.id, file.filename or "media", content, file.content_type or "application/octet-stream",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(asset)
    schedule_media_processing(asset.id)
    return asset


@router.get("/organizations/{org_id}/media", response_model=MediaAssetListResponse)
async def list_media_endpoint(
    org_id: uuid.UUID, media_type: str | None = None, limit: int = 50, offset: int = 0,
    _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db),
):
    return await media_service.list_media(db, org_id, media_type, limit, offset)


@router.get("/media/{media_asset_id}", response_model=MediaAssetResponse)
async def get_media_endpoint(asset_ctx: tuple[MediaAsset, OrganizationMember] = Depends(require_media_member)):
    asset, _caller = asset_ctx
    return asset


@router.delete("/media/{media_asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_endpoint(asset_ctx: tuple[MediaAsset, OrganizationMember] = Depends(require_media_admin), db: AsyncSession = Depends(get_db)):
    asset, _caller = asset_ctx
    await media_service.delete_media(db, asset.id)
    await db.commit()


@router.post("/media/{media_asset_id}/process", response_model=MediaAssetResponse)
async def process_media_endpoint(asset_ctx: tuple[MediaAsset, OrganizationMember] = Depends(require_media_admin), db: AsyncSession = Depends(get_db)):
    """Real, synchronous (in-request) processing -- distinct from the
    automatic Celery dispatch at upload time, useful to re-run
    processing on demand (e.g. after a real transient provider
    failure) without waiting for a broker round-trip."""
    asset, _caller = asset_ctx
    updated = await media_service.process_media_asset(db, asset.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.get("/media/{media_asset_id}/status", response_model=MediaAssetResponse)
async def get_media_status_endpoint(asset_ctx: tuple[MediaAsset, OrganizationMember] = Depends(require_media_member)):
    asset, _caller = asset_ctx
    return asset


@router.get("/media/{media_asset_id}/transcript", response_model=MediaTranscriptResponse)
async def get_media_transcript_endpoint(
    asset_ctx: tuple[MediaAsset, OrganizationMember] = Depends(require_media_member), db: AsyncSession = Depends(get_db),
):
    asset, _caller = asset_ctx
    transcript = await media_service.get_transcript(db, asset.id)
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No transcript yet for this media asset")
    return transcript


@router.get("/media/{media_asset_id}/description", response_model=MediaAssetResponse)
async def get_media_description_endpoint(asset_ctx: tuple[MediaAsset, OrganizationMember] = Depends(require_media_member)):
    """Real item ask (`describe_image`/`describe_video`'s own output)
    -- surfaced from the SAME real `MediaAsset.description`/
    `objects_json`/`tags_json` columns `GET /media/{id}` already
    returns, so this route is a real, documented, deliberate alias
    rather than a second, duplicated payload shape."""
    asset, _caller = asset_ctx
    return asset


@router.get("/media/{media_asset_id}/file")
async def get_media_file_endpoint(asset_ctx: tuple[MediaAsset, OrganizationMember] = Depends(require_media_member)):
    """Real, authenticated, chunked proxy -- same real
    "never a direct/public S3 URL" pattern as `GET /documents/{id}/preview`
    (api/routers/documents.py), reusing its own `stream_document_file`
    directly."""
    asset, _caller = asset_ctx
    try:
        chunks = stream_document_file(asset.file_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return StreamingResponse(chunks, media_type=asset.mime_type, headers={"Content-Disposition": f'inline; filename="{asset.filename}"'})


@router.get("/media/{media_asset_id}/frames", response_model=list[MediaFrameResponse])
async def list_media_frames_endpoint(
    asset_ctx: tuple[MediaAsset, OrganizationMember] = Depends(require_media_member), db: AsyncSession = Depends(get_db),
):
    asset, _caller = asset_ctx
    return await media_service.list_frames(db, asset.id)


@router.get("/media/{media_asset_id}/frames/{frame_id}/file")
async def get_media_frame_file_endpoint(
    frame_id: uuid.UUID, asset_ctx: tuple[MediaAsset, OrganizationMember] = Depends(require_media_member), db: AsyncSession = Depends(get_db),
):
    asset, _caller = asset_ctx
    frames = await media_service.list_frames(db, asset.id)
    frame = next((f for f in frames if f.id == frame_id), None)
    if frame is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        chunks = stream_document_file(frame.file_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return StreamingResponse(chunks, media_type="image/jpeg")


@router.post("/media/search", response_model=MediaSearchResponse)
async def search_media_endpoint(payload: MediaSearchRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Real, org-scoped by the caller's OWN organizations only -- see
    this module's own docstring for why `visual`/`audio` search are
    consolidated here as a real, optional `media_type` filter rather
    than 2 separate routes."""
    memberships = (await db.execute(select(OrganizationMember.organization_id).where(OrganizationMember.user_id == current_user.id))).scalars().all()
    if not memberships:
        return MediaSearchResponse(results=[])

    all_results = []
    for organization_id in memberships:
        all_results.extend(await media_service.search_media(db, organization_id, payload.query, payload.media_type, payload.top_k))
    all_results.sort(key=lambda r: r["score"], reverse=True)
    return MediaSearchResponse(results=all_results[: payload.top_k])
