"""Partie 5.1.5 -- per-tool token budget. Fast SQLite suite."""

import pytest
from sqlalchemy import select

from api.models.user import User, UserRole
from api.services.tool_budget import (
    check_tool_budget, get_tool_budget, get_tool_usage, reset_tool_budget, set_tool_budget, track_tool_usage,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _set_role(db_session, email: str, role: UserRole) -> None:
    user = await db_session.scalar(select(User).where(User.email == email))
    user.role = role
    await db_session.commit()


async def _register(client, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    return (await client.post("/auth/register", json=payload)).json()["access_token"]


# --------------------------------------- get/set_tool_budget --


async def test_get_tool_budget_falls_back_to_the_real_default(db_session):
    assert await get_tool_budget(db_session, "never-configured") == 1000


async def test_set_tool_budget_persists_a_real_override(db_session):
    await set_tool_budget(db_session, "calculator", 5000)
    await db_session.commit()
    assert await get_tool_budget(db_session, "calculator") == 5000


async def test_set_tool_budget_rejects_a_value_below_the_real_minimum(db_session):
    with pytest.raises(ValueError):
        await set_tool_budget(db_session, "calculator", 1)


async def test_set_tool_budget_rejects_a_value_above_the_real_maximum(db_session):
    with pytest.raises(ValueError):
        await set_tool_budget(db_session, "calculator", 999999)


# --------------------------------------- track/check/reset --


async def test_track_and_check_and_reset_tool_budget(db_session):
    """Validation criterion: le budget fonctionne, l'utilisation est
    suivie, et peut être réinitialisée."""
    await set_tool_budget(db_session, "calculator", 100)
    await db_session.commit()

    assert await check_tool_budget(db_session, "calculator", 50) is True
    total = await track_tool_usage(db_session, "calculator", 50)
    await db_session.commit()
    assert total == 50
    assert await get_tool_usage(db_session, "calculator") == 50

    assert await check_tool_budget(db_session, "calculator", 60) is False  # 50 + 60 > 100
    assert await check_tool_budget(db_session, "calculator", 40) is True  # 50 + 40 <= 100

    reset = await reset_tool_budget(db_session, "calculator")
    await db_session.commit()
    assert reset is True
    assert await get_tool_usage(db_session, "calculator") == 0


async def test_check_tool_budget_returns_true_when_tracking_disabled(db_session, monkeypatch):
    from api.config import settings
    monkeypatch.setattr(settings, "TOOL_BUDGET_TRACKING_ENABLED", False)
    await set_tool_budget(db_session, "calculator", 100)
    await db_session.commit()

    assert await check_tool_budget(db_session, "calculator", 99999) is True


async def test_reset_tool_budget_returns_false_for_an_unconfigured_tool(db_session):
    assert await reset_tool_budget(db_session, "never-configured") is False


async def test_track_tool_usage_creates_a_row_on_first_use(db_session):
    total = await track_tool_usage(db_session, "brand-new-tool", 30)
    await db_session.commit()
    assert total == 30
    assert await get_tool_budget(db_session, "brand-new-tool") == 1000  # real global default


# --------------------------------------- endpoints (superadmin) --


async def test_superadmin_can_list_and_update_and_reset_tool_budgets(client, db_session, register_payload):
    token = await _register(client, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)

    response = await client.patch("/admin/tools/calculator/budget", json={"budget_limit": 2000}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["budget_limit"] == 2000

    listing = await client.get("/admin/tools/budget", headers=_auth_header(token))
    assert listing.status_code == 200

    usage = await client.get("/admin/tools/usage", headers=_auth_header(token))
    assert usage.status_code == 200

    reset = await client.post("/admin/tools/calculator/budget/reset", headers=_auth_header(token))
    assert reset.status_code == 200
    assert reset.json()["tokens_used"] == 0


async def test_non_superadmin_cannot_update_tool_budgets(client, register_payload):
    """Validation criterion: sécurité."""
    token = await _register(client, register_payload["email"], register_payload["password"])
    response = await client.patch("/admin/tools/calculator/budget", json={"budget_limit": 2000}, headers=_auth_header(token))
    assert response.status_code == 403
