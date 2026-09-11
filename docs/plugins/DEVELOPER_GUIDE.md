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

| Hook | Fires when | Actually wired to a real platform event? |
|---|---|---|
| `on_document_uploaded` | A document finishes uploading | **Yes** — `api/security/documents.py`'s own `upload_document` |
| `on_message_received` | A message is received | No — declared and dispatchable, not yet wired |
| `on_message_sent` | A message is sent | No |
| `on_agent_created` | An agent is created | No |
| `on_conversation_started` | A conversation starts | No |
| `on_error` | A platform error occurs | No |
| `on_schedule` | A scheduled time is reached | No |

Only `on_document_uploaded` is genuinely fired by a real platform
event today. The other 6 are real, working, and dispatchable — any
code can call `api.services.plugin_hooks.trigger_hook(db,
organization_id, PluginHook.on_message_sent, payload)` right now and
it will find and run every enabled installation of every approved
plugin that declared that hook — but no existing module currently
calls `trigger_hook` for those 6 events. Wiring each into its own
business-logic module is real, separate follow-up work, tracked
honestly rather than claimed done.

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

- `POST /organizations/{org_id}/plugins/publish` — first publish, always creates a `pending` plugin.
- `PUT /organizations/{org_id}/plugins/{id}` — a new version (bumped `version`, real code/manifest change). Creates a real `PluginVersion` history row and resets moderation to `pending` — an approved plugin does not silently inherit approval for new code.
- `GET /marketplace/plugins/{id}/versions` — the real, full version history, including each version's own changelog.

## Real limits

- Code: 1 MB max per version.
- Execution: `PLUGINS_MAX_EXECUTION_TIME` seconds (default 30), `PLUGINS_MAX_MEMORY` MB (default 256, POSIX only — see SECURITY.md), `PLUGINS_MAX_API_CALLS` invocations/minute (default 100).
- These are real platform settings (`api/config.py`), not per-plugin.
