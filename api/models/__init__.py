"""
Import every model module here so Base.metadata is fully populated as soon
as `api.models` is imported once -- Alembic's env.py and the test DB
fixture both rely on that (a model class that's never imported never
registers its table).
"""

from api.database import Base
from api.models.audit_log import AuditLog
from api.models.consent_reactivation_token import ConsentReactivationToken
from api.models.enterprise_sso import EnterpriseSSOAccount, EnterpriseSSOConnection
from api.models.jwt_signing_key import JWTSigningKey
from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken
from api.models.oauth import OAuthAccount
from api.models.organization import Organization, OrganizationMember
from api.models.password_history import PasswordHistory
from api.models.recovery_code import TwoFactorRecoveryCode
from api.models.restore_token import AccountRestoreToken
from api.models.revoked_token import RevokedAccessToken
from api.models.session import Session
from api.models.token import EmailVerificationToken, PasswordResetToken
from api.models.user import User
from api.models.webauthn_credential import WebAuthnCredential
from api.models.workspace import Workspace

__all__ = [
    "Base", "User", "OAuthAccount", "Session", "PasswordResetToken", "EmailVerificationToken",
    "TwoFactorRecoveryCode", "AccountRestoreToken", "TwoFactorLockoutRecoveryToken", "ConsentReactivationToken",
    "RevokedAccessToken", "PasswordHistory", "AuditLog", "JWTSigningKey", "WebAuthnCredential",
    "EnterpriseSSOConnection", "EnterpriseSSOAccount", "Organization", "OrganizationMember", "Workspace",
]
