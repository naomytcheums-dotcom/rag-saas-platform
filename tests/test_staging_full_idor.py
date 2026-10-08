"""Bidirectional resource isolation, optionally using browser-created staging tenants."""

import pytest

pytest_plugins = ("staging_support",)

PATHS = {
    "document": "/documents/{id}",
    "agent": "/agents/{id}",
    "workflow": "/workflows/{id}",
    "conversation": "/conversations/{id}",
    "evaluation": "/datasets/{id}",
    "media": "/media/{id}",
    "mcp": "/organizations/{org}/mcp-servers/{id}/tools",
    "billing": "/organizations/{org}/billing/invoices/{id}",
}


@pytest.mark.parametrize("surface", PATHS)
async def test_staging_resource_ab(surface, staging_resources):
    client, _, tenants, _ = staging_resources
    for owner, foreign in ((tenants[0], tenants[1]), (tenants[1], tenants[0])):
        path = PATHS[surface].format(id=owner[surface].id, org=owner["org"].id)
        control = await client.get(path, headers=owner["headers"])
        assert control.status_code == 200, f"{surface}: owner control failed"
        denied = await client.get(path, headers=foreign["headers"])
        assert denied.status_code in (403, 404), f"{surface}: cross-tenant access succeeded"
        if surface in {"mcp", "billing"}:
            substituted = PATHS[surface].format(id=owner[surface].id, org=foreign["org"].id)
            denied_substitution = await client.get(substituted, headers=foreign["headers"])
            assert denied_substitution.status_code in (403, 404), f"{surface}: own org exposed a foreign resource"


async def test_staging_a2a_ab(staging_resources):
    client, _, tenants, _ = staging_resources
    keys = []
    for tenant in tenants:
        response = await client.post(
            f"/organizations/{tenant['org'].id}/api-keys", headers=tenant["headers"],
            json={"name": "staging-idor-only", "scopes": ["a2a:call"]},
        )
        assert response.status_code == 200
        keys.append({"X-API-Key": response.json()["key"]})
    for owner_index, foreign_index in ((0, 1), (1, 0)):
        path = f"/a2a/{tenants[owner_index]['org'].id}/.well-known/agent-card.json"
        control = await client.get(path, headers=keys[owner_index])
        assert control.status_code == 200
        denied = await client.get(path, headers=keys[foreign_index])
        assert denied.status_code in (403, 404)
