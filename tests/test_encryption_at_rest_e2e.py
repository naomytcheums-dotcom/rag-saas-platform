"""Spec 10.1.14 -- stored secrets are encrypted at rest, proved on the real database and not on a model attribute.

What is proved, with a throw-away PostgreSQL (tests/conftest.py refuses a remote one):

  * three stores written through their real API routes (webhook signing secret, per-organization connector credentials, BYOK LLM key) and one through the
    service layer (MCP server credential), each with its own unique plaintext marker;
  * the raw column, read with plain SQL, is an envelope and never contains the marker;
  * a scan of EVERY text / varchar / json / jsonb / bytea column of EVERY table finds the marker nowhere (so a copy of the value in an audit log, an event row or a
    log table would be caught as well), and a negative control proves the scan can find a plaintext value;
  * the stored value is authenticated: a flipped bit, a foreign key or a missing key makes decryption fail loudly instead of returning garbage;
  * rotation: after POST /encryption/rotate-keys the old key can be dropped and the secret still decrypts, the raw column changed.

Out of scope, said plainly: the content of uploaded documents and the chunks that make search possible are NOT encrypted by the application (they must be
searchable); their protection at rest is the storage layer's (PostgreSQL volume / Supabase / RDS disk encryption, S3 server-side encryption), see
docs/security/ENCRYPTION_AT_REST.md."""

import base64
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.database import get_db
from api.main import app
from api.models.webhook import Webhook
from api.security.encryption import DecryptionFailedError, decrypt_data, encrypt_data, generate_encryption_key
from api.security.secret_encryption import decrypt_secret
from api.services.mcp.discovery import create_mcp_server
from api.services.webhooks import decrypt_webhook_secret

WEBHOOK_SECRET = "WH-SECRET-9f3c1a77-at-rest-marker"
CONNECTOR_TOKEN = "JIRA-TOKEN-4be2d0aa-at-rest-marker"
BYOK_KEY = "sk-ant-BYOK-77d1c5e0-at-rest-marker"
MCP_CREDENTIAL = "MCP-BEARER-c0ffee11-at-rest-marker"
MARKERS = (WEBHOOK_SECRET, CONNECTOR_TOKEN, BYOK_KEY, MCP_CREDENTIAL)


@pytest.fixture(scope="module")
async def pg_engine():
    url = make_url(settings.DATABASE_URL)
    if "postgresql" not in url.drivername or url.host not in ("127.0.0.1", "localhost") or "test" not in (url.database or ""):
        pytest.skip("needs a disposable local PostgreSQL (database name containing 'test'); run it with scripts/run_tests_local.sh")
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"the local PostgreSQL is not reachable ({exc})")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine):
    async with async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)() as session:
        yield session


@pytest_asyncio.fixture
async def pg_client(pg_engine):
    factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    from api.services import connector_credentials as cc

    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY", generate_encryption_key())
    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY_PREVIOUS", None)
    monkeypatch.setattr(settings, "CONNECTORS_ALLOW_PLATFORM_CREDENTIALS", False)
    monkeypatch.setattr(cc, "_public_host_or_raise", lambda host: None)


async def _scan_database_for(db_session, markers):
    """(table, column, marker) for every place a marker appears, over every textual column of every table."""
    columns = (await db_session.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public' "
        "AND data_type IN ('text', 'character varying', 'json', 'jsonb', 'bytea', 'ARRAY')"
    ))).all()
    found = []
    for table, column in columns:
        # identifiers come from the catalog; the markers are bound parameters
        for marker in markers:
            hit = await db_session.scalar(
                text(f'SELECT count(*) FROM "{table}" WHERE position(convert_to(:p, \'UTF8\') in convert_to("{column}"::text, \'UTF8\')) > 0').bindparams(p=marker)
            )
            if hit:
                found.append((table, column, marker))
    return found


