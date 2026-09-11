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

`api/models/plugins.py` — `Plugin` (one real, versionless row per
published plugin: a re-publish overwrites `manifest`/`code_key`/
`version` in place and resets `status` back to `pending` — no separate
`PluginVersion` history table nothing reads yet), `PluginInstallation`
(one real row per `(plugin, installing organization)`, unique
constraint), `PluginReview` (one real row per `(plugin, user)`, upserted
on re-review — a marketplace rating means "this user's CURRENT
opinion", not an append-only feed).

`api/security/plugin_manifest.py` — real manifest schema validation
(`name`/`version`/`entry_point`/`description`/`permissions`, semver
enforced, slug format enforced) against a fixed, real permission
whitelist (`ALLOWED_PLUGIN_PERMISSIONS`, same static-catalog pattern as
`api/security/permission_catalog.py` — a plugin cannot declare a
permission this platform doesn't actually recognize). A real static
regex scan (`scan_plugin_code`) rejects a fixed list of dangerous call
patterns (`eval`, `new Function`, `exec`, `os.system`, `subprocess`,
Node `child_process`/`fs`) and enforces a 1MB size cap — publication is
rejected outright on a match, not silently flagged.

**Honest scope on "sandbox"**: no plugin runtime exists anywhere in
this codebase — nothing here ever executes uploaded plugin code
server-side. A real execution sandbox (isolated V8/WASM/per-plugin
Docker) is a genuine, separate engineering effort this pass does not
build; faking one would be exactly the kind of fabricated completeness
this project's whole discipline exists to avoid. What's real instead:
manifest/permission validation before publish, and a static forbidden-
pattern scan of the code — real gates, not a real runtime.

`api/services/plugins.py` — publish/republish/delete, marketplace
listing (search, `approved` only), admin moderation
(approve/reject/suspend — suspend deliberately leaves existing
installations in place, only blocks new ones), install/uninstall,
enable/disable + per-installation config, reviews (upsert) +
rating summary (average/count). Plugin code is stored in the SAME S3
bucket as documents (`S3_DOCUMENTS_BUCKET_NAME`, `plugins/{id}/code`
key prefix) — same "no new S3_* setting" reasoning as
`api/services/storage.py`'s own branding-assets-share-the-avatar-bucket
docstring.

## Real bug found and fixed during live verification

Every endpoint that returns a `Plugin`/`PluginInstallation`/
`PluginReview` row right after an UPDATE (approve/reject/suspend,
enable/disable, review upsert, republish) hit a real
`MissingGreenlet`/`ResponseValidationError` on the `updated_at` column:
SQLAlchemy expires an `onupdate=func.now()` column's in-memory value
after an UPDATE flush (regardless of this project's global
`expire_on_commit=False`) so a later read reflects the real DB value —
but re-reading it needs a DB round-trip, which fails when attempted
during FastAPI's response serialization, outside the request's own
async/greenlet context. Fixed two ways: (1) `publish_plugin`
pre-generates the row's UUID so the S3 key can be set in the SAME
insert instead of a second UPDATE flush right after, and (2) every
router endpoint that genuinely does go through an UPDATE path calls
`await db.refresh(obj)` right after `db.commit()`, before returning.

## Endpoints (16 total)

Public marketplace (`/marketplace/...`): `GET /permissions`, `GET
/plugins` (search), `GET /plugins/{id}`, `GET /plugins/{id}/rating`,
`GET /plugins/{id}/reviews`.

Org-scoped (`/organizations/{org_id}/plugins/...`): `POST /publish`,
`PUT /{id}` (republish, re-triggers moderation), `GET /published`,
`DELETE /{id}`, `POST /{id}/install`, `GET /installed`, `PATCH
/installed/{id}`, `DELETE /installed/{id}`, `POST /{id}/reviews`.

Admin (`/admin/plugins/...`, `require_superadmin`): `GET /pending`,
`POST /{id}/approve`, `POST /{id}/reject`, `POST /{id}/suspend`.

## Frontend

One consolidated page, `/dashboard/marketplace` (added to the sidebar
nav under "Widget & integrations"), 3 tabs — Browse / My plugins /
Installed — same tabbed-single-page discipline as `/dashboard/billing`
and every other multi-section screen in this project, not a separate
route per concern.

## Verified live, end-to-end, in a real browser (2026-09-11)

Registered a real user, published a real plugin through the actual
publish form (name/description/version/entry_point/permissions/code) —
confirmed real `201 Created`, a real S3 object written to a real
`documents` bucket (created live on this session's own Supabase
S3-compatible storage, since `S3_DOCUMENTS_BUCKET_NAME` had never been
configured on this dev machine before — a real, separate gap found and
fixed along the way), and a real `pending` row shown in "My plugins".
Promoted the same user to `superadmin` in the real dev DB, approved the
plugin via `POST /admin/plugins/{id}/approve`, confirmed it appeared in
the public `GET /marketplace/plugins` listing and in the Browse tab.
Installed it from the Browse tab (real `201 Created`), confirmed it
appeared in the Installed tab with working Disable/Uninstall.

## Honest remaining gaps

- No real execution sandbox (see "Honest scope on sandbox" above) —
  manifest/permission validation and static code scanning are real;
  actually running a plugin's code is not built.
- No plugin version history (`republish_plugin` overwrites in place).
- No org-scoped plugin visibility (every published-and-approved plugin
  is visible to every organization in the marketplace) — no
  private/unlisted plugin concept yet.
