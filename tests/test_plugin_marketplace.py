"""Partie 16 (ter) -- marketplace search/filter/sort and installation
lifecycle (install/list/enable/disable/uninstall). See
tests/test_plugins.py's own top docstring for the file-split rationale
and tests/plugin_test_helpers.py for the shared real setup helpers."""

import pytest

from plugin_test_helpers import _auth_header, _files, _mock_s3_fixture, _publish_and_approve, _register_and_create_org, _valid_manifest

_mock_s3 = pytest.fixture(autouse=True)(_mock_s3_fixture)


async def test_search_matches_name_and_description(client, db_session, register_payload):
    await _publish_and_approve(client, db_session, register_payload, name="Analytics Dashboard", manifest_overrides={"description": "Real-time analytics"})

    by_name = await client.get("/marketplace/plugins?search=Analytics")
    assert len(by_name.json()) == 1

    no_match = await client.get("/marketplace/plugins?search=NoSuchThing")
    assert no_match.json() == []


async def test_filter_by_category(client, db_session, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Security Scanner", "description": "...", "category": "security"},
        files=_files(_valid_manifest(name="Security Scanner")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]
    from plugin_test_helpers import _promote_to_superadmin

    await _promote_to_superadmin(db_session, register_payload["email"])
    await client.post(f"/admin/plugins/{plugin_id}/approve", headers=_auth_header(token))

    matching = await client.get("/marketplace/plugins?category=security")
    assert len(matching.json()) == 1

    non_matching = await client.get("/marketplace/plugins?category=analytics")
    assert non_matching.json() == []


async def test_sort_by_popularity_reflects_real_install_count(client, db_session, register_payload):
    _, org_id_a, plugin_a = await _publish_and_approve(client, db_session, register_payload, name="Popular Plugin")
    other_payload = {**register_payload, "email": "installer@example.com"}
    installer_token, installer_org_id = await _register_and_create_org(client, other_payload)
    install_response = await client.post(f"/organizations/{installer_org_id}/plugins/{plugin_a}/install", headers=_auth_header(installer_token))
    assert install_response.status_code == 201

    other_publisher_payload = {**register_payload, "email": "unpopular-publisher@example.com"}
    _, org_id_b, plugin_b = await _publish_and_approve(client, db_session, other_publisher_payload, name="Unpopular Plugin")

    listing = await client.get("/marketplace/plugins?sort_by=popularity")
    ids_in_order = [p["id"] for p in listing.json()]
    assert ids_in_order.index(plugin_a) < ids_in_order.index(plugin_b)
    assert next(p for p in listing.json() if p["id"] == plugin_a)["install_count"] == 1


async def test_install_requires_approved_status(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Unreviewed Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Unreviewed Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))
    assert response.status_code == 400


async def test_install_and_uninstall_flow(client, db_session, register_payload):
    token, org_id, plugin_id = await _publish_and_approve(client, db_session, register_payload, name="Installable Plugin")

    installed = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))
    assert installed.status_code == 201
    installation_id = installed.json()["id"]

    duplicate = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))
    assert duplicate.status_code == 409

    listing = await client.get(f"/organizations/{org_id}/plugins/installed", headers=_auth_header(token))
    assert len(listing.json()) == 1

    disabled = await client.patch(f"/organizations/{org_id}/plugins/installed/{installation_id}", json={"enabled": False}, headers=_auth_header(token))
    assert disabled.json()["enabled"] is False

    uninstalled = await client.delete(f"/organizations/{org_id}/plugins/installed/{installation_id}", headers=_auth_header(token))
    assert uninstalled.status_code == 204

    listing_after = await client.get(f"/organizations/{org_id}/plugins/installed", headers=_auth_header(token))
    assert listing_after.json() == []


async def test_uninstall_decrements_the_real_install_count(client, db_session, register_payload):
    token, org_id, plugin_id = await _publish_and_approve(client, db_session, register_payload, name="Countable Plugin")

    installed = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))
    installation_id = installed.json()["id"]

    after_install = await client.get(f"/marketplace/plugins/{plugin_id}")
    assert after_install.json()["install_count"] == 1

    await client.delete(f"/organizations/{org_id}/plugins/installed/{installation_id}", headers=_auth_header(token))

    after_uninstall = await client.get(f"/marketplace/plugins/{plugin_id}")
    assert after_uninstall.json()["install_count"] == 0


async def test_filter_by_pricing_and_sort_by_price(client, db_session, register_payload):
    from plugin_test_helpers import _files, _valid_manifest

    token, org_id = await _register_and_create_org(client, register_payload)
    free_created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Free Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Free Plugin")), headers=_auth_header(token),
    )
    paid_created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Paid Plugin", "description": "...", "pricing": "paid", "price": "9.99"},
        files=_files(_valid_manifest(name="Paid Plugin")), headers=_auth_header(token),
    )
    from plugin_test_helpers import _promote_to_superadmin

    await _promote_to_superadmin(db_session, register_payload["email"])
    await client.post(f"/admin/plugins/{free_created.json()['id']}/approve", headers=_auth_header(token))
    await client.post(f"/admin/plugins/{paid_created.json()['id']}/approve", headers=_auth_header(token))

    free_only = await client.get("/marketplace/plugins?pricing=free")
    assert {p["id"] for p in free_only.json()} == {free_created.json()["id"]}

    paid_only = await client.get("/marketplace/plugins?pricing=paid")
    assert {p["id"] for p in paid_only.json()} == {paid_created.json()["id"]}

    by_price = await client.get("/marketplace/plugins?sort_by=price")
    ids_in_order = [p["id"] for p in by_price.json()]
    # free (price=None, sorted first via nulls_first) before the real 9.99 paid plugin
    assert ids_in_order.index(free_created.json()["id"]) < ids_in_order.index(paid_created.json()["id"])
