"""
The User model backs 1.1.1-1.1.4 and 1.1.7, 1.1.10-1.1.14 directly (auth,
2FA, soft-delete, RGPD consent, profile, preferences); OAuthAccount and
Session (1.1.5-1.1.6, 1.1.8-1.1.9) live in their own modules since they're
one-to-many from User, not columns on it.

hashed_password is nullable: a user who only ever registers via Google/
GitHub OAuth (1.1.5/1.1.6) never sets a password, and login_password()
below refuses to succeed for such an account instead of comparing against
None/empty-string (a real footgun a naive `verify_password(pw, user.hashed_password)`
would hit).
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.models.organization import OrganizationRole


class UserRole(str, enum.Enum):
    """5.1 -- prep for Partie 1.2's RBAC work, same pattern as
    api/models/oauth.py's OAuthProvider (a native Postgres ENUM via
    SQLAlchemy's Enum type, not a free-text column). Replaces the old
    is_superadmin boolean, which was reserved for this exact purpose
    (see its removal in Alembic migration 0010) but could only ever
    represent two tiers -- this can grow a third (or more) without
    another schema change, which is the whole point of adding it now
    rather than waiting for 1.2 to need it."""

    user = "user"
    admin = "admin"
    superadmin = "superadmin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # 320 = the theoretical max length of an RFC 5321 email address (64
    # local-part + @ + 255 domain). Unique + indexed since every login
    # and registration check looks a user up by email.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    # bcrypt hash, never the plaintext password. None for an OAuth-only
    # account -- see this file's top docstring.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # False for a soft-deleted account (see deleted_at below) -- checked
    # on every login and every access-token validation, so a deactivated
    # account is locked out everywhere immediately, not just from new logins.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 1.1.4 -- flips to True once the emailed 6-digit code is confirmed.
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 5.1 -- not enforced by anything in Partie 1.1 yet (no route checks
    # it), but a real column with a real constrained type from day one,
    # so Partie 1.2's RBAC work is a matter of *checking* this field, not
    # inventing it under production data. See UserRole above.
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user, nullable=False)

    # Partie 11.3 -- a real platform-admin suspend/reactivate. Reuses the
    # existing `is_active` flag (already checked on every login/token
    # validation, see that column's own comment above) rather than
    # inventing a second boolean an admin suspend and the real, existing
    # soft-delete flow (DELETE /account/me) could disagree about --
    # `suspended_at`/`suspended_reason` exist only to distinguish "an
    # admin suspended this account" from "the user deleted their own
    # account" (deleted_at below) for real, since both set is_active=False.
    suspended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # -- 1.1.7 2FA (TOTP) ----------------------------------------------------
    # The shared secret used to generate/verify 6-digit codes. Set by
    # /auth/2fa/setup but only *enforced* once totp_enabled is True (see
    # api/routers/two_factor.py for why those are two separate steps).
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # -- 1.1.13 profile ----------------------------------------------------
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Public URL of the uploaded avatar image (see api/services/storage.py)
    # -- the file itself lives in S3/R2/Supabase Storage, not the database.
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # -- 1.1.14 preferences --------------------------------------------------
    locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)  # UI language, e.g. "en", "fr"
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)  # IANA name, e.g. "Africa/Douala"

    # -- 1.1.12 RGPD consent -------------------------------------------------
    # Captured once, at registration, and never edited afterwards -- see
    # api/routers/auth.py's register(). Recording *when* consent was
    # given and to *which version* of the terms is what makes this a
    # real compliance record rather than just a checkbox that was ticked.
    consent_given_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Set by POST /account/consent/withdraw -- distinct from deleted_at/
    # deletion_scheduled_at below: withdrawing consent deactivates the
    # account immediately but does NOT schedule a purge, since objecting
    # to further processing (RGPD Art. 7(3)/21) is a different right from
    # asking for erasure (Art. 17). In practice this field and deleted_at
    # are never both set at once: both withdraw_consent() and
    # delete_account() (api/routers/account.py) require is_active=True to
    # even be reached, and each sets is_active=False as its very first
    # effect -- so once one fires, the other is unreachable for that
    # account until its own reactivation path (which clears exactly this
    # field, or deleted_at/deletion_scheduled_at respectively) restores
    # is_active=True first.
    consent_withdrawn_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # -- 1.1.10 soft-delete --------------------------------------------------
    # Both null for a normal, active account. Set together by
    # DELETE /account/me: deleted_at records when the user asked to be
    # deleted, deletion_scheduled_at is deleted_at + the grace period
    # (ACCOUNT_PURGE_DELAY_DAYS) -- the actual hard delete, once that date
    # passes, is done by api/tasks/account_purge.py, not automatically.
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_scheduled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set by api/tasks/account_deletion_reminder.py once the pre-purge
    # reminder email has actually been sent, so the daily sweep doesn't
    # re-send it every day for the remaining grace window. Cleared by
    # DELETE /account/me (a fresh deletion cycle) and by
    # POST /account/restore/confirm (the cycle was cancelled), so a
    # LATER deletion is eligible for its own reminder.
    deletion_reminder_sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # cascade="all, delete-orphan": deleting a User in the ORM also
    # deletes their oauth_accounts/sessions rows -- belt-and-suspenders
    # alongside the database's own ON DELETE CASCADE foreign keys (see
    # the Alembic migration), so it's correct even for code paths that
    # go through the ORM's session.delete() instead of a raw SQL DELETE.
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    # Etape 1.2.2 -- one row per organization this user belongs to,
    # carrying their role in it (api/models/organization.py's
    # OrganizationMember). Like oauth_accounts/sessions above, this
    # codebase never lazy-accesses ORM relationships from an async
    # request handler -- every route that needs this data loads it
    # explicitly (selectinload) or queries OrganizationMember directly;
    # this relationship exists for cascade-delete (removing a user also
    # removes their memberships) and for the two properties below, which
    # assume it's already loaded.
    organization_memberships: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="user", foreign_keys="OrganizationMember.user_id", cascade="all, delete-orphan"
    )

    @property
    def is_deleted(self) -> bool:
        """True once DELETE /account/me has been called (soft-deleted),
        even before the grace period ends and the row is actually
        purged. Checked alongside is_active everywhere login/access is
        gated, so a soft-deleted account is locked out right away."""
        return self.deleted_at is not None

    @property
    def organizations(self) -> list["Organization"]:
        """Every organization this user is a member of, any role.
        Requires organization_memberships (and each membership's own
        .organization) to already be eager-loaded -- see that
        relationship's own comment above for why."""
        return [m.organization for m in self.organization_memberships]

    @property
    def owned_organizations(self) -> list["Organization"]:
        """The subset of `organizations` where this user holds the
        Owner role specifically. Same eager-loading requirement as
        `organizations` above."""
        return [m.organization for m in self.organization_memberships if m.role == OrganizationRole.owner]
