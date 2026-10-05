"""Hardening Mission, §24 -- automatic cross-tenant sweep over the WHOLE API.

For every route mounted under `/organizations/{org_id}/...`, a fully authenticated
user who belongs to a DIFFERENT organization must never get a 2xx, and an
anonymous caller must never get one either (except the deliberately public
reads listed below). Tenant A owns real data; tenant B's owner token is used
against A's `org_id` on every method. One parametrized sweep instead of
hand-written tests for hundreds of routes -- a new route that forgets its
membership dependency fails here without anyone remembering to add a test.

Mutating methods are sent with an empty JSON body: FastAPI resolves dependencies
(authentication, membership, permission) BEFORE it reports body-validation
errors, so a correctly gated route answers 401/403/404 and a route that is NOT
gated shows up as 422 (it got as far as validating the body for an outsider).
Those are reported separately and must be explained, never silently accepted."""

import uuid

import pytest
from api.main import app

# Deliberately reachable without membership (documented in their routers). Anything added here needs a reason.
PUBLIC_BY_DESIGN = {
    ("GET", "/organizations/{org_id}/branding"),  # login screen / embeddable widget branding, see organization_branding.py
}
# Methods that cannot change state and are safe to fire at every route.
READ_METHODS = {"GET"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _org_routes():
    # Read from the OpenAPI schema, not `app.routes`: recent FastAPI versions keep included routers as lazy
    # `_IncludedRouter` objects there, so walking `app.routes` only finds the handful of directly-declared routes.
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/organizations/{org_id}"):
            for method in operations:
                if method.upper() in READ_METHODS | WRITE_METHODS:
                    yield method.upper(), path


ROUTES = sorted(set(_org_routes()))


def _fill(path: str, org_id: str) -> str:
    """Real org id for `{org_id}`; a fresh random UUID for every other path parameter (it cannot exist)."""
    out = path.replace("{org_id}", org_id)
    while "{" in out:
        start = out.index("{")
        end = out.index("}", start)
        out = out[:start] + str(uuid.uuid4()) + out[end + 1:]
    return out


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def two_tenants(client, register_payload):
    token_a = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    org_a = (await client.post("/organizations", json={"name": "Tenant A"}, headers=_auth_header(token_a))).json()["id"]
    email_b = f"tenant-b-{uuid.uuid4().hex[:8]}@example.com"
    token_b = (await client.post("/auth/register", json={"email": email_b, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    await client.post("/organizations", json={"name": "Tenant B"}, headers=_auth_header(token_b))
    return {"org_a": org_a, "token_a": token_a, "token_b": token_b}


def test_the_sweep_actually_covers_the_api():
    """Guard against the sweep silently shrinking (e.g. a refactor changing the path prefix)."""
    assert len(ROUTES) > 300, f"only {len(ROUTES)} organization routes found"
    assert {m for m, _ in ROUTES} >= {"GET", "POST", "PATCH", "DELETE"}


async def test_an_outsider_never_gets_a_2xx_on_any_organization_route(client, two_tenants):
    leaks, ungated = [], []
    for method, path in ROUTES:
        if (method, path) in PUBLIC_BY_DESIGN:
            continue
        url = _fill(path, two_tenants["org_a"])
        kwargs = {"headers": _auth_header(two_tenants["token_b"])}
        if method in WRITE_METHODS:
            kwargs["json"] = {}
        response = await client.request(method, url, **kwargs)
        if 200 <= response.status_code < 300:
            leaks.append(f"{method} {path} -> {response.status_code}")
        elif method in WRITE_METHODS and response.status_code in (400, 422):
            ungated.append(f"{method} {path} -> {response.status_code}")

    assert not leaks, "cross-tenant LEAK (outsider got a 2xx):\n  " + "\n  ".join(leaks)
    assert not ungated, "outsider reached body validation (route not gated by a membership dependency first):\n  " + "\n  ".join(ungated)


async def test_an_anonymous_caller_never_gets_a_2xx_on_any_organization_route(client, two_tenants):
    leaks = []
    for method, path in ROUTES:
        if (method, path) in PUBLIC_BY_DESIGN:
            continue
        kwargs = {"json": {}} if method in WRITE_METHODS else {}
        response = await client.request(method, _fill(path, two_tenants["org_a"]), **kwargs)
        if 200 <= response.status_code < 300:
            leaks.append(f"{method} {path} -> {response.status_code}")

    assert not leaks, "anonymous LEAK (2xx without credentials):\n  " + "\n  ".join(leaks)


async def test_the_owner_of_the_organization_is_not_locked_out_of_its_own_routes(client, two_tenants):
    """Sanity check of the sweep itself: with the OWNER's token, plenty of the same GET routes do answer 2xx,
    so the outsider's 404/403 above are real denials and not just 'this route never works in tests'."""
    ok = 0
    for method, path in ROUTES:
        if method != "GET":
            continue
        response = await client.get(_fill(path, two_tenants["org_a"]), headers=_auth_header(two_tenants["token_a"]))
        ok += 200 <= response.status_code < 300
    assert ok >= 15, f"only {ok} GET routes answered 2xx for the owner -- the sweep's control group is too small"
