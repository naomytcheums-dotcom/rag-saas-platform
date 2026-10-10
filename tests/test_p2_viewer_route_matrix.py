"""Spec 1.2.6 -- a read-only viewer must not reach any organization write route (route x role contract).

Every POST / PUT / PATCH / DELETE operation under /organizations/{org_id}/... is called by a viewer of the organization with an empty body. The authorization
dependency runs before body validation, so 403 / 404 means the viewer was stopped; anything else (typically 422) means the viewer got past the gate. The only
routes allowed to do that are listed below with the reason; a NEW viewer-reachable write route makes this test fail until someone decides it is intended."""

import re
import uuid

from sqlalchemy import select

from api.main import app
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User

# route -> why a viewer may reach it
VIEWER_ALLOWED = {
    ("POST", "/organizations/{org_id}/search"): "read-only search, expressed as POST because of the request body",
    ("POST", "/organizations/{org_id}/notifications/templates/preview"): "renders a preview, stores nothing",
    ("POST", "/organizations/{org_id}/plugins/{plugin_id}/reviews"): "any member can review a marketplace plugin",
}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


async def test_a_viewer_cannot_reach_any_organization_write_route_except_the_allowed_ones(client, db_session):
    owner = (await client.post("/auth/register", json={"email": "vm-owner@example.com", "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": "Viewer Matrix"}, headers=_h(owner))).json()["id"]
    viewer_token = (await client.post("/auth/register", json={"email": "vm-viewer@example.com", "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    viewer = await db_session.scalar(select(User).where(User.email == "vm-viewer@example.com"))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org), user_id=viewer.id, role=OrganizationRole.viewer))
    await db_session.commit()

    checked, reachable = 0, set()
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith("/organizations/{org_id}"):
            continue
        for method in operations:
            if method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
                continue
            url = re.sub(r"\{[^}]+\}", lambda m: org if m.group(0) == "{org_id}" else str(uuid.uuid4()), path)
            response = await client.request(method.upper(), url, headers=_h(viewer_token), json={})
            checked += 1
            if response.status_code not in (403, 404, 405):
                reachable.add((method.upper(), path))
    assert checked > 150, f"the OpenAPI schema only exposed {checked} organization write operations"
    assert reachable == set(VIEWER_ALLOWED), f"unexpected viewer-reachable write routes: {sorted(reachable - set(VIEWER_ALLOWED))}; no longer reachable: {sorted(set(VIEWER_ALLOWED) - reachable)}"
