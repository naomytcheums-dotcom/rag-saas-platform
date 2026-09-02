"""
Partie 1.3.4 -- email-based organization invitations. See
api/models/invitation.py's module docstring for how this differs from
api/routers/organization_members.py's invite_organization_member
(Etape 1.2.3/1.2.4, immediate-add of an EXISTING account, unchanged and
still available side by side with this).
"""

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_db
from api.models.audit_log import AuditAction
from api.models.invitation import Invitation
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.schemas.invitations import (
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationEntry,
    InvitationListResponse,
)
from api.security.audit_log import log_audit_action
from api.security.hashing import hash_password
from api.security.invitations import (
    create_or_reissue_invitation,
    is_already_a_member,
    reject_if_manager_exceeds_own_role,
    resolve_valid_invitation,
)
from api.security.organizations import require_org_manager
from api.security.password_history import record_password_change
from api.security.quotas import require_quota_available
from api.security.password_similarity import is_password_too_similar
from api.security.password_strength import is_password_known_breached
from api.security.rate_limit import enforce_rate_limit
from api.security.sessions import issue_session
from api.services.email import send_organization_invitation_email, send_organization_member_added_email
from api.services.verification import create_and_send_email_otp
from api.utils import client_ip

router = APIRouter(tags=["invitations"])
logger = logging.getLogger(__name__)


def _to_entry(invitation: Invitation) -> InvitationEntry:
    return InvitationEntry(
        id=invitation.id, organization_id=invitation.organization_id, email=invitation.email, role=invitation.role,
        invited_by=invitation.invited_by, expires_at=invitation.expires_at, accepted_at=invitation.accepted_at,
        created_at=invitation.created_at,
    )


@router.get("/organizations/{org_id}/invitations", response_model=InvitationListResponse)
async def list_invitations(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Invitation).where(Invitation.organization_id == org_id).order_by(Invitation.created_at.desc())
    )).scalars().all()
    return InvitationListResponse(items=[_to_entry(i) for i in rows])


@router.post("/organizations/{org_id}/invitations", response_model=InvitationEntry, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    org_id: uuid.UUID, payload: InvitationCreateRequest, request: Request,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    reject_if_manager_exceeds_own_role(caller.role, payload.role)

    if await is_already_a_member(db, organization_id=org_id, email=payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This user is already a member of the organization")

    organization = await db.get(Organization, org_id)
    invitation, raw_token = await create_or_reissue_invitation(
        db, organization_id=org_id, email=payload.email, role=payload.role, invited_by=caller.user_id,
    )

    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.INVITATION_CREATED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(org_id), "invitation_id": str(invitation.id), "email": payload.email, "role": payload.role.value},
    )
    await db.commit()
    await db.refresh(invitation)

    invite_link = f"{settings.FRONTEND_URL.rstrip('/')}/invitations/accept?token={raw_token}"
    try:
        send_organization_invitation_email(payload.email, organization.name, payload.role.value, invite_link)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send invitation email to %s: %s", payload.email, exc)

    return _to_entry(invitation)


@router.delete("/organizations/{org_id}/invitations/{invitation_id}")
async def cancel_invitation(
    org_id: uuid.UUID, invitation_id: uuid.UUID, request: Request,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    invitation = await db.scalar(
        select(Invitation).where(Invitation.id == invitation_id, Invitation.organization_id == org_id)
    )
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.INVITATION_CANCELLED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(org_id), "invitation_id": str(invitation_id), "email": invitation.email},
    )
    await db.execute(delete(Invitation).where(Invitation.id == invitation.id))
    await db.commit()
    return {"message": "Invitation cancelled"}


