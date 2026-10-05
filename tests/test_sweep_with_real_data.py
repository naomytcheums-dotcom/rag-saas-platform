"""Second all-routes sweep: with REAL data.

tests/test_no_unhandled_errors_sweep.py calls every route with random ids, so most handlers answer 404 before they reach the code
that serializes a real row. Here the sweep first CREATES data through the API itself (every `POST /organizations/{org_id}/<collection>`
that accepts a schema-valid body), remembers the ids that come back, and then calls every operation substituting those real ids
into the path parameters: GETs first, then writes, then DELETEs. A 5xx or an exception escaping the application is a bug a real client
can trigger on real data."""

import asyncio
import re
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from api.database import Base, get_db
from api.main import app
from test_no_unhandled_errors_sweep import EXCLUDED, OPERATIONS, _request_kwargs, is_expected_501

REQUEST_TIMEOUT_SECONDS = 25

# Operations that would end the sweep's own session or delete the tenant it works in.
SKIP = re.compile(
    r"^(DELETE /organizations/\{org_id\}$|DELETE /account|POST /auth/logout|POST /account/|DELETE /auth/sessions|POST /auth/sessions/revoke|"
    r"POST /auth/password/change|POST /auth/2fa/disable|DELETE /auth/2fa)"
)


def _singular(segment: str) -> str:
    segment = segment.replace("-", "_")
    if segment.endswith("ies"):
        return segment[:-3] + "y"
    if segment.endswith("sses"):
        return segment[:-2]
    return segment[:-1] if segment.endswith("s") else segment


def _fill(path: str, ids: dict[str, str], org_id: str) -> str:
    out = path.replace("{org_id}", org_id)
    for name in re.findall(r"\{(\w+)\}", out):
        out = out.replace("{" + name + "}", ids.get(name) or str(uuid.uuid4()), 1)
    return out


async def _call(client, method, url, kwargs):
    try:
        return await asyncio.wait_for(client.request(method, url, **kwargs), REQUEST_TIMEOUT_SECONDS), None
    except asyncio.TimeoutError:
        return None, "no answer within the time limit"
    except Exception as exc:  # noqa: BLE001 -- an exception escaping the ASGI app IS the finding
        return None, f"EXC {type(exc).__name__}: {str(exc)[:200]}"


@pytest_asyncio.fixture
async def client(tmp_path):
    """A client whose every request gets its OWN database session AND its own connection, as in production. The shared fixtures use one
    in-memory SQLite connection for everything: a request cancelled by the sweep's time limit closes it and the whole database vanishes
    ("no such table"), which would turn one slow route into hundreds of bogus failures. A file database with no connection pooling
    keeps every request independent."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sweep.db'}", poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def _register_with_org(client, email, password, org_name):
    token = (await client.post("/auth/register", json={"email": email, "password": password, "accept_terms": True})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org_id = (await client.post("/organizations", json={"name": org_name}, headers=headers)).json()["id"]
    return headers, org_id


async def _create_world(client, spec, headers, org_id, problems):
    """Create data through the API as the organization's owner and return the real ids that came back."""
    ids: dict[str, str] = {}

    def judge(method, path, response, error):
        if error:
            problems.append(f"{method} {path} -> {error}")
        elif response.status_code >= 500 and not is_expected_501(method, path, response):
            problems.append(f"{method} {path} -> {response.status_code} {response.text[:200]}")

    # 1. every collection-create route under the organization
    creates = [
        (m, p) for m, p in OPERATIONS
        if m == "POST" and re.fullmatch(r"/organizations/\{org_id\}/[a-z0-9\-_]+", p) and (m, p) not in EXCLUDED
    ]
    for method, path in creates:
        kwargs = {"headers": headers, **_request_kwargs(spec["paths"][path][method.lower()], spec)}
        response, error = await _call(client, method, _fill(path, ids, org_id), kwargs)
        judge(method, path, response, error)
        if response is not None and response.status_code in (200, 201):
            try:
                created = response.json()
            except ValueError:
                continue
            if isinstance(created, dict) and created.get("id"):
                ids[f"{_singular(path.rsplit('/', 1)[1])}_id"] = str(created["id"])
                ids.setdefault("id", str(created["id"]))

    # 2. ids that only exist as items of a list (documents, conversations, ...)
    for method, path in OPERATIONS:
        if method == "GET" and re.fullmatch(r"/organizations/\{org_id\}/[a-z0-9\-_]+", path):
            response, error = await _call(client, method, _fill(path, ids, org_id), {"headers": headers})
            if response is not None and response.status_code == 200:
                payload = response.json()
                items = payload if isinstance(payload, list) else next((v for v in payload.values() if isinstance(v, list)), []) if isinstance(payload, dict) else []
                if items and isinstance(items[0], dict) and items[0].get("id"):
                    ids.setdefault(f"{_singular(path.rsplit('/', 1)[1])}_id", str(items[0]["id"]))
    return ids, judge


ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 2, "DELETE": 3}


