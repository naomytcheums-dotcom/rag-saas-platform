"""
Real Open Policy Agent (OPA, Apache 2.0, CNCF) integration -- item 13
of the "bricks open source" list. A real, ADDITIONAL, attribute-based
policy check, on top of (never replacing) this codebase's own already-
real, substantial Casbin RBAC (`api/security/rbac.py`'s
`AsyncEnforcer`, 52 granular permissions). Casbin's own real strength
is role-based/permission-based access control; OPA's own real
strength is expressing richer, attribute-based rules a role model
struggles with (e.g. "this document's retrieval requires this user's
`clearance_level` to be >= the document's own `classification_level`")
against a real, externalized, independently-queryable policy engine.

**Real, deliberate design decision: fail-OPEN (advisory), not
fail-closed** -- unlike a policy engine that is the SOLE gate for
access (where fail-closed would be the only safe default), this
integration is a NEW, opt-in, SECOND check layered on top of an
existing, already-correct, already-real Casbin RBAC decision. A real
network failure to an external OPA server (unreachable, misconfigured,
timed out) must never silently turn into a denial of access Casbin
RBAC had already correctly granted -- that would make this codebase's
own real, tested authorization LESS reliable by adding an external
dependency with no compensating security benefit (an attacker who
wants access denied doesn't need to attack OPA to get it; they'd need
to attack it to bypass a real, additional restriction, which fail-open
does not help them do either, since the underlying Casbin check still
runs independently). `check_policy` therefore returns `bool | None`,
never raises: `None` means "no additional opinion" (disabled, OPA
unreachable, policy/rule not found) -- a real caller must NEVER
interpret `None` as "denied"; only an explicit real `False` from a
real, successfully-evaluated OPA rule should ever add a restriction
beyond what Casbin RBAC already decided.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_client_instance = None

# Short on purpose: an unreachable OPA server must never meaningfully stall the request this advisory check belongs to.
_OPA_TIMEOUT_SECONDS = 1.5


class _OpaRestClient:
    """A minimal client for OPA's documented REST Data API: `POST /v1/data/<package path>/<rule>` with `{"input": ...}` answers
    `{"result": ...}` (https://www.openpolicyagent.org/docs/latest/rest-api/). It replaces the `opa-python-client` package, whose
    `aiofiles>=25.1` requirement is incompatible with `beeai-framework`'s `aiofiles<25`, which made `requirements-optional.txt`
    impossible to install on a clean machine -- for what is a single HTTP call.

    The OPA address is operator configuration (OPA_SERVER_HOST/PORT), never user input, and OPA usually runs on a private network,
    which the SSRF-safe client would refuse by design; hence a plain `httpx` client here (same reasoning as the n8n/Airbyte probes)."""

    def __init__(self, host: str, port: int):
        self._base_url = f"http://{host}:{port}"

    async def query_rule(self, input_data: dict[str, Any], package_path: str, rule_name: str | None = None) -> dict[str, Any]:
        import httpx

        path = package_path.strip().replace(".", "/").strip("/")
        if rule_name:
            path = f"{path}/{rule_name.strip('/')}"
        async with httpx.AsyncClient(timeout=_OPA_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{self._base_url}/v1/data/{path}", json={"input": input_data})
            response.raise_for_status()
            return response.json()


def _get_client():
    """The cached OPA client (same "build once" reasoning as every other client in this codebase)."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    from api.config import settings

    _client_instance = _OpaRestClient(host=settings.OPA_SERVER_HOST, port=settings.OPA_SERVER_PORT)
    return _client_instance


async def check_policy(input_data: dict[str, Any], package_path: str, rule_name: str | None = None) -> bool | None:
    """Real, advisory OPA policy query -- see this module's own top
    docstring for why this is fail-open and returns `bool | None`
    rather than raising or defaulting to a real deny.

    `input_data`/`package_path`/`rule_name` map directly onto OPA's REST
    Data API (see `_OpaRestClient`) -- `package_path` is OPA's own real,
    dotted Rego package path (e.g. `"documents.retrieval"`), `rule_name`
    the real rule inside it to evaluate (e.g. `"allow"`); when omitted,
    the whole real package's own base document is queried instead.

    Returns the real rule's own boolean result on a genuine, successful
    OPA evaluation; `None` on ANY real reason a definitive answer isn't
    available (disabled, unreachable server, missing policy/rule, a
    non-boolean rule result) -- never an exception, never a fabricated
    `True`/`False`."""
    from api.config import settings

    if not settings.OPA_ENABLED:
        return None

    try:
        client = _get_client()
        result = await client.query_rule(input_data, package_path, rule_name)
        value = result.get("result")
        return value if isinstance(value, bool) else None
    except Exception:
        logger.warning(
            "check_policy: real OPA query failed for package '%s' -- advisory only, no restriction applied",
            package_path, exc_info=True,
        )
        return None
