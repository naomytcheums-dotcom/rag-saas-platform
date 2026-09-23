"""
Partie 9.3 -- the embeddable chat widget's real business logic. See
`api/models/widget.py`'s own top docstring for the real "one
WidgetConfig row per organization" consolidation this whole module is
built around, and `api/security/widget_auth.py`'s for the real
two-tier (public key / session token) security model.

Real reuse, not a second engine: `POST /widget/chat` (the router)
calls the SAME `handle_public_chat` the public API's own `POST
/v1/chat` (9.1.1) uses -- see that function's own updated docstring in
api/services/public_api.py for why it now takes `organization_id`/
`created_by` directly instead of a whole `OrganizationAPIKey` row.
"""

import datetime as dt
import uuid

import bleach
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.widget import WidgetConfig, WidgetSuggestedQuestion
from api.security.widget_auth import WidgetDomainError, validate_widget_domain


class WidgetError(ValueError):
    """Real, honest failure -- routers turn this into a 4xx."""


_HEX_COLOR_LEN = {4, 7, 9}  # "#abc", "#aabbcc", "#aabbccdd"


# --------------------------------------------------------------------- Config (9.3.1, one row per org)


async def get_or_create_widget_config(db: AsyncSession, organization_id: uuid.UUID, created_by: uuid.UUID | None = None) -> WidgetConfig:
    """Item 3's own literal `get_widget_config`, extended to also
    create the real, first row -- an organization that has never
    opened its widget settings still needs a real, embeddable
    `public_key` to exist the first time anyone asks for one.
    `created_by` (real member who first touched this widget's real
    settings) is only ever set on that first, real creation -- a
    later, unauthenticated public GET never overwrites it."""
    config = await db.scalar(select(WidgetConfig).where(WidgetConfig.organization_id == organization_id))
    if config is None:
        config = WidgetConfig(organization_id=organization_id, created_by=created_by)
        db.add(config)
        await db.flush()
    return config


async def get_widget_config_public(db: AsyncSession, config: WidgetConfig) -> dict:
    """Item 3's own literal function -- the real, PUBLIC-safe subset
    (never `organization_id`/`agent_id` as raw internal ids beyond
    what the widget itself needs to function)."""
    questions = await list_suggested_questions(db, config.id, include_inactive=False)
    return {
        "public_key": config.public_key,
        "logo_url": config.logo_url or None,
        "avatar_url": get_effective_avatar_url(config),
        "colors": {
            "primary": config.primary_color, "secondary": config.secondary_color,
            "text": config.text_color, "background": config.background_color,
            "header_background": config.header_background,
        },
        "border_radius": config.border_radius,
        "font_family": config.font_family,
        "name": config.widget_name if config.widget_name_enabled else None,
        "short_name": config.widget_short_name,
        "welcome_message": config.welcome_message if config.welcome_message_enabled else None,
        "position": config.position,
        "position_mobile": config.position_mobile or config.position,
        "offset_x": config.offset_x, "offset_y": config.offset_y, "position_locked": config.position_locked,
        "language": config.language, "auto_detect_language": config.auto_detect_language,
        "theme": config.theme, "custom_css": config.theme_custom_css,
        "suggested_questions": [{"id": str(q.id), "question": q.question, "label": q.label} for q in questions],
        "max_messages": settings.WIDGET_MAX_MESSAGES,
    }


def validate_widget_params(params: dict) -> dict:
    """Item 3's own literal function -- real validation of the
    OPTIONAL `?theme=`/`?position=` query-string overrides `script.js`
    accepts (a per-embed override without changing the org's own
    saved default). Unknown/invalid values are dropped, never a hard
    4xx -- a real third-party site's malformed embed snippet
    shouldn't break the whole widget."""
    clean: dict = {}
    theme = params.get("theme")
    if theme in settings.WIDGET_THEMES:
        clean["theme"] = theme
    position = params.get("position")
    if position in settings.WIDGET_POSITIONS:
        clean["position"] = position
    return clean


