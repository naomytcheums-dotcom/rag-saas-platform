"""
Partie 9.4 -- real inbound-webhook signature verification for Slack
and Discord. Same real, honest "return False, never raise, for a
missing/wrong signature OR a not-yet-configured secret" convention as
`api/services/telephony.py`'s own `verify_twilio_signature`.

Teams (Bot Framework) is the one, honest exception: its own real auth
is a JWT bearer token whose signing key comes from Microsoft's live
JWKS endpoint (`https://login.botframework.com/v1/.well-known/
openidconfiguration`), not a static shared secret this codebase can
verify offline the same way -- see api/services/chat_integrations/
teams.py's own docstring for the real, honest scope this leaves open.
"""

import hashlib
import hmac
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from api.config import settings

_SLACK_MAX_CLOCK_SKEW_SECONDS = 60 * 5


def verify_slack_signature(timestamp: str | None, body: bytes, signature: str | None) -> bool:
    """Slack's real v0 HMAC-SHA256 signing scheme:
    `v0=HMAC_SHA256(signing_secret, f"v0:{timestamp}:{body}")`, timing-
    safe compared, with a real replay-window check (Slack's own docs
    require rejecting a timestamp more than 5 real minutes old)."""
    if not settings.SLACK_SIGNING_SECRET or not timestamp or not signature:
        return False
    try:
        if abs(time.time() - float(timestamp)) > _SLACK_MAX_CLOCK_SKEW_SECONDS:
            return False
    except ValueError:
        return False

    basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    computed = "v0=" + hmac.new(settings.SLACK_SIGNING_SECRET.encode("utf-8"), basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


def verify_discord_signature(timestamp: str | None, body: bytes, signature: str | None) -> bool:
    """Discord's real Ed25519 signature scheme (NOT HMAC, unlike
    Slack/Stripe/Twilio) -- `PUBLIC_KEY.verify(signature,
    timestamp + body)`. `cryptography` (already a real dependency,
    used by `api/security/secret_encryption.py`'s own Fernet) provides
    a real Ed25519 implementation -- no new dependency needed."""
    if not settings.DISCORD_PUBLIC_KEY or not timestamp or not signature:
        return False
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(settings.DISCORD_PUBLIC_KEY))
        public_key.verify(bytes.fromhex(signature), (timestamp.encode("utf-8") + body))
        return True
    except (InvalidSignature, ValueError):
        return False
