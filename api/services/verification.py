"""
1.1.4 -- issuing and sending a fresh email OTP. Shared by the register flow
(auth.py, which sends the first code) and verify.py's "resend code"
endpoint, so both paths create tokens the exact same way.

A failed email send is logged, not raised further up -- see
api/services/email.py's docstring: delivery failure must never block
account creation or block a user from re-requesting a code.

Real bug fixed here (2026-09-15, found via live persona-based testing):
api/services/email.py's send_*_email functions call `httpx.post` (the
sync, blocking client), not `httpx.AsyncClient`. Calling
send_verification_code_email directly from this async function blocked
the whole FastAPI event loop for as long as the real Resend HTTP call
took -- confirmed directly: POST /auth/register took 22-59s wall time
against this real Resend account, while the same Resend call made in
isolation took ~2-3s and bcrypt hashing (also in this request) took
~0.3s. Concurrent requests on the same worker were serialized behind
that one blocked call, compounding the delay. Wrapping the call in
asyncio.to_thread moves the blocking I/O off the event loop without
touching email.py's sync API or its other ~30 call sites -- see that
module's own docstring for why the rest of them share the same
blocking-call issue, out of scope for this specific fix."""

import asyncio
import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.token import EmailVerificationToken
from api.models.user import User
from api.security.hashing import generate_otp_code, hash_token
from api.services.email import send_verification_code_email

logger = logging.getLogger(__name__)


async def create_and_send_email_otp(db: AsyncSession, user: User) -> None:
    """
    Generates a fresh 6-digit code, stores only its hash (with an
    expiry), and emails the raw code to the user. Does NOT commit the
    database session itself -- the caller (auth.py's register(), or
    verify.py's request_verification_code()) commits, so this can be
    composed into a larger transaction that also does other work.
    """
    code = generate_otp_code()
    token = EmailVerificationToken(
        user_id=user.id,
        code_hash=hash_token(code),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=settings.EMAIL_OTP_EXPIRE_MINUTES),
    )
    db.add(token)
    await db.flush()

    try:
        await asyncio.to_thread(send_verification_code_email, user.email, code)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send verification email to %s: %s", user.email, exc)
