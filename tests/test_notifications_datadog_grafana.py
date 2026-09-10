"""Real Grafana Cloud Loki/Tempo status, Datadog status, and Twilio
SMS/WhatsApp -- all honestly 501/not-configured until real credentials
exist, all wired via os.getenv() only (no secret in code)."""


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_admin(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.admin
    await db_session.commit()
    return token


async def test_loki_status_reflects_real_config_state(client, db_session, register_payload):
    from api.config import settings

    token = await _make_admin(client, db_session, register_payload)
    response = await client.get("/monitoring/loki/status", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["configured"] == bool(settings.LOKI_HOST)


async def test_datadog_status_reflects_real_config_state(client, db_session, register_payload):
    from api.config import settings

    token = await _make_admin(client, db_session, register_payload)
    response = await client.get("/monitoring/datadog/status", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["configured"] == bool(settings.DD_API_KEY)


async def test_send_sms_honestly_501s_without_full_twilio_config(client, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Notif Org"}, headers=_auth_header(token))).json()["id"]

    response = await client.post(f"/organizations/{org_id}/notifications/sms/send", json={"to": "+15551234567", "message": "test"}, headers=_auth_header(token))
    assert response.status_code == 501


async def test_send_sms_succeeds_with_mocked_twilio_client(client, db_session, register_payload, monkeypatch):
    from api.config import settings
    from api.services import twilio_sms

    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15550000000")

    class _FakeMessage:
        sid = "SMtest123"

    class _FakeMessages:
        def create(self, **kwargs):
            return _FakeMessage()

    class _FakeClient:
        messages = _FakeMessages()

    monkeypatch.setattr(twilio_sms, "_client", lambda: _FakeClient())

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Notif Org"}, headers=_auth_header(token))).json()["id"]

    response = await client.post(f"/organizations/{org_id}/notifications/sms/send", json={"to": "+15551234567", "message": "Hello"}, headers=_auth_header(token))
    assert response.status_code == 201
    assert response.json()["status"] == "sent"
    assert response.json()["provider_message_id"] == "SMtest123"

    listing = await client.get(f"/organizations/{org_id}/notifications/sms", headers=_auth_header(token))
    assert len(listing.json()) == 1
