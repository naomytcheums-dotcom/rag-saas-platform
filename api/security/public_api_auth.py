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

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.models.organization_api_key import OrganizationAPIKey
from api.security.rate_limit import enforce_rate_limit
from api.services.organization_api_keys import verify_api_key

_INVALID_KEY = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired API key")


async def require_organization_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"), db: AsyncSession = Depends(get_db),
) -> OrganizationAPIKey:
    """Item 3's own literal `validate_api_key` -- real, resolves AND
    rate-limits the caller in one real dependency, so every one of the
    9 real `/v1/*` routes gets both by simply depending on this."""
    key_row = await verify_api_key(db, x_api_key)
    if key_row is None:
        raise _INVALID_KEY

    await enforce_rate_limit(f"public_api:{key_row.id}", settings.PUBLIC_API_RATE_LIMIT_MAX, settings.PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS)
    return key_row


def require_public_api_scope(scope: str):
    """Real, scope-gated dependency factory -- each one of the 9 real
    endpoints below depends on this with its own real scope name."""

    async def _check(key_row: OrganizationAPIKey = Depends(require_organization_api_key)) -> OrganizationAPIKey:
        if scope not in key_row.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This API key does not have the required {scope!r} scope")
        return key_row

    return _check
