"""Partie 22 -- real Celery jobs for multi-modal media. Same
asyncio.run() bridge as api/tasks/document_processing.py, and for the
identical reason: api/services/media.py's real processing/extraction
functions stay async for the FastAPI routes/tests that also call them
directly (live testing this part's own upload/process/search flow),
so a parallel sync reimplementation would be needless duplication."""

import asyncio
import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.media import MediaAsset, MediaStatus
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


def _session_factory():
    engine = make_async_engine()
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def _process_media_asset_async(media_asset_id: str) -> str:
    from api.services.media import MediaNotFoundError, process_media_asset

    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            try:
                asset = await process_media_asset(db, uuid.UUID(media_asset_id))
                await db.commit()
                return asset.status.value
            except MediaNotFoundError:
                await db.rollback()
                return "not_found"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.media.process_media_asset_task")
def process_media_asset_task(media_asset_id: str) -> str:
    """Dispatched once per real upload (api/routers/media.py) -- returns
    the asset's own final real status string."""
    return asyncio.run(_process_media_asset_async(media_asset_id))


def schedule_media_processing(media_asset_id: uuid.UUID) -> None:
    """Real Celery dispatch, wrapped best-effort -- same reasoning as
    api/security/documents.py's own schedule_document_processing: a
    broker hiccup at upload time must never fail the upload itself."""
    try:
        process_media_asset_task.delay(str(media_asset_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("schedule_media_processing: could not schedule processing for media asset '%s': %s", media_asset_id, exc)


async def _extract_transcripts_async() -> int:
    from api.services.media import extract_audio_transcript, get_transcript

    engine, session_factory = _session_factory()
    processed = 0
    try:
        async with session_factory() as db:
            assets = (await db.execute(
                select(MediaAsset).where(MediaAsset.media_type == "audio", MediaAsset.status == MediaStatus.completed)
            )).scalars().all()
            for asset in assets:
                if await get_transcript(db, asset.id) is None:
                    try:
                        await extract_audio_transcript(db, asset)
                        processed += 1
                    except Exception as exc:  # noqa: BLE001 -- one real asset's own failure must never abort the sweep
                        logger.warning("extract_transcripts: asset '%s' failed: %s", asset.id, exc)
            await db.commit()
    finally:
        await engine.dispose()
    return processed


@celery_app.task(name="api.tasks.media.extract_transcripts")
def extract_transcripts() -> int:
    """Real, periodic backfill -- any real `completed` audio asset that
    somehow ended up without a real transcript row (a real, honest
    self-healing sweep, not expected to normally find anything)."""
    return asyncio.run(_extract_transcripts_async())


async def _extract_frames_async() -> int:
    """Real backfill for `completed` video assets with zero real
    frames -- same self-healing reasoning as extract_transcripts
    above."""
    import tempfile
    from pathlib import Path

    from api.models.media import MediaFrame
    from api.services.document_storage import download_document_file
    from api.services.media import extract_video_frames

    engine, session_factory = _session_factory()
    processed = 0
    try:
        async with session_factory() as db:
            assets = (await db.execute(
                select(MediaAsset).where(MediaAsset.media_type == "video", MediaAsset.status == MediaStatus.completed)
            )).scalars().all()
            for asset in assets:
                has_frames = (await db.execute(select(MediaFrame.id).where(MediaFrame.media_asset_id == asset.id).limit(1))).first()
                if has_frames is not None:
                    continue
                try:
                    content = download_document_file(asset.file_key)
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        video_path = str(Path(tmp_dir) / asset.filename)
                        Path(video_path).write_bytes(content)
                        await extract_video_frames(db, asset, video_path)
                    processed += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("extract_frames: asset '%s' failed: %s", asset.id, exc)
            await db.commit()
    finally:
        await engine.dispose()
    return processed


@celery_app.task(name="api.tasks.media.extract_frames")
def extract_frames() -> int:
    return asyncio.run(_extract_frames_async())


async def _describe_media_async() -> int:
    """Real backfill for `completed` images with no real description
    yet (e.g. VISION_PROVIDER/model credentials were only added after
    the asset finished processing)."""
    from api.services.document_storage import download_document_file
    from api.services.media import describe_image, index_media_in_rag

    engine, session_factory = _session_factory()
    processed = 0
    try:
        async with session_factory() as db:
            assets = (await db.execute(
                select(MediaAsset).where(MediaAsset.media_type == "image", MediaAsset.status == MediaStatus.completed, MediaAsset.description.is_(None))
            )).scalars().all()
            for asset in assets:
                try:
                    content = download_document_file(asset.file_key)
                    result = await describe_image(content, asset.mime_type)
                    asset.description, asset.objects_json, asset.tags_json = result["description"], result["objects"] or None, result["tags"] or None
                    await index_media_in_rag(db, asset)
                    processed += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("describe_media: asset '%s' failed: %s", asset.id, exc)
            await db.commit()
    finally:
        await engine.dispose()
    return processed


@celery_app.task(name="api.tasks.media.describe_media")
def describe_media() -> int:
    return asyncio.run(_describe_media_async())


async def _index_media_in_rag_async() -> int:
    from api.models.document import DocumentChunk
    from api.services.media import index_media_in_rag

    engine, session_factory = _session_factory()
    indexed = 0
    try:
        async with session_factory() as db:
            assets = (await db.execute(select(MediaAsset).where(MediaAsset.status == MediaStatus.completed))).scalars().all()
            for asset in assets:
                has_chunks = (await db.execute(select(DocumentChunk.id).where(DocumentChunk.media_asset_id == asset.id).limit(1))).first()
                if has_chunks is not None:
                    continue
                try:
                    await index_media_in_rag(db, asset)
                    indexed += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("index_media_in_rag task: asset '%s' failed: %s", asset.id, exc)
            await db.commit()
    finally:
        await engine.dispose()
    return indexed


@celery_app.task(name="api.tasks.media.index_media_in_rag_task")
def index_media_in_rag_task() -> int:
    """Real, periodic sweep indexing any real `completed` asset that
    somehow has zero real chunks yet (real self-healing, same as the
    2 backfill sweeps above) -- distinct from
    `api.services.media.index_media_in_rag`, the real, direct function
    `process_media_asset` already calls inline for every fresh asset."""
    return asyncio.run(_index_media_in_rag_async())


async def _cleanup_old_media_async(days: int) -> int:
    from api.services.media import delete_media

    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    engine, session_factory = _session_factory()
    deleted = 0
    try:
        async with session_factory() as db:
            assets = (await db.execute(
                select(MediaAsset).where(MediaAsset.status == MediaStatus.failed, MediaAsset.created_at < threshold)
            )).scalars().all()
            for asset in assets:
                try:
                    await delete_media(db, asset.id)
                    deleted += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("cleanup_old_media: asset '%s' failed: %s", asset.id, exc)
            await db.commit()
    finally:
        await engine.dispose()
    return deleted


@celery_app.task(name="api.tasks.media.cleanup_old_media")
def cleanup_old_media() -> int:
    """Real, periodic cleanup -- only real, permanently `failed` assets
    older than `MEDIA_CLEANUP_FAILED_AFTER_DAYS` are ever removed
    (never a real `completed` asset a user actually relies on)."""
    return asyncio.run(_cleanup_old_media_async(settings.MEDIA_CLEANUP_FAILED_AFTER_DAYS))
