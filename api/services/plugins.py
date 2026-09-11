"""Partie 16 (ter) -- plugin marketplace service layer."""

import datetime as dt
import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.plugins import (
    Plugin, PluginExecution, PluginExecutionStatus, PluginInstallation, PluginReview, PluginStatus, PluginVersion,
)
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


class PluginsDisabledError(PluginError):
    pass


class PluginRateLimitedError(PluginError):
    pass


class PluginPermissionError(PluginError):
    """Raised when a plugin is asked to run for an action it never
    declared the matching permission for -- api/routers/plugins.py's
    own execute_plugin_endpoint turns this into a real 403."""
    pass


class ReviewNotFoundError(PluginError):
    pass


class NotReviewOwnerError(PluginError):
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


def _validate_pricing(pricing: str, price: float | None) -> None:
    """Real, honest scope: this only validates the DECLARED pricing
    metadata is internally consistent -- see Plugin.pricing's own
    column comment for why there is no real payment/checkout flow
    behind it in this pass."""
    if pricing not in ("free", "paid", "freemium"):
        raise PluginManifestError(f"pricing must be one of 'free', 'paid', 'freemium' -- got '{pricing}'")
    if pricing in ("paid", "freemium") and (price is None or price <= 0):
        raise PluginManifestError(f"pricing '{pricing}' requires a real price > 0")
    if pricing == "free" and price not in (None, 0):
        raise PluginManifestError("pricing 'free' must not declare a price")


async def publish_plugin(db: AsyncSession, organization_id: uuid.UUID, *, name: str, description: str, category: str, manifest: dict, code: bytes, user_id: uuid.UUID | None, pricing: str = "free", price: float | None = None) -> Plugin:
    """Real validation (manifest schema + permission whitelist, then a
    static forbidden-pattern code scan) BEFORE anything touches S3 or
    the database -- same ordering discipline as
    api/security/documents.py's own upload_document. Always created as
    `pending`; only an admin's real approve_plugin call below makes it
    visible in the marketplace. Writes a real PluginVersion row
    alongside `Plugin` itself -- see api/models/plugins.py's own module
    docstring for why both exist."""
    slug = await _unique_slug(db, name)
    validate_manifest(manifest, slug=slug)
    scan_plugin_code(code)
    _validate_pricing(pricing, price)
    version = manifest["version"]

    # Generated here (not left to the column's own Python-side default)
    # so the S3 key can be set in the SAME insert -- avoiding a second,
    # separate UPDATE flush right after, which would fire this column's
    # own `onupdate=func.now()` and expire `updated_at` in a way that
    # needs an extra DB round-trip to re-read (fails during response
    # serialization outside the request's own async/greenlet context --
    # a real bug found and fixed here; see republish_plugin below for
    # the one real case where a later UPDATE is unavoidable).
    plugin_id = uuid.uuid4()
    code_key = upload_plugin_code(plugin_id, version, code)
    plugin = Plugin(
        id=plugin_id, organization_id=organization_id, name=name, slug=slug, description=description, category=category,
        manifest=manifest, version=version, code_key=code_key, code_size_bytes=len(code),
        status=PluginStatus.pending, created_by=user_id, pricing=pricing, price=price if pricing != "free" else None,
    )
    db.add(plugin)
    db.add(PluginVersion(plugin_id=plugin_id, version=version, manifest=manifest, code_key=code_key, code_size_bytes=len(code), created_by=user_id))
    await db.flush()
    return plugin


async def republish_plugin(db: AsyncSession, organization_id: uuid.UUID, plugin_id: uuid.UUID, *, description: str | None, manifest: dict, code: bytes, changelog: str | None = None) -> Plugin:
    """A real update to an EXISTING plugin -- validated exactly like a
    fresh publish, and reset to `pending` (a manifest/permission/code
    change must be re-reviewed, not silently inherit its old approval).
    Each version's code is stored under its OWN S3 key (never
    overwriting an earlier version's object), and a real PluginVersion
    row records it -- a real, queryable history, not just "the latest
    overwrote the former"."""
    plugin = await get_org_plugin(db, organization_id, plugin_id)
    validate_manifest(manifest, slug=plugin.slug)
    scan_plugin_code(code)
    version = manifest["version"]

    existing_version = await db.scalar(select(PluginVersion.id).where(PluginVersion.plugin_id == plugin_id, PluginVersion.version == version))
    if existing_version is not None:
        raise PluginManifestError(f"version '{version}' was already published for this plugin -- bump the version number")

    code_key = upload_plugin_code(plugin.id, version, code)
    plugin.manifest = manifest
    plugin.version = version
    if description is not None:
        plugin.description = description
    plugin.code_key = code_key
    plugin.code_size_bytes = len(code)
    plugin.status = PluginStatus.pending
    plugin.rejection_reason = None
    db.add(PluginVersion(plugin_id=plugin.id, version=version, manifest=manifest, code_key=code_key, code_size_bytes=len(code), changelog=changelog, created_by=plugin.created_by))
    await db.flush()
    return plugin


