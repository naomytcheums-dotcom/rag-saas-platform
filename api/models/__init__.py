"""
Import every model module here so Base.metadata is fully populated as soon
as `api.models` is imported once -- Alembic's env.py and the test DB
fixture both rely on that (a model class that's never imported never
registers its table).
"""

from api.database import Base
from api.models.consent_reactivation_token import ConsentReactivationToken
from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken
from api.models.oauth import OAuthAccount
from api.models.recovery_code import TwoFactorRecoveryCode
from api.models.restore_token import AccountRestoreToken
from api.models.session import Session
from api.models.token import EmailVerificationToken, PasswordResetToken
from api.models.user import User

__all__ = [
    "Base", "User", "OAuthAccount", "Session", "PasswordResetToken", "EmailVerificationToken",
    "TwoFactorRecoveryCode", "AccountRestoreToken", "TwoFactorLockoutRecoveryToken", "ConsentReactivationToken",
]
