"""Spec 10.4.3 -- SCIM 2.0 user provisioning (RFC 7643 / 7644, Users resource only).

Two surfaces:
  * `/organizations/{org_id}/scim/tokens` -- an organization owner/admin creates, lists and revokes the bearer tokens an identity provider uses;
  * `/scim/v2/*` -- what the identity provider calls, authenticated by `Authorization: Bearer <scim token>` and confined to the organization of that token.

Provisioning rules: a created user becomes a plain `member` (SCIM never grants admin rights); an unknown e-mail creates a passwordless account that can
only sign in through SSO / password reset; deactivating or deleting a SCIM user REMOVES THEIR MEMBERSHIP of this organization but never deletes the
account itself (it may belong to other organizations). The owner of an organization can never be removed through SCIM."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.scim import ScimToken
from api.models.user import User
from api.security.hashing import generate_raw_token, hash_token
from api.security.organizations import require_org_admin
from api.security.quotas import require_quota_available

router = APIRouter(tags=["scim"])

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
SCIM_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
_MEDIA = "application/scim+json"
_MAX_PAGE = 200


def _scim_error(code: int, detail: str, scim_type: str | None = None) -> JSONResponse:
    body = {"schemas": [SCIM_ERROR_SCHEMA], "status": str(code), "detail": detail}
    if scim_type:
        body["scimType"] = scim_type
    return JSONResponse(status_code=code, content=body, media_type=_MEDIA)


# ----------------------------------------------------------------- token administration (organization owner/admin)

class ScimTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@router.post("/organizations/{org_id}/scim/tokens", status_code=status.HTTP_201_CREATED)
async def create_scim_token(org_id: uuid.UUID, payload: ScimTokenCreate, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    raw = "scim_" + generate_raw_token()
    row = ScimToken(organization_id=org_id, name=payload.name, token_hash=hash_token(raw), created_by=caller.user_id)
    db.add(row)
    await db.commit()
    return {"id": str(row.id), "name": row.name, "token": raw, "note": "Copy this token now: it is not shown again."}


@router.get("/organizations/{org_id}/scim/tokens")
async def list_scim_tokens(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(ScimToken).where(ScimToken.organization_id == org_id).order_by(ScimToken.created_at.desc()))).all()
    return [{"id": str(r.id), "name": r.name, "created_at": r.created_at, "last_used_at": r.last_used_at, "revoked": r.revoked_at is not None} for r in rows]


@router.delete("/organizations/{org_id}/scim/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_scim_token(org_id: uuid.UUID, token_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    row = await db.get(ScimToken, token_id)
    if row is None or row.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    row.revoked_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()


# ----------------------------------------------------------------- SCIM authentication

async def require_scim_token(authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)) -> ScimToken:
    scheme, _, raw = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SCIM token")
    token = await db.scalar(select(ScimToken).where(ScimToken.token_hash == hash_token(raw.strip())))
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SCIM token")
    token.last_used_at = dt.datetime.now(dt.timezone.utc)
    return token


def _resource(user: User, member: OrganizationMember) -> dict:
    return {
        "schemas": [SCIM_USER_SCHEMA], "id": str(user.id), "userName": user.email, "displayName": user.full_name or user.email,
        "emails": [{"value": user.email, "primary": True}], "active": bool(user.is_active),
        "meta": {"resourceType": "User", "created": member.joined_at.isoformat() if member.joined_at else None},
    }


async def _member_in_org(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> tuple[User, OrganizationMember] | None:
    row = (await db.execute(
        select(User, OrganizationMember).join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == org_id, User.id == user_id)
    )).first()
    return (row[0], row[1]) if row else None


def _email_from_body(body: dict) -> str | None:
    emails = body.get("emails") or []
    primary = next((e for e in emails if e.get("primary")), emails[0] if emails else None)
    value = (primary or {}).get("value") or body.get("userName")
    return value.strip().lower() if isinstance(value, str) and "@" in value else None


# ----------------------------------------------------------------- SCIM endpoints

@router.get("/scim/v2/ServiceProviderConfig")
async def service_provider_config(_t: ScimToken = Depends(require_scim_token)):
    return JSONResponse(media_type=_MEDIA, content={
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True}, "bulk": {"supported": False}, "filter": {"supported": True, "maxResults": _MAX_PAGE},
        "changePassword": {"supported": False}, "sort": {"supported": False}, "etag": {"supported": False},
        "authenticationSchemes": [{"type": "oauthbearertoken", "name": "Bearer token", "description": "SCIM bearer token created by an organization admin"}],
    })


@router.get("/scim/v2/Users")
async def list_users(
    filter: str | None = Query(default=None), startIndex: int = Query(default=1, ge=1), count: int = Query(default=100, ge=0, le=_MAX_PAGE),
    token: ScimToken = Depends(require_scim_token), db: AsyncSession = Depends(get_db),
):
    query = select(User, OrganizationMember).join(OrganizationMember, OrganizationMember.user_id == User.id).where(OrganizationMember.organization_id == token.organization_id)
    if filter:
        parts = filter.split()
        if len(parts) == 3 and parts[0].lower() in ("username", "emails.value") and parts[1].lower() == "eq":
            query = query.where(User.email == parts[2].strip('"').lower())
        else:
            return _scim_error(400, "Only the filter 'userName eq \"value\"' is supported", "invalidFilter")
    rows = (await db.execute(query.order_by(User.email))).all()
    page = rows[startIndex - 1: startIndex - 1 + count]
    await db.commit()
    return JSONResponse(media_type=_MEDIA, content={
        "schemas": [SCIM_LIST_SCHEMA], "totalResults": len(rows), "startIndex": startIndex, "itemsPerPage": len(page),
        "Resources": [_resource(u, m) for u, m in page],
    })


@router.get("/scim/v2/Users/{user_id}")
async def get_user(user_id: uuid.UUID, token: ScimToken = Depends(require_scim_token), db: AsyncSession = Depends(get_db)):
    found = await _member_in_org(db, token.organization_id, user_id)
    await db.commit()
    if found is None:
        return _scim_error(404, "User not found")
    return JSONResponse(media_type=_MEDIA, content=_resource(*found))


@router.post("/scim/v2/Users", status_code=status.HTTP_201_CREATED)
async def create_user(body: dict, token: ScimToken = Depends(require_scim_token), db: AsyncSession = Depends(get_db)):
    email = _email_from_body(body)
    if email is None:
        return _scim_error(400, "userName / emails.value must be an e-mail address", "invalidValue")
    user = await db.scalar(select(User).where(User.email == email))
    if user is not None:
        if await _member_in_org(db, token.organization_id, user.id) is not None:
            return _scim_error(409, "User already exists in this organization", "uniqueness")
    await require_quota_available(db, token.organization_id, "users")  # same member limit as invitations
    if user is None:
        user = User(email=email, hashed_password=None, is_active=body.get("active", True) is not False, is_email_verified=False, full_name=body.get("displayName"))
        db.add(user)
        await db.flush()
    member = OrganizationMember(organization_id=token.organization_id, user_id=user.id, role=OrganizationRole.member)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return JSONResponse(status_code=201, media_type=_MEDIA, content=_resource(user, member))


async def _deactivate(db: AsyncSession, token: ScimToken, user: User, member: OrganizationMember) -> JSONResponse | None:
    if member.role == OrganizationRole.owner:
        return _scim_error(403, "The owner of an organization cannot be removed through SCIM", "mutability")
    await db.delete(member)
    return None


@router.patch("/scim/v2/Users/{user_id}")
async def patch_user(user_id: uuid.UUID, body: dict, token: ScimToken = Depends(require_scim_token), db: AsyncSession = Depends(get_db)):
    found = await _member_in_org(db, token.organization_id, user_id)
    if found is None:
        return _scim_error(404, "User not found")
    user, member = found
    for op in body.get("Operations", []):
        path = (op.get("path") or "").lower()
        value = op.get("value")
        wanted_active = None
        if path == "active":
            wanted_active = value
        elif not path and isinstance(value, dict) and "active" in value:
            wanted_active = value["active"]
        if isinstance(wanted_active, str):
            wanted_active = wanted_active.lower() == "true"
        if wanted_active is False:
            error = await _deactivate(db, token, user, member)
            if error is not None:
                return error
            await db.commit()
            return JSONResponse(media_type=_MEDIA, content={**_resource(user, member), "active": False})
    await db.commit()
    return JSONResponse(media_type=_MEDIA, content=_resource(user, member))


@router.put("/scim/v2/Users/{user_id}")
async def replace_user(user_id: uuid.UUID, body: dict, token: ScimToken = Depends(require_scim_token), db: AsyncSession = Depends(get_db)):
    found = await _member_in_org(db, token.organization_id, user_id)
    if found is None:
        return _scim_error(404, "User not found")
    user, member = found
    if body.get("active") is False:
        error = await _deactivate(db, token, user, member)
        if error is not None:
            return error
        await db.commit()
        return JSONResponse(media_type=_MEDIA, content={**_resource(user, member), "active": False})
    if isinstance(body.get("displayName"), str) and body["displayName"].strip():
        user.full_name = body["displayName"].strip()[:200]
    await db.commit()
    return JSONResponse(media_type=_MEDIA, content=_resource(user, member))


@router.delete("/scim/v2/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, token: ScimToken = Depends(require_scim_token), db: AsyncSession = Depends(get_db)):
    found = await _member_in_org(db, token.organization_id, user_id)
    if found is None:
        return _scim_error(404, "User not found")
    error = await _deactivate(db, token, *found)
    if error is not None:
        return error
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
