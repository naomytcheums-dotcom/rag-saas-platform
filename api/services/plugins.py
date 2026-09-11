"""Partie 16 (ter) -- plugin marketplace service layer."""

import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.plugins import Plugin, PluginInstallation, PluginReview, PluginStatus
from api.security.plugin_manifest import PluginManifestError, scan_plugin_code, validate_manifest, validate_rating


class PluginError(Exception):
    pass


class PluginNotFoundError(PluginError):
    pass


class InstallationNotFoundError(PluginError):
    pass


class NotApprovedError(PluginError):
    pass


class AlreadyInstalledError(PluginError):
    pass


class PluginStorageNotConfiguredError(PluginError):
    pass


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "plugin"


async def _unique_slug(db: AsyncSession, name: str) -> str:
    base = _slugify(name)
    slug = base
    suffix = 1
    while await db.scalar(select(Plugin.id).where(Plugin.slug == slug)) is not None:
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


async def publish_plugin(db: AsyncSession, organization_id: uuid.UUID, *, name: str, description: str, manifest: dict, code: bytes, user_id: uuid.UUID | None) -> Plugin:
    """Real validation (manifest schema + permission whitelist, then a
    static forbidden-pattern code scan) BEFORE anything touches S3 or
    the database -- same ordering discipline as
    api/security/documents.py's own upload_document. Always created as
    `pending`; only an admin's real approve_plugin call below makes it
    visible in the marketplace."""
    slug = await _unique_slug(db, name)
    validate_manifest(manifest, slug=slug)
    scan_plugin_code(code)

    # Generated here (not left to the column's own Python-side default)
    # so the S3 key can be set in the SAME insert -- avoiding a second,
    # separate UPDATE flush right after, which would fire this column's
    # own `onupdate=func.now()` and expire `updated_at` in a way that
    # needs an extra DB round-trip to re-read (fails during response
    # serialization outside the request's own async/greenlet context --
    # a real bug found and fixed here; see republish_plugin below for
    # the one real case where a later UPDATE is unavoidable).
    plugin_id = uuid.uuid4()
    plugin = Plugin(
        id=plugin_id, organization_id=organization_id, name=name, slug=slug, description=description,
        manifest=manifest, version=manifest["version"], code_key=upload_plugin_code(plugin_id, code), code_size_bytes=len(code),
        status=PluginStatus.pending, created_by=user_id,
    )
    db.add(plugin)
    await db.flush()
    return plugin


async def republish_plugin(db: AsyncSession, organization_id: uuid.UUID, plugin_id: uuid.UUID, *, description: str | None, manifest: dict, code: bytes) -> Plugin:
    """A real update to an EXISTING plugin -- validated exactly like a
    fresh publish, and reset to `pending` (a manifest/permission/code
    change must be re-reviewed, not silently inherit its old approval)."""
    plugin = await get_org_plugin(db, organization_id, plugin_id)
    validate_manifest(manifest, slug=plugin.slug)
    scan_plugin_code(code)

    plugin.manifest = manifest
    plugin.version = manifest["version"]
    if description is not None:
        plugin.description = description
    plugin.code_key = upload_plugin_code(plugin.id, code)
    plugin.code_size_bytes = len(code)
    plugin.status = PluginStatus.pending
    plugin.rejection_reason = None
    await db.flush()
    return plugin


