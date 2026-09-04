"""Partie 5.1.7 -- tool and LLM fallback chains. Fast SQLite suite."""

import pytest
from sqlalchemy import select

from api.models.user import User, UserRole
from api.services.fallback import (
    delete_tool_fallbacks, execute_with_fallback, get_llm_fallback, get_tool_fallback, get_tool_fallback_chain,
    set_llm_fallback, set_tool_fallback,
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


async def _ok(**kwargs) -> str:
    return "primary-ok"


async def _always_fails(**kwargs) -> str:
    raise RuntimeError("primary failed")


async def _fallback_ok(**kwargs) -> str:
    return "fallback-ok"


PRIMARY_TOOL = ToolSpec(name="primary", description="", parameters={}, capability_tags=(), handler=_always_fails)
WORKING_FALLBACK = ToolSpec(name="fallback", description="", parameters={}, capability_tags=(), handler=_fallback_ok)
BROKEN_FALLBACK = ToolSpec(name="broken-fallback", description="", parameters={}, capability_tags=(), handler=_always_fails)


# --------------------------------------- get/set_tool_fallback --


async def test_get_tool_fallback_returns_none_when_unconfigured(db_session):
    assert await get_tool_fallback(db_session, "never-configured") is None


async def test_set_and_get_tool_fallback(db_session):
    await set_tool_fallback(db_session, "primary", "fallback", priority=1)
    await db_session.commit()
    assert await get_tool_fallback(db_session, "primary") == "fallback"


async def test_get_tool_fallback_chain_is_ordered_by_priority(db_session):
    await set_tool_fallback(db_session, "primary", "second", priority=2)
    await set_tool_fallback(db_session, "primary", "first", priority=1)
    await db_session.commit()

    assert await get_tool_fallback_chain(db_session, "primary") == ["first", "second"]


async def test_delete_tool_fallbacks_removes_every_priority(db_session):
    await set_tool_fallback(db_session, "primary", "first", priority=1)
    await set_tool_fallback(db_session, "primary", "second", priority=2)
    await db_session.commit()

    removed = await delete_tool_fallbacks(db_session, "primary")
    await db_session.commit()

    assert removed == 2
    assert await get_tool_fallback_chain(db_session, "primary") == []


# --------------------------------------- execute_with_fallback --


async def test_execute_with_fallback_uses_primary_when_it_succeeds():
    result = await execute_with_fallback(ToolSpec(name="p", description="", parameters={}, capability_tags=(), handler=_ok), {}, [])
    assert result == "primary-ok"


async def test_execute_with_fallback_falls_back_on_a_real_primary_failure():
    """Validation criterion: le fallback fonctionne."""
    result = await execute_with_fallback(PRIMARY_TOOL, {}, [WORKING_FALLBACK])
    assert result == "fallback-ok"


async def test_execute_with_fallback_walks_the_real_chain():
    """Validation criterion: la chaîne de fallback fonctionne."""
    result = await execute_with_fallback(PRIMARY_TOOL, {}, [BROKEN_FALLBACK, WORKING_FALLBACK])
    assert result == "fallback-ok"


async def test_execute_with_fallback_raises_the_real_last_exception_when_all_fail():
    with pytest.raises(RuntimeError):
        await execute_with_fallback(PRIMARY_TOOL, {}, [BROKEN_FALLBACK])


async def test_execute_with_fallback_never_falls_back_when_disabled(monkeypatch):
    from api.config import settings
    monkeypatch.setattr(settings, "FALLBACK_ENABLED", False)

    with pytest.raises(RuntimeError):
        await execute_with_fallback(PRIMARY_TOOL, {}, [WORKING_FALLBACK])


# --------------------------------------- LLM fallback --


async def test_get_llm_fallback_returns_none_when_unconfigured(db_session):
    assert await get_llm_fallback(db_session, "anthropic") is None


async def test_set_and_get_llm_fallback(db_session):
    await set_llm_fallback(db_session, "anthropic", "openai")
    await db_session.commit()
    assert await get_llm_fallback(db_session, "anthropic") == "openai"


# --------------------------------------- endpoints (superadmin) --


async def test_superadmin_can_create_list_and_delete_tool_fallbacks(client, db_session, register_payload):
    token = await _register(client, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)

    created = await client.post("/admin/tools/fallback", json={"tool_name": "primary", "fallback_tool": "backup", "priority": 1}, headers=_auth_header(token))
    assert created.status_code == 200

    listing = await client.get("/admin/tools/fallback", headers=_auth_header(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    deleted = await client.delete("/admin/tools/fallback/primary", headers=_auth_header(token))
    assert deleted.status_code == 204


async def test_delete_unknown_tool_fallback_returns_404(client, db_session, register_payload):
    token = await _register(client, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)

    response = await client.delete("/admin/tools/fallback/never-configured", headers=_auth_header(token))
    assert response.status_code == 404


async def test_non_superadmin_cannot_create_tool_fallback(client, register_payload):
    """Validation criterion: sécurité (implicite, cohérent avec les autres endpoints admin)."""
    token = await _register(client, register_payload["email"], register_payload["password"])
    response = await client.post("/admin/tools/fallback", json={"tool_name": "primary", "fallback_tool": "backup"}, headers=_auth_header(token))
    assert response.status_code == 403