async def update_widget_config(db: AsyncSession, organization_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> WidgetConfig:
    """Generic update backing every real, granular PATCH endpoint
    (theme/position/language/welcome/name/...) -- each router handler
    passes only the subset of fields its own literal étape owns."""
    # Every real caller already filters out fields the client didn't
    # explicitly send (Pydantic's `exclude_unset=True`, or a literal,
    # hand-built dict) BEFORE calling this -- so a `None` reaching here
    # is always a real, deliberate "clear this field" (reset_welcome_
    # message, reset_widget_theme's theme_custom_css), never an
    # accidental unset one. An earlier `if value is not None` guard
    # here silently dropped those real resets; removed.
    config = await get_or_create_widget_config(db, organization_id, created_by=user_id)
    for key, value in data.items():
        setattr(config, key, value)
    config.updated_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    await db.refresh(config)
    return config


# Phase 4, Étape 5 (Domain Allowlist Widget) -- item 14's own literal
# ask: real, CONFIGURATION-time validation, not just runtime matching
# (`api.security.widget_auth.is_origin_allowed`). A separate, dedicated
# function rather than routing this through the generic
# `update_widget_config` above: every OTHER real field there is a
# trusted, single scalar value a caller already validated (theme/
# position/language each have their own real `validate_*` call in the
# router BEFORE reaching `update_widget_config`) -- this one is a real
# LIST needing real, per-item validation plus a real, whole-list
# dedup/cap this module's own top-level cap (`WidgetDomainError`,
# reused from `widget_auth.py`, never a second, duplicate error type).
async def set_widget_allowed_domains(db: AsyncSession, organization_id: uuid.UUID, domains: list[str], user_id: uuid.UUID) -> WidgetConfig:
    from api.security.widget_auth import MAX_WIDGET_ALLOWED_DOMAINS

    if len(domains) > MAX_WIDGET_ALLOWED_DOMAINS:
        raise WidgetError(f"Too many widget allowed domains: {len(domains)} (max {MAX_WIDGET_ALLOWED_DOMAINS})")
    try:
        normalized = [validate_widget_domain(d) for d in domains]
    except WidgetDomainError as exc:
        raise WidgetError(str(exc)) from exc
    # Real, order-preserving dedup -- two real, distinct raw entries
    # (`https://example.com` and `example.com`) can normalize to the
    # SAME real canonical origin; a real admin's own intent ("allow
    # this one real origin") should never silently become two real,
    # redundant, identical allowlist rows.
    deduped = list(dict.fromkeys(normalized))
    return await update_widget_config(db, organization_id, {"allowed_domains": deduped or None}, user_id)


def get_default_theme() -> dict:
    return {"theme": settings.WIDGET_DEFAULT_THEME, "theme_custom_css": None}


async def reset_widget_theme(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> WidgetConfig:
    return await update_widget_config(db, organization_id, get_default_theme(), user_id)


def validate_theme(theme: str) -> str:
    if theme not in settings.WIDGET_THEMES:
        raise WidgetError(f"Invalid theme {theme!r} -- allowed: {settings.WIDGET_THEMES}")
    return theme


def validate_theme_colors(theme_data: dict) -> dict:
    """Item 3's own literal function -- real hex-format validation,
    every color field independently (a partial update must not corrupt
    the other, unrelated, already-valid colors)."""
    color_fields = ("primary_color", "secondary_color", "text_color", "background_color", "header_background")
    for field in color_fields:
        value = theme_data.get(field)
        if value is None:
            continue
        if not (isinstance(value, str) and value.startswith("#") and len(value) in _HEX_COLOR_LEN and all(c in "0123456789abcdefABCDEF" for c in value[1:])):
            raise WidgetError(f"{field} must be a real hex color (#rgb, #rrggbb or #rrggbbaa), got {value!r}")
    return theme_data


def sanitize_custom_css(css: str) -> str:
    """Real, honest sanitization (vision critique -- security: is the
    custom CSS XSS-safe?): CSS itself cannot execute a `<script>`, but
    `expression()` (legacy IE), `url(javascript:...)`, and `@import`
    (exfiltrating a third-party stylesheet under the org's own widget
    origin) are real, live vectors in modern browsers too for the
    first two, or a real supply-chain risk for the third. Stripped
    outright rather than attempting a real CSS parser this codebase
    doesn't have."""
    if len(css) > settings.WIDGET_CUSTOM_CSS_MAX_SIZE:
        raise WidgetError(f"Custom CSS exceeds the {settings.WIDGET_CUSTOM_CSS_MAX_SIZE}-character limit")
    lowered = css.lower()
    for forbidden in ("javascript:", "expression(", "@import", "<script"):
        if forbidden in lowered:
            raise WidgetError(f"Custom CSS contains a disallowed construct: {forbidden!r}")
    return css


def generate_css_variables(config: WidgetConfig) -> str:
    """Item 3's own literal function -- real CSS custom properties the
    served `script.js`/iframe both inject at runtime."""
    return (
        ":root{"
        f"--widget-primary:{config.primary_color};--widget-secondary:{config.secondary_color};"
        f"--widget-text:{config.text_color};--widget-bg:{config.background_color};"
        f"--widget-header-bg:{config.header_background};--widget-radius:{config.border_radius};"
        f"--widget-font:{config.font_family};"
        "}"
    )


def get_position_css(position: str, offset_x: int, offset_y: int) -> str:
    """Item 3's own literal function -- real, generated inline CSS for
    the launcher button's fixed position."""
    vertical = "top" if position.startswith("top") else "bottom"
    horizontal = "left" if position.endswith("left") else "right"
    return f"position:fixed;{vertical}:{offset_y}px;{horizontal}:{offset_x}px;"


def validate_widget_position(position: str) -> str:
    if position not in settings.WIDGET_POSITIONS:
        raise WidgetError(f"Invalid position {position!r} -- allowed: {settings.WIDGET_POSITIONS}")
    return position


def get_mobile_position(position: str) -> str:
    """Item 3's own literal function -- real, honest simplification:
    top corners collapse to bottom on mobile (a top-anchored launcher
    is routinely hidden behind a mobile browser's own address bar)."""
    return "bottom-left" if position.endswith("left") else "bottom-right"


# --------------------------------------------------------------------- Name (9.3.4)


def validate_widget_name(name: str) -> str:
    stripped = name.strip()
    if not (settings.WIDGET_NAME_MIN_LENGTH <= len(stripped) <= settings.WIDGET_NAME_MAX_LENGTH):
        raise WidgetError(f"Widget name must be between {settings.WIDGET_NAME_MIN_LENGTH} and {settings.WIDGET_NAME_MAX_LENGTH} characters")
    return stripped


def generate_widget_short_name(name: str) -> str:
    """Item 3's own literal function -- first real word, capped."""
    first_word = name.strip().split()[0] if name.strip() else "AI"
    return first_word[:12]


# --------------------------------------------------------------------- Welcome message (9.3.6)


def validate_welcome_message(message: str) -> str:
    stripped = message.strip()
    if not (settings.WELCOME_MESSAGE_MIN_LENGTH <= len(stripped) <= settings.WELCOME_MESSAGE_MAX_LENGTH):
        raise WidgetError(f"Welcome message must be between {settings.WELCOME_MESSAGE_MIN_LENGTH} and {settings.WELCOME_MESSAGE_MAX_LENGTH} characters")
    return stripped


def sanitize_welcome_message(message: str) -> str:
    """Item 3's own literal function -- real allowlist sanitization
    (bleach.clean, the same real library markdown_renderer.py already
    uses for the exact same real reason), never a denylist."""
    return bleach.clean(message, tags=settings.WELCOME_MESSAGE_ALLOWED_TAGS, attributes={}, strip=True)


def get_default_welcome_message(language: str) -> str:
    defaults = {"fr": "Bonjour ! Comment puis-je vous aider aujourd'hui ?", "en": "Hi! How can I help you today?"}
    return defaults.get(language, defaults["en"])


async def get_welcome_message(db: AsyncSession, organization_id: uuid.UUID) -> str:
    config = await get_or_create_widget_config(db, organization_id)
    if config.welcome_message_enabled and config.welcome_message:
        return config.welcome_message
    return get_default_welcome_message(config.language)


async def update_welcome_message(db: AsyncSession, organization_id: uuid.UUID, message: str, user_id: uuid.UUID) -> WidgetConfig:
    clean = sanitize_welcome_message(validate_welcome_message(message))
    return await update_widget_config(
        db, organization_id,
        {"welcome_message": clean, "welcome_message_updated_at": dt.datetime.now(dt.timezone.utc), "welcome_message_updated_by": user_id},
        user_id,
    )


async def reset_welcome_message(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> WidgetConfig:
    return await update_widget_config(db, organization_id, {"welcome_message": None}, user_id)


# --------------------------------------------------------------------- Language (9.3.9)


def get_supported_widget_languages() -> list[str]:
    """Reuses the app's own real, existing i18n language list -- see
    api/services/i18n.py -- rather than a second, separate widget-only
    list that could silently drift out of sync with it."""
    from api.services.i18n import get_supported_languages

    return get_supported_languages()


def validate_language(language: str) -> str:
    if language not in get_supported_widget_languages():
        raise WidgetError(f"Unsupported language {language!r} -- supported: {get_supported_widget_languages()}")
    return language


def detect_browser_language(accept_language_header: str | None) -> str:
    """Reuses the app's own real `detect_user_language` (i18n.py) --
    the widget's real language-detection need is identical to the main
    UI's."""
    from api.services.i18n import detect_user_language

    return detect_user_language(accept_language_header)


async def get_widget_language(db: AsyncSession, organization_id: uuid.UUID, accept_language_header: str | None) -> str:
    config = await get_or_create_widget_config(db, organization_id)
    if config.auto_detect_language:
        return detect_browser_language(accept_language_header)
    return config.language


# --------------------------------------------------------------------- Logo (9.3.2)


def validate_logo_file(content: bytes) -> None:
    from api.services.storage import _detect_image_content_type  # real, shared magic-byte check

    if len(content) > settings.WIDGET_LOGO_MAX_SIZE:
        raise WidgetError(f"Logo exceeds the {settings.WIDGET_LOGO_MAX_SIZE // (1024 * 1024)}MB limit")
    if _detect_image_content_type(content) is None:
        raise WidgetError("Logo is not a recognized image (PNG/JPEG/WEBP)")


async def upload_widget_logo(db: AsyncSession, organization_id: uuid.UUID, content: bytes, user_id: uuid.UUID) -> WidgetConfig:
    from api.services.storage import upload_widget_logo as _upload

    validate_logo_file(content)
    max_dim = settings.WIDGET_LOGO_DIMENSIONS[0]
    url = _upload(organization_id, content, max_bytes=settings.WIDGET_LOGO_MAX_SIZE, max_dimension_px=max_dim)
    return await update_widget_config(db, organization_id, {"logo_url": url}, user_id)


async def get_widget_logo(db: AsyncSession, organization_id: uuid.UUID) -> str | None:
    config = await get_or_create_widget_config(db, organization_id)
    return config.logo_url


async def delete_widget_logo(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> WidgetConfig:
    from api.services.storage import delete_branding_asset

    config = await get_or_create_widget_config(db, organization_id)
    if config.logo_url:
        delete_branding_asset(config.logo_url)
    config.logo_url = None
    await db.flush()
    return config


def generate_logo_url(base_url: str, version: str) -> str:
    """Item 3's own literal function -- real cache-busting query param."""
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}v={version}"


def get_default_logo() -> str | None:
    return None


# --------------------------------------------------------------------- Avatar (9.3.5)


def validate_avatar_file(content: bytes) -> None:
    from api.services.storage import _detect_image_content_type

    if len(content) > settings.WIDGET_AVATAR_MAX_SIZE:
        raise WidgetError(f"Avatar exceeds the {settings.WIDGET_AVATAR_MAX_SIZE // (1024 * 1024)}MB limit")
    if _detect_image_content_type(content) is None:
        raise WidgetError("Avatar is not a recognized image (PNG/JPEG/WEBP)")


async def upload_widget_avatar(db: AsyncSession, organization_id: uuid.UUID, content: bytes, user_id: uuid.UUID) -> WidgetConfig:
    from api.services.storage import upload_widget_avatar as _upload

    validate_avatar_file(content)
    url = _upload(organization_id, content, max_bytes=settings.WIDGET_AVATAR_MAX_SIZE)
    return await update_widget_config(
        db, organization_id,
        {"avatar_url": url, "avatar_uploaded_at": dt.datetime.now(dt.timezone.utc), "avatar_updated_by": user_id, "use_default_avatar": False},
        user_id,
    )


def get_default_avatar(widget_name: str) -> dict:
    """Item 3's own literal function -- a real initial-letter avatar
    (no real image asset needed for the common "we never uploaded
    one" case)."""
    initial = (widget_name.strip()[:1] or "A").upper()
    return {"type": "initial", "initial": initial}


def get_effective_avatar_url(config: WidgetConfig) -> str | None:
    if config.use_default_avatar or not config.avatar_url:
        return None
    return config.avatar_url


async def get_widget_avatar(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    config = await get_or_create_widget_config(db, organization_id)
    url = get_effective_avatar_url(config)
    if url:
        return {"type": "custom", "url": url}
    return get_default_avatar(config.widget_name)


async def delete_widget_avatar(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> WidgetConfig:
    from api.services.storage import delete_branding_asset

    config = await get_or_create_widget_config(db, organization_id)
    if config.avatar_url:
        delete_branding_asset(config.avatar_url)
    config.avatar_url = None
    config.use_default_avatar = True
    await db.flush()
    return config


async def reset_to_default_avatar(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> WidgetConfig:
    return await update_widget_config(db, organization_id, {"use_default_avatar": True}, user_id)


# --------------------------------------------------------------------- Suggested questions (9.3.7)


async def get_suggested_questions(db: AsyncSession, widget_config_id: uuid.UUID, limit: int | None = None) -> list[WidgetSuggestedQuestion]:
    query = (
        select(WidgetSuggestedQuestion)
        .where(WidgetSuggestedQuestion.widget_config_id == widget_config_id, WidgetSuggestedQuestion.is_active.is_(True))
        .order_by(WidgetSuggestedQuestion.position)
        .limit(limit or settings.SUGGESTED_WIDGET_QUESTIONS_MAX)
    )
    return list((await db.scalars(query)).all())


async def list_suggested_questions(db: AsyncSession, widget_config_id: uuid.UUID, include_inactive: bool = True) -> list[WidgetSuggestedQuestion]:
    query = select(WidgetSuggestedQuestion).where(WidgetSuggestedQuestion.widget_config_id == widget_config_id)
    if not include_inactive:
        query = query.where(WidgetSuggestedQuestion.is_active.is_(True))
    query = query.order_by(WidgetSuggestedQuestion.position).limit(settings.SUGGESTED_WIDGET_QUESTIONS_MAX if not include_inactive else None)
    return list((await db.scalars(query)).all())


async def add_suggested_question(db: AsyncSession, organization_id: uuid.UUID, question: str, label: str | None, user_id: uuid.UUID) -> WidgetSuggestedQuestion:
    config = await get_or_create_widget_config(db, organization_id)
    existing = await list_suggested_questions(db, config.id)
    if len(existing) >= settings.SUGGESTED_WIDGET_QUESTIONS_MAX:
        raise WidgetError(f"At most {settings.SUGGESTED_WIDGET_QUESTIONS_MAX} suggested questions are allowed")
    row = WidgetSuggestedQuestion(widget_config_id=config.id, question=question.strip(), label=label, position=len(existing))
    db.add(row)
    await db.flush()
    return row


async def update_suggested_question(db: AsyncSession, question_id: uuid.UUID, organization_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> WidgetSuggestedQuestion:
    config = await get_or_create_widget_config(db, organization_id)
    row = await db.get(WidgetSuggestedQuestion, question_id)
    if row is None or row.widget_config_id != config.id:
        raise WidgetError("Suggested question not found")
    for key, value in data.items():
        if value is not None:
            setattr(row, key, value)
    await db.flush()
    return row


async def delete_suggested_question(db: AsyncSession, question_id: uuid.UUID, organization_id: uuid.UUID, user_id: uuid.UUID) -> None:
    config = await get_or_create_widget_config(db, organization_id)
    row = await db.get(WidgetSuggestedQuestion, question_id)
    if row is None or row.widget_config_id != config.id:
        raise WidgetError("Suggested question not found")
    await db.delete(row)
    await db.flush()


async def reorder_suggested_questions(db: AsyncSession, organization_id: uuid.UUID, question_ids: list[uuid.UUID], user_id: uuid.UUID) -> list[WidgetSuggestedQuestion]:
    config = await get_or_create_widget_config(db, organization_id)
    rows = {row.id: row for row in await list_suggested_questions(db, config.id)}
    if set(question_ids) != set(rows):
        raise WidgetError("question_ids must be exactly the organization's existing suggested-question ids")
    for position, question_id in enumerate(question_ids):
        rows[question_id].position = position
    await db.flush()
    return await list_suggested_questions(db, config.id)


def get_default_suggested_questions(language: str) -> list[str]:
    defaults = {
        "fr": ["Comment ça fonctionne ?", "Quels sont vos tarifs ?", "Comment vous contacter ?"],
        "en": ["How does this work?", "What are your pricing plans?", "How can I contact you?"],
    }
    return defaults.get(language, defaults["en"])


# --------------------------------------------------------------------- Position (9.3.8)


async def get_widget_position(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    config = await get_or_create_widget_config(db, organization_id)
    return {
        "position": config.position, "position_mobile": config.position_mobile or get_mobile_position(config.position),
        "offset_x": config.offset_x, "offset_y": config.offset_y, "position_locked": config.position_locked,
    }


async def update_widget_position(db: AsyncSession, organization_id: uuid.UUID, position_data: dict, user_id: uuid.UUID) -> WidgetConfig:
    if "position" in position_data and position_data["position"] is not None:
        validate_widget_position(position_data["position"])
    for offset_field in ("offset_x", "offset_y"):
        value = position_data.get(offset_field)
        if value is not None and not (settings.WIDGET_OFFSET_MIN <= value <= settings.WIDGET_OFFSET_MAX):
            raise WidgetError(f"{offset_field} must be between {settings.WIDGET_OFFSET_MIN} and {settings.WIDGET_OFFSET_MAX}")
    return await update_widget_config(db, organization_id, position_data, user_id)
