"""
Entry point: `uvicorn api.main:app --reload` (dev) or the Dockerfile's
production command. Everything under Partie 1.1 (authentication) is wired
here; later parts (multi-tenant, billing, ...) add more routers to this
same app rather than starting a second one.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from api.config import settings
from api.routers import account, auth, oauth, password, sessions, two_factor, verify

app = FastAPI(title="RAG SaaS Platform API", version="0.1.0")

# Required by Authlib's Starlette OAuth client (api/routers/oauth.py) to
# hold the `state`/`nonce` between the /authorize redirect and /callback.
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_MIDDLEWARE_SECRET, same_site="lax", https_only=settings.COOKIE_SECURE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,  # the refresh-token cookie requires this
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(password.router)
app.include_router(verify.router)
app.include_router(oauth.router)
app.include_router(two_factor.router)
app.include_router(sessions.router)
app.include_router(account.router)


@app.get("/health", tags=["monitoring"])
async def health():
    return {"status": "ok"}