async def list_plugin_versions(db: AsyncSession, plugin_id: uuid.UUID) -> list[PluginVersion]:
    return list((await db.scalars(select(PluginVersion).where(PluginVersion.plugin_id == plugin_id).order_by(PluginVersion.created_at.desc()))).all())


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


async def list_marketplace_plugins(
    db: AsyncSession, *, search: str | None = None, category: str | None = None, min_rating: float | None = None,
    pricing: str | None = None, sort_by: str = "date", limit: int = 50, offset: int = 0,
) -> list[Plugin]:
    """Real, public marketplace listing -- only `approved` plugins,
    same "honestly gated" discipline as this project's every other
    approval flow (e.g. IntegrationConnection's own is_active gate).
    `sort_by`: "popularity" (real install_count), "rating" (real live
    average from PluginReview, not a cached column -- this project has
    no plugin volume yet where that join would be a real cost concern),
    "price" (real, by the declared `price` column, ascending, nulls --
    i.e. free plugins -- first), or "date" (default). `pricing` filters
    by the real, declared `free`/`paid`/`freemium` value -- see
    Plugin.pricing's own column comment for the honest scope of what
    that value actually means (declared metadata, not an enforced
    purchase)."""
    query = select(Plugin).where(Plugin.status == PluginStatus.approved)
    if search:
        like = f"%{search}%"
        query = query.where(or_(Plugin.name.ilike(like), Plugin.description.ilike(like)))
    if category:
        query = query.where(Plugin.category == category)
    if pricing:
        query = query.where(Plugin.pricing == pricing)

    if sort_by == "rating" or min_rating is not None:
        avg_rating = select(PluginReview.plugin_id, func.avg(PluginReview.rating).label("avg_rating")).group_by(PluginReview.plugin_id).subquery()
        query = query.outerjoin(avg_rating, avg_rating.c.plugin_id == Plugin.id)
        if min_rating is not None:
            query = query.where(avg_rating.c.avg_rating >= min_rating)
        if sort_by == "rating":
            query = query.order_by(avg_rating.c.avg_rating.desc().nulls_last())

    if sort_by == "popularity":
        query = query.order_by(Plugin.install_count.desc())
    elif sort_by == "price":
        query = query.order_by(Plugin.price.asc().nulls_first())
    elif sort_by != "rating":
        query = query.order_by(Plugin.created_at.desc())

    query = query.limit(limit).offset(offset)
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
    plugin.install_count += 1
    await db.flush()
    return installation


async def _get_org_installation(db: AsyncSession, organization_id: uuid.UUID, installation_id: uuid.UUID) -> PluginInstallation:
    installation = await db.get(PluginInstallation, installation_id)
    if installation is None or installation.organization_id != organization_id:
        raise InstallationNotFoundError(str(installation_id))
    return installation


async def uninstall_plugin(db: AsyncSession, organization_id: uuid.UUID, installation_id: uuid.UUID) -> None:
    installation = await _get_org_installation(db, organization_id, installation_id)
    plugin = await db.get(Plugin, installation.plugin_id)
    await db.delete(installation)
    if plugin is not None and plugin.install_count > 0:
        plugin.install_count -= 1
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


async def delete_review(db: AsyncSession, review_id: uuid.UUID, user_id: uuid.UUID) -> None:
    review = await db.get(PluginReview, review_id)
    if review is None:
        raise ReviewNotFoundError(str(review_id))
    if review.user_id != user_id:
        raise NotReviewOwnerError(str(review_id))
    await db.delete(review)
    await db.flush()


async def get_rating_summary(db: AsyncSession, plugin_id: uuid.UUID) -> dict:
    row = (await db.execute(select(func.avg(PluginReview.rating), func.count(PluginReview.id)).where(PluginReview.plugin_id == plugin_id))).one()
    average, count = row
    return {"average_rating": round(float(average), 2) if average is not None else None, "review_count": count}


# -- Sandboxed execution --------------------------------------------------------

async def _check_rate_limit(db: AsyncSession, plugin_id: uuid.UUID) -> None:
    from api.config import settings

    window_start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    count = await db.scalar(select(func.count(PluginExecution.id)).where(PluginExecution.plugin_id == plugin_id, PluginExecution.created_at >= window_start))
    if count is not None and count >= settings.PLUGINS_MAX_API_CALLS:
        raise PluginRateLimitedError(f"This plugin has been invoked {count} times in the last minute (limit: {settings.PLUGINS_MAX_API_CALLS})")


