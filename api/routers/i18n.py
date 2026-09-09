"""Partie 8.1.19 -- Multi-langue UI (i18n) endpoints. `GET /i18n/*` are
real, public (no auth needed to read UI strings), `POST /i18n/language`
sets the real preference cookie -- see `api/services/i18n.py`'s own
top docstring for why a cookie, not a DB column."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from api.config import settings
from api.schemas.i18n import SetLanguageRequest, SupportedLanguagesResponse
from api.services.i18n import detect_user_language, get_all_categories_merged, get_supported_languages

router = APIRouter(prefix="/i18n", tags=["i18n"])


@router.get("/languages", response_model=SupportedLanguagesResponse)
async def list_supported_languages_endpoint():
    return SupportedLanguagesResponse(languages=get_supported_languages(), default=settings.UI_DEFAULT_LANGUAGE)


@router.get("/translations/{language}")
async def get_translations_endpoint(language: str):
    """Real bug fixed (manual QA on the live chat interface): this
    used to call `get_all_translations(language)` with no category,
    silently defaulting to `common` alone -- so `chat.json` and
    `widget.json` strings were never actually served, no matter what
    language a visitor picked. Now returns every real category
    merged."""
    if language not in get_supported_languages():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported language")
    return get_all_categories_merged(language)


@router.get("/detect")
async def detect_language_endpoint(request: Request):
    cookie_value = request.cookies.get(settings.UI_LANGUAGE_COOKIE_NAME)
    language = detect_user_language(request.headers.get("accept-language"), cookie_value)
    return {"language": language}


@router.post("/language")
async def set_language_endpoint(payload: SetLanguageRequest, response: Response):
    if payload.language not in get_supported_languages():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language")
    response.set_cookie(settings.UI_LANGUAGE_COOKIE_NAME, payload.language, max_age=60 * 60 * 24 * 365, samesite="lax")
    return {"language": payload.language}
