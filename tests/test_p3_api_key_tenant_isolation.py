"""Phase 3 of the 2026-10-12 security audit (TEN-004): tenant isolation of the API key routes addressed by key id.

`/api-keys/{key_id}/...` carries no organization in its path: the organization is derived from the key (dependency `require_key_org_admin`). This pins that an
administrator of ANOTHER organization cannot read, change, rotate (a rotation returns a new plaintext secret), expire, throttle or delete a key it does not own,
neither through the key-id routes nor through its own organization path. Local SQLite fixtures only.
"""

from sqlalchemy import select
import uuid

from api.models.organization_api_key import OrganizationAPIKey
from test_document_idor import denied, make_tenants, snapshot

KEY_ROUTES = [
    ("GET", "/api-keys/{key_id}", None),
    ("PATCH", "/api-keys/{key_id}", {"name": "attacker-rename"}),
    ("POST", "/api-keys/{key_id}/rotate", {}),
    ("GET", "/api-keys/{key_id}/rotation-history", None),
    ("POST", "/api-keys/{key_id}/schedule-rotation", {}),
    ("PATCH", "/api-keys/{key_id}/expiration", {}),
    ("DELETE", "/api-keys/{key_id}/expiration", None),
    ("GET", "/api-keys/{key_id}/rate-limit", None),
    ("PATCH", "/api-keys/{key_id}/rate-limit", {}),
    ("GET", "/api-keys/{key_id}/quota", None),
    ("PATCH", "/api-keys/{key_id}/quota", {}),
    ("GET", "/api-keys/{key_id}/quota/status", None),
    ("PATCH", "/api-keys/{key_id}/scopes", {}),
]


async def test_an_admin_of_another_organization_cannot_touch_a_key_it_does_not_own(client, db_session, monkeypatch):
    (owner, org_a, _), (attacker, org_b, _) = await make_tenants(client, db_session, monkeypatch, "apikey")
    scopes = (await client.get("/api-keys/scopes", headers=owner)).json()["scopes"]
    assert scopes, "the control needs at least one valid scope"
    created = await client.post(f"/organizations/{org_a}/api-keys", headers=owner, json={"name": "private-key", "scopes": [scopes[0]["name"] if isinstance(scopes[0], dict) else scopes[0]]})
    assert created.status_code == 200, created.text
    key_id = created.json()["id"]
    key_uuid = uuid.UUID(key_id)
    row = await db_session.scalar(select(OrganizationAPIKey).where(OrganizationAPIKey.id == key_uuid))
    baseline = await snapshot(db_session, row)

    control = await client.get(f"/api-keys/{key_id}", headers=owner)
    assert control.status_code == 200, control.text

    violations: list[str] = []
    for method, template, body in KEY_ROUTES:
        kwargs = {} if body is None else {"json": body}
        await denied(client, method, template.format(key_id=key_id), attacker, violations, **kwargs)
    # The attacker's own organization path must not reach a key of another organization either, and A's organization path is closed to B.
    await denied(client, "DELETE", f"/organizations/{org_b}/api-keys/{key_id}", attacker, violations)
    await denied(client, "DELETE", f"/organizations/{org_a}/api-keys/{key_id}", attacker, violations)
    await denied(client, "GET", f"/organizations/{org_a}/api-keys", attacker, violations)
    await denied(client, "GET", f"/organizations/{org_a}/api-keys/expiring", attacker, violations)
    await denied(client, "POST", f"/organizations/{org_a}/api-keys", attacker, violations, json={"name": "attacker-key", "scopes": [scopes[0]["name"] if isinstance(scopes[0], dict) else scopes[0]]})

    db_session.expire_all()
    row = await db_session.scalar(select(OrganizationAPIKey).where(OrganizationAPIKey.id == key_uuid))
    assert row is not None, "the key must still exist"
    assert await snapshot(db_session, row) == baseline, "a refused request must not change the key (name, scopes, hash, rotation, quota, expiry)"
    keys_of_a = (await db_session.scalars(select(OrganizationAPIKey).where(OrganizationAPIKey.organization_id == org_a))).all()
    assert len(keys_of_a) == 1, "no key may be created in the victim organization"
    assert not violations, "\n".join(violations)

    # Control, last (it changes the key): the legitimate administrator of the owning organization can still revoke it.
    own = await client.delete(f"/organizations/{org_a}/api-keys/{key_id}", headers=owner)
    assert own.status_code == 204, own.text
