"""
Etape 1.2 -- Roles & Permissions. Tests for each numbered sub-item land
here as they're implemented; 1.2.1 (Super Admin) is the first.

Fast SQLite suite (conftest.py's `client`/`db_session` fixtures) -- pure
dependency/DB logic, no external infrastructure needed, same tier as
tests/test_audit_log.py's own admin-route tests.
"""

import uuid

from sqlalchemy import select

from api.models.user import User, UserRole


async def _set_role(db_session, email: str, role: UserRole) -> None:
    user = await db_session.scalar(select(User).where(User.email == email))
    user.role = role
    await db_session.commit()


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register_and_get(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


# --------------------------------------------------------- 1.2.1 -------

async def test_regular_user_gets_403_from_the_superadmin_only_route(client, db_session, register_payload):
    access_token, _ = await _register_and_get(client, db_session, register_payload["email"], register_payload["password"])
    _, target = await _register_and_get(client, db_session, "target-regular@example.com")

    response = await client.patch(
        f"/admin/users/{target.id}/role", json={"role": "admin"}, headers=_auth_header(access_token),
    )
    assert response.status_code == 403


async def test_plain_admin_also_gets_403_from_the_superadmin_only_route(client, db_session, register_payload):
    """The core distinction this step introduces: require_admin's tier
    is NOT enough here -- only require_superadmin's stricter tier is."""
    access_token, _ = await _register_and_get(client, db_session, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.admin)
    _, target = await _register_and_get(client, db_session, "target-admin@example.com")

    response = await client.patch(
        f"/admin/users/{target.id}/role", json={"role": "admin"}, headers=_auth_header(access_token),
    )
    assert response.status_code == 403


async def test_superadmin_can_promote_a_user_to_admin(client, db_session, register_payload):
    access_token, _ = await _register_and_get(client, db_session, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)
    _, target = await _register_and_get(client, db_session, "target-promote@example.com")

    response = await client.patch(
        f"/admin/users/{target.id}/role", json={"role": "admin"}, headers=_auth_header(access_token),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    await db_session.refresh(target)
    assert target.role == UserRole.admin


async def test_superadmin_can_also_reach_every_existing_admin_only_route(client, db_session, register_payload):
    """Validation criterion: a superadmin can access ALL protected
    routes, not just the new superadmin-exclusive one -- proven against
    a real pre-existing require_admin-gated endpoint (audit finding
    19/20's GET /admin/audit-logs)."""
    access_token, _ = await _register_and_get(client, db_session, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)

    response = await client.get("/admin/audit-logs", headers=_auth_header(access_token))
    assert response.status_code == 200


async def test_cannot_demote_the_last_remaining_superadmin(client, db_session, register_payload):
    access_token, user = await _register_and_get(client, db_session, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)

    response = await client.patch(
        f"/admin/users/{user.id}/role", json={"role": "admin"}, headers=_auth_header(access_token),
    )
    assert response.status_code == 400


async def test_demoting_a_superadmin_is_allowed_when_another_superadmin_remains(client, db_session, register_payload):
    access_token, _ = await _register_and_get(client, db_session, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)
    _, second = await _register_and_get(client, db_session, "second-superadmin@example.com")
    await _set_role(db_session, "second-superadmin@example.com", UserRole.superadmin)

    response = await client.patch(
        f"/admin/users/{second.id}/role", json={"role": "user"}, headers=_auth_header(access_token),
    )
    assert response.status_code == 200

    await db_session.refresh(second)
    assert second.role == UserRole.user


async def test_updating_the_role_of_an_unknown_user_returns_404(client, db_session, register_payload):
    access_token, _ = await _register_and_get(client, db_session, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)

    response = await client.patch(
        f"/admin/users/{uuid.uuid4()}/role", json={"role": "admin"}, headers=_auth_header(access_token),
    )
    assert response.status_code == 404


async def test_role_change_is_recorded_in_the_audit_log(client, db_session, register_payload):
    from api.models.audit_log import AuditAction, AuditLog

    access_token, superadmin = await _register_and_get(client, db_session, register_payload["email"], register_payload["password"])
    await _set_role(db_session, register_payload["email"], UserRole.superadmin)
    _, target = await _register_and_get(client, db_session, "target-audited@example.com")

    await client.patch(f"/admin/users/{target.id}/role", json={"role": "admin"}, headers=_auth_header(access_token))

    row = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == AuditAction.USER_ROLE_CHANGED.value, AuditLog.user_id == superadmin.id)
    )
    assert row is not None
    assert row.success is True
