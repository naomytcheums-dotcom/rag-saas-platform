"""
Objectif 10 -- one real user's full lifecycle through Partie 1.1, in order,
against real infrastructure: Supabase Postgres, real Celery+Redis (the
purge step actually dispatches through a running worker, not .apply()),
and real S3-compatible storage for the avatar. Email sending is
monkeypatched here only because Objective 2 already proved real Resend
delivery separately (tests/test_auth_api.py) -- running this scenario
repeatedly must not spam a real inbox every time the suite runs.

Steps, matching the requested scenario 1:1:
 1. register                         11. avatar upload
 2. verification email "received"     12. list sessions
 3. verify email                      13. revoke a session
 4. login                             14. request password reset
 5. session created                   15. reset password
 6. enable 2FA                        16. soft-delete the account
 7. logout                            17. confirm deletion_scheduled_at is set
 8. login again, with 2FA             18. run the real purge task via Celery
 9. view profile                      19. confirm the account is gone
10. update preferences

Requires a live Celery worker consuming CELERY_BROKER_URL (see README.md's
"Running the full Celery chain" section) -- skips if none responds to a
ping within a few seconds, same reachability-skip pattern as the other
integration test files.
"""

import uuid

import boto3
import pyotp
import pytest
import pytest_asyncio
from botocore.exceptions import ClientError
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from api.config import settings
from api.main import app
from api.models.user import User
from api.tasks.celery_app import celery_app

# Loop scope is set globally to "session" in pyproject.toml, not pinned
# per-file here -- see that file's comment for why.


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping the E2E lifecycle test ({exc})")
    yield engine
    await engine.dispose()


@pytest.fixture(scope="module")
def s3_client():
    if not (settings.S3_BUCKET_NAME and settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY):
        pytest.skip("S3_* env vars are not configured -- skipping the E2E lifecycle test")
    client = boto3.client(
        "s3", endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )
    try:
        client.list_objects_v2(Bucket=settings.S3_BUCKET_NAME, MaxKeys=1)
    except ClientError as exc:
        pytest.skip(f"S3 bucket is not reachable -- skipping the E2E lifecycle test ({exc})")
    return client


@pytest.fixture(scope="module", autouse=True)
def _require_live_worker():
    try:
        pong = celery_app.control.inspect(timeout=3).ping()
    except Exception:
        pong = None
    if not pong:
        pytest.skip(
            "No live Celery worker responded to a ping -- start one with "
            "`python -m celery -A api.tasks.celery_app worker --loglevel=info --pool=solo` "
            "(add --pool=solo only on Windows) before running this test"
        )


PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c626001000000050001a5f645400000000049454e44ae426082"
)


