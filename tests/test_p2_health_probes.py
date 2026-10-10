"""Specs 11.3.7 / 11.3.8 -- vector store and LLM provider probes in the admin system health. Fast SQLite suite."""

from sqlalchemy import select

from api.config import settings
from api.models.user import User, UserRole
from api.services.admin_monitoring import llm_providers_status, vector_store_status


async def test_vector_store_is_reported_as_not_applicable_on_sqlite(db_session):
    assert (await vector_store_status(db_session)).startswith("not applicable")


async def test_llm_providers_report_configuration_without_revealing_keys(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-secret-value")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    result = llm_providers_status()
    assert result["anthropic"] == "configured" and result["openai"] == "not configured"
    assert "secret" not in str(result)
    assert set(result) == {"anthropic", "openai", "gemini", "mistral"}


async def test_admin_health_endpoint_includes_the_new_probes_and_stays_admin_only(client, db_session, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/admin/monitoring/health", headers=h)).status_code == 404  # anti-enumeration for non-admins
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.admin
    await db_session.commit()
    body = (await client.get("/admin/monitoring/health", headers=h)).json()
    assert body["database"] == "ok"
    assert body["vector_store"].startswith("not applicable")
    assert set(body["llm_providers"]) == {"anthropic", "openai", "gemini", "mistral"}
