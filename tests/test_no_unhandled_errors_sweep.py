"""No route may answer with an unhandled server error.

For EVERY operation in the OpenAPI schema, an authenticated organization owner sends a request with a fresh random id in every
path parameter (GET: no body; POST/PUT/PATCH/DELETE: an empty JSON body). A correct API answers such a request with a 4xx
(not found, validation, permission...) or a 2xx -- never a 5xx and never an exception escaping the application. Each failure
found here is an unhandled error a real client could trigger, so the list below must stay empty; an exception to the rule needs
a written reason in EXCLUDED."""

import asyncio
import uuid

import pytest

from api.main import app

READ = {"get"}
WRITE = {"post", "put", "patch", "delete"}

# Operations that would invalidate the caller's own session or are long-lived streams; each needs a reason.
EXCLUDED = {
    ("DELETE", "/account"): "deletes the sweep's own user",
    ("POST", "/auth/logout"): "revokes the sweep's own session",
}
REQUEST_TIMEOUT_SECONDS = 20


def _operations():
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            if method.lower() in READ | WRITE:
                yield method.upper(), path


OPERATIONS = sorted(set(_operations()))


def _fill(path: str, org_id: str) -> str:
    out = path.replace("{org_id}", org_id)
    while "{" in out:
        start = out.index("{")
        end = out.index("}", start)
        out = out[:start] + str(uuid.uuid4()) + out[end + 1:]
    return out


# 501 Not Implemented is this API's honest answer for "this provider is not configured on this deployment"; it is not an
# unhandled error. Each entry needs the reason it is expected.
EXPECTED_501 = {
    ("POST", "/billing/stripe/webhook"): "Stripe not configured (STRIPE_SECRET_KEY unset)",
    ("POST", "/billing/paystack/webhook"): "Paystack not configured (PAYSTACK_SECRET_KEY unset)",
}


def _resolve(schema, spec):
    while isinstance(schema, dict) and "$ref" in schema:
        node = spec
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        schema = node
    return schema


def _example(schema, spec, depth=0):
    """A minimal value that satisfies `schema` (required fields only), so a request gets past validation into real code."""
    schema = _resolve(schema, spec) or {}
    if depth > 4:
        return None
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = [o for o in schema[key] if _resolve(o, spec).get("type") != "null"]
            return _example(options[0], spec, depth + 1) if options else None
    if "allOf" in schema:
        merged = {}
        for part in schema["allOf"]:
            value = _example(part, spec, depth + 1)
            if isinstance(value, dict):
                merged.update(value)
        return merged
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    kind, fmt = schema.get("type"), schema.get("format")
    if kind == "object" or "properties" in schema:
        props, required = schema.get("properties", {}), schema.get("required", [])
        return {name: _example(props[name], spec, depth + 1) for name in required if name in props}
    if kind == "array":
        return [_example(schema.get("items", {}), spec, depth + 1)]
    if kind == "integer":
        return max(int(schema.get("minimum", 1)), 1)
    if kind == "number":
        return float(max(schema.get("minimum", 1), 1))
    if kind == "boolean":
        return False
    if fmt == "uuid":
        return str(uuid.uuid4())
    if fmt == "email":
        return "sweep@example.com"
    if fmt == "date-time":
        return "2026-01-01T00:00:00Z"
    if fmt == "date":
        return "2026-01-01"
    if fmt == "uri":
        return "https://example.com/"
    text = "sweep"
    return text.ljust(schema.get("minLength", 0), "x")[: schema.get("maxLength", 10**6)]


def _request_kwargs(operation, spec):
    """Query parameters and a body generated from the operation's own schema."""
    kwargs = {}
    params = {}
    for parameter in operation.get("parameters", []):
        parameter = _resolve(parameter, spec)
        if parameter.get("in") == "query" and parameter.get("required"):
            params[parameter["name"]] = _example(parameter.get("schema", {}), spec)
    if params:
        kwargs["params"] = params
    content = (operation.get("requestBody") or {}).get("content", {})
    if "application/json" in content:
        kwargs["json"] = _example(content["application/json"].get("schema", {}), spec)
    elif "multipart/form-data" in content:
        schema = _resolve(content["multipart/form-data"].get("schema", {}), spec)
        files, data = {}, {}
        for name, prop in schema.get("properties", {}).items():
            prop = _resolve(prop, spec)
            if prop.get("format") == "binary" or prop.get("items", {}).get("format") == "binary":
                files[name] = ("sweep.txt", b"hello sweep", "text/plain")
            elif name in schema.get("required", []):
                data[name] = str(_example(prop, spec))
        if files:
            kwargs["files"] = files
        if data:
            kwargs["data"] = data
    return kwargs


