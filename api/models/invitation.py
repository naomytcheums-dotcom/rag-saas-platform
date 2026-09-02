"""
Partie 1.3.4 -- email-based invitations: an org Manager+ invites an
email address (not necessarily an existing account) to join with a
proposed role; the recipient accepts via a link containing a one-time
token. Closes the gap api/services/email.py's send_organization_member_added_email
docstring already names: "This app has no email-based invitation LINK
yet (item 1.3.4) -- this is the notification for an immediate add, not
an invitation someone has to accept." That immediate-add path
(api/routers/organization_members.py's invite_organization_member,
Etape 1.2.3/1.2.4) is UNCHANGED and still exists side by side with this
-- it adds an EXISTING account right away; this creates a pending
invitation an email address accepts on its own time, existing account
or not.

`token_hash`, not `token` -- same "never store the raw secret, only its
SHA-256" convention as PasswordResetToken/EmailVerificationToken
(api/models/token.py): a DB leak or backup must not directly hand out
usable invitation links.

One row per (organization_id, email) -- re-inviting the same address
updates this SAME row (fresh token, fresh expiry, accepted_at cleared)
rather than erroring or creating a duplicate; see
api/security/invitations.py's create_or_reissue_invitation.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base
from api.models.organization import OrganizationRole


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    # Reuses the SAME native Postgres enum type organizations.role
    # already created (name="organizationrole", SQLAlchemy's default
    # derivation from the class name) -- create_type=False so this
    # table's own CREATE TABLE doesn't try to CREATE TYPE a second time.
    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole, name="organizationrole", create_type=False), nullable=False,
    )
    # SET NULL, not CASCADE -- an invitation outlives the account that
    # sent it, same reasoning as OrganizationMember.invited_by.
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_invitations_org_email"),
    )