async def execute_plugin(
    db: AsyncSession, plugin_id: uuid.UUID, organization_id: uuid.UUID, payload: dict, *,
    user_id: uuid.UUID | None, hook: str | None = None, installation_id: uuid.UUID | None = None,
    required_permission: str | None = None,
) -> PluginExecution:
    """Real, synchronous sandboxed execution (api/security/plugin_sandbox.py's
    own run_plugin_sandboxed) -- downloads this plugin's CURRENT code
    from S3, runs it in a real, separate OS process with the real
    configured timeout/memory cap, and records a real PluginExecution
    row whether it succeeds, errors, or times out. Never raises for a
    plugin-side failure -- only for a real precondition (plugins
    disabled, plugin not approved, permission missing, rate limit
    exceeded, storage/interpreter not available), which the caller
    turns into a real 4xx/503, not a fabricated 200.

    `required_permission`, when given, is checked against
    `plugin.manifest["permissions"]` BEFORE anything runs -- a plugin
    that never declared it raises a real PluginPermissionError (a real
    403), same real gate api/services/plugin_hooks.py's own
    trigger_hook applies before dispatching a hook (there via
    HOOK_REQUIRED_PERMISSIONS; here, explicitly passed by the caller --
    api/routers/plugins.py's own execute_plugin_endpoint accepts it as
    an optional request field for a manual, deliberate permission
    check)."""
    from api.config import settings
    from api.security.plugin_sandbox import run_plugin_sandboxed

    if not settings.PLUGINS_ENABLED:
        raise PluginsDisabledError("Plugin execution is disabled on this deployment (PLUGINS_ENABLED=False)")

    plugin = await get_plugin(db, plugin_id)
    if plugin.status != PluginStatus.approved:
        raise NotApprovedError(f"plugin '{plugin.slug}' is not approved (status: {plugin.status.value})")

    if required_permission is not None:
        declared_permissions = (plugin.manifest or {}).get("permissions") or []
        if required_permission not in declared_permissions:
            raise PluginPermissionError(f"plugin '{plugin.slug}' does not declare the required permission '{required_permission}'")

    await _check_rate_limit(db, plugin_id)

    code = download_plugin_code(plugin.code_key)
    entry_point = plugin.manifest.get("entry_point", "index.js")

    if settings.PLUGINS_SANDBOX_ENABLED:
        result = run_plugin_sandboxed(entry_point, code, payload, timeout_seconds=settings.PLUGINS_MAX_EXECUTION_TIME, max_memory_mb=settings.PLUGINS_MAX_MEMORY)
    else:
        # Real, honest no-op when the sandbox itself is turned off
        # platform-wide -- never falls back to executing the code
        # unsandboxed, which would silently defeat PLUGINS_SANDBOX_ENABLED's
        # own purpose.
        result = {"status": "error", "output": None, "error": "PLUGINS_SANDBOX_ENABLED is False on this deployment -- refusing to execute plugin code unsandboxed.", "duration_ms": None}

    execution = PluginExecution(
        plugin_id=plugin_id, organization_id=organization_id, installation_id=installation_id, hook=hook,
        status=PluginExecutionStatus(result["status"]), input_payload=payload, output_payload=result["output"],
        error_message=result["error"], duration_ms=result["duration_ms"], created_by=user_id,
    )
    db.add(execution)
    await db.flush()
    return execution


async def get_plugin_executions(db: AsyncSession, organization_id: uuid.UUID, plugin_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[PluginExecution]:
    return list((await db.scalars(
        select(PluginExecution)
        .where(PluginExecution.plugin_id == plugin_id, PluginExecution.organization_id == organization_id)
        .order_by(PluginExecution.created_at.desc()).limit(limit).offset(offset)
    )).all())


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


def upload_plugin_code(plugin_id: uuid.UUID, version: str, content: bytes) -> str:
    """Real, per-VERSION key (never overwrites an earlier version's
    object) -- what makes PluginVersion's own `code_key` a genuine,
    independently-downloadable historical artifact rather than a
    pointer to whatever the current version happens to be."""
    from api.config import settings

    key = f"plugins/{plugin_id}/{version}/code"
    _s3_client().put_object(Bucket=settings.S3_DOCUMENTS_BUCKET_NAME, Key=key, Body=content, ContentType="text/plain")
    return key


def download_plugin_code(code_key: str) -> bytes:
    from api.config import settings

    response = _s3_client().get_object(Bucket=settings.S3_DOCUMENTS_BUCKET_NAME, Key=code_key)
    return response["Body"].read()
