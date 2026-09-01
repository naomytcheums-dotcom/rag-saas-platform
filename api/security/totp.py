"""1.1.7 -- TOTP secret generation, enrollment QR code, and verification."""

import base64
from io import BytesIO

import pyotp
import qrcode


def generate_totp_secret() -> str:
    """A fresh random secret for one user's 2FA enrollment (base32-encoded,
    the standard TOTP format every authenticator app expects)."""
    return pyotp.random_base32()


def totp_provisioning_qr_data_uri(secret: str, account_email: str, issuer: str = "RAG Assistant") -> str:
    """A data: URI PNG the frontend can drop straight into an <img src=""> --
    avoids a round trip through object storage for an artifact that's only
    ever needed once, during enrollment."""
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=issuer)
    image = qrcode.make(uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_totp_code(secret: str, code: str) -> bool:
    """True if `code` is the current (or one-step-adjacent) 6-digit code
    for this secret -- the same check used by /auth/2fa/enable, /disable,
    and /verify-login."""
    # valid_window=1 tolerates one 30s step of clock drift between the
    # user's authenticator app and the server, standard TOTP practice.
    return pyotp.TOTP(secret).verify(code, valid_window=1)