def test_the_sweep_covers_the_whole_api():
    assert len(OPERATIONS) > 700, f"only {len(OPERATIONS)} operations found"


async def test_no_operation_answers_with_an_unhandled_server_error(client, register_payload):
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org_id = (await client.post("/organizations", json={"name": "Sweep"}, headers=headers)).json()["id"]

    server_errors, escaped, slow = [], [], []
    await _sweep(client, headers, org_id, server_errors, escaped, slow, schema_valid=False)
    report = _report(server_errors, escaped, slow)
    assert not report, "EMPTY BODIES\n" + report


async def test_no_operation_answers_with_an_unhandled_server_error_when_the_request_is_schema_valid(client, register_payload):
    """Same sweep, but each request carries the minimal body/query the operation's own schema requires, so it gets past
    validation and runs the real handler."""
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org_id = (await client.post("/organizations", json={"name": "Sweep"}, headers=headers)).json()["id"]
    server_errors, escaped, slow = [], [], []
    await _sweep(client, headers, org_id, server_errors, escaped, slow, schema_valid=True)
    report = _report(server_errors, escaped, slow)
    assert not report, "SCHEMA-VALID BODIES\n" + report


async def _sweep(client, headers, org_id, server_errors, escaped, slow, *, schema_valid):
    spec = app.openapi()
    for method, path in OPERATIONS:
        if (method, path) in EXCLUDED:
            continue
        kwargs = {"headers": headers}
        if schema_valid:
            kwargs.update(_request_kwargs(spec["paths"][path][method.lower()], spec))
        elif method.lower() in WRITE:
            kwargs["json"] = {}
        try:
            response = await asyncio.wait_for(client.request(method, _fill(path, org_id), **kwargs), REQUEST_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            slow.append(f"{method} {path}")
            continue
        except Exception as exc:  # noqa: BLE001 -- an exception escaping the ASGI app IS the finding
            escaped.append(f"{method} {path} -> {type(exc).__name__}: {str(exc)[:200]}")
            continue
        if response.status_code == 501 and (method, path) in EXPECTED_501:
            continue
        if response.status_code >= 500:
            server_errors.append(f"{method} {path} -> {response.status_code} {response.text[:200]}")


def _report(server_errors, escaped, slow):
    report = []
    if server_errors:
        report.append("5xx answers:\n  " + "\n  ".join(server_errors))
    if escaped:
        report.append("exceptions escaping the app:\n  " + "\n  ".join(escaped))
    if slow:
        report.append(f"no answer within {REQUEST_TIMEOUT_SECONDS}s:\n  " + "\n  ".join(slow))
    return "\n\n".join(report)


# Every operation an anonymous caller may reach, with the reason. A NEW entry here is a security decision: review it.
PUBLIC_BY_DESIGN = {
    # Health and monitoring (documented as open; /metrics can be token-protected with METRICS_AUTH_TOKEN)
    "GET /health",
    "GET /health/ready",
    "GET /metrics",
    # Sign-in, sign-up, account recovery and SSO entry points (no session exists yet; answers are generic)
    "GET /auth/oauth/{provider}/authorize",
    "GET /auth/oauth/{provider}/callback",
    "GET /auth/sso/{connection_id}/authorize",
    "GET /auth/sso/{connection_id}/callback",
    "POST /account/consent/reactivate/confirm",
    "POST /account/consent/reactivate/request",
    "POST /account/restore/confirm",
    "POST /account/restore/request",
    "POST /auth/2fa/lockout-recovery/confirm",
    "POST /auth/2fa/lockout-recovery/request",
    "POST /auth/password/forgot",
    "POST /auth/password/reset",
    "POST /auth/register",
    "POST /auth/sso/discover",
    "POST /invitations/accept",
    # Public catalogue, i18n and marketing surfaces
    "GET /api/versions",
    "GET /api/versions/{version}",
    "GET /billing/plans",
    "GET /billing/plans/{plan_id}",
    "GET /i18n/detect",
    "GET /i18n/languages",
    "GET /i18n/translations/{language}",
    "GET /integrations/providers",
    "GET /marketplace/permissions",
    "GET /marketplace/plugins",
    "GET /marketplace/plugins/{plugin_id}",
    "GET /marketplace/plugins/{plugin_id}/rating",
    "GET /marketplace/plugins/{plugin_id}/reviews",
    "GET /marketplace/plugins/{plugin_id}/versions",
    "GET /widget/avatar",
    "GET /widget/chat.js",
    "GET /widget/config",
    "GET /widget/embed.js",
    "GET /widget/iframe",
    "GET /widget/language",
    "GET /widget/languages",
    "GET /widget/logo",
    "GET /widget/position",
    "GET /widget/script.js",
    "GET /widget/styles.css",
    "GET /widget/suggested-questions",
    "GET /widget/theme",
    "GET /widget/welcome",
    "POST /i18n/language",
    "POST /widget/session",
    # Shared links and branding, addressed by an unguessable token or code
    "GET /organizations/{org_id}/branding",
    "GET /organizations/{org_id}/domains/verify/{token}",
    "GET /r/{code}",
    "GET /share/{token}",
    # Machine endpoints authenticated by their own credential (API key header, signature or webhook token): a missing credential is a 4xx
    "GET /a2a/{org_id}/.well-known/agent-card.json",
    "GET /integrations/slack/callback",
    "GET /mcp/v1/tools",
    "GET /v1/agents",
    "GET /v1/analytics",
    "GET /v1/conversations",
    "GET /v1/documents",
    "GET /v1/knowledge-bases",
    "GET /v1/usage",
    "POST /a2a/{org_id}",
    "POST /api/agents/run",
    "POST /billing/paystack/webhook",
    "POST /billing/stripe/webhook",
    "POST /integrations/teams/webhook",
    "POST /mcp/v1/tools/{tool_name}/call",
    "POST /twilio/dtmf",
    "POST /twilio/incoming",
    "POST /twilio/speech",
    "POST /twilio/status",
    "POST /v1/agents/run",
    "POST /v1/chat",
    "POST /v1/documents",
    "POST /v1/embed",
    "POST /v1/knowledge-bases",
    "POST /v1/search",
    "POST /webhooks/{trigger_id}",
    # Public sign-up for partners and license validation (both rate-limited per IP)
    "POST /license/validate",
    "POST /partners/register",
    # Documented redirects
    "POST /compliance/data-deletion",
}


async def test_anonymous_callers_reach_only_the_endpoints_meant_to_be_public(client):
    """Every operation is called with NO credentials and a schema-valid request. 401/403 is the expected answer for anything
    protected; any other answer must come from an operation listed in PUBLIC_BY_DESIGN, and must never be a server error."""
    spec = app.openapi()
    unexpected, errors = [], []
    for method, path in OPERATIONS:
        if (method, path) in EXCLUDED:
            continue
        kwargs = _request_kwargs(spec["paths"][path][method.lower()], spec)
        try:
            response = await asyncio.wait_for(client.request(method, _fill(path, str(uuid.uuid4())), **kwargs), REQUEST_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{method} {path} -> EXC {type(exc).__name__}")
            continue
        if response.status_code >= 500 and not (response.status_code == 501 and (method, path) in EXPECTED_501):
            errors.append(f"{method} {path} -> {response.status_code}")
        if response.status_code not in (401, 403) and f"{method} {path}" not in PUBLIC_BY_DESIGN:
            unexpected.append(f"{method} {path} -> {response.status_code}")
    assert not errors, "server errors for an anonymous caller:\n  " + "\n  ".join(errors)
    assert not unexpected, "operations that answer an anonymous caller but are not listed in PUBLIC_BY_DESIGN:\n  " + "\n  ".join(unexpected)
