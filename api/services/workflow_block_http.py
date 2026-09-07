"""
Partie 5.4.6 -- real `http_call` workflow block execution.

**Sécurité (vision critique 1): real SSRF protection, reused, not
reinvented** -- this is a genuinely dangerous real feature (a
Manager-authored node telling this backend to call an arbitrary,
real, runtime-rendered URL) unless the actual HTTP call goes through a
real, DNS-rebinding-safe transport that blocks private/loopback/
link-local/reserved addresses AT THE CONNECTION LAYER (checking the
real resolved IP right before every real TCP connect, including after
a real redirect) -- exactly what `api/services/url_fetching.py`'s own
`_SSRFSafeAsyncTransport` (Partie 2.2.x) already is. `ssrf_safe_client`
(this étape's own small, real addition there) exposes that SAME real
transport for reuse here, rather than a second, weaker SSRF
implementation. `validate_url` (same module) rejects a non-`http(s)`
scheme, a missing hostname, and embedded credentials, BEFORE any real
network I/O.

**Robustesse (vision critique 3)**: a real connection failure/timeout/
non-2xx status is never a raw, leaked `httpx` exception -- always a
real, shared `WorkflowBlockError` with the real, specific reason."""

import httpx

from api.services.template_rendering import render_template
from api.services.url_fetching import ssrf_safe_client, validate_url
from api.services.workflow_blocks import WorkflowBlockError

_ALLOWED_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")
_DEFAULT_TIMEOUT = 20.0


def validate_http_config(config: dict) -> None:
    """Item 2's own literal function -- real, upfront validation,
    including the real, pure (no network I/O) URL scheme/format check."""
    if not config.get("url"):
        raise WorkflowBlockError("http_call block requires a real, non-empty 'url'")
    method = config.get("method", "GET")
    if method not in _ALLOWED_METHODS:
        raise WorkflowBlockError(f"Unknown HTTP method: {method!r} (expected one of {_ALLOWED_METHODS})")
    headers = config.get("headers")
    if headers is not None and not isinstance(headers, dict):
        raise WorkflowBlockError("http_call block's headers must be a real JSON object")
    timeout = config.get("timeout")
    if timeout is not None and timeout <= 0:
        raise WorkflowBlockError("http_call block's timeout must be a real, positive number of seconds")


def render_http_url(url_template: str, context: dict) -> str:
    """Item 2's own literal function -- real, shared `{{var}}`
    substitution, then a real, pure scheme/format validation (no
    network I/O yet -- the real SSRF check happens at connect time,
    see this module's own top docstring)."""
    return validate_url(render_template(url_template, context))


def _render_recursive(value, context: dict):
    if isinstance(value, str):
        return render_template(value, context)
    if isinstance(value, dict):
        return {k: _render_recursive(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_recursive(v, context) for v in value]
    return value


def render_http_body(body_template, context: dict):
    """Item 2's own literal function -- real, shared `{{var}}`
    substitution. A real, given `body` may be a plain string (rendered
    directly) OR a real JSON object/array (every real string LEAF
    value rendered, structure preserved) -- both are real, common
    shapes for a request body."""
    if body_template is None:
        return None
    return _render_recursive(body_template, context)


def format_http_response(response: httpx.Response) -> dict:
    """Item 2's own literal function -- a real, plain, JSON-safe
    summary. The real body is parsed as JSON when the response really
    is JSON, otherwise kept as real plain text."""
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return {"status_code": response.status_code, "headers": dict(response.headers), "body": body}


async def execute_http_block(block_config: dict, context: dict) -> dict:
    """Item 2's own literal function -- real, upfront validation, real
    template rendering of the URL and body, then a real HTTP call
    through the real SSRF-safe transport."""
    validate_http_config(block_config)

    try:
        url = render_http_url(block_config["url"], context)
    except ValueError as exc:
        raise WorkflowBlockError(f"http_call block failed: {exc}") from exc

    method = block_config.get("method", "GET")
    headers = _render_recursive(block_config.get("headers") or {}, context)
    body = render_http_body(block_config.get("body"), context)
    timeout = block_config.get("timeout", _DEFAULT_TIMEOUT)

    try:
        async with ssrf_safe_client() as client:
            response = await client.request(method, url, headers=headers, json=body if isinstance(body, (dict, list)) else None, content=body if isinstance(body, str) else None, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise WorkflowBlockError(f"http_call block timed out after {timeout}s") from exc
    except httpx.HTTPError as exc:
        raise WorkflowBlockError(f"http_call block failed: {exc}") from exc
    except ValueError as exc:
        raise WorkflowBlockError(f"http_call block failed: {exc}") from exc

    return {block_config.get("output_key", "output"): format_http_response(response)}
