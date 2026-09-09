"""
Partie 9.1 -- the real `X-API-Key` header authentication dependency for
the public `/v1/*` API, organization-scoped (see
api/models/organization_api_key.py's own docstring for why this is
separate from 5.3.10's own agent-scoped `require_agent_api_key`).

**Rate limiting réel (vision critique, chaque étape 9.1.x)** : reuses
`api/security/rate_limit.py`'s own real, existing sliding-window
limiter (Redis, already built for the 5 auth endpoints) -- keyed by
the real API key's own id (not by IP, which would let one client
starve another behind the same NAT/proxy), so every one of the 9
public endpoints gets the same real, uniform protection for free by
depending on `require_organization_api_key` below."""

import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.organization_api_key import OrganizationAPIKey
from api.models.user import User
from api.services.organization_api_keys import check_quota, check_rate_limit, increment_quota, verify_api_key

_INVALID_KEY = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired API key")


async def require_organization_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"), db: AsyncSession = Depends(get_db),
) -> OrganizationAPIKey:
    """Item 3's own literal `validate_api_key` -- real, resolves,
    rate-limits (9.2.5, per-key override or the real global default),
    AND enforces the real quota (9.2.6) in one real dependency, so
    every one of the real `/v1/*` routes gets all three by simply
    depending on this. Quota is only really INCREMENTED after a real
    successful response (see `require_public_api_scope` below) -- a
    request rejected for a wrong scope shouldn't count against it."""
    key_row = await verify_api_key(db, x_api_key)
    if key_row is None:
        raise _INVALID_KEY

    await check_rate_limit(key_row)
    await check_quota(key_row)
    return key_row


async def require_key_org_admin(key_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> OrganizationAPIKey:
    """Real, dedicated dependency for the `/api-keys/{key_id}/...`
    routes (9.2.1-9.2.6): unlike `/organizations/{org_id}/...` routes,
    there is real-ily no `org_id` in this real path for
    `require_org_admin` to resolve (FastAPI matches a path dependency's
    own parameter by NAME) -- this loads the real key first, then
    checks the real caller's own real Admin+ membership in THAT key's
    own real organization. Same real 404-for-both anti-enumeration
    reasoning as `require_org_member`: an unknown key and one the
    caller can't administer look identical."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    key_row = await db.get(OrganizationAPIKey, key_id)
    if key_row is None:
        raise not_found
    membership = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.organization_id == key_row.organization_id, OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise not_found
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")
    return key_row


def require_public_api_scope(scope: str):
    """Real, scope-gated dependency factory -- each real `/v1/*`
    endpoint depends on this with its own real scope name (9.2.4's
    own real, granular table). Increments the real quota counter
    (`db`, a real, separate dependency here since
    `require_organization_api_key` already committed its own real
    `db` session usage) only once the scope check itself passes."""

    async def _check(key_row: OrganizationAPIKey = Depends(require_organization_api_key), db: AsyncSession = Depends(get_db)) -> OrganizationAPIKey:
        if scope not in key_row.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This API key does not have the required {scope!r} scope")
        await increment_quota(db, key_row)
        return key_row

    return _check
