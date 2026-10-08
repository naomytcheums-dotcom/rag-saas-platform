# Autonomous audit 03 — security inventory

Date: 2026-10-03.

Generated route dependency inventory; declaring a dependency does not prove authorization.
Filter tenant, exploitable behavior and database policies require separate specialist/live tests.
See `SECURITY_REPORT.md` for verified specialist findings and coverage limits.

## All API operations currently registered

| Method | Path | Handler source | Dependency call names | Tenant filter verified |
|---|---|---|---|---|
| POST | `/auth/register` | `api/routers/auth.py:89` | get_db | UNKNOWN |
| POST | `/auth/login` | `api/routers/auth.py:196` | get_db | UNKNOWN |
| POST | `/auth/refresh` | `api/routers/auth.py:330` | get_db, verify_csrf | UNKNOWN |
| POST | `/auth/logout` | `api/routers/auth.py:382` | get_db, verify_csrf | UNKNOWN |
| POST | `/auth/password/forgot` | `api/routers/password.py:32` | get_db | UNKNOWN |
| POST | `/auth/password/reset` | `api/routers/password.py:57` | get_db | UNKNOWN |
| POST | `/auth/verify-email/request` | `api/routers/verify.py:22` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/auth/verify-email/confirm` | `api/routers/verify.py:44` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/auth/oauth/{provider}/authorize` | `api/routers/oauth.py:200` | none declared | UNKNOWN |
| GET | `/auth/oauth/{provider}/callback` | `api/routers/oauth.py:214` | none declared | UNKNOWN |
| POST | `/auth/2fa/setup` | `api/routers/two_factor.py:115` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/auth/2fa/enable` | `api/routers/two_factor.py:139` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/auth/2fa/disable` | `api/routers/two_factor.py:207` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/auth/2fa/recovery-codes/regenerate` | `api/routers/two_factor.py:259` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/auth/2fa/recovery-codes/status` | `api/routers/two_factor.py:296` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/auth/2fa/verify-login` | `api/routers/two_factor.py:322` | get_db | UNKNOWN |
| POST | `/auth/2fa/verify-recovery-code` | `api/routers/two_factor.py:368` | get_db | UNKNOWN |
| POST | `/auth/2fa/lockout-recovery/request` | `api/routers/two_factor.py:431` | get_db | UNKNOWN |
| POST | `/auth/2fa/lockout-recovery/confirm` | `api/routers/two_factor.py:472` | get_db | UNKNOWN |
| GET | `/sessions` | `api/routers/sessions.py:32` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/sessions/{session_id}` | `api/routers/sessions.py:65` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/account/me` | `api/routers/account.py:71` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/account/consent/accept-updated-terms` | `api/routers/account.py:81` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/account/profile` | `api/routers/account.py:102` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/account/preferences` | `api/routers/account.py:135` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/account/avatar` | `api/routers/account.py:164` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/account/set-password` | `api/routers/account.py:188` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/account/change-password` | `api/routers/account.py:250` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/account/me` | `api/routers/account.py:328` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/account/restore/request` | `api/routers/account.py:373` | get_db | UNKNOWN |
| POST | `/account/restore/confirm` | `api/routers/account.py:405` | get_db | UNKNOWN |
| POST | `/account/consent/withdraw` | `api/routers/account.py:442` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/account/consent/reactivate/request` | `api/routers/account.py:480` | get_db | UNKNOWN |
| POST | `/account/consent/reactivate/confirm` | `api/routers/account.py:510` | get_db | UNKNOWN |
| GET | `/account/export` | `api/routers/account.py:547` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/account/export-csv` | `api/routers/account.py:581` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/account/audit-logs` | `api/routers/audit.py:73` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/admin/audit-logs` | `api/routers/audit.py:93` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/organizations/{org_id}/audit-logs` | `api/routers/audit.py:109` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_admin, require_org_member | UNKNOWN |
| GET | `/admin/failed-logins` | `api/routers/audit.py:128` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/audit-logs/verify-integrity` | `api/routers/audit.py:175` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/audit/stats` | `api/routers/audit.py:187` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/audit/actions` | `api/routers/audit.py:212` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/audit/export` | `api/routers/audit.py:220` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/audit/user/{user_id}` | `api/routers/audit.py:247` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/audit/resource/{resource_type}/{resource_id}` | `api/routers/audit.py:255` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| DELETE | `/audit/logs/purge` | `api/routers/audit.py:272` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/admin/jwt-keys` | `api/routers/audit.py:294` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/auth/webauthn/register/options` | `api/routers/webauthn.py:59` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/auth/webauthn/register/verify` | `api/routers/webauthn.py:79` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/auth/webauthn/credentials` | `api/routers/webauthn.py:124` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/auth/webauthn/credentials/{credential_id}` | `api/routers/webauthn.py:132` | HTTPBearer, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/auth/webauthn/authenticate/options` | `api/routers/webauthn.py:165` | get_db | UNKNOWN |
| POST | `/auth/webauthn/authenticate/verify` | `api/routers/webauthn.py:189` | get_db | UNKNOWN |
| POST | `/admin/sso/connections` | `api/routers/enterprise_sso.py:112` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/sso/connections` | `api/routers/enterprise_sso.py:143` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| DELETE | `/admin/sso/connections/{connection_id}` | `api/routers/enterprise_sso.py:149` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/auth/sso/discover` | `api/routers/enterprise_sso.py:161` | get_db | UNKNOWN |
| GET | `/auth/sso/{connection_id}/authorize` | `api/routers/enterprise_sso.py:184` | get_db | UNKNOWN |
| GET | `/auth/sso/{connection_id}/callback` | `api/routers/enterprise_sso.py:211` | get_db | UNKNOWN |
| PATCH | `/admin/users/{user_id}/role` | `api/routers/admin_users.py:28` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/organizations` | `api/routers/organizations.py:42` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/organizations` | `api/routers/organizations.py:58` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/organizations/{org_id}` | `api/routers/organizations.py:69` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}` | `api/routers/organizations.py:77` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| DELETE | `/organizations/{org_id}` | `api/routers/organizations.py:108` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/members` | `api/routers/organization_members.py:83` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_can_invite_members | UNKNOWN |
| POST | `/organizations/{org_id}/members/invite` | `api/routers/organization_members.py:99` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_can_invite_members | UNKNOWN |
| PATCH | `/organizations/{org_id}/members/{user_id}/role` | `api/routers/organization_members.py:180` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/members/{user_id}` | `api/routers/organization_members.py:216` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/workspaces` | `api/routers/workspaces.py:64` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/workspaces` | `api/routers/workspaces.py:74` | HTTPBearer, _check, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| PATCH | `/workspaces/{workspace_id}` | `api/routers/workspaces.py:101` | HTTPBearer, _check, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/workspaces/{workspace_id}` | `api/routers/workspaces.py:118` | HTTPBearer, _check, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/organizations/{org_id}/workflows` | `api/routers/workflows.py:56` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/workflows` | `api/routers/workflows.py:70` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/workflows/import` | `api/routers/workflows.py:89` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| GET | `/workflows/{workflow_id}/export` | `api/routers/workflows.py:103` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_member | UNKNOWN |
| GET | `/workflows/{workflow_id}` | `api/routers/workflows.py:109` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_member | UNKNOWN |
| PATCH | `/workflows/{workflow_id}` | `api/routers/workflows.py:115` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_manager | UNKNOWN |
| DELETE | `/workflows/{workflow_id}` | `api/routers/workflows.py:130` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_manager | UNKNOWN |
| POST | `/workflows/{workflow_id}/validate` | `api/routers/workflows.py:139` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_manager | UNKNOWN |
| POST | `/workflows/{workflow_id}/triggers` | `api/routers/workflows.py:149` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_manager | UNKNOWN |
| GET | `/workflows/{workflow_id}/triggers` | `api/routers/workflows.py:170` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_manager | UNKNOWN |
| DELETE | `/workflows/{workflow_id}/triggers/{trigger_id}` | `api/routers/workflows.py:178` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_manager | UNKNOWN |
| POST | `/webhooks/{trigger_id}` | `api/routers/workflows.py:190` | get_db | UNKNOWN |
| POST | `/workflows/{workflow_id}/run` | `api/routers/workflows.py:204` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_member | UNKNOWN |
| GET | `/workflows/{workflow_id}/runs` | `api/routers/workflows.py:224` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_member | UNKNOWN |
| GET | `/workflows/runs/{run_id}` | `api/routers/workflows.py:233` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_run_member | UNKNOWN |
| GET | `/workflows/runs/{run_id}/stream` | `api/routers/workflows.py:239` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_run_member | UNKNOWN |
| GET | `/workflows/runs/{run_id}/trace` | `api/routers/workflows.py:245` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_run_member | UNKNOWN |
| GET | `/workflows/runs/{run_id}/human-blocks` | `api/routers/workflows.py:256` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_run_member | UNKNOWN |
| GET | `/workflows/runs/{run_id}/human-blocks/{block_id}` | `api/routers/workflows.py:266` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_run_member | UNKNOWN |
| POST | `/workflows/runs/{run_id}/human-blocks/{block_id}/submit` | `api/routers/workflows.py:279` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_run_member | UNKNOWN |
| GET | `/workflows/{workflow_id}/versions` | `api/routers/workflows.py:302` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_member | UNKNOWN |
| GET | `/workflows/{workflow_id}/versions/{version_number}` | `api/routers/workflows.py:310` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_member | UNKNOWN |
| POST | `/workflows/{workflow_id}/versions/create` | `api/routers/workflows.py:322` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_manager | UNKNOWN |
| POST | `/workflows/{workflow_id}/versions/restore` | `api/routers/workflows.py:333` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_manager | UNKNOWN |
| POST | `/workflows/{workflow_id}/versions/diff` | `api/routers/workflows.py:348` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_workflow_member | UNKNOWN |
| GET | `/resources/{resource_type}/{resource_id}/permissions` | `api/routers/resource_permissions.py:134` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/resources/{resource_type}/{resource_id}/permissions` | `api/routers/resource_permissions.py:144` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/resources/{resource_type}/{resource_id}/permissions/{user_id}/{action}` | `api/routers/resource_permissions.py:185` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/users/me/permissions` | `api/routers/resource_permissions.py:208` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/organizations/{org_id}/retrieval-diagnostics` | `api/routers/retrieval_diagnostics.py:29` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/teams` | `api/routers/teams.py:71` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/teams` | `api/routers/teams.py:81` | HTTPBearer, _check, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| GET | `/teams/{team_id}` | `api/routers/teams.py:107` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_team_member | UNKNOWN |
| PATCH | `/teams/{team_id}` | `api/routers/teams.py:113` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_team_org_manager | UNKNOWN |
| DELETE | `/teams/{team_id}` | `api/routers/teams.py:126` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_team_org_manager | UNKNOWN |
| GET | `/teams/{team_id}/members` | `api/routers/teams.py:141` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_team_member | UNKNOWN |
| POST | `/teams/{team_id}/members` | `api/routers/teams.py:157` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_team_admin | UNKNOWN |
| PATCH | `/teams/{team_id}/members/{user_id}` | `api/routers/teams.py:207` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_team_admin | UNKNOWN |
| DELETE | `/teams/{team_id}/members/{user_id}` | `api/routers/teams.py:238` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_team_admin | UNKNOWN |
| GET | `/organizations/{org_id}/invitations` | `api/routers/invitations.py:63` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/invitations` | `api/routers/invitations.py:73` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/invitations/{invitation_id}` | `api/routers/invitations.py:122` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| POST | `/invitations/accept` | `api/routers/invitations.py:143` | get_db | UNKNOWN |
| GET | `/organizations/{org_id}/quotas` | `api/routers/quotas.py:47` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_admin, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/quotas` | `api/routers/quotas.py:54` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/users/me/limits` | `api/routers/user_limits.py:43` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/organizations/{org_id}/members/{user_id}/limits` | `api/routers/user_limits.py:59` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/members/{user_id}/limits` | `api/routers/user_limits.py:70` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/usage` | `api/routers/usage.py:31` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/usage/details` | `api/routers/usage.py:57` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/usage/export` | `api/routers/usage.py:99` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/settings` | `api/routers/organization_settings.py:27` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/settings` | `api/routers/organization_settings.py:35` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/llm-config` | `api/routers/organization_settings.py:84` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/llm-config` | `api/routers/organization_settings.py:91` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| DELETE | `/organizations/{org_id}/llm-config/{provider}` | `api/routers/organization_settings.py:108` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/branding` | `api/routers/organization_branding.py:44` | get_db | UNKNOWN |
| PATCH | `/organizations/{org_id}/branding` | `api/routers/organization_branding.py:54` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| POST | `/organizations/{org_id}/branding/logo` | `api/routers/organization_branding.py:65` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| POST | `/organizations/{org_id}/branding/favicon` | `api/routers/organization_branding.py:93` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| DELETE | `/organizations/{org_id}/branding/logo` | `api/routers/organization_branding.py:117` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| DELETE | `/organizations/{org_id}/branding/favicon` | `api/routers/organization_branding.py:131` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/sandbox` | `api/routers/sandbox.py:19` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/sandbox` | `api/routers/sandbox.py:29` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/sandbox/{sandbox_id}` | `api/routers/sandbox.py:49` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/sandbox/{sandbox_id}/reset` | `api/routers/sandbox.py:63` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/domains` | `api/routers/custom_domains.py:76` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/domains` | `api/routers/custom_domains.py:91` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| DELETE | `/organizations/{org_id}/domains/{domain_id}` | `api/routers/custom_domains.py:101` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/domains/verify/{token}` | `api/routers/custom_domains.py:125` | get_db | UNKNOWN |
| POST | `/organizations/{org_id}/domains/{domain_id}/verify` | `api/routers/custom_domains.py:159` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/domains/{domain_id}/status` | `api/routers/custom_domains.py:179` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| POST | `/organizations/{org_id}/custom-tools` | `api/routers/custom_tools.py:33` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/custom-tools` | `api/routers/custom_tools.py:47` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/custom-tools/{tool_id}` | `api/routers/custom_tools.py:54` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_custom_tool_member | UNKNOWN |
| PATCH | `/custom-tools/{tool_id}` | `api/routers/custom_tools.py:60` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_custom_tool_manager | UNKNOWN |
| DELETE | `/custom-tools/{tool_id}` | `api/routers/custom_tools.py:75` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_custom_tool_manager | UNKNOWN |
| POST | `/custom-tools/{tool_id}/execute` | `api/routers/custom_tools.py:84` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_custom_tool_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/salesforce/import` | `api/routers/crm.py:69` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/hubspot/import` | `api/routers/crm.py:88` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/jira/import` | `api/routers/crm.py:107` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/zendesk/import` | `api/routers/crm.py:126` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/pipedrive/import` | `api/routers/crm.py:145` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/linear/import` | `api/routers/crm.py:168` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/asana/import` | `api/routers/crm.py:187` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/trello/import` | `api/routers/crm.py:206` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/airtable/import` | `api/routers/crm.py:227` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/dropbox/import` | `api/routers/crm.py:251` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/box/import` | `api/routers/crm.py:270` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/clickup/import` | `api/routers/crm.py:289` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/intercom/import` | `api/routers/crm.py:310` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/zoho/import` | `api/routers/crm.py:329` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/shopify/import` | `api/routers/crm.py:348` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/woocommerce/import` | `api/routers/crm.py:367` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/docusign/import` | `api/routers/crm.py:386` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/monday/import` | `api/routers/crm.py:409` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/gitlab/import` | `api/routers/crm.py:428` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/bitbucket/import` | `api/routers/crm.py:447` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/azure-devops/import` | `api/routers/crm.py:466` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/basecamp/import` | `api/routers/crm.py:485` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/wrike/import` | `api/routers/crm.py:504` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/smartsheet/import` | `api/routers/crm.py:523` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/coda/import` | `api/routers/crm.py:542` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/miro/import` | `api/routers/crm.py:561` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/podio/import` | `api/routers/crm.py:584` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/pipefy/import` | `api/routers/crm.py:605` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/hive/import` | `api/routers/crm.py:626` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/teamwork/import` | `api/routers/crm.py:647` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/nifty/import` | `api/routers/crm.py:666` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/smartsuite/import` | `api/routers/crm.py:687` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/process-street/import` | `api/routers/crm.py:708` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/activecampaign/import` | `api/routers/crm.py:727` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/mailchimp/import` | `api/routers/crm.py:746` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/crm/klaviyo/import` | `api/routers/crm.py:765` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/mcp-servers` | `api/routers/mcp_servers.py:52` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/mcp-servers` | `api/routers/mcp_servers.py:75` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/mcp-servers/{server_id}` | `api/routers/mcp_servers.py:82` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/mcp-servers/{server_id}` | `api/routers/mcp_servers.py:98` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/mcp-servers/{server_id}/test` | `api/routers/mcp_servers.py:108` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/mcp-servers/{server_id}/tools` | `api/routers/mcp_servers.py:120` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/mcp-servers/{server_id}/sync` | `api/routers/mcp_servers.py:129` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/mcp-servers/{server_id}/tools/{tool_name}/call` | `api/routers/mcp_servers.py:144` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/mcp/v1/tools` | `api/routers/mcp_server.py:77` | _check, get_db, require_organization_api_key | UNKNOWN |
| POST | `/mcp/v1/tools/{tool_name}/call` | `api/routers/mcp_server.py:107` | _check, get_db, require_organization_api_key | UNKNOWN |
| GET | `/a2a/{org_id}/.well-known/agent-card.json` | `api/routers/a2a.py:103` | _check, get_db, require_organization_api_key | UNKNOWN |
| POST | `/a2a/{org_id}` | `api/routers/a2a.py:116` | _check, get_db, require_organization_api_key | UNKNOWN |
| POST | `/organizations/{org_id}/factory/blueprint` | `api/routers/agent_factory.py:62` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/factory/deploy` | `api/routers/agent_factory.py:74` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/quality-alerts/metrics` | `api/routers/quality_alerts.py:107` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/quality-alerts/rules` | `api/routers/quality_alerts.py:112` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/quality-alerts/rules` | `api/routers/quality_alerts.py:117` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/quality-alerts/rules/{rule_id}` | `api/routers/quality_alerts.py:131` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/quality-alerts/rules/{rule_id}` | `api/routers/quality_alerts.py:143` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/quality-alerts/rules/{rule_id}/test` | `api/routers/quality_alerts.py:152` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/quality-alerts/history` | `api/routers/quality_alerts.py:160` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/quality-alerts/channels` | `api/routers/quality_alerts.py:168` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/quality-alerts/channels` | `api/routers/quality_alerts.py:173` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/quality-alerts/channels/{channel_id}` | `api/routers/quality_alerts.py:183` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/domains/{domain_id}/ssl/generate` | `api/routers/ssl_certificates.py:67` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/domains/{domain_id}/ssl` | `api/routers/ssl_certificates.py:85` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| POST | `/organizations/{org_id}/domains/{domain_id}/ssl/renew` | `api/routers/ssl_certificates.py:97` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| DELETE | `/organizations/{org_id}/domains/{domain_id}/ssl` | `api/routers/ssl_certificates.py:115` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| POST | `/organizations/{org_id}/domains/{domain_id}/email/verify` | `api/routers/email_domains.py:45` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/domains/{domain_id}/email/status` | `api/routers/email_domains.py:57` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/domains/{domain_id}/email/dns` | `api/routers/email_domains.py:66` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/white-label` | `api/routers/white_label.py:42` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| PATCH | `/organizations/{org_id}/white-label` | `api/routers/white_label.py:50` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_member, require_org_owner | UNKNOWN |
| GET | `/organizations/{org_id}/whitelabel/config` | `api/routers/white_label.py:70` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/whitelabel/config` | `api/routers/white_label.py:78` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/whitelabel/domain` | `api/routers/white_label.py:89` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/whitelabel/domain` | `api/routers/white_label.py:102` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/whitelabel/domain/verify` | `api/routers/white_label.py:114` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/whitelabel/email` | `api/routers/white_label.py:126` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/whitelabel/email` | `api/routers/white_label.py:136` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/whitelabel/logo` | `api/routers/white_label.py:145` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/whitelabel/logo` | `api/routers/white_label.py:161` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/whitelabel/favicon` | `api/routers/white_label.py:170` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/whitelabel/preview` | `api/routers/white_label.py:186` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/whitelabel/reset` | `api/routers/white_label.py:194` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents` | `api/routers/documents.py:225` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/batch` | `api/routers/documents.py:265` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/url` | `api/routers/documents.py:299` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/sitemap` | `api/routers/documents.py:321` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/github/repo` | `api/routers/documents.py:344` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/github/issues` | `api/routers/documents.py:368` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/google-drive` | `api/routers/documents.py:394` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/google-docs` | `api/routers/documents.py:418` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/notion` | `api/routers/documents.py:443` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/confluence` | `api/routers/documents.py:466` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/documents/onedrive` | `api/routers/documents.py:489` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/documents` | `api/routers/documents.py:513` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/documents/outdated` | `api/routers/documents.py:528` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}` | `api/routers/documents.py:541` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/documents/{document_id}/check-modified` | `api/routers/documents.py:549` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}/metadata` | `api/routers/documents.py:570` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}/images` | `api/routers/documents.py:587` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}/preview` | `api/routers/documents.py:607` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}/progress` | `api/routers/documents.py:638` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}/progress/stream` | `api/routers/documents.py:651` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/documents/{document_id}` | `api/routers/documents.py:669` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/documents/{document_id}/permanent` | `api/routers/documents.py:694` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/documents/{document_id}/replace` | `api/routers/documents.py:717` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/organizations/{org_id}/tags` | `api/routers/documents.py:743` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/tags` | `api/routers/documents.py:761` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/tags/{tag_id}` | `api/routers/documents.py:780` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/tags/{tag_id}` | `api/routers/documents.py:806` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/documents/{document_id}/tags` | `api/routers/documents.py:824` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/documents/{document_id}/tags/{tag_id}` | `api/routers/documents.py:854` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}/tags` | `api/routers/documents.py:876` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}/versions` | `api/routers/documents.py:911` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}/versions/{version_number}` | `api/routers/documents.py:922` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/documents/{document_id}/versions` | `api/routers/documents.py:935` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/documents/{document_id}/versions/restore` | `api/routers/documents.py:967` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/documents/{document_id}/reindex` | `api/routers/documents.py:992` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/organizations/{org_id}/documents/reindex` | `api/routers/documents.py:1005` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/documents/{document_id}/history` | `api/routers/documents.py:1025` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/documents/{document_id}/status` | `api/routers/documents.py:1049` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/organizations/{org_id}/documents/status` | `api/routers/documents.py:1066` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/embeddings/status` | `api/routers/documents.py:1085` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/documents/{document_id}/duplicates` | `api/routers/documents.py:1109` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/organizations/{org_id}/documents/deduplicate` | `api/routers/documents.py:1123` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/documents/{document_id}/reindex-sync` | `api/routers/documents_sync.py:23` | none declared | UNKNOWN |
| POST | `/organizations/{org_id}/sources` | `api/routers/external_sources.py:76` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/sources` | `api/routers/external_sources.py:94` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| PATCH | `/sources/{source_id}` | `api/routers/external_sources.py:102` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/sources/{source_id}` | `api/routers/external_sources.py:115` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/sources/{source_id}/sync` | `api/routers/external_sources.py:126` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/organizations/{org_id}/reindex-schedules` | `api/routers/reindex_schedules.py:60` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/reindex-schedules` | `api/routers/reindex_schedules.py:74` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/reindex-schedules/{schedule_id}` | `api/routers/reindex_schedules.py:82` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/reindex-schedules/{schedule_id}` | `api/routers/reindex_schedules.py:98` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/organizations/{org_id}/batch/jobs` | `api/routers/batch_jobs.py:70` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/batch/jobs` | `api/routers/batch_jobs.py:86` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/batch/jobs/{job_id}` | `api/routers/batch_jobs.py:96` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/batch/jobs/{job_id}/cancel` | `api/routers/batch_jobs.py:105` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/batch/jobs/{job_id}/items` | `api/routers/batch_jobs.py:120` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/responses/{response_id}` | `api/routers/citations.py:67` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_response_member | UNKNOWN |
| GET | `/responses/{response_id}/flight-recording` | `api/routers/citations.py:75` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_response_member | UNKNOWN |
| GET | `/responses/{response_id}/citations` | `api/routers/citations.py:99` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_response_member | UNKNOWN |
| GET | `/responses/{response_id}/confidence` | `api/routers/citations.py:113` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_response_member | UNKNOWN |
| GET | `/responses/{response_id}/confidence/factors` | `api/routers/citations.py:123` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_response_member | UNKNOWN |
| GET | `/citations/{citation_id}` | `api/routers/citations.py:132` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_citation_member | UNKNOWN |
| GET | `/documents/{document_id}/citations` | `api/routers/citations.py:145` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_document_citations_member | UNKNOWN |
| GET | `/chat/stream` | `api/routers/chat_stream.py:72` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/chat/stream` | `api/routers/chat_stream.py:83` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/organizations/{org_id}/search` | `api/routers/search.py:42` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/rag-control-plane/health-check` | `api/routers/rag_control_plane.py:30` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/evolution/run` | `api/routers/rag_control_plane.py:79` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/evolution/retrieval/run-multi` | `api/routers/rag_control_plane.py:102` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/evolution/retrieval/run` | `api/routers/rag_control_plane.py:128` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/agents/{agent_id}/retrieval-config/apply` | `api/routers/rag_control_plane.py:152` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/ab-tests/{test_id}/evaluate-canary` | `api/routers/rag_control_plane.py:183` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/agents/{agent_id}/tools/{tool_name}/permissions` | `api/routers/tool_permissions.py:38` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/agents/{agent_id}/tools/{tool_name}/permissions/{user_id}` | `api/routers/tool_permissions.py:50` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/agents/{agent_id}/tools/permissions` | `api/routers/tool_permissions.py:61` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/users/me/tools/permissions` | `api/routers/tool_permissions.py:69` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/admin/tools/timeout` | `api/routers/tool_config.py:29` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| PATCH | `/admin/tools/{tool_name}/timeout` | `api/routers/tool_config.py:34` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/admin/tools/budget` | `api/routers/tool_config.py:47` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| PATCH | `/admin/tools/{tool_name}/budget` | `api/routers/tool_config.py:52` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/admin/tools/usage` | `api/routers/tool_config.py:65` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/admin/tools/{tool_name}/budget/reset` | `api/routers/tool_config.py:70` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/admin/tools/fallback` | `api/routers/tool_config.py:81` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/admin/tools/fallback` | `api/routers/tool_config.py:86` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| DELETE | `/admin/tools/fallback/{tool_name}` | `api/routers/tool_config.py:95` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/organizations/{org_id}/approvals/pending` | `api/routers/human_approval.py:35` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/approvals/{approval_id}/approve` | `api/routers/human_approval.py:60` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/approvals/{approval_id}/reject` | `api/routers/human_approval.py:71` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/approvals/{approval_id}` | `api/routers/human_approval.py:82` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/conversations` | `api/routers/conversations.py:67` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations` | `api/routers/conversations.py:100` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/stats` | `api/routers/conversations.py:116` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/search` | `api/routers/conversations.py:121` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/deleted` | `api/routers/conversations.py:139` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/public` | `api/routers/conversations.py:147` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/{conversation_id}` | `api/routers/conversations.py:155` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/{conversation_id}/messages` | `api/routers/conversations.py:162` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/conversations/{conversation_id}/messages` | `api/routers/conversations.py:171` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/conversations/{conversation_id}` | `api/routers/conversations.py:185` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/conversations/{conversation_id}/archive` | `api/routers/conversations.py:203` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/conversations/{conversation_id}` | `api/routers/conversations.py:213` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/conversations/{conversation_id}/restore` | `api/routers/conversations.py:226` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/conversations/{conversation_id}/permanent` | `api/routers/conversations.py:238` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/{conversation_id}/export/pdf` | `api/routers/conversations.py:255` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/{conversation_id}/export/docx` | `api/routers/conversations.py:266` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/{conversation_id}/export/json` | `api/routers/conversations.py:280` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/{conversation_id}/export/markdown` | `api/routers/conversations.py:290` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/conversations/{conversation_id}/share` | `api/routers/conversations.py:304` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/{conversation_id}/shares` | `api/routers/conversations.py:318` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/conversations/{conversation_id}/visibility` | `api/routers/conversations.py:328` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/conversations/{conversation_id}/messages/{message_id}/regenerate` | `api/routers/conversations.py:359` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/conversations/{conversation_id}/messages/{message_id}` | `api/routers/conversations.py:377` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/conversations/{conversation_id}/messages/{message_id}/edit` | `api/routers/conversations.py:392` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/conversations/{conversation_id}/messages/{message_id}/edit-history` | `api/routers/conversations.py:407` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/conversations/{conversation_id}/messages/{message_id}/revert` | `api/routers/conversations.py:419` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/conversations/{conversation_id}/messages/{message_id}/retry` | `api/routers/conversations.py:434` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/share/{token}` | `api/routers/conversation_shares.py:21` | get_db | UNKNOWN |
| DELETE | `/share/{token}` | `api/routers/conversation_shares.py:33` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/messages/{message_id}/feedback` | `api/routers/feedback.py:43` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/messages/{message_id}/feedback` | `api/routers/feedback.py:58` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/feedback/{feedback_id}` | `api/routers/feedback.py:66` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/feedback/{feedback_id}` | `api/routers/feedback.py:85` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/organizations/{org_id}/feedback/stats` | `api/routers/feedback.py:98` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/suggested-questions` | `api/routers/questions.py:41` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/messages/{message_id}/follow-up` | `api/routers/questions.py:61` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/messages/{message_id}/follow-up` | `api/routers/questions.py:76` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/i18n/languages` | `api/routers/i18n.py:15` | none declared | UNKNOWN |
| GET | `/i18n/translations/{language}` | `api/routers/i18n.py:20` | none declared | UNKNOWN |
| GET | `/i18n/detect` | `api/routers/i18n.py:33` | none declared | UNKNOWN |
| POST | `/i18n/language` | `api/routers/i18n.py:40` | none declared | UNKNOWN |
| GET | `/voice/elevenlabs/voices` | `api/routers/voice.py:34` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/voice/tts` | `api/routers/voice.py:42` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/voice/stt` | `api/routers/voice.py:51` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/voice/organizations/{org_id}/chat` | `api/routers/voice.py:63` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/voice/organizations/{org_id}/agent` | `api/routers/voice.py:84` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/conversations/{conversation_id}/voice-messages` | `api/routers/voice_messages.py:33` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/voice-messages/{message_id}` | `api/routers/voice_messages.py:43` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/voice-messages/{message_id}` | `api/routers/voice_messages.py:50` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/voice-messages/{message_id}/audio` | `api/routers/voice_messages.py:59` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/users/me/voice-settings` | `api/routers/voice_settings.py:14` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/users/me/voice-settings` | `api/routers/voice_settings.py:21` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/users/me/voice-settings/reset` | `api/routers/voice_settings.py:35` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/twilio/incoming` | `api/routers/twilio.py:26` | get_db | UNKNOWN |
| POST | `/twilio/speech` | `api/routers/twilio.py:37` | get_db | UNKNOWN |
| POST | `/twilio/dtmf` | `api/routers/twilio.py:47` | get_db | UNKNOWN |
| POST | `/twilio/status` | `api/routers/twilio.py:55` | get_db | UNKNOWN |
| POST | `/twilio/outbound` | `api/routers/twilio.py:67` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/twilio/calls` | `api/routers/twilio.py:76` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/twilio/{call_sid}/end` | `api/routers/twilio.py:81` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/organizations/{org_id}/api-keys` | `api/routers/public_api.py:62` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/api-keys` | `api/routers/public_api.py:85` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/api-keys/{key_id}` | `api/routers/public_api.py:92` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/api-keys/scopes` | `api/routers/public_api.py:117` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/organizations/{org_id}/api-keys/expiring` | `api/routers/public_api.py:125` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/api-keys/{key_id}` | `api/routers/public_api.py:136` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| PATCH | `/api-keys/{key_id}` | `api/routers/public_api.py:141` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| POST | `/api-keys/{key_id}/rotate` | `api/routers/public_api.py:157` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| GET | `/api-keys/{key_id}/rotation-history` | `api/routers/public_api.py:178` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| POST | `/api-keys/{key_id}/schedule-rotation` | `api/routers/public_api.py:183` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| PATCH | `/api-keys/{key_id}/expiration` | `api/routers/public_api.py:195` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| DELETE | `/api-keys/{key_id}/expiration` | `api/routers/public_api.py:204` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| GET | `/api-keys/{key_id}/rate-limit` | `api/routers/public_api.py:214` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| PATCH | `/api-keys/{key_id}/rate-limit` | `api/routers/public_api.py:219` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| GET | `/api-keys/{key_id}/quota` | `api/routers/public_api.py:235` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| PATCH | `/api-keys/{key_id}/quota` | `api/routers/public_api.py:240` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| GET | `/api-keys/{key_id}/quota/status` | `api/routers/public_api.py:253` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| PATCH | `/api-keys/{key_id}/scopes` | `api/routers/public_api.py:261` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_key_org_admin | UNKNOWN |
| POST | `/v1/chat` | `api/routers/public_api.py:279` | _check, get_db, require_organization_api_key | UNKNOWN |
| POST | `/v1/documents` | `api/routers/public_api.py:303` | _check, get_db, require_organization_api_key | UNKNOWN |
| POST | `/v1/knowledge-bases` | `api/routers/public_api.py:321` | _check, get_db, require_organization_api_key | UNKNOWN |
| GET | `/v1/conversations` | `api/routers/public_api.py:336` | _check, get_db, require_organization_api_key | UNKNOWN |
| POST | `/v1/search` | `api/routers/public_api.py:347` | _check, get_db, require_organization_api_key | UNKNOWN |
| POST | `/v1/agents/run` | `api/routers/public_api.py:357` | _check, get_db, require_organization_api_key | UNKNOWN |
| GET | `/v1/usage` | `api/routers/public_api.py:373` | _check, get_db, require_organization_api_key | UNKNOWN |
| GET | `/v1/analytics` | `api/routers/public_api.py:384` | _check, get_db, require_organization_api_key | UNKNOWN |
| POST | `/v1/embed` | `api/routers/public_api.py:396` | _check, get_db, require_organization_api_key | UNKNOWN |
| GET | `/v1/documents` | `api/routers/public_api.py:409` | _check, get_db, require_organization_api_key | UNKNOWN |
| GET | `/v1/agents` | `api/routers/public_api.py:418` | _check, get_db, require_organization_api_key | UNKNOWN |
| GET | `/v1/knowledge-bases` | `api/routers/public_api.py:427` | _check, get_db, require_organization_api_key | UNKNOWN |
| POST | `/organizations/{org_id}/webhooks` | `api/routers/webhooks.py:42` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/webhooks` | `api/routers/webhooks.py:69` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/webhooks/{webhook_id}` | `api/routers/webhooks.py:78` | HTTPBearer, _require_webhook_org_admin, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/webhooks/{webhook_id}` | `api/routers/webhooks.py:83` | HTTPBearer, _require_webhook_org_admin, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/webhooks/{webhook_id}` | `api/routers/webhooks.py:95` | HTTPBearer, _require_webhook_org_admin, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/webhooks/{webhook_id}/deliveries` | `api/routers/webhooks.py:105` | HTTPBearer, _require_webhook_org_admin, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/webhooks/{webhook_id}/test` | `api/routers/webhooks.py:110` | HTTPBearer, _require_webhook_org_admin, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/api/versions` | `api/routers/api_versioning.py:18` | none declared | UNKNOWN |
| GET | `/api/versions/{version}` | `api/routers/api_versioning.py:27` | none declared | UNKNOWN |
| GET | `/widget/embed.js` | `api/routers/widget.py:83` | none declared | UNKNOWN |
| GET | `/widget/script.js` | `api/routers/widget.py:83` | none declared | UNKNOWN |
| GET | `/widget/chat.js` | `api/routers/widget.py:89` | none declared | UNKNOWN |
| GET | `/widget/styles.css` | `api/routers/widget.py:94` | none declared | UNKNOWN |
| GET | `/widget/iframe` | `api/routers/widget.py:102` | get_db, require_widget_public_key | UNKNOWN |
| GET | `/widget/config` | `api/routers/widget.py:134` | get_db, require_widget_public_key | UNKNOWN |
| GET | `/organizations/{org_id}/widget/config` | `api/routers/widget.py:151` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/widget/session` | `api/routers/widget.py:162` | get_db | UNKNOWN |
| POST | `/widget/chat` | `api/routers/widget.py:194` | get_db, require_widget_session | UNKNOWN |
| GET | `/organizations/{org_id}/widget/domains` | `api/routers/widget.py:213` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/domains` | `api/routers/widget.py:220` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/widget/theme` | `api/routers/widget.py:237` | get_db, require_widget_public_key | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/theme` | `api/routers/widget.py:242` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/widget/theme/reset` | `api/routers/widget.py:257` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/config` | `api/routers/widget.py:264` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/agent` | `api/routers/widget.py:291` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/config/name` | `api/routers/widget.py:305` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/widget/welcome` | `api/routers/widget.py:320` | get_db, require_widget_public_key | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/welcome` | `api/routers/widget.py:325` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/widget/welcome/reset` | `api/routers/widget.py:335` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/widget/position` | `api/routers/widget.py:345` | get_db, require_widget_public_key | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/position` | `api/routers/widget.py:350` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/widget/languages` | `api/routers/widget.py:363` | none declared | UNKNOWN |
| GET | `/widget/language` | `api/routers/widget.py:368` | get_db, require_widget_public_key | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/language` | `api/routers/widget.py:373` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/widget/logo` | `api/routers/widget.py:387` | get_db, require_widget_public_key | UNKNOWN |
| POST | `/organizations/{org_id}/widget/logo` | `api/routers/widget.py:392` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/widget/logo` | `api/routers/widget.py:404` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/widget/avatar` | `api/routers/widget.py:414` | get_db, require_widget_public_key | UNKNOWN |
| POST | `/organizations/{org_id}/widget/avatar` | `api/routers/widget.py:419` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/widget/avatar` | `api/routers/widget.py:431` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/avatar/default` | `api/routers/widget.py:438` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/widget/suggested-questions` | `api/routers/widget.py:448` | get_db, require_widget_public_key | UNKNOWN |
| GET | `/organizations/{org_id}/widget/suggested-questions/admin` | `api/routers/widget.py:454` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/widget/suggested-questions` | `api/routers/widget.py:461` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/suggested-questions/reorder` | `api/routers/widget.py:476` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/widget/suggested-questions/{question_id}` | `api/routers/widget.py:486` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/widget/suggested-questions/{question_id}` | `api/routers/widget.py:496` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/slack/auth` | `api/routers/chat_integrations_slack.py:35` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/integrations/slack/callback` | `api/routers/chat_integrations_slack.py:43` | get_db | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/slack/configure` | `api/routers/chat_integrations_slack.py:53` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/slack/config` | `api/routers/chat_integrations_slack.py:71` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/integrations/slack` | `api/routers/chat_integrations_slack.py:76` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/slack/send` | `api/routers/chat_integrations_slack.py:88` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/integrations/slack/events` | `api/routers/chat_integrations_slack.py:94` | get_db | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/teams/configure` | `api/routers/chat_integrations_teams.py:33` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/teams/config` | `api/routers/chat_integrations_teams.py:47` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/integrations/teams` | `api/routers/chat_integrations_teams.py:52` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/teams/send` | `api/routers/chat_integrations_teams.py:64` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/integrations/teams/webhook` | `api/routers/chat_integrations_teams.py:73` | get_db | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/discord/configure` | `api/routers/chat_integrations_discord.py:35` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/discord/config` | `api/routers/chat_integrations_discord.py:49` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/integrations/discord` | `api/routers/chat_integrations_discord.py:54` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/discord/send` | `api/routers/chat_integrations_discord.py:66` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/integrations/discord/interactions` | `api/routers/chat_integrations_discord.py:72` | get_db | UNKNOWN |
| POST | `/integrations/discord/message` | `api/routers/chat_integrations_discord.py:107` | get_db | UNKNOWN |
| GET | `/organizations/{org_id}/agents/runs/{run_id}/traces` | `api/routers/agent_traces.py:38` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/agents/runs/{run_id}/traces/tree` | `api/routers/agent_traces.py:47` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/agents/runs/{run_id}/traces/export` | `api/routers/agent_traces.py:56` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/agents` | `api/routers/agents.py:61` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_org_manager, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/agents` | `api/routers/agents.py:80` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/agents/{agent_id}` | `api/routers/agents.py:94` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| PATCH | `/agents/{agent_id}` | `api/routers/agents.py:100` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| DELETE | `/agents/{agent_id}` | `api/routers/agents.py:115` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| POST | `/agents/{agent_id}/activate` | `api/routers/agents.py:128` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| POST | `/agents/{agent_id}/pause` | `api/routers/agents.py:139` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| POST | `/agents/{agent_id}/archive` | `api/routers/agents.py:150` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/agents/{agent_id}/system-prompt/preview` | `api/routers/agents.py:164` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| PATCH | `/agents/{agent_id}/system-prompt` | `api/routers/agents.py:181` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/agents/{agent_id}/system-prompt/variables` | `api/routers/agents.py:193` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| GET | `/agents/{agent_id}/model` | `api/routers/agents.py:202` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| PATCH | `/agents/{agent_id}/model` | `api/routers/agents.py:210` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/models` | `api/routers/agents.py:224` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/models/{provider}` | `api/routers/agents.py:233` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/agents/{agent_id}/knowledge-base` | `api/routers/agents.py:244` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| PATCH | `/agents/{agent_id}/knowledge-base` | `api/routers/agents.py:253` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/agents/{agent_id}/knowledge-base/config` | `api/routers/agents.py:275` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| GET | `/agents/{agent_id}/knowledge-base/options` | `api/routers/agents.py:283` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| GET | `/agents/{agent_id}/tools` | `api/routers/agents.py:294` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| PATCH | `/agents/{agent_id}/tools` | `api/routers/agents.py:302` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| POST | `/agents/{agent_id}/tools/{tool_name}/enable` | `api/routers/agents.py:316` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| POST | `/agents/{agent_id}/tools/{tool_name}/disable` | `api/routers/agents.py:330` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/tools/available` | `api/routers/agents.py:341` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/agents/{agent_id}/memory-config` | `api/routers/agents.py:353` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| PATCH | `/agents/{agent_id}/memory-config` | `api/routers/agents.py:361` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/agents/{agent_id}/memory-usage` | `api/routers/agents.py:375` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| POST | `/agents/{agent_id}/memory/clear` | `api/routers/agents.py:383` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/agents/{agent_id}/permissions` | `api/routers/agents.py:396` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| PATCH | `/agents/{agent_id}/permissions` | `api/routers/agents.py:406` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| POST | `/agents/{agent_id}/permissions/users` | `api/routers/agents.py:425` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/agents/{agent_id}/guardrails` | `api/routers/agents.py:444` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| PATCH | `/agents/{agent_id}/guardrails` | `api/routers/agents.py:452` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/agents/{agent_id}/memory` | `api/routers/agents.py:473` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_member | UNKNOWN |
| PUT | `/agents/{agent_id}/memory/{key}` | `api/routers/agents.py:482` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| DELETE | `/agents/{agent_id}/memory/{key}` | `api/routers/agents.py:494` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| DELETE | `/agents/{agent_id}/permissions/users/{user_id}` | `api/routers/agents.py:503` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| POST | `/agents/{agent_id}/api-keys` | `api/routers/agent_api_keys.py:32` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/agents/{agent_id}/api-keys` | `api/routers/agent_api_keys.py:48` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| DELETE | `/agents/{agent_id}/api-keys/{key_id}` | `api/routers/agent_api_keys.py:56` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| POST | `/api/agents/run` | `api/routers/agent_api_keys.py:68` | _check, get_db, require_agent_api_key | UNKNOWN |
| GET | `/organizations/{org_id}/quality/dashboard` | `api/routers/quality_dashboard.py:32` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/quality/metrics` | `api/routers/quality_dashboard.py:40` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/quality/trends` | `api/routers/quality_dashboard.py:53` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/quality/responses` | `api/routers/quality_dashboard.py:62` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/quality/export` | `api/routers/quality_dashboard.py:70` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/datasets` | `api/routers/evaluation_datasets.py:33` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/datasets` | `api/routers/evaluation_datasets.py:43` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/datasets/{dataset_id}` | `api/routers/evaluation_datasets.py:52` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| PATCH | `/datasets/{dataset_id}` | `api/routers/evaluation_datasets.py:58` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| DELETE | `/datasets/{dataset_id}` | `api/routers/evaluation_datasets.py:69` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/questions` | `api/routers/evaluation_datasets.py:78` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/questions` | `api/routers/evaluation_datasets.py:92` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| PATCH | `/questions/{question_id}` | `api/routers/evaluation_datasets.py:103` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_admin | UNKNOWN |
| DELETE | `/questions/{question_id}` | `api/routers/evaluation_datasets.py:114` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/questions/import` | `api/routers/evaluation_datasets.py:123` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/questions/export` | `api/routers/evaluation_datasets.py:138` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/sets` | `api/routers/question_sets.py:29` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/sets` | `api/routers/question_sets.py:40` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/sets/{set_id}` | `api/routers/question_sets.py:49` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_set_admin | UNKNOWN |
| PATCH | `/sets/{set_id}` | `api/routers/question_sets.py:55` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_set_admin | UNKNOWN |
| DELETE | `/sets/{set_id}` | `api/routers/question_sets.py:66` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_set_admin | UNKNOWN |
| POST | `/sets/{set_id}/questions` | `api/routers/question_sets.py:75` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_set_admin | UNKNOWN |
| DELETE | `/sets/{set_id}/questions/{question_id}` | `api/routers/question_sets.py:86` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_set_admin | UNKNOWN |
| PATCH | `/sets/{set_id}/questions/reorder` | `api/routers/question_sets.py:96` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_set_admin | UNKNOWN |
| POST | `/sets/{set_id}/duplicate` | `api/routers/question_sets.py:110` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_set_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/versions` | `api/routers/benchmark_versions.py:29` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/versions` | `api/routers/benchmark_versions.py:40` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/versions/{version_id}` | `api/routers/benchmark_versions.py:49` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_benchmark_version_admin | UNKNOWN |
| POST | `/versions/{version_id}/compare/{other_version_id}` | `api/routers/benchmark_versions.py:57` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_benchmark_version_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/versions/rollback` | `api/routers/benchmark_versions.py:69` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| POST | `/questions/{question_id}/run` | `api/routers/evaluation_results.py:25` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_admin | UNKNOWN |
| GET | `/questions/{question_id}/results` | `api/routers/evaluation_results.py:38` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/metrics/{metric}` | `api/routers/evaluation_results.py:47` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| POST | `/questions/{question_id}/latency` | `api/routers/evaluation_results.py:56` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_admin | UNKNOWN |
| POST | `/sets/{set_id}/compare` | `api/routers/evaluation_comparisons.py:25` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_set_admin | UNKNOWN |
| POST | `/sets/{set_id}/ab-test` | `api/routers/evaluation_comparisons.py:36` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_set_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/evaluate` | `api/routers/evaluation_jobs.py:30` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/jobs` | `api/routers/evaluation_jobs.py:53` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/jobs/{job_id}` | `api/routers/evaluation_jobs.py:62` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_evaluation_job_admin | UNKNOWN |
| POST | `/jobs/{job_id}/cancel` | `api/routers/evaluation_jobs.py:68` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_evaluation_job_admin | UNKNOWN |
| GET | `/jobs/{job_id}/results` | `api/routers/evaluation_jobs.py:81` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_evaluation_job_admin | UNKNOWN |
| GET | `/jobs/{job_id}/failures` | `api/routers/evaluation_jobs.py:90` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_evaluation_job_admin | UNKNOWN |
| GET | `/jobs/{job_id}/failures/categories` | `api/routers/evaluation_jobs.py:99` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_evaluation_job_admin | UNKNOWN |
| GET | `/jobs/{job_id}/comparison` | `api/routers/evaluation_jobs.py:107` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_evaluation_job_admin | UNKNOWN |
| POST | `/questions/{question_id}/evaluate` | `api/routers/manual_evaluations.py:26` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_member | UNKNOWN |
| GET | `/questions/{question_id}/evaluations` | `api/routers/manual_evaluations.py:43` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_member | UNKNOWN |
| GET | `/questions/{question_id}/evaluations/summary` | `api/routers/manual_evaluations.py:52` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_question_member | UNKNOWN |
| GET | `/evaluations/{evaluation_id}` | `api/routers/manual_evaluations.py:60` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_manual_evaluation_access | UNKNOWN |
| PATCH | `/evaluations/{evaluation_id}` | `api/routers/manual_evaluations.py:68` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_manual_evaluation_access | UNKNOWN |
| GET | `/datasets/{dataset_id}/evaluations/stats` | `api/routers/manual_evaluations.py:92` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/compare` | `api/routers/comparison_jobs.py:44` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/comparisons` | `api/routers/comparison_jobs.py:53` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/comparisons/{comparison_id}` | `api/routers/comparison_jobs.py:62` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_comparison_admin | UNKNOWN |
| GET | `/comparisons/{comparison_id}/results` | `api/routers/comparison_jobs.py:68` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_comparison_admin | UNKNOWN |
| POST | `/comparisons/{comparison_id}/run` | `api/routers/comparison_jobs.py:76` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_comparison_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/retrievers/compare` | `api/routers/comparison_jobs.py:87` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/retrievers/comparisons` | `api/routers/comparison_jobs.py:96` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/retriever-comparisons/{comparison_id}` | `api/routers/comparison_jobs.py:105` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_comparison_admin | UNKNOWN |
| GET | `/retriever-comparisons/{comparison_id}/results` | `api/routers/comparison_jobs.py:111` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_comparison_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/rerankers/compare` | `api/routers/comparison_jobs.py:121` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/rerankers/comparisons` | `api/routers/comparison_jobs.py:130` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/reranker-comparisons/{comparison_id}` | `api/routers/comparison_jobs.py:139` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_comparison_admin | UNKNOWN |
| GET | `/reranker-comparisons/{comparison_id}/results` | `api/routers/comparison_jobs.py:145` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_comparison_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/prompts/compare` | `api/routers/comparison_jobs.py:155` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/prompts/comparisons` | `api/routers/comparison_jobs.py:164` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/prompt-comparisons/{comparison_id}` | `api/routers/comparison_jobs.py:173` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_comparison_admin | UNKNOWN |
| GET | `/prompt-comparisons/{comparison_id}/results` | `api/routers/comparison_jobs.py:179` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_comparison_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/regressions` | `api/routers/regression_detection.py:19` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/datasets/{dataset_id}/regressions/summary` | `api/routers/regression_detection.py:28` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| POST | `/datasets/{dataset_id}/regressions/detect` | `api/routers/regression_detection.py:36` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| POST | `/regressions/{regression_id}/resolve` | `api/routers/regression_detection.py:54` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_regression_admin | UNKNOWN |
| POST | `/organizations/{org_id}/thresholds` | `api/routers/regression_thresholds.py:30` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/thresholds` | `api/routers/regression_thresholds.py:41` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/thresholds/{threshold_id}` | `api/routers/regression_thresholds.py:46` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_regression_threshold_admin | UNKNOWN |
| PATCH | `/thresholds/{threshold_id}` | `api/routers/regression_thresholds.py:52` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_regression_threshold_admin | UNKNOWN |
| DELETE | `/thresholds/{threshold_id}` | `api/routers/regression_thresholds.py:64` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_regression_threshold_admin | UNKNOWN |
| POST | `/organizations/{org_id}/thresholds/check` | `api/routers/regression_thresholds.py:73` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/agents/{agent_id}/deploy/evaluate` | `api/routers/deployment_evaluations.py:29` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/agents/{agent_id}/deploy/evaluations` | `api/routers/deployment_evaluations.py:42` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/deploy/evaluations/{evaluation_id}` | `api/routers/deployment_evaluations.py:48` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_deployment_evaluation_manager | UNKNOWN |
| POST | `/deploy/evaluations/{evaluation_id}/pass` | `api/routers/deployment_evaluations.py:54` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_deployment_evaluation_manager | UNKNOWN |
| POST | `/agents/{agent_id}/deploy` | `api/routers/deployment_evaluations.py:65` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_agent_manager | UNKNOWN |
| GET | `/organizations/{org_id}/rbac/permissions` | `api/routers/rbac.py:64` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/rbac/roles` | `api/routers/rbac.py:78` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/rbac/roles` | `api/routers/rbac.py:83` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/rbac/roles/{role_id}` | `api/routers/rbac.py:96` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/rbac/roles/{role_id}` | `api/routers/rbac.py:105` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/rbac/roles/{role_id}` | `api/routers/rbac.py:119` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/rbac/roles/{role_id}/permissions` | `api/routers/rbac.py:128` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/rbac/roles/{role_id}/permissions/{permission_id}` | `api/routers/rbac.py:143` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/rbac/users/{user_id}/roles` | `api/routers/rbac.py:155` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/rbac/users/{user_id}/roles/{role_id}` | `api/routers/rbac.py:169` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/rbac/users/{user_id}/permissions` | `api/routers/rbac.py:178` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/rbac/check` | `api/routers/rbac.py:190` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/compliance/data-requests` | `api/routers/compliance.py:45` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/compliance/data-requests` | `api/routers/compliance.py:52` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/compliance/data-requests/{request_id}` | `api/routers/compliance.py:57` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/compliance/data-requests/{request_id}` | `api/routers/compliance.py:65` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/compliance/data-requests/{request_id}/process` | `api/routers/compliance.py:75` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/compliance/data-export` | `api/routers/compliance.py:88` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/compliance/data-deletion` | `api/routers/compliance.py:101` | none declared | UNKNOWN |
| POST | `/compliance/consent` | `api/routers/compliance.py:115` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/compliance/consent` | `api/routers/compliance.py:122` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/compliance/consent/{consent_type}` | `api/routers/compliance.py:128` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/compliance/status` | `api/routers/compliance.py:135` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/compliance/report` | `api/routers/compliance.py:140` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/compliance/data-breach` | `api/routers/compliance.py:150` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/encryption/status` | `api/routers/encryption.py:26` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/encryption/algorithms` | `api/routers/encryption.py:31` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/encryption/rotate-keys` | `api/routers/encryption.py:36` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/encryption/test` | `api/routers/encryption.py:46` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/organizations/{org_id}/security/scan` | `api/routers/security_scan.py:53` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/security/scans` | `api/routers/security_scan.py:61` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/security/scans/{scan_id}` | `api/routers/security_scan.py:67` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/security/vulnerabilities` | `api/routers/security_scan.py:75` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/security/vulnerabilities/{vuln_id}` | `api/routers/security_scan.py:80` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/security/vulnerabilities/{vuln_id}` | `api/routers/security_scan.py:88` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/security/alerts` | `api/routers/security_scan.py:97` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/security/alerts/{alert_id}/dismiss` | `api/routers/security_scan.py:102` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/security/score` | `api/routers/security_scan.py:111` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/security/report` | `api/routers/security_scan.py:116` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/security/policies` | `api/routers/security_scan.py:121` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/security/policies` | `api/routers/security_scan.py:129` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/admin/stats` | `api/routers/admin_dashboard.py:40` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/stats/users` | `api/routers/admin_dashboard.py:45` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/stats/organizations` | `api/routers/admin_dashboard.py:50` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/stats/revenue` | `api/routers/admin_dashboard.py:55` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/stats/api-usage` | `api/routers/admin_dashboard.py:60` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/stats/conversations` | `api/routers/admin_dashboard.py:65` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/stats/documents` | `api/routers/admin_dashboard.py:70` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/monitoring/health` | `api/routers/admin_dashboard.py:75` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/monitoring/resources` | `api/routers/admin_dashboard.py:80` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/monitoring/queues` | `api/routers/admin_dashboard.py:85` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/logs` | `api/routers/admin_dashboard.py:90` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/logs/stats` | `api/routers/admin_dashboard.py:100` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/logs/sources` | `api/routers/admin_dashboard.py:105` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/logs/levels` | `api/routers/admin_dashboard.py:110` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/logs/export` | `api/routers/admin_dashboard.py:115` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/activity` | `api/routers/admin_dashboard.py:135` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/alerts` | `api/routers/admin_dashboard.py:146` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/logs/{log_id}` | `api/routers/admin_dashboard.py:160` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| DELETE | `/admin/logs/purge` | `api/routers/admin_dashboard.py:168` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/admin/organizations` | `api/routers/admin_organizations.py:36` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/organizations/{org_id}` | `api/routers/admin_organizations.py:42` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| PATCH | `/admin/organizations/{org_id}` | `api/routers/admin_organizations.py:51` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| DELETE | `/admin/organizations/{org_id}` | `api/routers/admin_organizations.py:61` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/admin/organizations/{org_id}/suspend` | `api/routers/admin_organizations.py:74` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/organizations/{org_id}/activate` | `api/routers/admin_organizations.py:88` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/organizations/{org_id}/members` | `api/routers/admin_organizations.py:102` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/organizations/{org_id}/usage` | `api/routers/admin_organizations.py:108` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/organizations/{org_id}/billing` | `api/routers/admin_organizations.py:113` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/organizations/{org_id}/activity` | `api/routers/admin_organizations.py:122` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/users` | `api/routers/admin_users_management.py:38` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/users/{user_id}` | `api/routers/admin_users_management.py:44` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| PATCH | `/admin/users/{user_id}` | `api/routers/admin_users_management.py:53` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/users/{user_id}/suspend` | `api/routers/admin_users_management.py:63` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/users/{user_id}/activate` | `api/routers/admin_users_management.py:77` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/users/{user_id}/reset-password` | `api/routers/admin_users_management.py:91` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/users/{user_id}/verify-email` | `api/routers/admin_users_management.py:108` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/users/{user_id}/sessions` | `api/routers/admin_users_management.py:118` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| DELETE | `/admin/users/{user_id}/sessions/{session_id}` | `api/routers/admin_users_management.py:124` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/users/{user_id}/activity` | `api/routers/admin_users_management.py:132` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/subscriptions` | `api/routers/admin_subscriptions.py:41` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/subscriptions/stats` | `api/routers/admin_subscriptions.py:46` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/subscriptions/{sub_id}` | `api/routers/admin_subscriptions.py:51` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| PATCH | `/admin/subscriptions/{sub_id}` | `api/routers/admin_subscriptions.py:60` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/subscriptions/{sub_id}/cancel` | `api/routers/admin_subscriptions.py:70` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| DELETE | `/admin/subscriptions/{sub_id}` | `api/routers/admin_subscriptions.py:86` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/subscriptions/{sub_id}/refund` | `api/routers/admin_subscriptions.py:98` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/subscriptions/{sub_id}/extend` | `api/routers/admin_subscriptions.py:110` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/admin/plans` | `api/routers/admin_subscriptions.py:120` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/plans` | `api/routers/admin_subscriptions.py:127` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| PATCH | `/admin/plans/{plan_id}` | `api/routers/admin_subscriptions.py:134` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| DELETE | `/admin/plans/{plan_id}` | `api/routers/admin_subscriptions.py:144` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/plans/sync/stripe-products` | `api/routers/admin_subscriptions.py:159` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/admin/plans/sync/stripe-prices` | `api/routers/admin_subscriptions.py:172` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/billing/plans` | `api/routers/billing.py:60` | get_db | UNKNOWN |
| GET | `/billing/plans/{plan_id}` | `api/routers/billing.py:67` | get_db | UNKNOWN |
| POST | `/billing/stripe/webhook` | `api/routers/billing.py:358` | get_db | UNKNOWN |
| POST | `/billing/paystack/webhook` | `api/routers/billing.py:380` | get_db | UNKNOWN |
| GET | `/organizations/{org_id}/billing/subscription` | `api/routers/billing.py:77` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/subscribe` | `api/routers/billing.py:84` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/downgrade` | `api/routers/billing.py:95` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/upgrade` | `api/routers/billing.py:95` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/cancel` | `api/routers/billing.py:104` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/reactivate` | `api/routers/billing.py:112` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/usage` | `api/routers/billing.py:122` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/usage/breakdown` | `api/routers/billing.py:127` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/usage/forecast` | `api/routers/billing.py:132` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/usage/alerts` | `api/routers/billing.py:137` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/usage/alerts` | `api/routers/billing.py:142` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/billing/usage/alerts/{alert_id}` | `api/routers/billing.py:149` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/credits` | `api/routers/billing.py:158` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/credits/transactions` | `api/routers/billing.py:165` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/credits/packs` | `api/routers/billing.py:170` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/credits/purchase` | `api/routers/billing.py:175` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/credits/checkout` | `api/routers/billing.py:202` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/invoices` | `api/routers/billing.py:225` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/invoices/stats` | `api/routers/billing.py:230` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/invoices/{invoice_id}` | `api/routers/billing.py:235` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/invoices/{invoice_id}/pdf` | `api/routers/billing.py:245` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/invoices/{invoice_id}/send` | `api/routers/billing.py:258` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/invoices/{invoice_id}/remind` | `api/routers/billing.py:268` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/invoices/{invoice_id}/pay` | `api/routers/billing.py:276` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/invoices/{invoice_id}/void` | `api/routers/billing.py:286` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/stripe/create-checkout-session` | `api/routers/billing.py:298` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/stripe/create-portal-session` | `api/routers/billing.py:308` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/stripe/payment-methods` | `api/routers/billing.py:317` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/billing/stripe/payment-methods/{payment_method_id}` | `api/routers/billing.py:325` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/stripe/cancel` | `api/routers/billing.py:340` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/stripe/invoices` | `api/routers/billing.py:348` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/provider` | `api/routers/billing.py:407` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/country` | `api/routers/billing.py:416` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/billing/country` | `api/routers/billing.py:422` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/checkout` | `api/routers/billing.py:430` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/portal` | `api/routers/billing.py:446` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/payment-methods` | `api/routers/billing.py:456` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/billing/cancel-active-subscription` | `api/routers/billing.py:465` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/billing/provider-invoices` | `api/routers/billing.py:474` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/monitoring/metrics` | `api/routers/observability.py:30` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/monitoring/tracing/status` | `api/routers/observability.py:35` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/monitoring/loki/status` | `api/routers/observability.py:40` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/monitoring/loki/test` | `api/routers/observability.py:45` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/monitoring/datadog/status` | `api/routers/observability.py:55` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/alerting/channels` | `api/routers/observability.py:62` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/alerting/channels` | `api/routers/observability.py:67` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| PATCH | `/alerting/channels/{channel_id}` | `api/routers/observability.py:74` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| DELETE | `/alerting/channels/{channel_id}` | `api/routers/observability.py:84` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/alerting/rules` | `api/routers/observability.py:95` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/alerting/rules` | `api/routers/observability.py:100` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| PATCH | `/alerting/rules/{rule_id}` | `api/routers/observability.py:107` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| DELETE | `/alerting/rules/{rule_id}` | `api/routers/observability.py:117` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/alerting/rules/{rule_id}/test` | `api/routers/observability.py:126` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/alerting/history` | `api/routers/observability.py:134` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/alerting/incidents` | `api/routers/observability.py:141` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/alerting/incidents` | `api/routers/observability.py:146` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| PATCH | `/alerting/incidents/{incident_id}` | `api/routers/observability.py:153` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| POST | `/alerting/incidents/{incident_id}/resolve` | `api/routers/observability.py:163` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_admin | UNKNOWN |
| GET | `/integrations/n8n/status` | `api/routers/integrations_universal.py:38` | none declared | UNKNOWN |
| GET | `/integrations/airbyte/status` | `api/routers/integrations_universal.py:59` | none declared | UNKNOWN |
| GET | `/integrations/providers` | `api/routers/integrations_universal.py:74` | none declared | UNKNOWN |
| POST | `/integrations/inbound/{connection_id}` | `api/routers/integrations_universal.py:201` | get_db | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/connections` | `api/routers/integrations_universal.py:79` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/connections/{connection_id}` | `api/routers/integrations_universal.py:84` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/connections` | `api/routers/integrations_universal.py:92` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/integrations/connections/{connection_id}` | `api/routers/integrations_universal.py:99` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/integrations/connections/{connection_id}` | `api/routers/integrations_universal.py:109` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/connections/{connection_id}/logs` | `api/routers/integrations_universal.py:118` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/connections/{connection_id}/test` | `api/routers/integrations_universal.py:127` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/connections/{connection_id}/sync` | `api/routers/integrations_universal.py:136` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/connections/{connection_id}/syncs` | `api/routers/integrations_universal.py:151` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/connections/{connection_id}/mappings` | `api/routers/integrations_universal.py:163` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/connections/{connection_id}/mappings` | `api/routers/integrations_universal.py:172` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/integrations/mappings/{mapping_id}` | `api/routers/integrations_universal.py:183` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/integrations/mappings/{mapping_id}` | `api/routers/integrations_universal.py:193` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/airbyte/source-definitions` | `api/routers/integrations_universal.py:224` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/airbyte/connections` | `api/routers/integrations_universal.py:232` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/airbyte/sources` | `api/routers/integrations_universal.py:237` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/integrations/airbyte/sources/{source_id}/catalog` | `api/routers/integrations_universal.py:245` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/airbyte/connections` | `api/routers/integrations_universal.py:253` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/integrations/airbyte/connections/{connection_id}/sync` | `api/routers/integrations_universal.py:264` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/notifications/sms/send` | `api/routers/notifications.py:20` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/notifications/whatsapp/send` | `api/routers/notifications.py:30` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/notifications/sms` | `api/routers/notifications.py:40` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/notifications/sms/{message_id}` | `api/routers/notifications.py:45` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/notifications` | `api/routers/notification_center.py:41` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/notifications/unread-count` | `api/routers/notification_center.py:50` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/notifications/{notification_id}/read` | `api/routers/notification_center.py:56` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/notifications/mark-all-read` | `api/routers/notification_center.py:66` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| DELETE | `/notifications/{notification_id}` | `api/routers/notification_center.py:73` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/notifications/preferences` | `api/routers/notification_center.py:82` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| PATCH | `/notifications/preferences` | `api/routers/notification_center.py:87` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/notifications/stream` | `api/routers/notification_center.py:94` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/organizations/{org_id}/notifications/templates` | `api/routers/notification_templates.py:54` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/notifications/templates` | `api/routers/notification_templates.py:66` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/notifications/templates/{template_id}` | `api/routers/notification_templates.py:91` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/notifications/templates/{template_id}` | `api/routers/notification_templates.py:104` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/notifications/templates/{template_id}` | `api/routers/notification_templates.py:124` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/notifications/templates/preview` | `api/routers/notification_templates.py:138` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/notifications/templates/test` | `api/routers/notification_templates.py:151` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/license/generate` | `api/routers/sales.py:33` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/license/validate` | `api/routers/sales.py:40` | get_db | UNKNOWN |
| POST | `/reseller/create` | `api/routers/sales.py:101` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/reseller/{reseller_id}/clients` | `api/routers/sales.py:108` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/reseller/{reseller_id}/clients` | `api/routers/sales.py:118` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/reseller/{reseller_id}/commission` | `api/routers/sales.py:123` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/partners/register` | `api/routers/sales.py:133` | get_db | UNKNOWN |
| GET | `/partners/me` | `api/routers/sales.py:148` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/partners/me/clients` | `api/routers/sales.py:156` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/partners/me/commissions` | `api/routers/sales.py:164` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/partners/{reseller_id}/commissions` | `api/routers/sales.py:172` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/r/{code}` | `api/routers/sales.py:181` | get_db | UNKNOWN |
| POST | `/partners/commissions/{commission_id}/pay` | `api/routers/sales.py:203` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/organizations/{org_id}/license/activate` | `api/routers/sales.py:49` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/license/status` | `api/routers/sales.py:61` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/support/tickets` | `api/routers/sales.py:68` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/support/tickets` | `api/routers/sales.py:75` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/support/tickets/{ticket_id}/sla` | `api/routers/sales.py:80` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/support/tickets/{ticket_id}/respond` | `api/routers/sales.py:89` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/analytics/business/revenue` | `api/routers/analytics.py:35` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/analytics/business/customers` | `api/routers/analytics.py:41` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/analytics/business/retention` | `api/routers/analytics.py:46` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/analytics/business/churn` | `api/routers/analytics.py:52` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/analytics/business/ltv` | `api/routers/analytics.py:58` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| GET | `/analytics/business/revenue/trend` | `api/routers/analytics.py:64` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/organizations/{org_id}/analytics/events` | `api/routers/analytics.py:72` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/metrics` | `api/routers/analytics.py:79` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/metrics/query` | `api/routers/analytics.py:87` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/metrics/export` | `api/routers/analytics.py:95` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/metrics/{metric_name}` | `api/routers/analytics.py:107` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/product/usage` | `api/routers/analytics.py:117` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/product/adoption` | `api/routers/analytics.py:122` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/product/engagement` | `api/routers/analytics.py:127` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/product/funnels` | `api/routers/analytics.py:132` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/technical/performance` | `api/routers/analytics.py:143` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/technical/errors` | `api/routers/analytics.py:148` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/technical/api-usage` | `api/routers/analytics.py:153` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/technical/llm-usage` | `api/routers/analytics.py:158` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/dashboards` | `api/routers/analytics.py:165` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/analytics/dashboards` | `api/routers/analytics.py:170` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/analytics/dashboards/{dashboard_id}` | `api/routers/analytics.py:177` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/analytics/dashboards/{dashboard_id}` | `api/routers/analytics.py:185` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/analytics/dashboards/{dashboard_id}` | `api/routers/analytics.py:195` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/marketplace/permissions` | `api/routers/plugins.py:52` | none declared | UNKNOWN |
| GET | `/marketplace/plugins` | `api/routers/plugins.py:57` | get_db | UNKNOWN |
| GET | `/marketplace/plugins/{plugin_id}` | `api/routers/plugins.py:65` | get_db | UNKNOWN |
| GET | `/marketplace/plugins/{plugin_id}/rating` | `api/routers/plugins.py:73` | get_db | UNKNOWN |
| GET | `/marketplace/plugins/{plugin_id}/reviews` | `api/routers/plugins.py:78` | get_db | UNKNOWN |
| GET | `/marketplace/plugins/{plugin_id}/versions` | `api/routers/plugins.py:83` | get_db | UNKNOWN |
| DELETE | `/marketplace/reviews/{review_id}` | `api/routers/plugins.py:88` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/organizations/{org_id}/plugins/publish` | `api/routers/plugins.py:101` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PUT | `/organizations/{org_id}/plugins/{plugin_id}` | `api/routers/plugins.py:120` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/plugins/published` | `api/routers/plugins.py:141` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/plugins/{plugin_id}` | `api/routers/plugins.py:146` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/plugins/{plugin_id}/install` | `api/routers/plugins.py:157` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/plugins/installed` | `api/routers/plugins.py:172` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| PATCH | `/organizations/{org_id}/plugins/installed/{installation_id}` | `api/routers/plugins.py:177` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| DELETE | `/organizations/{org_id}/plugins/installed/{installation_id}` | `api/routers/plugins.py:188` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/plugins/{plugin_id}/reviews` | `api/routers/plugins.py:199` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/plugins/{plugin_id}/execute` | `api/routers/plugins.py:214` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/plugins/{plugin_id}/executions` | `api/routers/plugins.py:235` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/admin/plugins/pending` | `api/routers/plugins.py:242` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/admin/plugins/{plugin_id}/approve` | `api/routers/plugins.py:247` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/admin/plugins/{plugin_id}/reject` | `api/routers/plugins.py:258` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/admin/plugins/{plugin_id}/suspend` | `api/routers/plugins.py:269` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_superadmin | UNKNOWN |
| POST | `/organizations/{org_id}/ab-tests` | `api/routers/ab_tests.py:38` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/ab-tests` | `api/routers/ab_tests.py:55` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/ab-tests/{test_id}` | `api/routers/ab_tests.py:63` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_member | UNKNOWN |
| PATCH | `/ab-tests/{test_id}` | `api/routers/ab_tests.py:69` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| DELETE | `/ab-tests/{test_id}` | `api/routers/ab_tests.py:84` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| POST | `/ab-tests/{test_id}/start` | `api/routers/ab_tests.py:91` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| POST | `/ab-tests/{test_id}/pause` | `api/routers/ab_tests.py:100` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| POST | `/ab-tests/{test_id}/resume` | `api/routers/ab_tests.py:109` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| POST | `/ab-tests/{test_id}/complete` | `api/routers/ab_tests.py:118` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| GET | `/ab-tests/{test_id}/results` | `api/routers/ab_tests.py:127` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_member | UNKNOWN |
| GET | `/ab-tests/{test_id}/statistics` | `api/routers/ab_tests.py:133` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_member | UNKNOWN |
| GET | `/ab-tests/{test_id}/assignments` | `api/routers/ab_tests.py:146` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| GET | `/ab-tests/{test_id}/export` | `api/routers/ab_tests.py:155` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| POST | `/ab-tests/{test_id}/variants/choose` | `api/routers/ab_tests.py:167` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| POST | `/ab-tests/{test_id}/decide` | `api/routers/ab_tests.py:185` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| POST | `/ab-tests/{test_id}/track` | `api/routers/ab_tests.py:201` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_ab_test_admin | UNKNOWN |
| POST | `/organizations/{org_id}/media` | `api/routers/media.py:53` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/organizations/{org_id}/media` | `api/routers/media.py:71` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/media/{media_asset_id}` | `api/routers/media.py:79` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_media_member | UNKNOWN |
| DELETE | `/media/{media_asset_id}` | `api/routers/media.py:85` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_media_admin | UNKNOWN |
| POST | `/media/{media_asset_id}/process` | `api/routers/media.py:92` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_media_admin | UNKNOWN |
| GET | `/media/{media_asset_id}/status` | `api/routers/media.py:105` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_media_member | UNKNOWN |
| GET | `/media/{media_asset_id}/transcript` | `api/routers/media.py:111` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_media_member | UNKNOWN |
| GET | `/media/{media_asset_id}/description` | `api/routers/media.py:122` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_media_member | UNKNOWN |
| GET | `/media/{media_asset_id}/file` | `api/routers/media.py:133` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_media_member | UNKNOWN |
| GET | `/media/{media_asset_id}/frames` | `api/routers/media.py:147` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_media_member | UNKNOWN |
| GET | `/media/{media_asset_id}/frames/{frame_id}/file` | `api/routers/media.py:155` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_media_member | UNKNOWN |
| POST | `/media/search` | `api/routers/media.py:171` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/media/search/visual` | `api/routers/media.py:192` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| POST | `/media/search/similar` | `api/routers/media.py:208` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db | UNKNOWN |
| GET | `/organizations/{org_id}/autonomous-agents` | `api/routers/autonomous_agents.py:32` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/organizations/{org_id}/autonomous-agents` | `api/routers/autonomous_agents.py:40` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/autonomous-agents/{agent_id}` | `api/routers/autonomous_agents.py:51` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| PATCH | `/autonomous-agents/{agent_id}` | `api/routers/autonomous_agents.py:57` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_admin | UNKNOWN |
| DELETE | `/autonomous-agents/{agent_id}` | `api/routers/autonomous_agents.py:69` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_admin | UNKNOWN |
| POST | `/autonomous-agents/{agent_id}/run` | `api/routers/autonomous_agents.py:78` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| POST | `/autonomous-agents/{agent_id}/pause` | `api/routers/autonomous_agents.py:86` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| POST | `/autonomous-agents/{agent_id}/resume` | `api/routers/autonomous_agents.py:95` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| POST | `/autonomous-agents/{agent_id}/stop` | `api/routers/autonomous_agents.py:103` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| GET | `/autonomous-agents/{agent_id}/status` | `api/routers/autonomous_agents.py:112` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| GET | `/autonomous-agents/{agent_id}/cost` | `api/routers/autonomous_agents.py:118` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| GET | `/autonomous-agents/{agent_id}/plans` | `api/routers/autonomous_agents.py:126` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| GET | `/autonomous-agents/{agent_id}/plans/{plan_id}` | `api/routers/autonomous_agents.py:132` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| GET | `/autonomous-agents/{agent_id}/plans/{plan_id}/steps` | `api/routers/autonomous_agents.py:143` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| GET | `/autonomous-agents/{agent_id}/memory` | `api/routers/autonomous_agents.py:156` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| POST | `/autonomous-agents/{agent_id}/memory` | `api/routers/autonomous_agents.py:164` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| DELETE | `/autonomous-agents/{agent_id}/memory/{memory_id}` | `api/routers/autonomous_agents.py:175` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| POST | `/autonomous-agents/{agent_id}/collaborate` | `api/routers/autonomous_agents.py:186` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| GET | `/autonomous-agents/{agent_id}/collaborations` | `api/routers/autonomous_agents.py:199` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_autonomous_agent_member | UNKNOWN |
| GET | `/fine-tuning/datasets` | `api/routers/fine_tuning.py:45` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/fine-tuning/datasets` | `api/routers/fine_tuning.py:50` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/fine-tuning/datasets/{dataset_id}` | `api/routers/fine_tuning.py:66` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_member | UNKNOWN |
| DELETE | `/fine-tuning/datasets/{dataset_id}` | `api/routers/fine_tuning.py:72` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| POST | `/fine-tuning/datasets/{dataset_id}/validate` | `api/routers/fine_tuning.py:79` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_dataset_admin | UNKNOWN |
| GET | `/fine-tuning/jobs` | `api/routers/fine_tuning.py:90` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| POST | `/fine-tuning/jobs` | `api/routers/fine_tuning.py:95` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/fine-tuning/jobs/{job_id}` | `api/routers/fine_tuning.py:112` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_job_member | UNKNOWN |
| POST | `/fine-tuning/jobs/{job_id}/cancel` | `api/routers/fine_tuning.py:118` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_job_admin | UNKNOWN |
| GET | `/fine-tuning/jobs/{job_id}/metrics` | `api/routers/fine_tuning.py:127` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_job_member | UNKNOWN |
| GET | `/fine-tuning/models` | `api/routers/fine_tuning.py:135` | HTTPBearer, _dependency, get_current_user, get_current_user_any_consent_status, get_db, require_org_member | UNKNOWN |
| GET | `/fine-tuning/models/{model_id}` | `api/routers/fine_tuning.py:140` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_model_member | UNKNOWN |
| DELETE | `/fine-tuning/models/{model_id}` | `api/routers/fine_tuning.py:146` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_model_admin | UNKNOWN |
| POST | `/fine-tuning/models/{model_id}/deploy` | `api/routers/fine_tuning.py:153` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_model_admin | UNKNOWN |
| POST | `/fine-tuning/models/{model_id}/undeploy` | `api/routers/fine_tuning.py:165` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_model_admin | UNKNOWN |
| POST | `/fine-tuning/models/{model_id}/evaluate` | `api/routers/fine_tuning.py:176` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_model_admin | UNKNOWN |
| GET | `/fine-tuning/models/{model_id}/evaluations` | `api/routers/fine_tuning.py:194` | HTTPBearer, get_current_user, get_current_user_any_consent_status, get_db, require_model_member | UNKNOWN |
| GET | `/metrics` | `api/main.py:415` | none declared | UNKNOWN |
| GET | `/health` | `api/main.py:432` | none declared | UNKNOWN |
| GET | `/health/ready` | `api/main.py:441` | none declared | UNKNOWN |

