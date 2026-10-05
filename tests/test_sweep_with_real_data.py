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


async def test_no_operation_fails_with_an_unhandled_error_on_real_data(client, register_payload):
    spec = app.openapi()
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org_id = (await client.post("/organizations", json={"name": "Real Data Sweep"}, headers=headers)).json()["id"]

    ids: dict[str, str] = {}
    problems: list[str] = []

    def judge(method, path, response, error):
        if error:
            problems.append(f"{method} {path} -> {error}")
        elif response.status_code >= 500 and not is_expected_501(method, path, response):
            problems.append(f"{method} {path} -> {response.status_code} {response.text[:200]}")

    # 1. create data through the API: every collection-create route under the organization
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
                resource = _singular(path.rsplit("/", 1)[1])
                ids[f"{resource}_id"] = str(created["id"])
                ids.setdefault("id", str(created["id"]))

    # 2. ids that only exist as items of a list (documents, conversations, ...): read them from the GET collections
    for method, path in OPERATIONS:
        if method == "GET" and re.fullmatch(r"/organizations/\{org_id\}/[a-z0-9\-_]+", path):
            response, error = await _call(client, method, _fill(path, ids, org_id), {"headers": headers})
            if response is not None and response.status_code == 200:
                body = response.json()
                items = body if isinstance(body, list) else next((v for v in body.values() if isinstance(v, list)), []) if isinstance(body, dict) else []
                if items and isinstance(items[0], dict) and items[0].get("id"):
                    ids.setdefault(f"{_singular(path.rsplit('/', 1)[1])}_id", str(items[0]["id"]))

    # 3. every operation, real ids substituted: reads, then writes, then deletes
    order = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 2, "DELETE": 3}
    for method, path in sorted(OPERATIONS, key=lambda op: (order[op[0]], op[1])):
        if SKIP.match(f"{method} {path}") or (method, path) in EXCLUDED:
            continue
        kwargs = {"headers": headers, **_request_kwargs(spec["paths"][path][method.lower()], spec)}
        response, error = await _call(client, method, _fill(path, ids, org_id), kwargs)
        judge(method, path, response, error)

    assert len(ids) >= 3, f"the sweep created too little real data to be meaningful: {sorted(ids)}"
    assert not problems, f"{len(problems)} operations failed with an unhandled error (ids known: {sorted(ids)}):\n  " + "\n  ".join(problems)
