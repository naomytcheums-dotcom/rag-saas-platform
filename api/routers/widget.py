"""
Partie 9.3 -- the embeddable chat widget's real HTTP surface. See
`api/models/widget.py` for the real "one WidgetConfig row per
organization" consolidation and `api/security/widget_auth.py` for the
real public-key / session-token security split.

Real routing-order note (same class of bug fixed in Partie 9.2, see
docs/CAHIER_DES_CHARGES.md's own write-up): every STATIC path here
(`/widget/script.js`, `/widget/config`, `/widget/theme`, ...) sits
under the plain `/widget` prefix with no `{organization_id}` segment
at that depth, so there is no real static-vs-dynamic collision to
avoid this time -- admin (Member+) routes are instead scoped under
`/organizations/{org_id}/widget/...`, a real, different prefix
entirely.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_db
from api.models.organization import OrganizationMember
from api.models.user import User
from api.models.widget import WidgetConfig
from api.schemas.public_api import ChatResponse
from api.schemas.widget import (
    ReorderQuestionsRequest, SuggestedQuestionCreateRequest, SuggestedQuestionResponse, SuggestedQuestionUpdateRequest,
    WidgetChatRequest, WidgetConfigUpdateRequest, WidgetLanguageUpdateRequest, WidgetNameUpdateRequest,
    WidgetPositionResponse, WidgetPositionUpdateRequest, WidgetPublicConfigResponse, WidgetSessionRequest,
    WidgetSessionResponse, WidgetThemeResponse, WidgetThemeUpdateRequest, WidgetWelcomeUpdateRequest,
)
from api.security.organizations import require_org_member
from api.security.widget_auth import (
    WidgetAuthError, WidgetSession, create_widget_session_token, get_widget_config_by_public_key,
    require_widget_public_key, require_widget_session,
)
from api.services.public_api import PublicAPIError, handle_public_chat
from api.services.widget import (
    WidgetError, add_suggested_question, delete_suggested_question, delete_widget_avatar, delete_widget_logo,
    generate_css_variables, get_default_theme, get_or_create_widget_config, get_supported_widget_languages,
    get_widget_avatar, get_widget_config_public, get_widget_language, get_widget_logo, get_widget_position,
    list_suggested_questions, reorder_suggested_questions, reset_to_default_avatar, reset_welcome_message,
    reset_widget_theme, update_suggested_question, update_widget_config, update_widget_position, upload_widget_avatar,
    upload_widget_logo, validate_theme, validate_widget_name, validate_widget_params, validate_language,
    get_welcome_message, update_welcome_message, validate_theme_colors, sanitize_custom_css, generate_widget_short_name,
)

router = APIRouter(tags=["Widget"])

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "widget"
_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _to_http_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _cache_headers() -> dict:
    return {"Cache-Control": f"public, max-age={settings.WIDGET_SCRIPT_CACHE_TIME}"}


def serve_asset(filename: str, media_type: str) -> Response:
    """Item 3's own literal function."""
    path = _ASSETS_DIR / filename
    if not path.exists():
        raise _NOT_FOUND
    return Response(content=path.read_text(encoding="utf-8"), media_type=media_type, headers=_cache_headers())


# ------------------------------------------------------------------------- 9.3.1/9.3.14 Script / SDK


@router.get("/widget/script.js")
@router.get("/widget/embed.js")
async def get_widget_script():
    return serve_asset("embed.js", "application/javascript")


@router.get("/widget/chat.js")
async def get_widget_chat_js():
    return serve_asset("chat.js", "application/javascript")


@router.get("/widget/styles.css")
async def get_widget_styles():
    return serve_asset("styles.css", "text/css")


# ------------------------------------------------------------------------- 9.3.1/9.3.13 iframe


@router.get("/widget/iframe")
async def get_widget_iframe(config: WidgetConfig = Depends(require_widget_public_key)):
    """Item 3's own literal function (`render_iframe_html`) -- the
    real HTML shell itself needs no config baked in server-side
    (chat.js fetches /widget/config client-side once loaded), so this
    just serves the real static template with the widget's own real
    security headers layered on top."""
    path = _ASSETS_DIR / "iframe.html"
    if not path.exists():
        raise _NOT_FOUND
    headers = {**_cache_headers(), "X-Frame-Options": "ALLOWALL", "Content-Security-Policy": "frame-ancestors *"}
    return Response(content=path.read_text(encoding="utf-8"), media_type="text/html", headers=headers)


