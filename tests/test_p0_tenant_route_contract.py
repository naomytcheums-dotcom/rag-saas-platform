"""Tenant contract (Lot A): every route addressed by an organization id in its path must verify who is calling.

374 operations carry `{org_id}` in their path. Each must depend on an organization-membership / permission / role guard (or on a
platform admin guard for the /admin back-office), except a short, explicit allow-list of routes that are PUBLIC BY DESIGN. A new
route that forgets its guard fails this test; the guard-detection itself is proven on a synthetic router (it fails when the guard
is removed). This is a static contract: it proves the guard is declared, not that the guard's query is correct (see the
cross-tenant API tests: test_document_idor.py, test_billing_idor.py, test_a2a_idor.py, test_p0_*)."""

import importlib
import pkgutil

from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute

import api.routers
from api.security.organizations import require_org_member

ORG_PARAMS = {"org_id", "organization_id"}

# Public by design, each with its reason. Anything else on an org path must be guarded.
PUBLIC_BY_DESIGN = {
    ("GET", "/organizations/{org_id}/branding"): "public white-label branding shown on the login page of an organization's custom domain",
    ("GET", "/organizations/{org_id}/domains/verify/{token}"): "domain-ownership check, protected by the secret token in the path",
}

GUARD_NAMES = {"require_org_member", "require_org_owner", "require_org_manager", "require_org_admin", "require_can_invite_members", "require_admin",
               "require_superadmin", "require_dataset_admin", "require_role", "require_any_permission", "require_all_permissions"}


def _dependency_markers(dependant) -> set[str]:
    markers = set()
    call = dependant.call
    if call is not None:
        markers.add(getattr(call, "__name__", ""))
        qualname = getattr(call, "__qualname__", "")
        if "require_permission" in qualname:
            markers.add("require_permission")
    for child in dependant.dependencies:
        markers |= _dependency_markers(child)
    return markers


def _is_guarded(route: APIRoute) -> bool:
    markers = _dependency_markers(route.dependant)
    return bool(markers & (GUARD_NAMES | {"require_permission"})) or any(name.startswith("require_") for name in markers)


def _all_routers():
    seen, routers = set(), []
    for info in pkgutil.iter_modules(api.routers.__path__):
        module = importlib.import_module(f"api.routers.{info.name}")
        for value in vars(module).values():
            if isinstance(value, APIRouter) and id(value) not in seen:
                seen.add(id(value))
                routers.append(value)
    return routers


def _path_param_names(route: APIRoute) -> set[str]:
    names = {p.name for p in route.dependant.path_params}
    for child in route.dependant.dependencies:
        names |= {p.name for p in child.path_params}
    return names


def unguarded_org_routes(routers) -> list[str]:
    found = []
    for router in routers:
        for route in router.routes:
            if not isinstance(route, APIRoute) or not (ORG_PARAMS & _path_param_names(route)):
                continue
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                if (method, route.path) in PUBLIC_BY_DESIGN or _is_guarded(route):
                    continue
                found.append(f"{method} {route.path}")
    return sorted(found)


def test_the_check_detects_a_route_whose_guard_was_removed():
    guarded, unguarded = APIRouter(), APIRouter()

    @guarded.get("/organizations/{org_id}/secrets")
    async def read_guarded(org_id: str, _member=Depends(require_org_member)):
        return {}

    @unguarded.get("/organizations/{org_id}/secrets")
    async def read_unguarded(org_id: str):
        return {}

    assert unguarded_org_routes([guarded]) == []
    assert unguarded_org_routes([unguarded]) == ["GET /organizations/{org_id}/secrets"]


def test_the_scan_finds_the_organization_routes_it_is_supposed_to_guard():
    names = {(method, path) for router in _all_routers() for route in router.routes if isinstance(route, APIRoute) and ORG_PARAMS & _path_param_names(route)
             for method in route.methods - {"HEAD", "OPTIONS"} for path in [route.path]}
    assert len(names) > 300  # 374 at the time of writing: a scan that finds almost nothing would prove nothing
    assert ("POST", "/organizations/{org_id}/documents") in names


def test_every_organization_route_is_guarded_or_public_by_design():
    assert unguarded_org_routes(_all_routers()) == []


def test_the_public_by_design_allow_list_has_no_dead_entries():
    existing = {(method, route.path) for router in _all_routers() for route in router.routes if isinstance(route, APIRoute) for method in route.methods}
    assert set(PUBLIC_BY_DESIGN) <= existing
