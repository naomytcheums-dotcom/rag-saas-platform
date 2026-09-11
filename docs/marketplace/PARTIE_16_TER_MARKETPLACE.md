# Partie 16 (ter) — Plugin Marketplace

## Numbering collision (same discipline as every prior one)

DeepSeek's own "Partie 16" was already used earlier this session for
the 4 sales models (SaaS/self-hosted/hybrid/white-label —
`docs/sales/*.md`, migration `0094_partie_16_sales_models.py`,
documented as "Partie 16 (bis)"). This plugin marketplace prompt reused
"Partie 16" a second time for a completely different feature —
documented as "Partie 16 (ter)" rather than renumbered, same reasoning
as every earlier collision (10/11/12/13/15).

## What's real

`api/models/plugins.py` — `Plugin` (identity + CURRENT version's
content), `PluginVersion` (real, append-only history — one row per
publish/republish, each with its OWN S3 key, never overwriting an
earlier version), `PluginInstallation` (one real row per `(plugin,
installing organization)`, unique constraint, real live
`install_count` cache on `Plugin`), `PluginReview` (one real row per
`(plugin, user)`, upserted on re-review), `PluginExecution` (one real
row per sandboxed run, manual or hook-triggered).

`api/security/plugin_manifest.py` — real manifest schema validation
(`name`/`version`/`entry_point`/`description`/`permissions`/`hooks`,
semver enforced, slug format enforced) against fixed, real whitelists
(`ALLOWED_PLUGIN_PERMISSIONS` — real `resource:action` naming,
matching `api/security/permission_catalog.py`'s own convention;
`ALLOWED_PLUGIN_HOOKS`). A real static regex scan (`scan_plugin_code`)
rejects a fixed list of dangerous call patterns and enforces a 1MB
size cap — publication is rejected outright on a match, not silently
flagged.

**Real sandbox, honest scope** (`api/security/plugin_sandbox.py`,
added in a later pass) — see `docs/plugins/SECURITY.md` for the full,
plain-spoken analysis of what "sandboxed" does and does NOT mean here.
In short: a genuinely separate OS process (`node`/`python`
subprocess), a real timeout, a real POSIX-only memory cap, no ambient
authority — NOT a container-per-plugin sandbox, which is real,
separate infrastructure work this pass does not build.

`api/services/plugins.py` — publish/republish (real `PluginVersion`
row each time)/delete, marketplace listing (search/category/
min_rating/sort_by, `approved` only), admin moderation
(approve/reject/suspend), install/uninstall (real `install_count`
maintenance), enable/disable + per-installation config, reviews
(upsert) + rating summary, real sandboxed execution
(`execute_plugin`) + rate limiting + execution history. Plugin code is
stored in the SAME S3 bucket as documents (`S3_DOCUMENTS_BUCKET_NAME`,
`plugins/{id}/{version}/code` key prefix — versioned, never
overwritten) — same "no new S3_* setting" reasoning as
`api/services/storage.py`'s own branding-assets-share-the-avatar-bucket
docstring.

`api/services/plugin_hooks.py` — a real dispatcher (`trigger_hook`)
that finds every enabled installation of an approved plugin declaring
a given hook and runs each through the real sandbox. Exactly ONE of
the 7 hooks is wired to an actual platform event in this pass
(`on_document_uploaded`, from `api/security/documents.py`'s own
`upload_document`, best-effort — a plugin failure never fails the real
upload) — the other 6 are real and callable today, just not yet wired
to their own event; see `docs/plugins/DEVELOPER_GUIDE.md`'s hook
table for the honest breakdown rather than claiming all 7 fire
automatically.

`api/tasks/plugins.py` — 4 real Celery jobs: `validate_pending_plugins`
/`scan_plugin_security` (periodic re-scan, defense in depth against a
scan rule added after a plugin was already submitted/approved),
`cleanup_plugin_executions` (retention sweep), `update_plugin_stats`
(reconciles `install_count` from a real COUNT query, correcting any
drift from the live-maintained counter).

## Real bugs found and fixed

1. **`MissingGreenlet` on `updated_at`** — every endpoint returning a
   `Plugin`/`PluginInstallation`/`PluginReview` row right after an
   UPDATE (approve/reject/suspend, enable/disable, review upsert,
   republish) hit this: SQLAlchemy expires an `onupdate=func.now()`
   column's in-memory value after an UPDATE flush (regardless of this
   project's global `expire_on_commit=False`), and re-reading it needs
   a DB round-trip that fails during FastAPI's response serialization.
   Fixed two ways: `publish_plugin` pre-generates the row's UUID so the
   S3 key is set in the SAME insert (avoiding an unnecessary second
   UPDATE), and every router endpoint on a genuine UPDATE path calls
   `await db.refresh(obj)` right after `db.commit()`.