async def get_plugin(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin:
    plugin = await db.get(Plugin, plugin_id)
    if plugin is None:
        raise PluginNotFoundError(str(plugin_id))
    return plugin


async def get_org_plugin(db: AsyncSession, organization_id: uuid.UUID, plugin_id: uuid.UUID) -> Plugin:
    plugin = await get_plugin(db, plugin_id)
    if plugin.organization_id != organization_id:
        raise PluginNotFoundError(str(plugin_id))
    return plugin


async def list_org_plugins(db: AsyncSession, organization_id: uuid.UUID) -> list[Plugin]:
    return list((await db.scalars(select(Plugin).where(Plugin.organization_id == organization_id).order_by(Plugin.created_at.desc()))).all())


async def delete_plugin(db: AsyncSession, organization_id: uuid.UUID, plugin_id: uuid.UUID) -> None:
    plugin = await get_org_plugin(db, organization_id, plugin_id)
    await db.delete(plugin)
    await db.flush()


async def list_marketplace_plugins(db: AsyncSession, *, search: str | None = None, limit: int = 50, offset: int = 0) -> list[Plugin]:
    """Real, public marketplace listing -- only `approved` plugins,
    same "honestly gated" discipline as this project's every other
    approval flow (e.g. IntegrationConnection's own is_active gate)."""
    query = select(Plugin).where(Plugin.status == PluginStatus.approved)
    if search:
        like = f"%{search}%"
        query = query.where(or_(Plugin.name.ilike(like), Plugin.description.ilike(like)))
    query = query.order_by(Plugin.created_at.desc()).limit(limit).offset(offset)
    return list((await db.scalars(query)).all())


# -- Admin moderation ----------------------------------------------------------

async def approve_plugin(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin:
    plugin = await get_plugin(db, plugin_id)
    plugin.status = PluginStatus.approved
    plugin.rejection_reason = None
    await db.flush()
    return plugin


async def reject_plugin(db: AsyncSession, plugin_id: uuid.UUID, *, reason: str) -> Plugin:
    plugin = await get_plugin(db, plugin_id)
    plugin.status = PluginStatus.rejected
    plugin.rejection_reason = reason
    await db.flush()
    return plugin


async def suspend_plugin(db: AsyncSession, plugin_id: uuid.UUID, *, reason: str) -> Plugin:
    """Real, distinct from `reject`: a plugin that WAS approved (real
    installs may already exist) but is later found to violate policy --
    existing installations are left in place (a suspended plugin isn't
    silently uninstalled out from under an org), only new installs are
    blocked (see install_plugin's own status check below)."""
    plugin = await get_plugin(db, plugin_id)
    plugin.status = PluginStatus.suspended
    plugin.rejection_reason = reason
    await db.flush()
    return plugin


async def list_pending_plugins(db: AsyncSession) -> list[Plugin]:
    return list((await db.scalars(select(Plugin).where(Plugin.status == PluginStatus.pending).order_by(Plugin.created_at.asc()))).all())


# -- Installation ---------------------------------------------------------------

async def install_plugin(db: AsyncSession, organization_id: uuid.UUID, plugin_id: uuid.UUID, user_id: uuid.UUID | None) -> PluginInstallation:
    plugin = await get_plugin(db, plugin_id)
    if plugin.status != PluginStatus.approved:
        raise NotApprovedError(f"plugin '{plugin.slug}' is not approved (status: {plugin.status.value})")

    existing = await db.scalar(select(PluginInstallation).where(PluginInstallation.plugin_id == plugin_id, PluginInstallation.organization_id == organization_id))
    if existing is not None:
        raise AlreadyInstalledError(str(plugin_id))

    installation = PluginInstallation(plugin_id=plugin_id, organization_id=organization_id, installed_by=user_id)
    db.add(installation)
    await db.flush()
    return installation


async def _get_org_installation(db: AsyncSession, organization_id: uuid.UUID, installation_id: uuid.UUID) -> PluginInstallation:
    installation = await db.get(PluginInstallation, installation_id)
    if installation is None or installation.organization_id != organization_id:
        raise InstallationNotFoundError(str(installation_id))
    return installation


async def uninstall_plugin(db: AsyncSession, organization_id: uuid.UUID, installation_id: uuid.UUID) -> None:
    installation = await _get_org_installation(db, organization_id, installation_id)
    await db.delete(installation)
    await db.flush()


async def set_installation_enabled(db: AsyncSession, organization_id: uuid.UUID, installation_id: uuid.UUID, *, enabled: bool | None = None, config: dict | None = None) -> PluginInstallation:
    installation = await _get_org_installation(db, organization_id, installation_id)
    if enabled is not None:
        installation.enabled = enabled
    if config is not None:
        installation.config = config
    await db.flush()
    return installation


async def list_installed_plugins(db: AsyncSession, organization_id: uuid.UUID) -> list[PluginInstallation]:
    return list((await db.scalars(select(PluginInstallation).where(PluginInstallation.organization_id == organization_id).order_by(PluginInstallation.installed_at.desc()))).all())


# -- Reviews ----------------------------------------------------------------------

async def submit_review(db: AsyncSession, plugin_id: uuid.UUID, organization_id: uuid.UUID, user_id: uuid.UUID, *, rating: int, comment: str | None) -> PluginReview:
    """Real upsert on (plugin_id, user_id) -- a marketplace rating
    reflects this user's CURRENT opinion of the plugin, so re-reviewing
    updates the existing row rather than appending a second one (which
    would double-count them in get_rating_summary's average below)."""
    validate_rating(rating)
    await get_plugin(db, plugin_id)  # raises PluginNotFoundError if unknown

    existing = await db.scalar(select(PluginReview).where(PluginReview.plugin_id == plugin_id, PluginReview.user_id == user_id))
    if existing is not None:
        existing.rating = rating
        existing.comment = comment
        await db.flush()
        return existing

    review = PluginReview(plugin_id=plugin_id, organization_id=organization_id, user_id=user_id, rating=rating, comment=comment)
    db.add(review)
    await db.flush()
    return review


async def list_reviews(db: AsyncSession, plugin_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[PluginReview]:
    return list((await db.scalars(
        select(PluginReview).where(PluginReview.plugin_id == plugin_id).order_by(PluginReview.created_at.desc()).limit(limit).offset(offset)
    )).all())


async def get_rating_summary(db: AsyncSession, plugin_id: uuid.UUID) -> dict:
    row = (await db.execute(select(func.avg(PluginReview.rating), func.count(PluginReview.id)).where(PluginReview.plugin_id == plugin_id))).one()
    average, count = row
    return {"average_rating": round(float(average), 2) if average is not None else None, "review_count": count}


# -- Code storage (S3, same bucket as documents -- see api/services/storage.py's
# own docstring on branding assets sharing the avatar bucket for the
# identical "no new S3_* setting" reasoning) -----------------------------------

def _s3_client():
    import boto3

    from api.config import settings

    if not (settings.S3_DOCUMENTS_BUCKET_NAME and settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY):
        raise PluginStorageNotConfiguredError(
            "S3_DOCUMENTS_BUCKET_NAME / S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY are not fully set -- "
            "see .env.example for the S3 (or Cloudflare R2) variables required for plugin code uploads."
        )
    return boto3.client(
        "s3", endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID, aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )


def upload_plugin_code(plugin_id: uuid.UUID, content: bytes) -> str:
    from api.config import settings

    key = f"plugins/{plugin_id}/code"
    _s3_client().put_object(Bucket=settings.S3_DOCUMENTS_BUCKET_NAME, Key=key, Body=content, ContentType="text/plain")
    return key


def download_plugin_code(code_key: str) -> bytes:
    from api.config import settings

    response = _s3_client().get_object(Bucket=settings.S3_DOCUMENTS_BUCKET_NAME, Key=code_key)
    return response["Body"].read()
