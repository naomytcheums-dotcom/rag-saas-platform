# Plugin developer guide

## What a plugin is

A plugin is two files you submit together: `manifest.json` (metadata)
and one entry-point source file (`.js`, run via `node`, or `.py`, run
via `python`). The platform reviews and approves it, organizations
install it, and it runs inside a real, isolated sandbox — either
manually (`POST /organizations/{org_id}/plugins/{id}/execute`) or
automatically when a platform event it declared interest in happens
(see Hooks below).

## manifest.json

```json
{
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "What this plugin does.",
  "entry_point": "index.js",
  "permissions": ["read:documents"],
  "hooks": ["on_document_uploaded"]
}
```

| Field | Required | Notes |
|---|---|---|
| `name` | yes | 1-200 characters |
| `version` | yes | real semver, `major.minor.patch` |
| `description` | yes | 1-2000 characters |
| `entry_point` | yes | must end in `.js` or `.py` — the only two languages the sandbox runs |
| `permissions` | yes | list of permission ids from the fixed catalog below — `GET /marketplace/permissions` returns it live |
| `hooks` | no | list of hook names from the fixed set below — omit or leave empty for a plugin that's only ever run manually |
| `author`, `homepage`, `license`, `config_schema` | no | accepted and stored, not yet validated or used by anything in this pass |

`category` (analytics/automation/communication/data/integration/
productivity/security/other) is NOT part of `manifest.json` — it's a
separate field on the publish request itself (a marketplace
classification, not something the plugin declares about itself).

## Permissions

| id | Meaning |
|---|---|
| `read:documents` | Read this organization's documents |
| `write:documents` | Create or modify this organization's documents |
| `read:conversations` | Read this organization's conversations |
| `write:conversations` | Create or modify this organization's conversations |
| `read:agents` | Read this organization's agents |
| `write:agents` | Create or modify this organization's agents |
| `read:users` | Read this organization's member list |
| `write:users` | Modify this organization's members |
| `send:notifications` | Send notifications on this organization's behalf |
| `access:external_api` | Declared only — see Security below: no real outbound network path is granted to a plugin in this pass |

An unknown permission id is rejected at publish time — see
`docs/plugins/SECURITY.md` for why permissions are enforced by what
data the caller includes in the payload, not by anything the
sandboxed process can reach on its own.

## Hooks

| Hook | Fires when | Real call site | Required permission |
|---|---|---|---|
| `on_document_uploaded` | A document finishes uploading | `api/security/documents.py`'s `upload_document` | `read:documents` |
| `on_conversation_started` | A conversation starts | `api/routers/conversations.py`'s `create_conversation_endpoint` | `read:conversations` |
| `on_message_received` | A user message is received | `api/services/agent_orchestrator.py`'s `run_agent`/`stream_response` | `read:conversations` |
| `on_message_sent` | The assistant's response is sent | same two methods, after the response | `read:conversations` |
| `on_agent_created` | An agent is created | `api/security/agents.py`'s `create_agent` | `read:agents` |
| `on_error` | An unhandled error occurs on an org-scoped route | `plugin_error_hook_middleware` (`api/main.py`) | none |
| `on_schedule` | Hourly (Celery Beat) | `api/tasks/plugins.py`'s `fire_scheduled_hook` | none |

All 7 hooks are now wired to a real platform event. A plugin only
receives a hook if it BOTH declares that hook in `manifest.json`'s
`hooks` list AND declares the real permission that hook requires (see
the table above, and `docs/plugins/SECURITY.md`'s own permission-
enforcement section) — a plugin missing the required permission is
silently skipped for that hook, not executed with data it never asked
to be trusted with. `on_error`/`on_conversation_started`/`on_message_*`
only fire for requests/runs that carry a real `organization_id`; a
request with none has no org's plugins to notify.

## Your entry-point script's contract

Your script is invoked as a subprocess. Read one JSON value from
stdin (the payload); print exactly one JSON value to stdout (your
result). Anything printed to stderr, or a non-zero exit code, is
recorded as a real `error` execution. Anything past
`PLUGINS_MAX_EXECUTION_TIME` seconds (default 30) is recorded as a
real `timeout`.

**Python:**
```python
import sys, json

data = json.loads(sys.stdin.read())
result = {"echo": data}
print(json.dumps(result))
```

**JavaScript (Node.js):**
```javascript
const data = JSON.parse(require("fs").readFileSync(0, "utf8"));
const result = { echo: data };
console.log(JSON.stringify(result));
```

## Publishing and versioning

- `POST /organizations/{org_id}/plugins/publish` — first publish, always creates a `pending` plugin. Form fields: `name`, `description`, `category`, `pricing` (`free`/`paid`/`freemium`, default `free`), `price` (required if `pricing` isn't `free`), plus the `manifest` and `code` files.
- `PUT /organizations/{org_id}/plugins/{id}` — a new version (bumped `version`, real code/manifest change). Creates a real `PluginVersion` history row and resets moderation to `pending` — an approved plugin does not silently inherit approval for new code. `pricing`/`price` are not editable on republish in this pass (set once, at first publish).
- `GET /marketplace/plugins/{id}/versions` — the real, full version history, including each version's own changelog.

## Pricing (real metadata, not a real transaction)

`pricing` is `free`, `paid`, or `freemium`; `price` is a real decimal,
required (and validated `> 0`) for anything but `free`. This is real,
validated, filterable, sortable metadata (`GET /marketplace/plugins?
pricing=paid&sort_by=price`) — see `docs/plugins/SECURITY.md`'s own
honest note: no Stripe product or checkout flow exists behind it in
this pass, installing a `paid` plugin is not actually gated on
payment.

## Permission enforcement at execution time

`POST .../execute` accepts an optional `required_permission` field —
when given, the plugin must have declared that exact permission in its
manifest, or the call is a real `403`. Hooks apply this automatically
(see the Hooks table above's "Required permission" column) — you don't
pass anything for that case, `trigger_hook` checks it before ever
invoking your plugin.

## Real limits

- Code: 1 MB max per version.
- Execution: `PLUGINS_MAX_EXECUTION_TIME` seconds (default 30), `PLUGINS_MAX_MEMORY` MB (default 256 — a real Docker `--memory` cgroup limit when the Docker sandbox is active, `RLIMIT_AS` on POSIX only for the subprocess fallback, see SECURITY.md), `PLUGINS_MAX_API_CALLS` invocations/minute (default 100).
- These are real platform settings (`api/config.py`), not per-plugin.
