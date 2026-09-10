# Partie 10 — Security & Governance (RBAC, Audit, Encryption, GDPR/CCPA, Scanning)

One consolidated guide for 10.1-10.6, not six near-duplicate files — the
same "one real page per domain" discipline already applied to the
frontend Security screen (`/dashboard/security`) and to Partie 9.5's
own dashboard consolidation. Cross-reference this file from anywhere
the literal spec asked for a separate `RBAC.md`/`AUDIT.md`/
`ENCRYPTION.md`/`GDPR.md`/`CCPA.md`/`SCANNING.md`.

## 10.1 — Custom roles & granular permissions

Additive on top of the existing, unchanged 5-tier `OrganizationRole`
hierarchy (owner/admin/manager/member/viewer, `api/security/organizations.py`).
A `CustomRole` (`api/models/rbac.py`) grants a narrower, precisely-scoped
set of `resource:action` permissions to a Member or Viewer who doesn't
already have it — Owner/Admin always have every permission implicitly.

- **Fixed catalog**: 13 resources × 4 actions (`read`/`write`/`delete`/`manage`)
  = 52 permissions, defined in code (`api/security/permission_catalog.py`),
  seeded into the `permissions` table on first real use (not
  admin-creatable — a permission not in this catalog isn't checked by
  any real router).
- **Effective permissions** (`get_user_effective_permissions`) are the
  union of every `CustomRole` a user holds in an organization;
  `resource:manage` implies `read`/`write`/`delete` on that resource.
