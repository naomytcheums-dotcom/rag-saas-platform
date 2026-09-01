"""
1.1.16 -- double-submit CSRF protection for the two endpoints that
authenticate purely off a cookie with no Authorization header required:
POST /auth/refresh and POST /auth/logout. Every OTHER protected route
already requires a Bearer access token that lives in the frontend's JS
memory, not a cookie -- a cross-site attacker's forged request can't
attach a header it doesn't know the value of, so those are already safe
from classic cookie-riding CSRF by construction. These two are the
exception, and SameSite=lax on the refresh_token cookie (api/security/
sessions.py) already blocks most cross-site POST cookie-riding in modern
browsers -- this is defense-in-depth on top of that, not a replacement.

Double-submit, not a server-stored token: a second, JS-readable (NOT
httpOnly) cookie holds a random value; the caller must echo it back in
an X-CSRF-Token header. A cross-site attacker's page can make the browser
attach the cookie automatically, but the Same-Origin Policy blocks that
page's own JS from ever READING the cookie's value to also set a
matching header -- so the two only ever match for a same-origin caller
that can actually read its own cookies.
"""

import secrets

from fastapi import Cookie, Header, HTTPException, Response, status

from api.config import settings

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    """Deliberately NOT httpOnly, unlike the refresh-token cookie right
    next to it -- the frontend's JS must be able to read this one to
    echo it back in the X-CSRF-Token header. That's the whole mechanism,
    not an oversight. Same max_age/path/domain/secure/samesite as the
    refresh cookie it's always issued alongside (api/security/sessions.py's
    issue_session()), since the two are only ever meaningful as a pair."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=False,
        samesite="lax",
    )


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN)


async def verify_csrf(
    csrf_token: str | None = Cookie(default=None),
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER_NAME),
) -> None:
    """FastAPI dependency for POST /auth/refresh and POST /auth/logout.
    Requires both the cookie and the header to be present AND equal;
    secrets.compare_digest avoids a timing side-channel on the
    comparison, same reasoning as every other secret comparison in this
    codebase. A caller with no session at all (no csrf_token cookie --
    e.g. never logged in) fails here with 403 rather than reaching
    either route's own "is there a valid refresh token" logic, which is
    correct: there is nothing for either route to do for a caller that
    was never issued a session in the first place.
    """
    if not csrf_token or not x_csrf_token or not secrets.compare_digest(csrf_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing or invalid CSRF token")
