"""
Partie 1.3.4 -- email-based organization invitations. See
api/models/invitation.py's module docstring for how this differs from
the immediate-add path (api/routers/organization_members.py's
invite_organization_member).

Privilege-escalation guard, carried over from Etape 1.2.4: this
endpoint is Manager+, same tier as the immediate-add path, so it must
apply the SAME "a Manager cannot invite as admin/manager" restriction
that path already enforces -- an email-based invitation is just another
way to add a member, and the risk (a Manager handing out a role tier
they can't themselves grant via role-update) is identical.
"""

import datetime as dt
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.invitation import Invitation
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.hashing import generate_raw_token, hash_token
from api.utils import as_aware_utc


def reject_if_manager_exceeds_own_role(caller_role: OrganizationRole, proposed_role: OrganizationRole) -> None:
    """Etape 1.2.4's exact guard, restated for this endpoint -- see
    api/routers/organization_members.py's invite_organization_member for
    the original reasoning."""
    if caller_role == OrganizationRole.manager and proposed_role in (OrganizationRole.admin, OrganizationRole.manager):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers can only invite members as 'member' or 'viewer'",
        )


async def create_or_reissue_invitation(
    db: AsyncSession, *, organization_id: uuid.UUID, email: str, role: OrganizationRole, invited_by: uuid.UUID,
) -> tuple[Invitation, str]:
    """
    Returns (invitation, raw_token) -- the raw token exists ONLY in
    memory long enough to email it; only its hash is ever persisted
    (api/models/invitation.py's own docstring).

    One row per (organization_id, email): re-inviting an address that
    already has a row (pending, expired, or previously accepted and
    since removed from the org) reissues that SAME row in place --
    fresh token, fresh expiry, accepted_at cleared -- rather than
    erroring on the unique constraint or leaving stale rows to
    accumulate. Does NOT commit; the caller does, same convention as
    api/security/organizations.py's create_organization_with_owner.
    """
    raw_token = generate_raw_token()
    expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=settings.INVITATION_EXPIRE_DAYS)

    existing = await db.scalar(
        select(Invitation).where(Invitation.organization_id == organization_id, Invitation.email == email)
    )
    if existing is not None:
        existing.role = role
        existing.invited_by = invited_by
        existing.token_hash = hash_token(raw_token)
        existing.expires_at = expires_at
        existing.accepted_at = None
        await db.flush()
        return existing, raw_token

    invitation = Invitation(
        organization_id=organization_id, email=email, role=role, invited_by=invited_by,
        token_hash=hash_token(raw_token), expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()
    return invitation, raw_token


async def resolve_valid_invitation(db: AsyncSession, raw_token: str) -> Invitation:
    """
    Item 5's can_accept_invitation(token) -- a plain lookup function
    rather than a FastAPI Depends() dependency: the token arrives in the
    POST body, not a path/query parameter, so there is no natural
    per-route parameter for a dependency to resolve it from the way
    require_org_member resolves org_id.

    One generic error for "no such token" / "already accepted" /
    "expired" -- same anti-enumeration shape as
    api/routers/password.py's reset_password: a caller trying random
    tokens must not learn which failure mode they hit.
    """
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invitation")

    invitation = await db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(raw_token)))
    if invitation is None:
        raise invalid
    if invitation.accepted_at is not None:
        raise invalid
    if as_aware_utc(invitation.expires_at) < dt.datetime.now(dt.timezone.utc):
        raise invalid
    return invitation


async def is_already_a_member(db: AsyncSession, *, organization_id: uuid.UUID, email: str) -> bool:
    """Used both when CREATING an invitation (reject inviting someone
    already in the org) and, defensively, when ACCEPTING one (a race
    where the same person was added some other way in between)."""
    target_user = await db.scalar(select(User.id).where(User.email == email))
    if target_user is None:
        return False
    return (
        await db.scalar(
            select(OrganizationMember.id).where(
                OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == target_user,
            )
        )
    ) is not None