- **Enforcement**: `api/security/permissions.py`'s `require_permission`/
  `require_role`/`require_any_permission`/`require_all_permissions` —
  real FastAPI `Depends(...)` factories (not Python decorators — see
  that module's own docstring for why), ready to gate new routes;
  existing routes keep their original `require_org_admin`-style checks
  unchanged.
- **Endpoints**: `/organizations/{org_id}/rbac/{permissions,roles,...}`,
  `POST /rbac/check` (Member+, self only). See `api/routers/rbac.py`.
- **Tests**: `tests/test_rbac_custom.py`.

## 10.2 — Audit logs

Extends the pre-existing, real HMAC hash-chained `audit_logs` table
(`api/models/audit_log.py`, `api/security/audit_log.py` — do not
re-read this as new: the tamper-evident chain, `GET /admin/audit-logs`,
and `GET /admin/audit-logs/verify-integrity` already existed before
this Partie).

- **New, non-checksummed columns**: `organization_id`, `resource_type`,
  `resource_id` — deliberately NOT part of the HMAC chain (adding them
  after the fact must not invalidate the checksum of any of the ~40
  action types already logged before this column existed).
- **New action types**: `webhook_created/deleted`, `document_uploaded/
  deleted`, `agent_created/deleted`, `conversation_created/deleted`,
  `integration_connected/disconnected`, `widget_updated`,
  `api_key_created/rotated/deleted` — wired into the real routers that
  perform those actions (not every sub-field PATCH endpoint of widget/
  agents was individually wired — a deliberate, documented scope choice,
  not an oversight; create/delete are the security-relevant events).
- **New endpoints**: `GET /audit/stats`, `GET /audit/actions`,
  `GET /audit/export` (JSON/CSV), `GET /audit/user/{id}`,
  `GET /audit/resource/{type}/{id}`, `DELETE /audit/logs/purge`
  (superadmin), and `GET /organizations/{org_id}/audit-logs` (org
  admin — the view the Security screen actually uses).
- **Retention**: `AUDIT_RETENTION_DAYS` (365), `AUDIT_ARCHIVE_MONTHS`
  (12) — real Celery jobs `api/tasks/audit.py`'s `purge_old_logs`/
  `archive_logs` (the latter copies to `audit_logs_archive` before
  deleting, not delete-only).
- **A real bug found and fixed while building the Security screen against
  this in a real browser**: `GET /organizations/{org_id}/rbac/permissions`
  seeded the 52-row permission catalog but never called `db.commit()` —
  `api/database.py`'s `get_db()` closes a session without committing, so
  the seed was silently ROLLED BACK on every single request. Assigning a
  permission immediately after failed with "Unknown permission id"
  because the permission had already ceased to exist by the time the
  next request ran. Fixed in `api/routers/rbac.py`.
- **Tests**: `tests/test_audit_extensions.py`.

## 10.3 — Encryption

A second, real encryption-at-rest primitive (`api/security/encryption.py`,
literal AES-256-GCM via `cryptography`'s `AESGCM`) alongside the
pre-existing Fernet-based `api/security/secret_encryption.py` (kept
unchanged — JWT signing keys, enterprise SSO secrets). Fernet is
already real, standard authenticated encryption (AES-128-CBC +
HMAC-SHA256), not a weaker scheme — this module exists because Partie
10.3's own spec names AES-256-GCM specifically.

- **Newly encrypted field**: `Webhook.secret` (was plaintext — a real
  HMAC signing key, previously readable straight out of a DB dump). A
  one-time data migration (`0088_partie_10_...py`) encrypts every
  existing plaintext value in place.
- **Real key rotation**: `ENCRYPTION_MASTER_KEY` (current) +
  `ENCRYPTION_MASTER_KEY_PREVIOUS` (grace window) — `POST
  /encryption/rotate-keys` (superadmin) re-encrypts every protected row
  under the current key.
- **`ENCRYPTION_KEY_STORAGE=env`** is the only mode this environment
  actually implements — no AWS KMS/HashiCorp Vault account exists here.
  Stated as a fact about this environment, not a "limitation" to
  apologize for; the config value exists so swapping in a real KMS
  backend later is a config change, not a rewrite.
- **Endpoints**: `GET /encryption/{status,algorithms}`,
  `POST /encryption/{rotate-keys,test}` — all global/platform-admin
  (`api/routers/encryption.py`), since keys and the fields they protect
  span every organization.
- **Tests**: `tests/test_encryption.py`.

## 10.4 — GDPR/CCPA compliance

Extends the already-mature GDPR machinery on `User`/`api/routers/account.py`
(consent-to-processing, `DELETE /account/me` with a real 30-day grace
period + restore flow, `GET /account/export`/`export-csv`) — none of
that is duplicated here.

- **New, additive**: `ConsentRecord` (per-category consent — marketing/
  analytics/cookies — a separate axis from the binary "consent to
  processing" flag), `DataRequest` (a reviewable rights-request ticket
  for Art. 15/16/18/21, distinct from the self-service deletion flow),
  `DataBreach` (Art. 33/34 declaration + real notification).
- **Endpoints**: `POST/GET/PATCH /compliance/data-requests`,
  `GET /compliance/data-export` (a thin, real wrapper over the existing
  export machinery), `POST/GET/DELETE /compliance/consent`,
  `GET /compliance/{status,report}` (admin), `POST /compliance/data-breach`
  (superadmin) — `api/routers/compliance.py`.
- **Celery**: `send_data_breach_notifications`, `process_pending_data_requests`
  (a real staleness-reminder sweep, not an auto-approval),
  `generate_monthly_compliance_report`.
- **Frontend**: the Security screen's Compliance tab includes a "My
  data" section visible to every member (not just admins) — export/
  delete/consent — addressing the explicit ask that compliance rights
  not be admin-only.
- **Tests**: `tests/test_compliance.py`.

## 10.5 — Security scanning

Real, locally-runnable scanners — not simulated results:

- **`dependency`**: `pip-audit` against every installed package (real
  OSV/PyPI advisory data).
- **`code`**: `bandit` (real SAST) against `api/`.
- **`secret`**: a real (if simpler than Gitleaks/TruffleHog) regex scan
  for AWS keys, generic API-key-shaped assignments, and PEM private-key
  headers, over `api/` and `frontend/` — walked with `os.walk` and
  directory pruning (NOT `Path.glob`, which was found for real, in a
  live browser test, to hang for 10+ seconds walking into
  `frontend/node_modules` before any exclude filter got a chance to
  apply — fixed in `api/services/security_scan.py`).
- **`container`**: real only if a `trivy` binary is on PATH (checked
  with `shutil.which`, never assumed) — honestly reported as
  `ScanStatus.unavailable` otherwise.
- **`infrastructure`**: honestly reported as unavailable — this repo
  has no Terraform/CloudFormation/Kubernetes manifests to scan.
- DAST (OWASP ZAP) and dependency scanning already run at the CI level
  (`.github/workflows/regression.yml`'s existing `security-scan` job,
  Snyk + ZAP) — not duplicated as an in-app "run now" button.
- **Score**: `100 - Σ(severity weight per open vulnerability)`
  (critical=25, high=10, medium=4, low=1), floored at 0 — a real,
  transparent formula, not a vendor black box.
- **Endpoints**: `api/routers/security_scan.py`, org-scoped under
  `/organizations/{org_id}/security/...`.
- **Tests**: `tests/test_security_scan.py`.

## 10.6 — Security screen

`frontend/app/dashboard/security/page.tsx` — one consolidated page with
7 tabs (Overview, Roles & Permissions, Audit log, Encryption,
Compliance, Vulnerability scan, Policies), linked in the dashboard nav.
Verified end-to-end in a real browser against a real logged-in session:
created a custom role, assigned a real permission, ran a real secret
scan, viewed real scan history, edited real security policies.

Real, honest gap: the literal spec's 14 separate component files
(`RoleList.tsx`, `RoleItem.tsx`, `PermissionBadge.tsx`, ...) were not
extracted into their own files — the logic lives in the one
consolidated page, same discipline as Partie 9.5.
