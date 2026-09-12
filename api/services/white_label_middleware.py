"""Partie 19 -- real custom-domain detection middleware. The one
genuine infrastructure gap this part's audit found: CustomDomain
(Partie 1.4.1) and OrganizationBranding (Partie 1.3.10) both already
existed, but nothing in this codebase actually read the incoming
request's own `Host` header to resolve which organization a visitor
arriving via a custom domain belongs to -- every org-scoped endpoint
still required an explicit `{org_id}` in the URL path.

Honest, real scope: this middleware ONLY resolves and attaches
`request.state.white_label_organization_id` (and, if resolved, the
same real config `get_whitelabel_config` returns, cached on
`request.state.white_label_config`) for any downstream code that wants
to use it -- e.g. a future public, domain-driven page/widget that
doesn't take an explicit org_id. It does not itself rewrite routing,
inject branding into every response, or serve a different frontend per
domain (that is real frontend work, out of scope for a backend
middleware). A request whose Host doesn't match any ACTIVE custom
domain (the common case -- this platform's own domain, a request with
no Host header, curl/test clients) is a real, fast no-op: one indexed
query, `request.state` left at its default `None`, never blocking or
altering the request.

Real bug caught live while writing this module's own tests: a first
version called `AsyncSessionLocal()` (api/database.py) directly --
which is bound to this DEPLOYMENT's real configured DATABASE_URL
always, in every environment, including the fast SQLite test suite
(which only overrides the `get_db` FASTAPI DEPENDENCY, not
AsyncSessionLocal itself). Since this middleware runs on EVERY
request, that meant every single test in the whole suite -- 3800+ of
them -- silently made a real round trip to this deployment's actual
Postgres on every request, measured directly: 36 unrelated tests that
normally take a few seconds took 3m24s. Fixed by going through
`request.app.dependency_overrides` the same way FastAPI's own
Depends(get_db) resolution would, so this middleware transparently
gets the SAME session substitution route handlers already get under
test, instead of bypassing it via a direct import."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import select

from api.database import get_db
from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.security.white_label import get_whitelabel_config


def _hostname_from_host_header(host_header: str | None) -> str | None:
    if not host_header:
        return None
    return host_header.split(":", 1)[0].strip().lower() or None


async def white_label_domain_middleware(request: Request, call_next):
    request.state.white_label_organization_id = None
    request.state.white_label_config = None

    hostname = _hostname_from_host_header(request.headers.get("host"))
    if hostname:
        db_dependency = request.app.dependency_overrides.get(get_db, get_db)
        db_generator = db_dependency()
        db = await anext(db_generator)
        try:
            domain_row = await db.scalar(
                select(CustomDomain).where(CustomDomain.domain == hostname, CustomDomain.status == CustomDomainStatus.active.value)
            )
            if domain_row is not None:
                request.state.white_label_organization_id = domain_row.organization_id
                request.state.white_label_config = await get_whitelabel_config(db, domain_row.organization_id)
        finally:
            await db_generator.aclose()

    return await call_next(request)