_CREATED: list[tuple[str, str]] = []  # (organization id, e-mail) to remove afterwards: the key of each test is random, a leftover row could not be decrypted by the next one


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(pg_engine):
    yield
    async with pg_engine.begin() as conn:
        while _CREATED:
            org_id, email = _CREATED.pop()
            for table in ("webhooks", "connector_credentials", "organization_llm_configs", "mcp_server_configs"):
                await conn.execute(text(f"DELETE FROM {table} WHERE organization_id = :o").bindparams(o=uuid.UUID(org_id)))
            await conn.execute(text("DELETE FROM organizations WHERE id = :o").bindparams(o=uuid.UUID(org_id)))
            await conn.execute(text("DELETE FROM users WHERE email = :e").bindparams(e=email))


async def _provision(client, db_session):
    email = f"enc-{uuid.uuid4().hex[:10]}@example.com"
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": f"Enc {uuid.uuid4().hex[:6]}"}, headers=_auth(token))).json()
    org_id = org["id"]
    _CREATED.append((org_id, email))
    created = await client.post(
        f"/organizations/{org_id}/webhooks",
        json={"name": "enc", "url": "https://hooks.example.com/in", "events": ["message.created"], "secret": WEBHOOK_SECRET}, headers=_auth(token),
    )
    assert created.status_code == 200, created.text
    put = await client.put(
        f"/organizations/{org_id}/connectors/jira",
        json={"fields": {"JIRA_BASE_URL": "https://acme.atlassian.net", "JIRA_EMAIL": "ada@acme.example", "JIRA_API_TOKEN": CONNECTOR_TOKEN}}, headers=_auth(token),
    )
    assert put.status_code == 200, put.text
    byok = await client.post(f"/organizations/{org_id}/llm-config", json={"provider": "anthropic", "api_key": BYOK_KEY}, headers=_auth(token))
    assert byok.status_code == 201, byok.text
    server = await create_mcp_server(
        db_session, uuid.UUID(org_id), name="remote", transport="streamable_http", url="https://mcp.example.com/mcp",
        auth_type="bearer", auth_credential=MCP_CREDENTIAL,
    )
    await db_session.commit()
    return token, org_id, server, email


async def test_every_stored_secret_is_an_envelope_in_the_raw_column_and_nowhere_in_plaintext(pg_client, pg_session):
    token, org_id, server, _email = await _provision(pg_client, pg_session)
    org = uuid.UUID(org_id)

    raw = {
        "webhook": await pg_session.scalar(text("SELECT secret FROM webhooks WHERE organization_id = :o").bindparams(o=org)),
        "connector": await pg_session.scalar(text("SELECT encrypted_payload FROM connector_credentials WHERE organization_id = :o").bindparams(o=org)),
        "byok": await pg_session.scalar(text("SELECT encrypted_api_key FROM organization_llm_configs WHERE organization_id = :o").bindparams(o=org)),
        "mcp": await pg_session.scalar(text("SELECT auth_credential_encrypted FROM mcp_server_configs WHERE id = :i").bindparams(i=server.id)),
    }
    assert all(raw.values()), raw
    for name, value in raw.items():
        for marker in MARKERS:
            assert marker not in value, f"{name} stores a plaintext secret"
    assert raw["webhook"].startswith("current:") and raw["mcp"].startswith("current:") and raw["connector"].startswith("current:")  # AES-256-GCM envelope
    assert raw["byok"].startswith("gAAAA")  # Fernet token, api/security/secret_encryption.py

    # the same plaintext written twice never gives the same ciphertext (random 96-bit nonce)
    assert encrypt_data(WEBHOOK_SECRET) != encrypt_data(WEBHOOK_SECRET)

    # round trip through the real readers
    webhook = await pg_session.scalar(select(Webhook).where(Webhook.organization_id == org))
    assert decrypt_webhook_secret(webhook) == WEBHOOK_SECRET
    assert decrypt_secret(raw["byok"]) == BYOK_KEY
    assert decrypt_data(raw["mcp"]) == MCP_CREDENTIAL

    # nothing the API answers carries the plaintext
    for path in (f"/organizations/{org_id}/webhooks", f"/organizations/{org_id}/connectors", f"/organizations/{org_id}/llm-config", f"/organizations/{org_id}/mcp-servers"):
        body = (await pg_client.get(path, headers=_auth(token))).text
        assert not any(marker in body for marker in MARKERS), path

    # the whole database, every textual column of every table (audit logs, events, system logs included)
    assert await _scan_database_for(pg_session, MARKERS) == []