# ------------------------------------------------------------------------- 9.3.1 Config (public)


@router.get("/widget/config", response_model=WidgetPublicConfigResponse)
async def get_widget_config_endpoint(
    config: WidgetConfig = Depends(require_widget_public_key), theme: str | None = Query(default=None),
    position: str | None = Query(default=None), db: AsyncSession = Depends(get_db),
):
    overrides = validate_widget_params({"theme": theme, "position": position})
    data = await get_widget_config_public(db, config)
    data.update(overrides)
    return data


# Real, additive: an admin-side equivalent of GET /widget/config --
# not named by any literal 9.3.x étape, but without it a real
# dashboard has no way to learn its own organization's real
# `public_key` (needed to build the real <script data-key="..."> embed
# snippet) without already knowing it. Same honest-gap-fill pattern as
# 9.1's own `POST /organizations/{org_id}/api-keys`.
@router.get("/organizations/{org_id}/widget/config")
async def get_widget_config_admin_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    config = await get_or_create_widget_config(db, org_id)
    data = await get_widget_config_public(db, config)
    await db.commit()
    return data


# ------------------------------------------------------------------------- 9.3.1 Session + chat


@router.post("/widget/session", response_model=WidgetSessionResponse)
async def create_widget_session_endpoint(payload: WidgetSessionRequest, db: AsyncSession = Depends(get_db)):
    try:
        config = await get_widget_config_by_public_key(db, payload.public_key)
    except WidgetAuthError as exc:
        raise _NOT_FOUND from exc
    token = create_widget_session_token(config.id, config.organization_id, config.agent_id)
    return {"session_token": token, "expires_in": settings.WIDGET_SESSION_TOKEN_EXPIRE_MINUTES * 60}


@router.post("/widget/chat", response_model=ChatResponse)
async def widget_chat_endpoint(payload: WidgetChatRequest, session: WidgetSession = Depends(require_widget_session), db: AsyncSession = Depends(get_db)):
    if session.agent_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This widget has no agent configured yet")
    config = await db.get(WidgetConfig, session.widget_config_id)
    if config is None or config.created_by is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This widget has no owner and cannot start a conversation -- configure it via an authenticated session first")
    try:
        result = await handle_public_chat(db, session.organization_id, config.created_by, payload.message, str(session.agent_id), payload.conversation_id)
    except PublicAPIError as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return result


# ------------------------------------------------------------------------- 9.3.3/9.3.10 Theme (Member+)


@router.get("/widget/theme", response_model=WidgetThemeResponse)
async def get_widget_theme_endpoint(config: WidgetConfig = Depends(require_widget_public_key)):
    return {"theme": config.theme, "theme_custom_css": config.theme_custom_css}


