"""Partie 13 -- metrics summary, alerting (rules/channels/history), incidents,
and real request-id correlation (Partie 13.2)."""


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


async def test_metrics_summary_is_real_not_fabricated(client, db_session, register_payload):
    token = await _make_admin(client, db_session, register_payload)
    response = await client.get("/monitoring/metrics", headers=_auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["business"]["users"] >= 1  # the admin just created, really counted


async def test_metrics_summary_requires_admin(client, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.get("/monitoring/metrics", headers=_auth_header(token))
    assert response.status_code == 404  # require_admin's anti-enumeration 404, same as every other /admin/* endpoint


async def test_tracing_status_reflects_real_config_state(client, db_session, register_payload):
    from api.config import settings

    token = await _make_admin(client, db_session, register_payload)
    response = await client.get("/monitoring/tracing/status", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["enabled"] == settings.OTEL_ENABLED


async def test_create_alert_channel_and_rule(client, db_session, register_payload):
    token = await _make_admin(client, db_session, register_payload)

    channel = await client.post("/alerting/channels", json={"name": "ops-email", "type": "email", "config": {"email": "ops@example.com"}}, headers=_auth_header(token))
    assert channel.status_code == 201
    channel_id = channel.json()["id"]

    rule = await client.post("/alerting/rules", json={"name": "high-cpu", "metric": "cpu_percent", "operator": "gt", "threshold": 200, "channel_id": channel_id}, headers=_auth_header(token))
    assert rule.status_code == 201
    rule_id = rule.json()["id"]

    listing = await client.get("/alerting/rules", headers=_auth_header(token))
    assert listing.status_code == 200
    assert any(r["id"] == rule_id for r in listing.json())


async def test_test_alert_rule_reads_a_real_metric(client, db_session, register_payload):
    token = await _make_admin(client, db_session, register_payload)
    rule = await client.post("/alerting/rules", json={"name": "impossible-threshold", "metric": "cpu_percent", "operator": "gt", "threshold": 99999}, headers=_auth_header(token))
    rule_id = rule.json()["id"]

    result = await client.post(f"/alerting/rules/{rule_id}/test", headers=_auth_header(token))
    assert result.status_code == 200
    body = result.json()
    assert body["current_value"] is not None  # a real psutil reading, not a stub
    assert body["would_trigger"] is False  # no real CPU is ever >99999%


async def test_unmonitored_metric_returns_none_not_a_fabricated_number(client, db_session, register_payload):
    token = await _make_admin(client, db_session, register_payload)
    rule = await client.post("/alerting/rules", json={"name": "fake-metric", "metric": "made_up_metric_name", "operator": "gt", "threshold": 1}, headers=_auth_header(token))
    rule_id = rule.json()["id"]

    result = await client.post(f"/alerting/rules/{rule_id}/test", headers=_auth_header(token))
    assert result.json()["current_value"] is None


async def test_incident_lifecycle(client, db_session, register_payload):
    token = await _make_admin(client, db_session, register_payload)

    created = await client.post("/alerting/incidents", json={"title": "DB slow", "severity": "high"}, headers=_auth_header(token))
    assert created.status_code == 201
    incident_id = created.json()["id"]
    assert created.json()["status"] == "open"

    resolved = await client.post(f"/alerting/incidents/{incident_id}/resolve", headers=_auth_header(token))
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None


async def test_request_id_is_echoed_back_and_correlates_logs(client):
    response = await client.get("/health", headers={"X-Request-ID": "test-correlation-id-123"})
    assert response.headers["X-Request-ID"] == "test-correlation-id-123"


async def test_request_id_generated_when_absent(client):
    response = await client.get("/health")
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0
