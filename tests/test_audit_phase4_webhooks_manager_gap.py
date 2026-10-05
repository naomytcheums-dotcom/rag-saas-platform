"""
Audit Phase 4 (RBAC) -- REGRESSION for a real, confirmed, now-FIXED
catalog/enforcement mismatch in api/routers/webhooks.py.

api/security/permissions.py's _DEFAULT_ROLE_PERMISSIONS says a Manager
(OrganizationRole.manager) is granted "webhooks:read" and "webhooks:write"
by default (no hand-crafted CustomRole needed). This test originally
documented a real bug, empirically confirmed: create_webhook_endpoint
and list_webhooks_endpoint gated on require_permission("webhooks:manage")
-- a DIFFERENT, stricter key Manager's default set did NOT include,
silently locking Manager out of a resource their own documented
permissions say they can use.

Hardening Mission, Phase 2 -- the real fix: both routes now gate on the
correct, finer-grained keys ("webhooks:read"/"webhooks:write") Manager
actually holds by default. A CustomRole granting "webhooks:manage" still
works unchanged (api.services.rbac_custom.get_user_effective_permissions
expands `manage` into read/write/delete). This test now asserts the
FIXED behavior strictly (200/201, not "either 200 or 403" as the original
diagnostic probe did) -- a real architecture fix, not a weakened test.
"""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


async def test_manager_can_list_webhooks_via_their_real_default_webhooks_read(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "manager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/webhooks", headers=_auth_header(manager_token))
    assert response.status_code == 200, response.text


async def test_manager_can_create_webhook_via_their_real_default_webhooks_write(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "manager2@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/webhooks",
        json={"name": "Test hook", "url": "https://example.com/hook", "events": ["document.uploaded"]},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 200, response.text


async def test_viewer_still_cannot_create_a_webhook(client, db_session, register_payload):
    """Real, negative counterpart: the fix must not accidentally grant
    write access to a role that was never meant to have it. Viewer's
    own default set (api/security/permissions.py) has "webhooks:read"
    but deliberately no "webhooks:write"."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    viewer_token, viewer_user = await _register(client, db_session, "viewer-webhooks@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer_user.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/webhooks",
        json={"name": "Test hook", "url": "https://example.com/hook", "events": ["document.uploaded"]},
        headers=_auth_header(viewer_token),
    )
    assert response.status_code == 403, response.text