@router.patch("/organizations/{org_id}/widget/theme", response_model=WidgetThemeResponse)
async def update_widget_theme_endpoint(org_id: uuid.UUID, payload: WidgetThemeUpdateRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        data = payload.model_dump(exclude_unset=True)
        if "theme" in data and data["theme"] is not None:
            validate_theme(data["theme"])
        if "theme_custom_css" in data and data["theme_custom_css"] is not None:
            data["theme_custom_css"] = sanitize_custom_css(data["theme_custom_css"])
        config = await update_widget_config(db, org_id, data, caller.user_id)
    except WidgetError as exc:
        raise _to_http_error(exc) from exc
    await db.commit()
    return {"theme": config.theme, "theme_custom_css": config.theme_custom_css}


@router.post("/organizations/{org_id}/widget/theme/reset", response_model=WidgetThemeResponse)
async def reset_widget_theme_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    config = await reset_widget_theme(db, org_id, caller.user_id)
    await db.commit()
    return {"theme": config.theme, "theme_custom_css": config.theme_custom_css}


@router.patch("/organizations/{org_id}/widget/config")
async def update_widget_colors_endpoint(org_id: uuid.UUID, payload: WidgetConfigUpdateRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    try:
        validate_theme_colors(data)
        config = await update_widget_config(db, org_id, data, caller.user_id)
    except WidgetError as exc:
        raise _to_http_error(exc) from exc
    await db.commit()
    return {"css_variables": generate_css_variables(config)}


# ------------------------------------------------------------------------- Real, additive: link an agent
#
# Not named by any literal 9.3.x étape, but without it the widget is
# real infrastructure with no real way to answer a real question --
# POST /widget/chat needs a real `agent_id` to run (see
# WidgetConfig.agent_id) and nothing else in this whole Partie 9.3
# batch ever sets it. Same honest-gap-fill reasoning as Partie 9.1's
# own `POST /organizations/{org_id}/api-keys` (see
# docs/CAHIER_DES_CHARGES.md's 9.1 write-up).


@router.patch("/organizations/{org_id}/widget/agent")
async def set_widget_agent_endpoint(org_id: uuid.UUID, payload: dict, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    agent_id = payload.get("agent_id")
    config = await get_or_create_widget_config(db, org_id, created_by=caller.user_id)
    config.agent_id = uuid.UUID(agent_id) if agent_id else None
    if config.created_by is None:
        config.created_by = caller.user_id
    await db.commit()
    return {"agent_id": str(config.agent_id) if config.agent_id else None}


# ------------------------------------------------------------------------- 9.3.4 Name (Member+)


@router.patch("/organizations/{org_id}/widget/config/name")
async def update_widget_name_endpoint(org_id: uuid.UUID, payload: WidgetNameUpdateRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        name = validate_widget_name(payload.name)
    except WidgetError as exc:
        raise _to_http_error(exc) from exc
    short_name = generate_widget_short_name(name)
    config = await update_widget_config(db, org_id, {"widget_name": name, "widget_short_name": short_name}, caller.user_id)
    await db.commit()
    return {"name": config.widget_name, "short_name": config.widget_short_name}


# ------------------------------------------------------------------------- 9.3.6 Welcome message (Member+)


@router.get("/widget/welcome")
async def get_widget_welcome_endpoint(config: WidgetConfig = Depends(require_widget_public_key), db: AsyncSession = Depends(get_db)):
    return {"message": await get_welcome_message(db, config.organization_id)}


@router.patch("/organizations/{org_id}/widget/welcome")
async def update_widget_welcome_endpoint(org_id: uuid.UUID, payload: WidgetWelcomeUpdateRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        config = await update_welcome_message(db, org_id, payload.message, caller.user_id)
    except WidgetError as exc:
        raise _to_http_error(exc) from exc
    await db.commit()
    return {"message": config.welcome_message}


@router.post("/organizations/{org_id}/widget/welcome/reset")
async def reset_widget_welcome_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    config = await reset_welcome_message(db, org_id, caller.user_id)
    await db.commit()
    return {"message": config.welcome_message}


# ------------------------------------------------------------------------- 9.3.8 Position (Member+)


@router.get("/widget/position", response_model=WidgetPositionResponse)
async def get_widget_position_public_endpoint(config: WidgetConfig = Depends(require_widget_public_key), db: AsyncSession = Depends(get_db)):
    return await get_widget_position(db, config.organization_id)


@router.patch("/organizations/{org_id}/widget/position", response_model=WidgetPositionResponse)
async def update_widget_position_endpoint(org_id: uuid.UUID, payload: WidgetPositionUpdateRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        await update_widget_position(db, org_id, payload.model_dump(exclude_unset=True), caller.user_id)
    except WidgetError as exc:
        raise _to_http_error(exc) from exc
    await db.commit()
    return await get_widget_position(db, org_id)


# ------------------------------------------------------------------------- 9.3.9 Language (Member+)


@router.get("/widget/languages")
async def get_widget_languages_endpoint():
    return {"languages": get_supported_widget_languages()}


@router.get("/widget/language")
async def get_widget_language_endpoint(config: WidgetConfig = Depends(require_widget_public_key), accept_language: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    return {"language": await get_widget_language(db, config.organization_id, accept_language)}


@router.patch("/organizations/{org_id}/widget/language")
async def update_widget_language_endpoint(org_id: uuid.UUID, payload: WidgetLanguageUpdateRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        validate_language(payload.language)
        config = await update_widget_config(db, org_id, {"language": payload.language}, caller.user_id)
    except WidgetError as exc:
        raise _to_http_error(exc) from exc
    await db.commit()
    return {"language": config.language}


# ------------------------------------------------------------------------- 9.3.2 Logo (Member+)


@router.get("/widget/logo")
async def get_widget_logo_endpoint(config: WidgetConfig = Depends(require_widget_public_key), db: AsyncSession = Depends(get_db)):
    return {"logo_url": await get_widget_logo(db, config.organization_id)}


@router.post("/organizations/{org_id}/widget/logo")
async def upload_widget_logo_endpoint(org_id: uuid.UUID, file: UploadFile = File(...), caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    try:
        config = await upload_widget_logo(db, org_id, content, caller.user_id)
    except (WidgetError, ValueError) as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return {"logo_url": config.logo_url}


@router.delete("/organizations/{org_id}/widget/logo")
async def delete_widget_logo_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    await delete_widget_logo(db, org_id, caller.user_id)
    await db.commit()
    return {"logo_url": None}


# ------------------------------------------------------------------------- 9.3.5 Avatar (Member+)


@router.get("/widget/avatar")
async def get_widget_avatar_endpoint(config: WidgetConfig = Depends(require_widget_public_key), db: AsyncSession = Depends(get_db)):
    return await get_widget_avatar(db, config.organization_id)


@router.post("/organizations/{org_id}/widget/avatar")
async def upload_widget_avatar_endpoint(org_id: uuid.UUID, file: UploadFile = File(...), caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    try:
        config = await upload_widget_avatar(db, org_id, content, caller.user_id)
    except (WidgetError, ValueError) as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return {"avatar_url": config.avatar_url}


@router.delete("/organizations/{org_id}/widget/avatar")
async def delete_widget_avatar_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    await delete_widget_avatar(db, org_id, caller.user_id)
    await db.commit()
    return {"avatar_url": None}


@router.patch("/organizations/{org_id}/widget/avatar/default")
async def reset_widget_avatar_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    await reset_to_default_avatar(db, org_id, caller.user_id)
    await db.commit()
    return {"use_default_avatar": True}


# ------------------------------------------------------------------------- 9.3.7 Suggested questions


@router.get("/widget/suggested-questions")
async def get_suggested_questions_endpoint(config: WidgetConfig = Depends(require_widget_public_key), db: AsyncSession = Depends(get_db)):
    questions = await list_suggested_questions(db, config.id, include_inactive=False)
    return [SuggestedQuestionResponse.model_validate(q) for q in questions]


@router.get("/organizations/{org_id}/widget/suggested-questions/admin")
async def list_suggested_questions_admin_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    config = await get_or_create_widget_config(db, org_id)
    questions = await list_suggested_questions(db, config.id, include_inactive=True)
    return [SuggestedQuestionResponse.model_validate(q) for q in questions]


@router.post("/organizations/{org_id}/widget/suggested-questions")
async def add_suggested_question_endpoint(org_id: uuid.UUID, payload: SuggestedQuestionCreateRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        row = await add_suggested_question(db, org_id, payload.question, payload.label, caller.user_id)
    except WidgetError as exc:
        raise _to_http_error(exc) from exc
    await db.commit()
    return SuggestedQuestionResponse.model_validate(row)


# Real routing-order note (same class of bug fixed in Partie 9.2 --
# see docs/CAHIER_DES_CHARGES.md's write-up on /api-keys/scopes): this
# static "reorder" path MUST be registered BEFORE the dynamic
# "/{question_id}" routes below at the same depth, or FastAPI parses
# "reorder" as a `question_id` UUID and 422s instead of matching.
@router.patch("/organizations/{org_id}/widget/suggested-questions/reorder")
async def reorder_suggested_questions_endpoint(org_id: uuid.UUID, payload: ReorderQuestionsRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        rows = await reorder_suggested_questions(db, org_id, payload.question_ids, caller.user_id)
    except WidgetError as exc:
        raise _to_http_error(exc) from exc
    await db.commit()
    return [SuggestedQuestionResponse.model_validate(r) for r in rows]


@router.patch("/organizations/{org_id}/widget/suggested-questions/{question_id}")
async def update_suggested_question_endpoint(org_id: uuid.UUID, question_id: uuid.UUID, payload: SuggestedQuestionUpdateRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        row = await update_suggested_question(db, question_id, org_id, payload.model_dump(exclude_unset=True), caller.user_id)
    except WidgetError as exc:
        raise _NOT_FOUND from exc
    await db.commit()
    return SuggestedQuestionResponse.model_validate(row)


@router.delete("/organizations/{org_id}/widget/suggested-questions/{question_id}")
async def delete_suggested_question_endpoint(org_id: uuid.UUID, question_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        await delete_suggested_question(db, question_id, org_id, caller.user_id)
    except WidgetError as exc:
        raise _NOT_FOUND from exc
    await db.commit()
    return {"deleted": True}
