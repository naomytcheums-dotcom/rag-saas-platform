"""Partie 19 -- POST/DELETE .../whitelabel/domain, POST .../domain/verify.
Real DNS lookups are monkeypatched, same convention as
tests/test_custom_domains.py (api.security.custom_domains.check_domain_dns_txt_record)."""

import uuid

from sqlalchemy import select

from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def test_set_domain_shows_up_in_config_as_unverified(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(f"/organizations/{org['id']}/whitelabel/domain", json={"domain": "app.acme-reseller.example"}, headers=_auth_header(owner_token))
    assert response.status_code == 201
    body = response.json()
    assert body["domain"] == "app.acme-reseller.example"
    assert body["domain_verified"] is False


async def test_setting_an_invalid_domain_is_rejected(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(f"/organizations/{org['id']}/whitelabel/domain", json={"domain": "not a domain"}, headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_verify_domain_with_matching_dns_marks_it_verified(client, db_session, register_payload, monkeypatch):
    async def _dns_matches(domain, token):
        return True

    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/whitelabel/domain", json={"domain": "verified.acme-reseller.example"}, headers=_auth_header(owner_token))

    response = await client.post(f"/organizations/{org['id']}/whitelabel/domain/verify", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["domain_verified"] is True


async def test_verify_domain_with_no_matching_dns_stays_unverified(client, db_session, register_payload, monkeypatch):
    async def _dns_does_not_match(domain, token):
        return False

    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_does_not_match)

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/whitelabel/domain", json={"domain": "failed.acme-reseller.example"}, headers=_auth_header(owner_token))

    response = await client.post(f"/organizations/{org['id']}/whitelabel/domain/verify", headers=_auth_header(owner_token))
    assert response.json()["domain_verified"] is False


async def test_verify_with_no_domain_configured_is_a_real_404(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(f"/organizations/{org['id']}/whitelabel/domain/verify", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_remove_domain_clears_it_from_config(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/whitelabel/domain", json={"domain": "remove-me.acme-reseller.example"}, headers=_auth_header(owner_token))

    response = await client.delete(f"/organizations/{org['id']}/whitelabel/domain", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["domain"] is None


async def test_remove_domain_with_none_configured_is_a_real_404(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.delete(f"/organizations/{org['id']}/whitelabel/domain", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_middleware_does_not_break_a_request_from_an_active_custom_domain(client, db_session, register_payload, monkeypatch):
    """Real, end-to-end exercise of api/services/white_label_middleware.py
    through the actual ASGI app (the `client` fixture, same override
    machinery every route already goes through -- see the middleware's
    own docstring for the real bug this caught: an earlier version
    opened its own DB session directly, bypassing the test override and
    silently hitting this deployment's real Postgres on every request)."""
    async def _dns_matches(domain, token):
        return True

    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/whitelabel/domain", json={"domain": "middleware-test.acme-reseller.example"}, headers=_auth_header(owner_token))
    await client.post(f"/organizations/{org['id']}/whitelabel/domain/verify", headers=_auth_header(owner_token))

    response = await client.get("/health", headers={"Host": "middleware-test.acme-reseller.example"})
    assert response.status_code == 200


async def test_middleware_does_not_break_a_request_from_an_unknown_host(client):
    response = await client.get("/health", headers={"Host": "no-such-domain.example"})
    assert response.status_code == 200


async def test_middleware_resolves_the_correct_organization_via_dependency_override(client, db_session, register_payload, monkeypatch):
    """Direct, real test of the middleware's own resolution logic --
    calls it exactly the way the ASGI app does (through
    app.dependency_overrides), asserting on request.state, which an
    httpx round trip has no way to inspect from outside."""
    from starlette.requests import Request

    from api.database import get_db
    from api.main import app
    from api.security.custom_domains import add_custom_domain, trigger_manual_verification
    from api.services.white_label_middleware import white_label_domain_middleware

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Middleware Direct Co")
    organization_id = uuid.UUID(org["id"])

    async def _dns_matches(domain, token):
        return True

    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)
    domain_row = await add_custom_domain(db_session, organization_id, "direct-test.acme-reseller.example")
    await db_session.commit()
    await trigger_manual_verification(db_session, domain_row)
    await db_session.commit()

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        scope = {"type": "http", "headers": [(b"host", b"direct-test.acme-reseller.example:443")], "method": "GET", "path": "/", "app": app}
        request = Request(scope)
        captured = {}

        async def _call_next(req):
            captured["organization_id"] = req.state.white_label_organization_id
            captured["config"] = req.state.white_label_config
            return "ok"

        result = await white_label_domain_middleware(request, _call_next)
        assert result == "ok"
        assert captured["organization_id"] == organization_id
        assert captured["config"] is not None
    finally:
        app.dependency_overrides.clear()