## All ORM tables (not a live catalog)

| Table | Tenant class | Foreign-key targets | Live RLS | Live policies |
|---|---|---|---|---|
| `ab_test_assignments` | see tenant matrix | ab_tests.id | UNKNOWN | UNKNOWN |
| `ab_test_results` | see tenant matrix | ab_tests.id | UNKNOWN | UNKNOWN |
| `ab_tests` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `account_restore_tokens` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `acme_accounts` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `agent_api_keys` | see tenant matrix | agents.id, users.id | UNKNOWN | UNKNOWN |
| `agent_collaborations` | see tenant matrix | autonomous_agents.id, autonomous_agents.id | UNKNOWN | UNKNOWN |
| `agent_long_term_memory_items` | see tenant matrix | agents.id, users.id | UNKNOWN | UNKNOWN |
| `agent_memories` | see tenant matrix | autonomous_agents.id | UNKNOWN | UNKNOWN |
| `agent_memory_items` | see tenant matrix | agent_sessions.id | UNKNOWN | UNKNOWN |
| `agent_plans` | see tenant matrix | autonomous_agents.id | UNKNOWN | UNKNOWN |
| `agent_runs` | DIRECT candidate | organizations.id, responses.id, users.id | UNKNOWN | UNKNOWN |
| `agent_sessions` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `agent_steps` | see tenant matrix | agent_plans.id | UNKNOWN | UNKNOWN |
| `agent_traces` | see tenant matrix | agent_runs.id | UNKNOWN | UNKNOWN |
| `agents` | DIRECT candidate | organizations.id, users.id, workspaces.id, workspaces.id | UNKNOWN | UNKNOWN |
| `airbyte_connections` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `alert_channels` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `alert_history` | see tenant matrix | alert_rules.id | UNKNOWN | UNKNOWN |
| `alert_rules` | DIRECT candidate | alert_channels.id, organizations.id, users.id | UNKNOWN | UNKNOWN |
| `analytics_aggregates` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `analytics_dashboards` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `analytics_events` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `audit_logs` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `audit_logs_archive` | DIRECT candidate | - | UNKNOWN | UNKNOWN |
| `autonomous_agents` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `batch_job_items` | see tenant matrix | batch_jobs.id | UNKNOWN | UNKNOWN |
| `batch_jobs` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `benchmark_versions` | see tenant matrix | evaluation_datasets.id, question_sets.id, users.id | UNKNOWN | UNKNOWN |
| `call_records` | see tenant matrix | agents.id, conversations.id | UNKNOWN | UNKNOWN |
| `citations` | see tenant matrix | document_chunks.id, documents.id, responses.id | UNKNOWN | UNKNOWN |
| `comparison_jobs` | see tenant matrix | evaluation_datasets.id, users.id | UNKNOWN | UNKNOWN |
| `consent_reactivation_tokens` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `consent_records` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `conversation_messages` | see tenant matrix | conversations.id | UNKNOWN | UNKNOWN |
| `conversation_shares` | see tenant matrix | conversations.id, users.id | UNKNOWN | UNKNOWN |
| `conversations` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `credit_transactions` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `credits` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `custom_domains` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `custom_roles` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `custom_tools` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `data_breaches` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `data_requests` | see tenant matrix | users.id, users.id | UNKNOWN | UNKNOWN |
| `deployment_evaluations` | see tenant matrix | agents.id, evaluation_datasets.id, evaluation_jobs.id, users.id | UNKNOWN | UNKNOWN |
| `discord_integrations` | DIRECT candidate | agents.id, organizations.id, users.id | UNKNOWN | UNKNOWN |
| `discord_messages` | see tenant matrix | conversations.id, discord_integrations.id | UNKNOWN | UNKNOWN |
| `document_audit_logs` | see tenant matrix | documents.id, users.id | UNKNOWN | UNKNOWN |
| `document_chunks` | DIRECT candidate | document_chunks.id, documents.id, media_assets.id, organizations.id | UNKNOWN | UNKNOWN |
| `document_entities` | see tenant matrix | documents.id | UNKNOWN | UNKNOWN |
| `document_images` | see tenant matrix | documents.id | UNKNOWN | UNKNOWN |
| `document_keywords` | see tenant matrix | documents.id | UNKNOWN | UNKNOWN |
| `document_tag_assignments` | see tenant matrix | document_tags.id, documents.id, users.id | UNKNOWN | UNKNOWN |
| `document_tags` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `document_versions` | see tenant matrix | documents.id, users.id | UNKNOWN | UNKNOWN |
| `documents` | DIRECT candidate | document_versions.id, organizations.id, users.id, users.id, workspaces.id | UNKNOWN | UNKNOWN |
| `email_verification_tokens` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `encryption_audit` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `encryption_key_records` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `enterprise_sso_accounts` | see tenant matrix | enterprise_sso_connections.id, users.id | UNKNOWN | UNKNOWN |
| `enterprise_sso_connections` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `escalations` | DIRECT candidate | agent_runs.id, organizations.id, users.id | UNKNOWN | UNKNOWN |
| `evaluation_datasets` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `evaluation_failures` | see tenant matrix | evaluation_jobs.id, evaluation_questions.id | UNKNOWN | UNKNOWN |
| `evaluation_jobs` | see tenant matrix | agents.id, evaluation_datasets.id, question_sets.id, users.id | UNKNOWN | UNKNOWN |
| `evaluation_questions` | see tenant matrix | evaluation_datasets.id | UNKNOWN | UNKNOWN |
| `evaluation_results` | see tenant matrix | agents.id, evaluation_jobs.id, evaluation_questions.id | UNKNOWN | UNKNOWN |
| `external_sources` | DIRECT candidate | organizations.id, users.id, workspaces.id | UNKNOWN | UNKNOWN |
| `fine_tuned_models` | DIRECT candidate | fine_tuning_jobs.id, organizations.id | UNKNOWN | UNKNOWN |
| `fine_tuning_datasets` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `fine_tuning_evaluations` | see tenant matrix | evaluation_datasets.id, evaluation_jobs.id, fine_tuned_models.id | UNKNOWN | UNKNOWN |
| `fine_tuning_jobs` | DIRECT candidate | fine_tuning_datasets.id, organizations.id, users.id | UNKNOWN | UNKNOWN |
| `flight_recordings` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `follow_up_questions` | see tenant matrix | conversation_messages.id | UNKNOWN | UNKNOWN |
| `human_approvals` | DIRECT candidate | agent_runs.id, organizations.id, users.id, users.id | UNKNOWN | UNKNOWN |
| `incidents` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `integration_connections` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `integration_logs` | see tenant matrix | integration_connections.id | UNKNOWN | UNKNOWN |
| `integration_mappings` | see tenant matrix | integration_connections.id | UNKNOWN | UNKNOWN |
| `invitations` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `invoice_lines` | see tenant matrix | invoices.id | UNKNOWN | UNKNOWN |
| `invoices` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `jwt_signing_keys` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `key_rotation_history` | see tenant matrix | organization_api_keys.id, organization_api_keys.id, organization_api_keys.id, users.id | UNKNOWN | UNKNOWN |
| `licenses` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `llm_fallbacks` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `manual_evaluations` | see tenant matrix | agents.id, evaluation_questions.id, users.id | UNKNOWN | UNKNOWN |
| `mcp_server_configs` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `mcp_tool_cache` | see tenant matrix | mcp_server_configs.id | UNKNOWN | UNKNOWN |
| `media_assets` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `media_frames` | see tenant matrix | media_assets.id | UNKNOWN | UNKNOWN |
| `media_transcripts` | see tenant matrix | media_assets.id | UNKNOWN | UNKNOWN |
| `message_edit_history` | see tenant matrix | conversation_messages.id, users.id | UNKNOWN | UNKNOWN |
| `message_feedback` | see tenant matrix | conversation_messages.id, users.id | UNKNOWN | UNKNOWN |
| `notification_preferences` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `notification_templates` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `notifications` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `oauth_accounts` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `organization_api_keys` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `organization_branding` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `organization_llm_configs` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `organization_members` | DIRECT candidate | organizations.id, users.id, users.id | UNKNOWN | UNKNOWN |
| `organization_quotas` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `organization_settings` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `organization_usage` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `organization_usage_details` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `organizations` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `partner_commissions` | see tenant matrix | resellers.id | UNKNOWN | UNKNOWN |
| `password_history` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `password_reset_tokens` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `payment_customers` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `payment_events` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `permission_groups` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `permissions` | see tenant matrix | permission_groups.id | UNKNOWN | UNKNOWN |
| `plans` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `plugin_executions` | DIRECT candidate | organizations.id, plugin_installations.id, plugins.id, users.id | UNKNOWN | UNKNOWN |
| `plugin_installations` | DIRECT candidate | organizations.id, plugins.id, users.id | UNKNOWN | UNKNOWN |
| `plugin_reviews` | DIRECT candidate | organizations.id, plugins.id, users.id | UNKNOWN | UNKNOWN |
| `plugin_versions` | see tenant matrix | plugins.id, users.id | UNKNOWN | UNKNOWN |
| `plugins` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `question_set_items` | see tenant matrix | evaluation_questions.id, question_sets.id | UNKNOWN | UNKNOWN |
| `question_sets` | see tenant matrix | evaluation_datasets.id, users.id | UNKNOWN | UNKNOWN |
| `rag_experiments` | DIRECT candidate | evaluation_jobs.id, evaluation_jobs.id, organizations.id, users.id | UNKNOWN | UNKNOWN |
| `regeneration_history` | see tenant matrix | conversation_messages.id, conversation_messages.id | UNKNOWN | UNKNOWN |
| `regression_detections` | see tenant matrix | evaluation_jobs.id, users.id | UNKNOWN | UNKNOWN |
| `regression_thresholds` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `reindex_schedules` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `resellers` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `resource_permissions` | DIRECT candidate | organizations.id, users.id, users.id | UNKNOWN | UNKNOWN |
| `responses` | DIRECT candidate | flight_recordings.id, organizations.id, users.id, workspaces.id | UNKNOWN | UNKNOWN |
| `retrieval_diagnostics` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `revoked_access_tokens` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `role_permissions` | see tenant matrix | custom_roles.id, permissions.id | UNKNOWN | UNKNOWN |
| `sandbox_environments` | DIRECT candidate | organization_api_keys.id, organizations.id | UNKNOWN | UNKNOWN |
| `security_alerts` | DIRECT candidate | organizations.id, users.id, vulnerabilities.id | UNKNOWN | UNKNOWN |
| `security_policies` | DIRECT candidate | organizations.id | UNKNOWN | UNKNOWN |
| `security_scans` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `sessions` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `slack_integrations` | DIRECT candidate | agents.id, organizations.id, users.id | UNKNOWN | UNKNOWN |
| `slack_messages` | see tenant matrix | conversations.id, slack_integrations.id | UNKNOWN | UNKNOWN |
| `sms_messages` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `ssl_certificates` | see tenant matrix | custom_domains.domain | UNKNOWN | UNKNOWN |
| `sub_clients` | DIRECT candidate | organizations.id, resellers.id | UNKNOWN | UNKNOWN |
| `subscriptions` | DIRECT candidate | organizations.id, plans.id | UNKNOWN | UNKNOWN |
| `support_ticket_responses` | see tenant matrix | support_tickets.id, users.id | UNKNOWN | UNKNOWN |
| `support_tickets` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `system_logs` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `task_plans` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `task_steps` | see tenant matrix | task_plans.id | UNKNOWN | UNKNOWN |
| `team_members` | see tenant matrix | teams.id, users.id | UNKNOWN | UNKNOWN |
| `teams` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `teams_integrations` | DIRECT candidate | agents.id, organizations.id, users.id | UNKNOWN | UNKNOWN |
| `teams_messages` | see tenant matrix | conversations.id, teams_integrations.id | UNKNOWN | UNKNOWN |
| `tool_budgets` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `tool_fallbacks` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `tool_permissions` | DIRECT candidate | organizations.id, users.id, users.id | UNKNOWN | UNKNOWN |
| `tool_timeout_overrides` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `two_factor_lockout_recovery_tokens` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `two_factor_recovery_codes` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `usage_alerts` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `user_custom_roles` | see tenant matrix | custom_roles.id, users.id, users.id | UNKNOWN | UNKNOWN |
| `users` | see tenant matrix | - | UNKNOWN | UNKNOWN |
| `voice_messages` | see tenant matrix | conversations.id, users.id | UNKNOWN | UNKNOWN |
| `voice_settings` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `vulnerabilities` | see tenant matrix | security_scans.id | UNKNOWN | UNKNOWN |
| `webauthn_credentials` | see tenant matrix | users.id | UNKNOWN | UNKNOWN |
| `webhook_deliveries` | see tenant matrix | webhooks.id | UNKNOWN | UNKNOWN |
| `webhooks` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |
| `widget_configs` | DIRECT candidate | agents.id, organizations.id, users.id, users.id, users.id | UNKNOWN | UNKNOWN |
| `widget_suggested_questions` | see tenant matrix | widget_configs.id | UNKNOWN | UNKNOWN |
| `workflow_human_inputs` | see tenant matrix | users.id, workflow_runs.id | UNKNOWN | UNKNOWN |
| `workflow_node_executions` | see tenant matrix | workflow_runs.id | UNKNOWN | UNKNOWN |
| `workflow_runs` | see tenant matrix | workflow_triggers.id, workflows.id | UNKNOWN | UNKNOWN |
| `workflow_triggers` | see tenant matrix | workflows.id | UNKNOWN | UNKNOWN |
| `workflow_versions` | see tenant matrix | users.id, workflows.id | UNKNOWN | UNKNOWN |
| `workflows` | DIRECT candidate | organizations.id, users.id, workspaces.id | UNKNOWN | UNKNOWN |
| `workspaces` | DIRECT candidate | organizations.id, users.id | UNKNOWN | UNKNOWN |

## Corrections and findings

See `AUTONOMOUS_AUDIT_05_FIXES.md` and `SECURITY_REPORT.md`; no live RLS state is inferred here.
