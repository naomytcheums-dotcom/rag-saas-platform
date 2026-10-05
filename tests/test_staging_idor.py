"""Document API A/B isolation and actual RLS checks; no SQLite substitute."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytest_plugins = ("staging_support",)


async def test_staging_document_ab(staging_resources):
    client, _, tenants, _ = staging_resources
    for owner, foreign in ((tenants[0], tenants[1]), (tenants[1], tenants[0])):
        path = f"/documents/{owner['document'].id}"
        control = await client.get(path, headers=owner["headers"])
        assert control.status_code == 200
        denied = await client.get(path, headers=foreign["headers"])
        assert denied.status_code in (403, 404)


async def test_staging_rls_under_nonbypass_role(staging_resources):
    _, session, tenants, connection = staging_resources
    # Flush before switching roles; transaction-local role/context cannot leak to a pool.
    await session.flush()
    await connection.execute(text("SET LOCAL ROLE rag_staging_tenant"))
    flags = (await connection.execute(text("""
        SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user
    """))).one()
    assert not flags.rolsuper and not flags.rolbypassrls
    assert (await connection.execute(text("SELECT count(*) FROM documents"))).scalar_one() == 0
    for tenant in tenants:
        await connection.execute(text(
            "SELECT set_config('app.current_organization_id', :org_id, true)"
        ), {"org_id": str(tenant["org"].id)})
        ids = (await connection.execute(text("SELECT id FROM documents"))).scalars().all()
        assert ids == [tenant["document"].id]
    own, foreign = tenants
    await connection.execute(text(
        "SELECT set_config('app.current_organization_id', :org_id, true)"
    ), {"org_id": str(own["org"].id)})
    with pytest.raises(DBAPIError):
        async with connection.begin_nested():
            await connection.execute(text(
                "UPDATE documents SET organization_id = :foreign WHERE id = :own"
            ), {"foreign": foreign["org"].id, "own": own["document"].id})
    await connection.execute(text("RESET ROLE"))
