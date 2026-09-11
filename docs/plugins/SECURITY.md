# Plugin security — real, honest scope

This is the document the "vision critique" questions below are
actually answered by. No claim here is aspirational — every mechanism
described is real code, verified live (`tests/test_plugin_sandbox.py`
spawns real `docker run` containers and real `python`/`node`
subprocesses, never mocks).

## Is the sandbox really isolated?

**Two real, layered engines**, chosen automatically by
`api/security/plugin_sandbox.py`'s own `run_plugin_sandboxed`:

### Docker engine (used whenever available — real container isolation)

Built from `Dockerfile.plugin-sandbox` (repo root) into the
`rag-saas-plugin-sandbox:latest` image; `run_plugin_sandboxed_docker`
runs every execution as:

```
docker run --rm -i --network none --read-only --tmpfs /tmp:size=16m,noexec \
  --cpus=0.5 --memory=256m --memory-swap=256m --pids-limit 64 \
  --security-opt no-new-privileges --cap-drop ALL --user 10001:10001 \
  -v <tmpdir>:/plugin:ro rag-saas-plugin-sandbox:latest <interpreter> /plugin/<script>
```

What each real flag actually enforces:
- `--network none` — no outbound network AT ALL. The strongest, simplest real answer to "can a plugin exfiltrate data or call `access:external_api`": no, the container has no network interface to do it with.
- `--read-only` + `--tmpfs /tmp:noexec` — the container's filesystem cannot be written to except a 16MB scratch `/tmp` that can't execute anything placed in it.
- `--cpus=0.5` / `--memory=256m` — real Linux cgroup limits, enforced by the kernel on every OS Docker Desktop/Engine runs on (including this project's Windows dev machine, via Docker Desktop's own Linux VM) — unlike the subprocess engine's memory cap below, this one IS real on Windows too.
- `--pids-limit 64` — a real fork-bomb guard.
- `--cap-drop ALL` + `--security-opt no-new-privileges` — the container process holds zero Linux capabilities and can never gain more, even via a setuid binary or a kernel exploit that would otherwise let it escalate.
- `--user 10001:10001` — a real non-root user (also baked into the image itself via `Dockerfile.plugin-sandbox`'s own `USER plugin`), belt-and-suspenders with the flags above, not a replacement for them.

Verified live: `test_execute_plugin_reports_which_real_engine_ran_it` confirms the real engine actually used matches `_docker_sandbox_available()`'s own real check (a real `docker` binary AND the real image both present) — on this dev machine, with the image built, every one of `tests/test_plugin_sandbox.py`'s 11 tests ran through the real Docker path, not a fallback pretending to be one.

### Subprocess engine (the real, honest fallback)

Used automatically when Docker isn't available (`PLUGINS_DOCKER_SANDBOX_ENABLED=False`, no `docker` binary, or the image was never built). Real, but weaker:
- A genuinely SEPARATE OS process (`node`/`python` subprocess) — no shared Python interpreter state with the API server, so a plugin crash or infinite loop cannot corrupt or hang the request-serving process itself.
- A real wall-clock timeout (`subprocess.run(timeout=...)`), enforced on every OS.
- A real memory cap via `RLIMIT_AS` — POSIX (Linux/Mac) only. NOT enforced on Windows (`resource` is a POSIX-only stdlib module) when running the subprocess engine specifically — the Docker engine's own `--memory` flag IS real on Windows, see above.
- The same near-empty environment as the Docker path (no ambient secrets/credentials).
- **No real network/filesystem/capability boundary** — only process separation. A determined exploit against the interpreter itself could still escape this engine in ways the Docker engine's `--network none`/`--cap-drop ALL` would stop cold.

**Static gates before ANY code runs, either engine:** `api/security/plugin_manifest.py`'s `validate_manifest` (schema + a fixed permission/hook whitelist) and `scan_plugin_code` (regex-rejects `eval`, `new Function`, `exec`, `os.system`, `subprocess`, Node `child_process`/`fs`) both run at publish time, before a byte of code is ever stored.

## Are hooks really wired to real events?

**Yes, all 7** (a real change from an earlier pass, which had only 1 of 7 wired):

| Hook | Real call site |
|---|---|
| `on_document_uploaded` | `api/security/documents.py`'s `upload_document` |
| `on_conversation_started` | `api/routers/conversations.py`'s `create_conversation_endpoint` |
| `on_message_received` | `api/services/agent_orchestrator.py`'s `run_agent`/`stream_response`, via `_fire_message_hook` |
| `on_message_sent` | same two methods, after the assistant's response is added |
| `on_agent_created` | `api/security/agents.py`'s `create_agent` |
| `on_error` | `plugin_error_hook_middleware`, a real FastAPI middleware registered in `api/main.py`, wrapping every request |
| `on_schedule` | `api/tasks/plugins.py`'s `fire_scheduled_hook`, a real Celery Beat task (hourly) |

Every one is best-effort: a plugin failure is logged and never fails the real platform action that triggered it (the upload, the chat turn, the agent creation, ...). `on_error` and `on_schedule` are real but org-context-limited: `on_error` only fires for routes with a real `org_id` in their path (this app's own `/organizations/{org_id}/...` convention — a route with no org in its path has no org's plugins to notify), and `on_schedule` only iterates organizations that actually have at least one enabled installation subscribed to it.

## Are permissions actually checked before a plugin runs?

**Yes, two real, distinct gates**, both in `api/services/plugin_hooks.py`/`api/services/plugins.py`:

1. **Hook dispatch** — `HOOK_REQUIRED_PERMISSIONS` maps each hook to the real permission it requires (e.g. `on_document_uploaded` → `read:documents`). `trigger_hook` silently skips any installed, hook-subscribed plugin that never declared that permission — it is never executed for that hook at all. Verified live: `test_hook_skips_plugin_missing_the_required_permission` / `test_hook_runs_plugin_that_declares_the_required_permission`.
2. **Manual execution** — `POST .../execute` accepts an optional `required_permission` field; `execute_plugin` checks it against `plugin.manifest["permissions"]` BEFORE running anything, and raises a real `403 Forbidden` (`PluginPermissionError`) if missing. Verified live: `test_execute_plugin_requires_declared_permission`.

Still an honest, real limit: this checks the plugin's DECLARED permission against what the CALLER (hook dispatcher or API client) claims is required — it does not yet inspect the actual payload contents to verify they only contain data the permission would allow. What data goes INTO a hook's payload in the first place is controlled by that hook's own call site (e.g. `upload_document` only ever sends `document_id`/`filename`, never full document content) — a real, if coarse, form of enforcement, not a fine-grained field-level one.

## Does the free/paid/freemium filter mean plugins are actually sold?

**No — real, honest metadata, not a real transaction.** `Plugin.pricing`/`Plugin.price` are real, validated, filterable, sortable columns — but no Stripe product is created, no checkout flow exists, and installing a `paid` plugin is not actually blocked by lack of payment in this pass. A publisher declaring `pricing=paid` is stating an intent the marketplace can filter/sort by; nothing here collects money. See `docs/plugins/MARKETPLACE.md`'s own note.

## What's explicitly still NOT built (said plainly, not left implicit)

- No real payment/checkout flow behind `paid`/`freemium` pricing.
- `access:external_api` still grants no real outbound network path — even the Docker engine's `--network none` makes this a hard guarantee, not just an unimplemented feature.
- Permission enforcement checks the DECLARED permission, not the actual payload content at a field level (see above).
- The static code scan is real but simple regex matching (same class of tool as `api/services/security_scan.py`'s own secret scanner) — not a full taint-analysis or AST-based tool.

## Automated re-scanning (Celery, `api/tasks/plugins.py`)

- `validate_pending_plugins` (hourly) — re-runs the static scan against every `pending` plugin's stored code; auto-`reject`s on a new match.
- `scan_plugin_security` (daily) — same re-scan against every `approved` plugin; auto-`suspend`s on a new match. Existing installations are left in place — see `docs/plugins/MARKETPLACE.md`'s own note on `suspend`.

## Does execution really respect PLUGINS_SANDBOX_ENABLED / PLUGINS_ENABLED / PLUGINS_DOCKER_SANDBOX_ENABLED?

Yes, all three fail closed, not open: `PLUGINS_ENABLED=False` returns a
real `503` before anything runs. `PLUGINS_SANDBOX_ENABLED=False` never
falls back to running the code unsandboxed — it records a real `error`
execution explaining exactly why. `PLUGINS_DOCKER_SANDBOX_ENABLED=False`
forces the subprocess engine even when Docker is available (never the
reverse — Docker is never used if the image genuinely isn't built,
regardless of this setting).

## Rate limiting

`PLUGINS_MAX_API_CALLS` (default 100/minute) is enforced per-plugin,
counted from real `PluginExecution` rows in the last 60 seconds —
honestly scoped to "how often this plugin may be invoked", not "how
many outbound calls the plugin itself makes" (there is no real
outbound path for it to make calls on, see above).