async def test_the_scan_itself_is_able_to_find_a_plaintext_value(pg_session):
    """Negative control: without it an always-empty scan would prove nothing."""
    org = uuid.uuid4()
    planted = "PLANTED-PLAINTEXT-negative-control-77"
    await pg_session.execute(text("INSERT INTO organizations (id, name, slug) VALUES (:i, :n, :s)").bindparams(i=org, n=planted, s=f"ctrl-{org.hex[:8]}"))
    await pg_session.commit()
    try:
        found = await _scan_database_for(pg_session, (planted,))
        assert ("organizations", "name", planted) in found
    finally:
        await pg_session.rollback()
        await pg_session.execute(text("DELETE FROM organizations WHERE id = :i").bindparams(i=org))
        await pg_session.commit()


async def test_a_tampered_or_foreign_or_missing_key_makes_decryption_fail_loudly(pg_client, pg_session, monkeypatch):
    _token, _org_id, server, _email = await _provision(pg_client, pg_session)
    stored = await pg_session.scalar(text("SELECT auth_credential_encrypted FROM mcp_server_configs WHERE id = :i").bindparams(i=server.id))

    _tag, nonce, ciphertext = stored.split(":")
    flipped = bytearray(base64.urlsafe_b64decode(ciphertext))
    flipped[0] ^= 0x01  # one flipped bit
    tampered = f"current:{nonce}:{base64.urlsafe_b64encode(bytes(flipped)).decode()}"
    with pytest.raises(DecryptionFailedError):
        decrypt_data(tampered)

    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY", generate_encryption_key())  # another deployment's key
    with pytest.raises(DecryptionFailedError):
        decrypt_data(stored)

    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY", None)
    with pytest.raises(Exception, match="ENCRYPTION_MASTER_KEY"):
        decrypt_data(stored)


async def test_rotation_reencrypts_the_stored_value_and_the_old_key_can_then_be_dropped(pg_client, pg_session, monkeypatch):
    from api.models.user import User, UserRole

    token, org_id, _server, email = await _provision(pg_client, pg_session)
    user = await pg_session.scalar(select(User).where(User.email == email))
    user.role = UserRole.superadmin
    await pg_session.commit()
    before = await pg_session.scalar(text("SELECT secret FROM webhooks WHERE organization_id = :o").bindparams(o=uuid.UUID(org_id)))

    old_key = settings.ENCRYPTION_MASTER_KEY
    new_key = generate_encryption_key()
    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY", new_key)
    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY_PREVIOUS", old_key)
    response = await pg_client.post("/encryption/rotate-keys", headers=_auth(token))
    assert response.status_code == 200 and response.json()["rotated_rows"] >= 1

    after = await pg_session.scalar(text("SELECT secret FROM webhooks WHERE organization_id = :o").bindparams(o=uuid.UUID(org_id)))
    assert after != before and WEBHOOK_SECRET not in after
    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY_PREVIOUS", None)  # the old key is gone
    assert decrypt_data(after) == WEBHOOK_SECRET
    # every other AES-256-GCM store is re-encrypted too, otherwise dropping the old key would silently destroy it
    connector = await pg_session.scalar(text("SELECT encrypted_payload FROM connector_credentials WHERE organization_id = :o").bindparams(o=uuid.UUID(org_id)))
    mcp = await pg_session.scalar(text("SELECT auth_credential_encrypted FROM mcp_server_configs WHERE organization_id = :o").bindparams(o=uuid.UUID(org_id)))
    assert CONNECTOR_TOKEN in decrypt_data(connector) and decrypt_data(mcp) == MCP_CREDENTIAL
    monkeypatch.setattr(settings, "ENCRYPTION_MASTER_KEY", old_key)
    with pytest.raises(DecryptionFailedError):
        decrypt_data(after)
