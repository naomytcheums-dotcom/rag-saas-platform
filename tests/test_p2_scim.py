"""Spec 10.4.3 -- SCIM 2.0 Users provisioning. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _org(client, db_session, email):
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": f"Org {email}"}, headers=_h(token))).json()
    return token, org["id"]


async def _scim_token(client, user_token, org_id):
    return (await client.post(f"/organizations/{org_id}/scim/tokens", json={"name": "Okta"}, headers=_h(user_token))).json()["token"]


def _user_body(email, **extra):
    return {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], "userName": email, "emails": [{"value": email, "primary": True}], **extra}


async def test_only_an_organization_admin_can_manage_tokens_and_the_plaintext_is_shown_once(client, db_session):
    token, org_id = await _org(client, db_session, "scim-owner@example.com")
    created = (await client.post(f"/organizations/{org_id}/scim/tokens", json={"name": "Okta"}, headers=_h(token))).json()
    assert created["token"].startswith("scim_")
    listing = (await client.get(f"/organizations/{org_id}/scim/tokens", headers=_h(token))).json()
    assert len(listing) == 1 and "token" not in listing[0] and listing[0]["revoked"] is False
    stranger, _ = await _org(client, db_session, "scim-stranger@example.com")
    assert (await client.post(f"/organizations/{org_id}/scim/tokens", json={"name": "x"}, headers=_h(stranger))).status_code in (403, 404)


async def test_scim_endpoints_reject_missing_wrong_and_revoked_tokens(client, db_session):
    token, org_id = await _org(client, db_session, "scim-auth@example.com")
    assert (await client.get("/scim/v2/Users")).status_code == 401
    assert (await client.get("/scim/v2/Users", headers=_h("scim_wrong"))).status_code == 401
    scim = await _scim_token(client, token, org_id)
    assert (await client.get("/scim/v2/Users", headers=_h(scim))).status_code == 200
    token_id = (await client.get(f"/organizations/{org_id}/scim/tokens", headers=_h(token))).json()[0]["id"]
    assert (await client.delete(f"/organizations/{org_id}/scim/tokens/{token_id}", headers=_h(token))).status_code == 204
    assert (await client.get("/scim/v2/Users", headers=_h(scim))).status_code == 401
    # a normal user access token is not a SCIM token
    assert (await client.get("/scim/v2/Users", headers=_h(token))).status_code == 401


async def test_create_list_filter_and_get_a_user(client, db_session):
    token, org_id = await _org(client, db_session, "scim-crud@example.com")
    scim = await _scim_token(client, token, org_id)
    created = await client.post("/scim/v2/Users", json=_user_body("New.Hire@Example.com", displayName="New Hire"), headers=_h(scim))
    assert created.status_code == 201
    body = created.json()
    assert body["userName"] == "new.hire@example.com" and body["active"] is True and body["displayName"] == "New Hire"
    user = await db_session.scalar(select(User).where(User.email == "new.hire@example.com"))
    assert user.hashed_password is None and user.is_email_verified is False
    member = await db_session.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id))
    assert member.role == OrganizationRole.member
    listing = (await client.get("/scim/v2/Users", headers=_h(scim))).json()
    assert listing["totalResults"] == 2  # the owner and the new hire
    filtered = (await client.get('/scim/v2/Users?filter=userName eq "new.hire@example.com"', headers=_h(scim))).json()
    assert filtered["totalResults"] == 1 and filtered["Resources"][0]["id"] == body["id"]
    assert (await client.get(f"/scim/v2/Users/{body['id']}", headers=_h(scim))).json()["userName"] == "new.hire@example.com"
    assert (await client.get('/scim/v2/Users?filter=name.givenName co "x"', headers=_h(scim))).status_code == 400


async def test_duplicates_and_invalid_users_are_rejected(client, db_session):
    token, org_id = await _org(client, db_session, "scim-dup@example.com")
    scim = await _scim_token(client, token, org_id)
    assert (await client.post("/scim/v2/Users", json=_user_body("dup@example.com"), headers=_h(scim))).status_code == 201
    assert (await client.post("/scim/v2/Users", json=_user_body("dup@example.com"), headers=_h(scim))).status_code == 409
    assert (await client.post("/scim/v2/Users", json={"userName": "not-an-email"}, headers=_h(scim))).status_code == 400


async def test_deactivating_removes_the_membership_but_keeps_the_account_and_the_owner_is_protected(client, db_session):
    token, org_id = await _org(client, db_session, "scim-deact@example.com")
    scim = await _scim_token(client, token, org_id)
    user_id = (await client.post("/scim/v2/Users", json=_user_body("leaver@example.com"), headers=_h(scim))).json()["id"]
    patch = {"schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"], "Operations": [{"op": "Replace", "path": "active", "value": False}]}
    patched = await client.patch(f"/scim/v2/Users/{user_id}", json=patch, headers=_h(scim))
    assert patched.status_code == 200 and patched.json()["active"] is False
    assert (await client.get(f"/scim/v2/Users/{user_id}", headers=_h(scim))).status_code == 404
    assert await db_session.scalar(select(User).where(User.id == uuid.UUID(user_id))) is not None  # the account itself survives
    owner = await db_session.scalar(select(User).where(User.email == "scim-deact@example.com"))
    assert (await client.delete(f"/scim/v2/Users/{owner.id}", headers=_h(scim))).status_code == 403
    assert (await client.put(f"/scim/v2/Users/{owner.id}", json={"active": False}, headers=_h(scim))).status_code == 403


async def test_delete_removes_the_membership(client, db_session):
    token, org_id = await _org(client, db_session, "scim-del@example.com")
    scim = await _scim_token(client, token, org_id)
    user_id = (await client.post("/scim/v2/Users", json=_user_body("gone@example.com"), headers=_h(scim))).json()["id"]
    assert (await client.delete(f"/scim/v2/Users/{user_id}", headers=_h(scim))).status_code == 204
    assert (await client.get(f"/scim/v2/Users/{user_id}", headers=_h(scim))).status_code == 404


async def test_a_token_only_sees_and_touches_its_own_organization(client, db_session):
    token_a, org_a = await _org(client, db_session, "scim-a@example.com")
    token_b, org_b = await _org(client, db_session, "scim-b@example.com")
    scim_a, scim_b = await _scim_token(client, token_a, org_a), await _scim_token(client, token_b, org_b)
    user_b = (await client.post("/scim/v2/Users", json=_user_body("only-in-b@example.com"), headers=_h(scim_b))).json()["id"]
    assert (await client.get(f"/scim/v2/Users/{user_b}", headers=_h(scim_a))).status_code == 404
    assert (await client.delete(f"/scim/v2/Users/{user_b}", headers=_h(scim_a))).status_code == 404
    assert (await client.get(f"/scim/v2/Users/{user_b}", headers=_h(scim_b))).status_code == 200
    assert "only-in-b@example.com" not in str((await client.get("/scim/v2/Users", headers=_h(scim_a))).json())


async def test_an_existing_account_is_attached_to_the_organization_without_touching_it(client, db_session):
    token, org_id = await _org(client, db_session, "scim-attach@example.com")
    _t, _other_org = await _org(client, db_session, "already-there@example.com")
    scim = await _scim_token(client, token, org_id)
    existing = await db_session.scalar(select(User).where(User.email == "already-there@example.com"))
    before = existing.hashed_password
    created = await client.post("/scim/v2/Users", json=_user_body("already-there@example.com"), headers=_h(scim))
    assert created.status_code == 201 and created.json()["id"] == str(existing.id)
    await db_session.refresh(existing)
    assert existing.hashed_password == before