2. **Alembic `add_column` with an enum type doesn't auto-create that
   type** — unlike `create_table`, which does. Migration 0096 initially
   failed with `UndefinedObjectError: type "plugincategory" does not
   exist`; fixed by calling `plugin_category.create(op.get_bind(),
   checkfirst=True)` explicitly before `add_column`.

## Endpoints (22 total)

Public marketplace (`/marketplace/...`): `GET /permissions`, `GET
/plugins` (search/category/min_rating/sort_by), `GET /plugins/{id}`,
`GET /plugins/{id}/rating`, `GET /plugins/{id}/reviews`, `GET
/plugins/{id}/versions`, `DELETE /reviews/{id}` (owner-only).

Org-scoped (`/organizations/{org_id}/plugins/...`): `POST /publish`,
`PUT /{id}` (republish, real new `PluginVersion`, re-triggers
moderation), `GET /published`, `DELETE /{id}`, `POST /{id}/install`,
`GET /installed`, `PATCH /installed/{id}`, `DELETE /installed/{id}`,
`POST /{id}/reviews`, `POST /{id}/execute` (real sandboxed run), `GET
/{id}/executions`.

Admin (`/admin/plugins/...`, `require_superadmin`): `GET /pending`,
`POST /{id}/approve`, `POST /{id}/reject`, `POST /{id}/suspend`.

Real, deliberate deviation from the literal spec's flat
`/plugins/{id}/install` (implying an ambient "current org" this app's
architecture has no real concept of): every org-scoped action stays
under `/organizations/{org_id}/plugins/...`, this project's own
established convention for anything org-scoped, applied consistently
since Partie 1.

## Frontend

14 real, separate components under `frontend/components/plugins/`
(`PluginMarketplace`/`PluginCard`/`PluginDetail`/
`PluginInstallButton`/`PluginList`/`PluginFilters`/`PluginSearch`/
`PluginReviews`/`PluginReviewForm`/`PluginCreateForm`/
`PluginVersionForm`/`InstalledPlugins`/`PluginConfigForm`/
`PluginLogs`), composed inside one consolidated page,
`/dashboard/marketplace` (sidebar nav under "Widget & integrations"),
3 tabs — Browse / My plugins / Installed — same tabbed-single-page
discipline as `/dashboard/billing` and every other multi-section
screen in this project, not a separate route per concern.

## Verified live

**End-to-end in a real browser (initial pass)**: registered a real
user, published a real plugin through the actual publish form,
confirmed a real `201`, a real S3 object written to a real `documents`
bucket (created live on this session's own Supabase S3-compatible
storage, since `S3_DOCUMENTS_BUCKET_NAME` had never been configured on
this dev machine — a real, separate gap found and fixed), a real
`pending` row. Promoted the user to `superadmin`, approved the plugin,
confirmed marketplace visibility, installed it, confirmed the
Installed tab.

**Real sandbox execution, without mocking the sandbox itself**
(`tests/test_plugin_sandbox.py`, 8 tests, all passing): real
subprocess success with a real computed result, a real plugin-side
error recorded as a row (not an API 500), a real timeout (a 5s-sleep
plugin against a 1s limit), real proof that a secret set in the TEST
process's own environment is invisible inside the sandboxed
subprocess, rate limiting, and both `PLUGINS_ENABLED`/
`PLUGINS_SANDBOX_ENABLED` fail-closed paths.

## Honest remaining gaps

- No container-per-plugin sandbox (Docker/gVisor) — real OS-process
  isolation only. See `docs/plugins/SECURITY.md` for the full analysis.
- `access:external_api` is declared-only — no real outbound network
  path is granted to a sandboxed plugin in this pass.
- 6 of 7 hooks (`on_message_received`/`on_message_sent`/
  `on_agent_created`/`on_conversation_started`/`on_error`/
  `on_schedule`) are real and dispatchable but not wired to their own
  real platform event yet — only `on_document_uploaded` is.
- Permissions are not checked against the actual payload contents at
  execution time — enforcement today is entirely upstream, in what
  `trigger_hook` chooses to include in the payload.
- No free/paid marketplace filter — no real pricing model for plugins
  exists in this pass.
- No org-scoped plugin visibility (every approved plugin is visible to
  every organization) — no private/unlisted plugin concept yet.
