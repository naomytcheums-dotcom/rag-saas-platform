"""
Audit finding 27 -- enterprise SSO via generic OIDC (Azure AD, Okta, and
any other OIDC-conformant IdP a customer's IT department already runs).
Chosen over hand-rolled SAML 2.0 -- the spec explicitly allows either
("SAML 2.0 (ou OIDC generique)") -- because this codebase already has a
working OIDC-shaped account-linking flow to extend (api/routers/oauth.py's
Google/GitHub integration, built on Authlib) and Azure AD / Okta both
expose full OIDC discovery endpoints, whereas SAML would mean a new
XML-signing dependency (python3-saml needs the system xmlsec1 library,
not a pure-Python wheel) for a protocol this app has no other reason to
speak. See api/routers/enterprise_sso.py's module docstring for the full
reasoning and self-critique of this choice.

Deliberately a NEW pair of tables (EnterpriseSSOConnection here, plus
EnterpriseSSOAccount below) rather than extending api/models/oauth.py's
OAuthAccount/OAuthProvider: OAuthProvider is a native Postgres ENUM
(google/github), and each enterprise customer's IdP is a genuinely
distinct trust boundary configured independently by an admin (issuer,
client id/secret) -- not one more fixed value in a hardcoded list the
way Google/GitHub are.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class EnterpriseSSOConnection(Base):
    """One row per customer IdP, admin-configured via
    POST /admin/sso/connections (api/routers/enterprise_sso.py).
    email_domain is how login picks which connection applies to a given
    user (POST /auth/sso/discover) -- one active connection per domain,
    enforced by the unique constraint below."""

    __tablename__ = "enterprise_sso_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # The IdP's OIDC discovery issuer, e.g.
    # "https://login.microsoftonline.com/{tenant-id}/v2.0" (Azure AD) or
    # "https://your-org.okta.com" (Okta) -- api/security/enterprise_oidc.py
    # fetches {issuer}/.well-known/openid-configuration from this at
    # authorize/callback time rather than caching endpoints, so an IdP
    # rotating its own signing keys/endpoints never requires an admin to
    # update this row.
    issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # Fernet-encrypted (api/security/secret_encryption.py) -- see that
    # module's docstring.
    client_secret_encrypted: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("email_domain", name="uq_enterprise_sso_connections_email_domain"),)


class EnterpriseSSOAccount(Base):
    """Links a User to one EnterpriseSSOConnection -- the enterprise-SSO
    analog of api/models/oauth.py's OAuthAccount, same shape and same
    account-linking trust model (see api/routers/enterprise_sso.py's
    _find_or_create_user, which mirrors api/routers/oauth.py's function
    of the same name almost line for line)."""

    __tablename__ = "enterprise_sso_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprise_sso_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The IdP's own stable subject identifier (the `sub` claim) -- not
    # the email, for the same reason api/models/oauth.py's
    # provider_account_id isn't: an IdP-side email change must not orphan
    # the link.
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("connection_id", "provider_subject", name="uq_enterprise_sso_accounts_connection_subject"),
    )
