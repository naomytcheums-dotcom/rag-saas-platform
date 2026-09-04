"""Partie 5.1.4 -- tool timeout. Fast SQLite suite."""

import asyncio

import pytest
from sqlalchemy import select

from api.models.user import User, UserRole
from api.services.tool_timeout import (
    ToolTimeoutError, execute_tool_with_timeout, get_default_timeout, get_tool_timeout, set_tool_timeout,
)
from api.services.tools import ToolSpec


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _set_role(db_session, email: str, role: UserRole) -> None:
    user = await db_session.scalar(select(User).where(User.email == email))
    user.role = role
    await db_session.commit()


async def _register(client, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    return (await client.post("/auth/register", json=payload)).json()["access_token"]


async def _slow_handler(**kwargs) -> str:
    await asyncio.Event().wait()


SLOW_TOOL = ToolSpec(name="slow-tool", description="hangs forever", parameters={}, capability_tags=(), handler=_slow_handler)


async def _fast_handler(value: str) -> str:
    return value.upper()


FAST_TOOL = ToolSpec(name="fast-tool", description="returns instantly", parameters={}, capability_tags=(), handler=_fast_handler)


# --------------------------------------- execute_tool_with_timeout --


async def test_execute_tool_with_timeout_returns_a_real_result():
    """Validation criterion: le timeout n'est pas atteint."""
    result = await execute_tool_with_timeout(FAST_TOOL, {"value": "hi"}, timeout=5)
    assert result == "HI"


async def test_execute_tool_with_timeout_raises_on_a_real_timeout():
    """Validation criterion: le timeout fonctionne."""
    with pytest.raises(ToolTimeoutError):
        await execute_tool_with_timeout(SLOW_TOOL, {}, timeout=0.05)


async def test_execute_tool_with_timeout_uses_the_real_default_when_unset():
    assert get_default_timeout() == 30.0


async def test_execute_tool_with_timeout_retries_a_real_timeout_when_configured(monkeypatch):
    """Validation criterion (Partie 5.1.6 integration): un vrai timeout
    peut être retenté."""
    monkeypatch.setattr("asyncio.sleep", lambda *_a, **_k: _noop())

    calls = {"count": 0}

    async def _flaky_then_fast(**kwargs) -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            await asyncio.Event().wait()
        return "ok"

    flaky_tool = ToolSpec(name="flaky", description="", parameters={}, capability_tags=(), handler=_flaky_then_fast)
    result = await execute_tool_with_timeout(flaky_tool, {}, timeout=0.05, max_retries=2)
    assert result == "ok"
    assert calls["count"] == 2


async def test_execute_tool_with_timeout_does_not_retry_a_real_handler_error():
    """A real handler failure (not a timeout) must never be blindly
    retried."""
    async def _always_bad(**kwargs) -> str:
        raise ValueError("bad input")

    bad_tool = ToolSpec(name="bad", description="", parameters={}, capability_tags=(), handler=_always_bad)
    with pytest.raises(ValueError):
        await execute_tool_with_timeout(bad_tool, {}, timeout=5, max_retries=3)


async def _noop():
    return None


# --------------------------------------- get/set_tool_timeout --


async def test_get_tool_timeout_falls_back_to_the_real_default(db_session):
    assert await get_tool_timeout(db_session, "never-configured") == get_default_timeout()


async def test_set_tool_timeout_persists_a_real_override(db_session):
    await set_tool_timeout(db_session, "slow-tool", 60.0)
    await db_session.commit()
    assert await get_tool_timeout(db_session, "slow-tool") == 60.0


async def test_set_tool_timeout_rejects_a_value_below_the_real_minimum(db_session):
    with pytest.raises(ValueError):
        await set_tool_timeout(db_session, "slow-tool", 1.0)


async def test_set_tool_timeout_rejects_a_value_above_the_real_maximum(db_session):
    with pytest.raises(ValueError):
        await set_tool_timeout(db_session, "slow-tool", 999.0)


# --------------------------------------- endpoints (superadmin) --


async def test_superadmin_can_list_and_update_tool_timeouts(client, db_session, register_payload):
    token = await _register(client, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)

    response = await client.patch("/admin/tools/slow-tool/timeout", json={"timeout_seconds": 45}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["timeout_seconds"] == 45

    listing = await client.get("/admin/tools/timeout", headers=_auth_header(token))
    assert listing.status_code == 200
    assert any(row["tool_name"] == "slow-tool" for row in listing.json())


async def test_non_superadmin_cannot_update_tool_timeouts(client, register_payload):
    """Validation criterion: sécurité."""
    token = await _register(client, register_payload["email"], register_payload["password"])
    response = await client.patch("/admin/tools/slow-tool/timeout", json={"timeout_seconds": 45}, headers=_auth_header(token))
    assert response.status_code == 403


async def test_update_tool_timeout_rejects_an_invalid_value(client, db_session, register_payload):
    token = await _register(client, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)

    response = await client.patch("/admin/tools/slow-tool/timeout", json={"timeout_seconds": 9999}, headers=_auth_header(token))
    assert response.status_code == 400