def _sweepable():
    return [op for op in sorted(OPERATIONS, key=lambda op: (ORDER[op[0]], op[1])) if not (SKIP.match(f"{op[0]} {op[1]}") or op in EXCLUDED)]


async def test_no_operation_fails_with_an_unhandled_error_on_real_data(client, register_payload):
    spec = app.openapi()
    headers, org_id = await _register_with_org(client, register_payload["email"], register_payload["password"], "Real Data Sweep")
    problems: list[str] = []
    ids, judge = await _create_world(client, spec, headers, org_id, problems)

    # 3. every operation, real ids substituted: reads, then writes, then deletes
    for method, path in _sweepable():
        kwargs = {"headers": headers, **_request_kwargs(spec["paths"][path][method.lower()], spec)}
        response, error = await _call(client, method, _fill(path, ids, org_id), kwargs)
        judge(method, path, response, error)

    assert len(ids) >= 3, f"the sweep created too little real data to be meaningful: {sorted(ids)}"
    assert not problems, f"{len(problems)} operations failed with an unhandled error (ids known: {sorted(ids)}):\n  " + "\n  ".join(problems)


async def test_another_tenant_never_succeeds_on_the_real_ids_of_this_one(client, register_payload):
    """Cross-tenant isolation with REAL ids. Tenant A creates data; tenant B (its own, fully valid account and organization) then calls every
    operation that takes an identifier, with A's organization id and A's real resource ids in the path. B must never get a 2xx: a success
    would mean B read, changed or deleted something of A's -- or reached A's handler at all."""
    from test_no_unhandled_errors_sweep import PUBLIC_BY_DESIGN

    spec = app.openapi()
    headers_a, org_a = await _register_with_org(client, register_payload["email"], register_payload["password"], "Tenant A")
    problems: list[str] = []
    ids, _judge = await _create_world(client, spec, headers_a, org_a, problems)
    headers_b, _org_b = await _register_with_org(client, "tenant-b@example.com", "correct-horse-battery-staple", "Tenant B")

    leaks = []
    for method, path in _sweepable():
        params = re.findall(r"\{(\w+)\}", path)
        if not params or f"{method} {path}" in PUBLIC_BY_DESIGN:
            continue
        # only operations that address something of A's: A's org id, or an id that A's own data produced
        if not any(name == "org_id" or name in ids for name in params):
            continue
        kwargs = {"headers": headers_b, **_request_kwargs(spec["paths"][path][method.lower()], spec)}
        response, error = await _call(client, method, _fill(path, ids, org_a), kwargs)
        if response is not None and 200 <= response.status_code < 300:
            leaks.append(f"{method} {path} -> {response.status_code} {response.text[:120]}")

    assert len(ids) >= 3, f"too little data was created for this test to mean anything: {sorted(ids)}"
    assert not leaks, f"{len(leaks)} operations let tenant B succeed on tenant A's real ids (ids: {sorted(ids)}):\n  " + "\n  ".join(leaks)
