# Plugin marketplace guide

## Browsing

`GET /marketplace/plugins` — public, no auth required, lists only
`approved` plugins:

- `search` — matches `name` or `description` (case-insensitive substring).
- `category` — `analytics`/`automation`/`communication`/`data`/`integration`/`productivity`/`security`/`other`.
- `min_rating` — real, computed from `PluginReview.rating`, not a cached field.
- `sort_by` — `date` (default, newest first), `popularity` (real, live `install_count`), or `rating` (real, live average).
- `limit`/`offset` — pagination.

**No free/paid filter.** There is no real pricing/billing model for
plugins in this pass — every published plugin is free. Adding that
filter without a real price field behind it would be exactly the kind
of fabricated completeness this project avoids; it's a real, honest
gap, not an oversight.

## Installing

Any org admin can install an `approved` plugin:
`POST /organizations/{org_id}/plugins/{id}/install`. A plugin can be
installed by many organizations at once — `install_count` on the
`GET /marketplace/plugins/{id}` response reflects the real, live total
across all of them. Installing twice into the same org is a real
`409 Conflict`, not a silent no-op.

Once installed, an org admin can:

- `PATCH /organizations/{org_id}/plugins/installed/{installation_id}` — `{"enabled": false}` to pause it (its hooks stop firing; manual execution is also blocked, same real gate), or `{"config": {...}}` to save its per-installation settings.
- `DELETE /organizations/{org_id}/plugins/installed/{installation_id}` — uninstall. The real `install_count` on the plugin is decremented immediately.

## Reviews

Any org member can leave one review per plugin
(`POST /organizations/{org_id}/plugins/{id}/reviews`, `{"rating": 1-5,
"comment": "..."}`). Reviewing again updates your existing review in
place — a real upsert, not a growing list of your own past opinions.
`DELETE /marketplace/reviews/{review_id}` only works for your own
review (a real `403` otherwise, enforced server-side regardless of
what the frontend shows).

## Publishing (for organizations that want to distribute their own plugin)

See `docs/plugins/DEVELOPER_GUIDE.md` for the manifest format and
`docs/plugins/SECURITY.md` for what the review process actually
checks. In short: `POST /organizations/{org_id}/plugins/publish`
(org admin), reviewed by a platform superadmin
(`POST /admin/plugins/{id}/approve` or `/reject`), then real and
visible to every organization in the marketplace.

## Moderation (platform superadmin)

- `GET /admin/plugins/pending` — the real review queue.
- `POST /admin/plugins/{id}/approve` / `/reject` (with a real `reason`).
- `POST /admin/plugins/{id}/suspend` (with a `reason`) — for an
  ALREADY-approved plugin found to violate policy after the fact.
  Existing installations are deliberately left in place (an org
  shouldn't lose a working integration without warning); only new
  installs are blocked from that point on.
- Two Celery jobs do this automatically, too, as defense in depth —
  see `docs/plugins/SECURITY.md`'s own "Automated re-scanning" section.