@router.post("/invitations/accept")
async def accept_invitation(payload: InvitationAcceptRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Public, no auth required -- the token itself is the proof of
    authorization (same posture as api/routers/password.py's
    reset_password). Two branches:

    - The invited email already has an account: added to the
      organization immediately with the invitation's role. NOT logged
      in automatically -- same reasoning as password-reset not
      auto-logging in either, an emailed token isn't treated as strong
      enough proof to hand out a session for an EXISTING, potentially
      higher-value account.
    - No account exists for that email yet: one is created (password +
      accept_terms required in the body, same validation as
      POST /auth/register: breach check, similarity check,
      password-history seeding) and immediately logged in, same as
      /auth/register itself -- there is no prior session to protect.
      Does NOT get the auto-created default organization
      POST /auth/register gives every new account (Etape 1.2.2) --
      they're joining the INVITING organization instead; a redundant
      personal one would be surprising here, not helpful.
    """
    await enforce_rate_limit(
        f"ratelimit:invitation-accept:ip:{client_ip(request)}",
        settings.INVITATION_ACCEPT_RATE_LIMIT_MAX_ATTEMPTS, settings.INVITATION_ACCEPT_RATE_LIMIT_WINDOW_SECONDS,
    )

    invitation = await resolve_valid_invitation(db, payload.token)
    organization = await db.get(Organization, invitation.organization_id)

    if await is_already_a_member(db, organization_id=invitation.organization_id, email=invitation.email):
        # Defensive: added some other way between invite and accept.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a member of this organization")

    # Partie 1.3.6 -- checked here, before either branch below, since
    # BOTH create an OrganizationMember row: an org whose invitations
    # were sent before it hit max_users must not let acceptance be the
    # loophole that bypasses the same check invite_organization_member
    # already enforces for the immediate-add path.
    await require_quota_available(db, invitation.organization_id, "users")

    existing_user = await db.scalar(select(User).where(User.email == invitation.email))

    if existing_user is not None:
        db.add(OrganizationMember(organization_id=invitation.organization_id, user_id=existing_user.id, role=invitation.role, invited_by=invitation.invited_by))
        invitation.accepted_at = dt.datetime.now(dt.timezone.utc)
        await log_audit_action(
            db, user_id=existing_user.id, action=AuditAction.INVITATION_ACCEPTED, ip=client_ip(request),
            user_agent=request.headers.get("user-agent"), success=True,
            metadata={"organization_id": str(invitation.organization_id), "invitation_id": str(invitation.id)},
        )
        await db.commit()

        try:
            send_organization_member_added_email(existing_user.email, organization.name, invitation.role.value)
        except (EnvironmentError, RuntimeError) as exc:
            logger.warning("failed to send invitation-accepted notification to %s: %s", existing_user.email, exc)

        return {
            "message": "Invitation accepted -- log in to access the organization",
            "organization_id": str(invitation.organization_id), "role": invitation.role.value,
        }

    # No account yet -- create one, mirroring /auth/register's own
    # validation exactly (breach check, similarity check, password
    # history seeding), minus the auto-created default organization
    # (see this function's own docstring for why).
    if not payload.accept_terms:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You must accept the terms of service")
    if payload.password is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A password is required to create your account")

    if await is_password_known_breached(payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has appeared in a known data breach -- please choose a different one.",
        )
    if is_password_too_similar(payload.password, invitation.email, payload.full_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password is too similar to your email or name -- please choose a more distinct one.",
        )

    hashed_password = hash_password(payload.password)
    new_user = User(
        email=invitation.email, hashed_password=hashed_password, full_name=payload.full_name,
        consent_given_at=dt.datetime.now(dt.timezone.utc), terms_version=settings.TERMS_VERSION,
    )
    db.add(new_user)
    await db.flush()
    await record_password_change(db, new_user.id, hashed_password)

    db.add(OrganizationMember(organization_id=invitation.organization_id, user_id=new_user.id, role=invitation.role, invited_by=invitation.invited_by))
    invitation.accepted_at = dt.datetime.now(dt.timezone.utc)

    await create_and_send_email_otp(db, new_user)
    tokens = await issue_session(db, response, request, new_user.id)
    await log_audit_action(
        db, user_id=new_user.id, action=AuditAction.INVITATION_ACCEPTED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(invitation.organization_id), "invitation_id": str(invitation.id), "created_account": True},
    )
    await db.commit()

    return {
        "message": "Account created and invitation accepted", "organization_id": str(invitation.organization_id),
        "role": invitation.role.value, "access_token": tokens.access_token, "token_type": "bearer",
    }