async def test_full_user_lifecycle(pg_engine, s3_client, monkeypatch):
    email = f"e2e-lifecycle-{uuid.uuid4().hex[:10]}@example.com"
    password = "correct-horse-battery-staple"

    captured_otp = {}
    captured_reset = {}
    monkeypatch.setattr("api.services.verification.send_verification_code_email", lambda to, code: captured_otp.update(code=code))
    monkeypatch.setattr("api.services.password_reset.send_password_reset_email", lambda to, link: captured_reset.update(link=link))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        try:
            # 1-2. register (fires the verification email -- step 2 "received")
            register = await client.post("/auth/register", json={
                "email": email, "password": password, "full_name": "E2E Lifecycle", "accept_terms": True,
            })
            assert register.status_code == 201, register.text
            access_token = register.json()["access_token"]
            assert captured_otp.get("code"), "step 2 failed: no verification email was sent"

            # 3. verify email
            verify = await client.post("/auth/verify-email/confirm", json={"code": captured_otp["code"]}, headers={"Authorization": f"Bearer {access_token}"})
            assert verify.status_code == 200, verify.text

            # 4-5. login (a fresh session is created as a side effect -- confirmed via step 12's list)
            login = await client.post("/auth/login", json={"email": email, "password": password})
            assert login.status_code == 200, login.text
            access_token = login.json()["access_token"]
            auth_header = {"Authorization": f"Bearer {access_token}"}

            # 6. enable 2FA (using pyotp to compute the code exactly as a
            # real authenticator app would from the same otpauth:// secret)
            setup = await client.post("/auth/2fa/setup", headers=auth_header)
            assert setup.status_code == 200, setup.text
            totp_secret = setup.json()["secret"]
            assert setup.json()["qr_code_data_uri"].startswith("data:image/png;base64,")

            enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(totp_secret).now()}, headers=auth_header)
            assert enable.status_code == 200, enable.text

            # 7. logout (CSRF-protected, 1.1.16 -- echo back the csrf_token
            # cookie set alongside the refresh cookie at login, same as a
            # real browser's JS would)
            logout = await client.post("/auth/logout", headers={"X-CSRF-Token": client.cookies.get("csrf_token") or ""})
            assert logout.status_code == 200, logout.text

            # 8. login again -- must now stop at the MFA challenge, not tokens directly
            login2 = await client.post("/auth/login", json={"email": email, "password": password})
            assert login2.status_code == 200, login2.text
            assert login2.json().get("mfa_required") is True, "step 8 failed: 2FA was not enforced on login"
            mfa_verify = await client.post("/auth/2fa/verify-login", json={
                "mfa_token": login2.json()["mfa_token"], "code": pyotp.TOTP(totp_secret).now(),
            })
            assert mfa_verify.status_code == 200, mfa_verify.text
            access_token = mfa_verify.json()["access_token"]
            auth_header = {"Authorization": f"Bearer {access_token}"}

            # 9. view profile
            profile = await client.get("/account/me", headers=auth_header)
            assert profile.status_code == 200 and profile.json()["email"] == email

            # 10. update preferences
            prefs = await client.patch("/account/preferences", json={"locale": "fr", "timezone": "Africa/Douala"}, headers=auth_header)
            assert prefs.status_code == 200
            assert prefs.json()["locale"] == "fr" and prefs.json()["timezone"] == "Africa/Douala"

            # 11. avatar upload
            avatar = await client.post("/account/avatar", headers=auth_header, files={"file": ("avatar.png", PNG_BYTES, "image/png")})
            assert avatar.status_code == 200, avatar.text
            avatar_url = avatar.json()["avatar_url"]

            # 12. list sessions
            sessions = await client.get("/sessions", headers=auth_header)
            assert sessions.status_code == 200
            session_list = sessions.json()
            assert len(session_list) >= 1
            current_session_id = next(s["id"] for s in session_list if s["is_current"])

            # 13. revoke that session -- the very cookie used to make this
            # call must stop working immediately afterwards. It's the
            # caller's own current session, so revoke_session_by_id also
            # clears both cookies on this response (1.1.9 + 1.1.16) --
            # a plain refresh call now hits the CSRF gate first, same
            # reasoning as tests/test_auth_api.py's
            # test_logout_revokes_session.
            revoke = await client.delete(f"/sessions/{current_session_id}", headers=auth_header)
            assert revoke.status_code == 200, revoke.text
            assert client.cookies.get("refresh_token") is None
            refresh_after_revoke = await client.post("/auth/refresh", headers={"X-CSRF-Token": ""})
            assert refresh_after_revoke.status_code == 403

            # 14-15. password reset (access_token from step 8 is still
            # valid -- it's a stateless JWT, independent of the session
            # row just revoked -- so it still authorizes account actions
            # up to its own 15-minute expiry)
            forgot = await client.post("/auth/password/forgot", json={"email": email})
            assert forgot.status_code == 200
            assert captured_reset.get("link"), "step 14 failed: no reset email was sent"
            reset_token = captured_reset["link"].split("token=")[1]

            new_password = "a-brand-new-e2e-password"
            reset = await client.post("/auth/password/reset", json={"token": reset_token, "new_password": new_password})
            assert reset.status_code == 200, reset.text

            relogin = await client.post("/auth/login", json={"email": email, "password": new_password})
            assert relogin.status_code == 200
            assert relogin.json().get("mfa_required") is True  # 2FA is still enabled through the password reset
            mfa_verify2 = await client.post("/auth/2fa/verify-login", json={
                "mfa_token": relogin.json()["mfa_token"], "code": pyotp.TOTP(totp_secret).now(),
            })
            access_token = mfa_verify2.json()["access_token"]
            auth_header = {"Authorization": f"Bearer {access_token}"}

            # 16. soft-delete the account
            delete = await client.delete("/account/me", headers=auth_header)
            assert delete.status_code == 200, delete.text

            # 17. confirm deletion_scheduled_at is set, account deactivated
            async with pg_engine.connect() as conn:
                row = (await conn.execute(select(User.is_active, User.deleted_at, User.deletion_scheduled_at).where(User.email == email))).one()
            assert row.is_active is False
            assert row.deleted_at is not None
            assert row.deletion_scheduled_at is not None

            # Login must be refused post-soft-delete, before the purge even runs
            login_after_delete = await client.post("/auth/login", json={"email": email, "password": new_password})
            assert login_after_delete.status_code == 401
        finally:
            pass  # nothing to clean up here anymore -- step 18's real purge deletes the S3 avatar itself, see below

    # 18. run the real purge task -- but deletion_scheduled_at is 30 days
    # out, so it would not be picked up today. Backdate it directly (the
    # same thing the passage of 30 real days would do), then dispatch
    # through the real broker to the real worker, not .apply().
    async with pg_engine.begin() as conn:
        await conn.execute(text("UPDATE users SET deletion_scheduled_at = now() - interval '1 day' WHERE email = :email"), {"email": email})

    from api.tasks.account_purge import purge_deleted_accounts
    result = purge_deleted_accounts.delay()
    purged_count = result.get(timeout=30)
    assert purged_count >= 1

    # 19a. confirm the avatar's S3 object was cleaned up by the purge
    # itself, not orphaned -- exercises the fix for the "purge leaves an
    # orphaned avatar" gap.
    avatar_key = avatar_url.split(f"/public/{settings.S3_BUCKET_NAME}/", 1)[1]
    with pytest.raises(ClientError):
        s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=avatar_key)

    # 19b. confirm the account itself is actually gone
    async with pg_engine.connect() as conn:
        remaining = (await conn.execute(select(User.id).where(User.email == email))).first()
    assert remaining is None, "step 19 failed: account still exists after the purge task ran"
