"""SADM-005 validation by introspection and by black-box calls: which dependency really guards every financial route of the running app,
and what an API key or an unsigned webhook can reach.

Scope (what this does and does not prove): the route table of the FastAPI app and HTTP calls against it. Celery tasks are not exposed
over HTTP (no route triggers them), which is a static finding; they run under a service identity and are not covered by these tests.
"""

import importlib
import pkgutil

import pytest
from fastapi import APIRouter
from sqlalchemy import func, select

import api.routers
from api.models.admin import Plan, Subscription
from api.models.billing import PaymentEvent
from api.services import admin_subscriptions
from api.services.organization_api_keys import generate_organization_api_key
from test_document_idor import make_tenants

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
FINANCIAL_WORDS = ("subscription", "plan", "invoice", "credit", "billing", "refund", "payment", "price", "coupon", "pricing")


def _dependency_names(dependant) -> set[str]:
    names = {getattr(dependant.call, "__name__", "")}
    for child in dependant.dependencies:
        names |= _dependency_names(child)
    return names


def _all_routes():
    """Every APIRoute of every router declared in api/routers (this FastAPI version wraps included routers in an internal type, so the
    app's own route table is not a stable thing to walk; each module's router objects are). route.path already carries the router prefix."""
    seen = set()
    for module_info in pkgutil.iter_modules(api.routers.__path__):
        module = importlib.import_module(f"api.routers.{module_info.name}")
        for value in vars(module).values():
            if isinstance(value, APIRouter) and id(value) not in seen:
                seen.add(id(value))
                yield from (route for route in value.routes if hasattr(route, "dependant"))


def _admin_routes():
    for route in _all_routes():
        if route.path.startswith("/admin"):
            yield route


def test_every_financial_write_under_admin_requires_the_superadmin_and_every_read_requires_an_admin():
    writes, reads = [], []
    for route in _admin_routes():
        names = _dependency_names(route.dependant)
        financial = any(word in route.path for word in FINANCIAL_WORDS)
        if not financial:
            continue
        for method in route.methods & (WRITE_METHODS | {"GET"}):
            (writes if method in WRITE_METHODS else reads).append((method, route.path, names))
    assert len(writes) >= 12, f"expected the 10 subscription/plan/sync writes plus the 2 invoice routes, found {len(writes)}: {[(m, p) for m, p, _ in writes]}"
    for method, path, names in writes:
        assert "require_superadmin" in names, f"{method} {path} is a financial write not guarded by the superadmin dependency: {names}"
    for method, path, names in reads:
        assert {"require_admin", "require_superadmin"} & names, f"GET {path} has no platform-role guard at all: {names}"


def test_the_expected_financial_routes_are_all_present():
    seen = {(method, route.path) for route in _admin_routes() for method in route.methods}
    expected = {
        ("PATCH", "/admin/subscriptions/{sub_id}"), ("POST", "/admin/subscriptions/{sub_id}/cancel"), ("DELETE", "/admin/subscriptions/{sub_id}"),
        ("POST", "/admin/subscriptions/{sub_id}/refund"), ("POST", "/admin/subscriptions/{sub_id}/extend"), ("POST", "/admin/plans"),
        ("PATCH", "/admin/plans/{plan_id}"), ("DELETE", "/admin/plans/{plan_id}"), ("POST", "/admin/plans/sync/stripe-products"),
        ("POST", "/admin/plans/sync/stripe-prices"), ("POST", "/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid"),
        ("POST", "/admin/organizations/{org_id}/invoices/{invoice_id}/void"),
    }
    assert expected <= seen, f"missing: {expected - seen}"


def test_no_route_outside_admin_can_write_a_plan_or_the_catalogue():
    """Alternative paths to the same operations: nothing outside /admin may create or edit plans or force a subscription's plan/status."""
    for route in _all_routes():
        path = route.path
        if path.startswith("/admin"):
            continue
        methods = route.methods & WRITE_METHODS
        if methods and path.rstrip("/").endswith(("/plans", "/plans/{plan_id}")):
            pytest.fail(f"{sorted(methods)} {path} can edit the plan catalogue outside /admin")


async def _api_key_world(client, db_session, monkeypatch, label):
    (_headers, org_id, _user), _other = await make_tenants(client, db_session, monkeypatch, label)
    await admin_subscriptions.ensure_default_plans_seeded(db_session)
    sub = await admin_subscriptions.get_or_create_subscription(db_session, org_id)
    sub_id = sub.id
    plan_id = (await db_session.scalar(select(Plan).where(Plan.key == "pro"))).id
    _row, api_key = await generate_organization_api_key(db_session, org_id, "key", ["kb:read", "kb:write"])
    await db_session.commit()
    return org_id, sub_id, plan_id, api_key


async def test_an_api_key_cannot_reach_any_financial_route(client, db_session, monkeypatch):
    org_id, sub_id, plan_id, api_key = await _api_key_world(client, db_session, monkeypatch, "keyfin")
    headers = {"X-API-Key": api_key}
    calls = [
        ("PATCH", f"/admin/subscriptions/{sub_id}", {"plan_id": str(plan_id)}), ("POST", f"/admin/subscriptions/{sub_id}/extend", {"days": 30}),
        ("POST", f"/admin/subscriptions/{sub_id}/cancel", {"reason": "x"}), ("POST", "/admin/plans", {"key": "k", "name": "K"}),
        ("POST", f"/organizations/{org_id}/billing/subscribe", {"plan_id": str(plan_id)}), ("POST", f"/organizations/{org_id}/billing/cancel", {"reason": "x"}),
        ("POST", f"/organizations/{org_id}/billing/credits/purchase", {"pack_id": "small"}), ("PATCH", f"/organizations/{org_id}/billing/country", {"billing_country": "FR"}),
        ("GET", f"/organizations/{org_id}/billing/invoices", None), ("GET", "/admin/subscriptions", None),
    ]
    for method, url, body in calls:
        response = await client.request(method, url, json=body, headers=headers)
        assert response.status_code in (401, 403), (method, url, response.status_code)
    db_session.expire_all()
    sub = await db_session.get(Subscription, sub_id)
    assert sub.canceled_at is None and sub.status.value == "active"
    assert await db_session.scalar(select(func.count()).select_from(Plan).where(Plan.key == "k")) == 0


async def test_an_unsigned_or_badly_signed_webhook_changes_nothing(client, db_session):
    for url, header in (("/billing/stripe/webhook", "stripe-signature"), ("/billing/paystack/webhook", "x-paystack-signature")):
        for headers in ({}, {header: "forged"}):
            response = await client.post(url, content=b'{"id":"evt_forged","type":"customer.subscription.deleted","data":{"object":{}}}', headers=headers)
            assert response.status_code in (400, 501), (url, headers, response.status_code)
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 0
