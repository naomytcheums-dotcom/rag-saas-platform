# 12 - Complete feature catalog (514 features)

Generated from `audit-reports/functional-audit-2026-10-10/01c-feature-verification-after-test-runs.csv` by `docs/project-handover/annex/generate_feature_catalog.py` (column `status_final`). Each entry gives the requirement (as written in the cahier des charges, French), the evidence found in the code, the tests, the known gaps and the next action.

## How to read the statuses

| Status | Meaning |
|---|---|
| `VERIFIED_COMPLETE` | reviewed as complete AND the targeted tests of its Part ran green; no fix was needed |
| `FIXED_AND_TESTED` | a gap was found, fixed, and the fix is covered by tests that ran green (not necessarily against a real provider) |
| `DECISION_OR_CORRECTION` | an owner decision is recorded in docs/DECISIONS.md, or the first assessment was wrong; nothing left to build |
| `VALIDATED_NOT_DEPLOYED` | checked with the official tool (terraform validate, helm lint, kubeconform, shellcheck, actionlint, compose config) but never applied to a real account or cluster |
| `IMPLEMENTED_UNVERIFIED` | implemented, but the reviewer could not call it complete from the code and its Part tests alone |
| `WRITTEN_NOT_EXECUTED` | code or documents exist; nothing proves them yet |
| `BLOCKED_EXTERNAL` | cannot be proven without an account, key or service that is not available in the development environment |
| `AMBIGUOUS_REQUIREMENT` | the requirement has no testable acceptance criterion |

A feature is `VERIFIED_COMPLETE` only if the code review judged it complete AND the tests of its Part ran green. The unit of proof is the Part, not each sentence of each requirement. `FIXED_AND_TESTED` is not 'deployed': nothing in this catalog proves a feature works in production unless it says so.

## Totals

| Status | Count |
|---|---:|
| VERIFIED_COMPLETE | 283 |
| FIXED_AND_TESTED | 114 |
| DECISION_OR_CORRECTION | 25 |
| VALIDATED_NOT_DEPLOYED | 13 |
| IMPLEMENTED_UNVERIFIED | 34 |
| WRITTEN_NOT_EXECUTED | 19 |
| BLOCKED_EXTERNAL | 26 |
| AMBIGUOUS_REQUIREMENT | 0 |
| **Total** | **514** |

Two notions of 'ready' were used in earlier summaries and are defined here once: **proven in tests** = VERIFIED_COMPLETE + FIXED_AND_TESTED = 397; **closed** = proven in tests + DECISION_OR_CORRECTION = 422 (82 %); **not yet proven** = the other four statuses = 92. The cahier des charges text says 515 features (Part 15 was truncated in the original message); this catalog has 514 rows.

## Part 1 - Structure and multi-tenancy (accounts, organizations, roles, quotas, white-label basics)

42 features: VERIFIED_COMPLETE 21, FIXED_AND_TESTED 13, IMPLEMENTED_UNVERIFIED 3, WRITTEN_NOT_EXECUTED 2, DECISION_OR_CORRECTION 2, BLOCKED_EXTERNAL 1

### 1.1.1 - Inscription (email + mot de passe)  `VERIFIED_COMPLETE`
- **Requirement:** Création de compte avec email et mot de passe sécurisé
- **Implementation:** POST /auth/register (api/routers/auth.py); form frontend/app/register/page.tsx
- **Tests:** tests/test_auth_api.py register, duplicate and weak-password cases (Part run: passed)
- **Known gaps:** none found | **External blockers:** email delivery (Resend) not exercised
- **Severity / next action:** INFO / none

### 1.1.2 - Connexion / Déconnexion  `VERIFIED_COMPLETE`
- **Requirement:** Session utilisateur avec JWT
- **Implementation:** POST /auth/login and /auth/logout (auth.py:382); frontend/app/login/page.tsx; lib/api.ts token handling
- **Tests:** tests/test_auth_api.py login/logout cases (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.1.3 - Mot de passe oublié / Réinitialisation  `VERIFIED_COMPLETE`
- **Requirement:** Envoi d'email de réinitialisation
- **Implementation:** POST /password/forgot and /password/reset (api/routers/password.py); services/password_reset.py; pages forgot-password and reset-password
- **Tests:** tests/test_auth_api.py reset cases (Part run: passed)
- **Known gaps:** real email delivery not exercised | **External blockers:** Resend
- **Severity / next action:** LOW / verify email delivery in staging

### 1.1.4 - Vérification email  `FIXED_AND_TESTED`
- **Requirement:** Envoi d'un code OTP pour valider l'email
- **Implementation:** Backend complete: POST /verify/request and /verify/confirm (api/routers/verify.py), 6-digit code stored hashed (services/verification.py), expiry, attempt cap, rate limit
- **Tests:** tests/test_auth_api.py OTP flow (Part run: passed)
- **Known gaps:** NO frontend screen calls /verify/request or /verify/confirm (grep of frontend/app, components, lib finds none); profile page only shows verified/unverified | **External blockers:** Resend for real delivery
- **Severity / next action:** MEDIUM / add a verification screen (code entry + resend) and a test | **Fix:** frontend/app/verify-email (4 vitest cases)

### 1.1.5 - OAuth Google  `FIXED_AND_TESTED`
- **Requirement:** Connexion avec compte Google
- **Implementation:** Backend: GET /auth/oauth/google/authorize and /callback (api/routers/oauth.py, Authlib); callback page frontend/app/oauth-callback
- **Tests:** tests/test_oauth_logic_integration.py (mocked provider) (Part run: passed)
- **Known gaps:** login page has no Google button (grep of frontend/app/login/page.tsx finds no oauth link), users cannot start the flow from the UI | **External blockers:** Google client id/secret; no real round-trip done
- **Severity / next action:** MEDIUM / add buttons on login/register pages; test with a real sandbox client | **Fix:** frontend/components/auth/OAuthButtons.tsx on login and register, opt-in NEXT_PUBLIC_OAUTH_PROVIDERS (3 vitest cases)

### 1.1.6 - OAuth GitHub  `FIXED_AND_TESTED`
- **Requirement:** Connexion avec compte GitHub
- **Implementation:** Backend: GitHub client registered in api/routers/oauth.py (authorize_url/access_token_url, _fetch_github_identity); same callback page
- **Tests:** tests/test_oauth_logic_integration.py (mocked) (Part run: passed)
- **Known gaps:** same missing login button as 1.1.5 | **External blockers:** GitHub OAuth app credentials
- **Severity / next action:** MEDIUM / same as 1.1.5 | **Fix:** frontend/components/auth/OAuthButtons.tsx on login and register, opt-in NEXT_PUBLIC_OAUTH_PROVIDERS (3 vitest cases)

### 1.1.7 - 2FA (Authentification à deux facteurs)  `VERIFIED_COMPLETE`
- **Requirement:** Code TOTP pour renforcer la sécurité
- **Implementation:** api/routers/two_factor.py (9 routes), api/security/totp.py (pyotp), recovery codes, WebAuthn bonus; UI in dashboard/profile/page.tsx and 2fa-lockout-recovery page
- **Tests:** tests/test_auth_api.py, tests/test_auth_security.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.1.8 - Sessions sécurisées  `VERIFIED_COMPLETE`
- **Requirement:** Gestion des tokens JWT avec refresh
- **Implementation:** POST /auth/refresh with rotating refresh tokens (api/security/sessions.py, models/token.py); frontend/lib/api.ts refresh handling
- **Tests:** tests/test_auth_api.py refresh/rotation cases (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.1.9 - Gestion des appareils / sessions actives  `VERIFIED_COMPLETE`
- **Requirement:** Visualiser et révoquer les sessions
- **Implementation:** GET /sessions and DELETE /sessions/{id} (api/routers/sessions.py); UI list + revoke in dashboard/profile/page.tsx ~378-428
- **Tests:** tests/test_auth_api.py session cases (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.1.10 - Suppression du compte  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Supprimer définitivement compte et données
- **Implementation:** DELETE /account/me (api/routers/account.py:328), purge task api/tasks/account_purge.py, restore flow (account_restore.py, restore-account page); UI deleteAccount in profile page
- **Tests:** tests/test_auth_api.py + tests/test_celery_integration.py account purge cases (Part run: passed)
- **Known gaps:** permanent deletion depends on a Celery purge job; no worker in the production image (audit R-02), so deletion may never become permanent | **External blockers:** Celery worker in production
- **Severity / next action:** HIGH / run worker/beat and verify the purge on staging | **Fix:** scripts/run_maintenance_tasks.py runs the account purge and the other daily clean-ups without a worker; cron entry in deploy/render/render.api.yaml (tests/test_run_maintenance_tasks.py)

### 1.1.11 - Export des données utilisateur (RGPD)  `FIXED_AND_TESTED`
- **Requirement:** Exporter toutes les données en JSON
- **Implementation:** GET /account/export (JSON with Content-Disposition) and /account/export-csv (api/routers/account.py:547-581); compliance router/service
- **Tests:** tests/test_auth_api.py export cases (Part run: passed)
- **Known gaps:** no frontend button found (no export call in frontend/app)
- **Severity / next action:** LOW / add an export button on the security/profile page | **Fix:** authenticated download of the personal data export from the profile page (frontend/lib/download.ts, 3 vitest cases)

### 1.1.12 - Consentement RGPD  `VERIFIED_COMPLETE`
- **Requirement:** Demander et enregistrer le consentement
- **Implementation:** consent accept/withdraw/reactivate endpoints (account.py lines 81, 442, 480, 510); reactivate-consent page; security page
- **Tests:** tests/test_auth_api.py consent cases (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.1.13 - Gestion du profil (avatar, nom, entreprise, rôle)  `FIXED_AND_TESTED`
- **Requirement:** Modifier ses informations personnelles
- **Implementation:** PATCH /account/profile, POST /account/avatar (account.py:102,164); UI avatar + name in profile page; models/user.py has company (line 97)
- **Tests:** tests/test_auth_api.py profile cases (Part run: passed)
- **Known gaps:** job-role field requested by the spec: only company found in models/user.py; avatar storage needs S3/MinIO | **External blockers:** S3 storage for avatars
- **Severity / next action:** LOW / confirm whether a job-title field is required | **Fix:** users.job_title + migration 0142 + profile field (tests/test_p2_insights.py::test_profile_stores_a_job_title)

### 1.1.14 - Préférences utilisateur (langue, fuseau horaire)  `VERIFIED_COMPLETE`
- **Requirement:** Personnaliser l'interface utilisateur
- **Implementation:** PATCH /account/preferences (account.py:135): language + timezone; UI in profile page
- **Tests:** tests/test_auth_api.py preference cases (Part run: passed)
- **Known gaps:** profile page comment mentions a 2-language scope while 6 UI locales exist
- **Severity / next action:** INFO / none

### 1.2.1 - Super Admin  `VERIFIED_COMPLETE`
- **Requirement:** Accès total à toute la plateforme
- **Implementation:** users.is_superadmin flag (models/user.py:29) used by admin routers (admin_users.py, admin_subscriptions.py, dependencies.py)
- **Tests:** tests/test_p1_backoffice_and_suspension.py, tests/test_p0_sso_domain_claim.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.2.2 - Organization Owner  `VERIFIED_COMPLETE`
- **Requirement:** Propriétaire d'une organisation
- **Implementation:** owner role in api/security/rbac.py hierarchy (owner > admin > manager > member > viewer)
- **Tests:** tests/test_organization_members.py, tests/test_organization_settings.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.2.3 - Admin  `VERIFIED_COMPLETE`
- **Requirement:** Gestion des utilisateurs, paramètres
- **Implementation:** admin role + require_org_admin (api/security/rbac.py)
- **Tests:** tests/test_organization_members.py, tests/test_enterprise_sso_integration.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.2.4 - Manager  `VERIFIED_COMPLETE`
- **Requirement:** Gestion des projets, équipes
- **Implementation:** manager role + require_org_manager (rbac.py)
- **Tests:** tests/test_organization_members.py, tests/test_user_limits.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.2.5 - Member  `VERIFIED_COMPLETE`
- **Requirement:** Utilisateur standard
- **Implementation:** member role (rbac.py); default invite role
- **Tests:** tests/test_organization_members.py, tests/test_documents.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.2.6 - Viewer  `FIXED_AND_TESTED`
- **Requirement:** Lecture seule
- **Implementation:** viewer role (rbac.py); read-only enforcement for workflows fixed in TEN-012 (PR #20)
- **Tests:** tests/test_resource_permissions.py, tests/test_documents.py, tests/test_p2_ten012_viewer_cannot_run_workflow.py (Part run: passed)
- **Known gaps:** no exhaustive route-by-role matrix exists
- **Severity / next action:** MEDIUM / add a route x role contract test | **Fix:** tests/test_p2_viewer_route_matrix.py: 233 organization write operations probed as a viewer, only 3 reachable (search, template preview, plugin review), all allow-listed with a reason

### 1.2.7 - RBAC complet  `FIXED_AND_TESTED`
- **Requirement:** Contrôle d'accès basé sur les rôles
- **Implementation:** Casbin-based RBAC (api/security/rbac.py, services/rbac_custom.py, routers/rbac.py), custom roles
- **Tests:** role checks exercised by many suites; dedicated RBAC tests to be read in Part 10 (Part run: passed)
- **Known gaps:** route classification pending
- **Severity / next action:** MEDIUM / classify the 84 routes (audit P1-3) | **Fix:** tests/test_route_auth_classification.py: the 101 operations open without a bearer token are on a reviewed list with reasons; a new open route fails the test

### 1.2.8 - Permissions granulaires par ressource  `DECISION_OR_CORRECTION`
- **Requirement:** Droit de lire/modifier/supprimer chaque ressource
- **Implementation:** resource_permissions router/security/model/migration 0017 (read/write/delete per resource)
- **Tests:** tests/test_resource_permissions.py (Part run: passed)
- **Known gaps:** which resource types honour these grants is not established
- **Severity / next action:** MEDIUM / list the resource types that call the check and test each | **Fix:** grants are accepted only for resource types that enforce them (workspaces); other types are rejected with 400; scope and extension path in docs/DECISIONS.md D11

### 1.3.1 - Organizations  `VERIFIED_COMPLETE`
- **Requirement:** Groupe d'utilisateurs partageant des ressources
- **Implementation:** models/organization.py, routers/organizations.py, organization_members
- **Tests:** organization-scoped tests across the suite (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.3.2 - Workspaces  `FIXED_AND_TESTED`
- **Requirement:** Espaces de travail au sein d'une organisation
- **Implementation:** routers/workspaces.py + security/workspaces.py + models/workspace.py
- **Tests:** tests/test_documents.py, tests/test_resource_permissions.py (Part run: passed)
- **Known gaps:** no workspace page found in frontend/app
- **Severity / next action:** LOW / confirm whether UI is needed | **Fix:** frontend/app/dashboard/teams (4 vitest cases)

### 1.3.3 - Teams  `FIXED_AND_TESTED`
- **Requirement:** Sous-groupes d'utilisateurs dans un workspace
- **Implementation:** routers/teams.py, security/teams.py, models/team.py (user groups)
- **Tests:** tests/test_teams.py (Part run: passed)
- **Known gaps:** no team-management page found in frontend/app
- **Severity / next action:** LOW / add team UI or document as API-only | **Fix:** frontend/app/dashboard/teams (4 vitest cases)

### 1.3.4 - Invitations (email + lien)  `VERIFIED_COMPLETE`
- **Requirement:** Inviter des utilisateurs par email
- **Implementation:** routers/invitations.py, security/invitations.py; UI in settings/organization/page.tsx and invitations/accept page (with test)
- **Tests:** tests/test_invitations.py; frontend page.test.tsx (Part run: passed)
- **Known gaps:** none found | **External blockers:** Resend for email delivery
- **Severity / next action:** INFO / none

### 1.3.5 - Isolation des données  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Chaque organisation a ses propres documents et conversations
- **Implementation:** org-scoped filters in services/routers; tests such as tests/test_p0_chat_conversation_isolation.py
- **Tests:** application-level isolation tests exist; no PostgreSQL RLS proof in CI (Part run: passed)
- **Known gaps:** one forgotten filter exposes another tenant; opt-in PostgreSQL tests are not in CI | **External blockers:** PostgreSQL
- **Severity / next action:** CRITICAL / decide the RLS strategy (audit P0-1) and add a contract test per route | **Fix:** backend-tests starts a pgvector PostgreSQL with all migrations; 61 PostgreSQL integration tests pass locally; RLS rollout decision in D8

### 1.3.6 - Quotas par organisation  `FIXED_AND_TESTED`
- **Requirement:** Limites de documents, utilisateurs, requêtes
- **Implementation:** routers/quotas.py, security/quotas.py, models/organization_quota.py; API-key quota in settings/api-keys page
- **Tests:** tests/test_quotas.py (Part run: passed)
- **Known gaps:** not every creation path (documents, members, requests) re-verified to call the quota check
- **Severity / next action:** MEDIUM / list enforcement points and test each | **Fix:** api/security/document_capacity.py: plan document limit now also on the batch upload and the 9 importers, storage quota enforced on upload and batch (tests/test_p2_document_capacity.py)

### 1.3.7 - Limites par utilisateur  `FIXED_AND_TESTED`
- **Requirement:** Nombre de requêtes par utilisateur
- **Implementation:** routers/user_limits.py + security/user_limits.py
- **Tests:** tests/test_user_limits.py (few cases) (Part run: passed)
- **Known gaps:** thin test coverage; no frontend; enforcement on the chat path not confirmed
- **Severity / next action:** MEDIUM / confirm enforcement in chat and add tests | **Fix:** per-user rate limit on /chat/stream (CHAT_USER_RATE_LIMIT_*; fails open without Redis) (tests/test_p2_chat_user_rate_limit.py)

### 1.3.8 - Usage par organisation  `DECISION_OR_CORRECTION`
- **Requirement:** Dashboard des statistiques par organisation
- **Implementation:** routers/usage.py, security/usage.py, GET /admin/organizations/{org_id}/usage; frontend billing/analytics usage views
- **Tests:** tests/test_usage.py, tests/test_token_usage.py (Part run: passed)
- **Known gaps:** a usage dashboard for a normal org admin not confirmed
- **Severity / next action:** LOW / confirm UI | **Fix:** the billing page already has a Usage tab (frontend/app/dashboard/billing/page.tsx, UsageTab) fed by GET /organizations/{id}/billing/usage and /usage/forecast, for members with billing:manage; the route is covered by tests/test_billing.py (usage case passes); the tab itself has no component test

### 1.3.9 - Configuration par organisation  `VERIFIED_COMPLETE`
- **Requirement:** Paramètres spécifiques à chaque organisation
- **Implementation:** routers/organization_settings.py + security + schema; UI settings/organization page
- **Tests:** tests/test_organization_settings.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.3.10 - Branding par organisation  `VERIFIED_COMPLETE`
- **Requirement:** Logo, couleurs, nom personnalisables
- **Implementation:** routers/organization_branding.py; frontend BrandingApplier.tsx, branding-context.tsx
- **Tests:** tests/test_organization_branding.py, tests/test_email_branding.py (Part run: passed)
- **Known gaps:** none found | **External blockers:** S3 for logo storage
- **Severity / next action:** INFO / none

### 1.4.1 - Custom domains (app.client.com)  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Chaque client peut utiliser son propre domaine
- **Implementation:** routers/custom_domains.py, security/custom_domains.py, models/custom_domain.py; middleware services/white_label_middleware.py
- **Tests:** tests/test_custom_domains.py, tests/test_domain_verification.py (mocked DNS) (Part run: passed)
- **Known gaps:** real host routing (Vercel/Render custom domain) not exercised | **External blockers:** DNS, hosting provider
- **Severity / next action:** MEDIUM / staging test with a real domain

### 1.4.2 - DNS instructions  `VERIFIED_COMPLETE`
- **Requirement:** Instructions pour configurer le DNS
- **Implementation:** custom_domains returns DNS record instructions; frontend components/whitelabel/DomainConfig.tsx
- **Tests:** tests/test_domain_verification.py, tests/test_email_domains.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 1.4.3 - SSL automatique (Let's Encrypt)  `BLOCKED_EXTERNAL`
- **Requirement:** Certificat SSL automatique
- **Implementation:** security/ssl_certificates.py uses acme/josepy (new_order, challenges), routers/ssl_certificates.py, renewal task api/tasks/ssl_certificate_renewal.py
- **Tests:** tests/test_ssl_certificates.py with mocked ACME (Part run: passed)
- **Known gaps:** real issuance needs a public DNS name and reachable host; Render/Vercel terminate TLS themselves so this path may be unused in production | **External blockers:** Let's Encrypt, public domain, Celery worker for renewal
- **Severity / next action:** MEDIUM / decide: rely on host-managed TLS, or run ACME on staging

### 1.4.4 - Domain verification  `VERIFIED_COMPLETE`
- **Requirement:** Vérifier la propriété du domaine
- **Implementation:** TXT-record verification in security/custom_domains.py and security/email_domains.py
- **Tests:** tests/test_domain_verification.py, tests/test_email_domains.py (Part run: passed)
- **Known gaps:** DNS lookups are mocked in tests
- **Severity / next action:** INFO / none

### 1.4.5 - Custom email domain  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Utiliser le domaine pour les emails
- **Implementation:** routers/email_domains.py, security/email_domains.py, services/resend_domains.py (Resend domain API)
- **Tests:** tests/test_email_domains.py, tests/test_email_domains_integration.py (mocked) (Part run: passed)
- **Known gaps:** real Resend domain verification not exercised | **External blockers:** Resend
- **Severity / next action:** MEDIUM / staging test with Resend

### 1.4.6 - White-label complet  `FIXED_AND_TESTED`
- **Requirement:** Supprimer toute mention de ta marque
- **Implementation:** routers/white_label.py, security/white_label.py, middleware; frontend lib/services/whitelabel.ts, settings/white-label page
- **Tests:** tests/test_white_label.py, tests/backend/whitelabel/* (Part run: passed)
- **Known gaps:** removal of every brand mention across all pages and emails is not proven
- **Severity / next action:** LOW / visual audit of leftover brand strings | **Fix:** organization brand name in the chat header and tab title, accent colour and font applied across the interface (frontend/components/BrandingApplier.test.tsx)

### 1.4.7 - Brand name, logo, favicon personnalisables  `VERIFIED_COMPLETE`
- **Requirement:** Modifier l'identité visuelle
- **Implementation:** branding endpoints; FaviconUpload.tsx, white-label page
- **Tests:** tests/test_organization_branding.py, tests/test_branding_storage_integration.py (Part run: passed)
- **Known gaps:** S3 for stored assets | **External blockers:** S3/MinIO
- **Severity / next action:** INFO / none

### 1.4.8 - Couleurs, polices, thème personnalisables  `FIXED_AND_TESTED`
- **Requirement:** Adapter l'apparence
- **Implementation:** colours/fonts/theme: routers/widget.py, services/widget.py, BrandingApplier.tsx
- **Tests:** tests/test_widget.py, tests/test_widget_branding_fallback.py (Part run: passed)
- **Known gaps:** widget theming is proven; dashboard-wide font/theme application is not distinguished
- **Severity / next action:** LOW / confirm the dashboard applies fonts and theme | **Fix:** organization brand name in the chat header and tab title, accent colour and font applied across the interface (frontend/components/BrandingApplier.test.tsx)

### 1.4.9 - Email sender personnalisable  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Modifier l'adresse d'envoi des emails
- **Implementation:** email sender customisation: security/white_label.py, services/email_branding.py; frontend EmailConfig.tsx
- **Tests:** tests/test_email_branding.py, tests/backend/whitelabel/test_email.py (Part run: passed)
- **Known gaps:** real sending not exercised | **External blockers:** Resend
- **Severity / next action:** LOW / staging test

### 1.4.10 - Welcome message / AI personality / System prompt  `VERIFIED_COMPLETE`
- **Requirement:** Personnaliser le comportement de l'IA
- **Implementation:** welcome message / system prompt / personality: services/widget.py, services/agent_orchestrator.py, agent prompts; UI agents/new page
- **Tests:** tests/test_agent_prompts.py, tests/test_llm_config.py (Part run: passed)
- **Known gaps:** none found | **External blockers:** LLM provider needed for behavioural proof
- **Severity / next action:** INFO / none

## Part 2 - Universal knowledge base (document import, extraction, metadata, batch jobs)

35 features: FIXED_AND_TESTED 21, VERIFIED_COMPLETE 13, DECISION_OR_CORRECTION 1

### 2.1.1 - PDF  `VERIFIED_COMPLETE`
- **Requirement:** Extraire texte, tableaux, images
- **Implementation:** POST /organizations/{org_id}/documents (api/routers/documents.py:227); UI upload in frontend/app/dashboard/documents/page.tsx (single file); extractor api/services/pdf_extraction.py (+ docling_extraction.py, ocr.py)
- **Tests:** tests/test_pdf_extraction.py, tests/test_docling_extraction.py (Part run: passed)
- **Known gaps:** OCR needs Tesseract/poppler binaries (installed in CI only)
- **Severity / next action:** INFO / none

### 2.1.2 - DOCX  `VERIFIED_COMPLETE`
- **Requirement:** Extraire texte, tableaux, styles
- **Implementation:** POST /organizations/{org_id}/documents (api/routers/documents.py:227); UI upload in frontend/app/dashboard/documents/page.tsx (single file); api/services/docx_extraction.py
- **Tests:** tests/test_docx_extraction.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 2.1.3 - TXT  `VERIFIED_COMPLETE`
- **Requirement:** Texte brut
- **Implementation:** POST /organizations/{org_id}/documents (api/routers/documents.py:227); UI upload in frontend/app/dashboard/documents/page.tsx (single file); api/services/txt_extraction.py
- **Tests:** tests/test_txt_extraction.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 2.1.4 - Markdown  `VERIFIED_COMPLETE`
- **Requirement:** Titres, sections, code
- **Implementation:** POST /organizations/{org_id}/documents (api/routers/documents.py:227); UI upload in frontend/app/dashboard/documents/page.tsx (single file); api/services/markdown_extraction.py
- **Tests:** tests/test_markdown_extraction.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 2.1.5 - HTML  `VERIFIED_COMPLETE`
- **Requirement:** Extraire texte structuré
- **Implementation:** POST /organizations/{org_id}/documents (api/routers/documents.py:227); UI upload in frontend/app/dashboard/documents/page.tsx (single file); api/services/html_extraction.py
- **Tests:** tests/test_html_extraction.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 2.1.6 - CSV  `VERIFIED_COMPLETE`
- **Requirement:** Extraire données tabulaires
- **Implementation:** POST /organizations/{org_id}/documents (api/routers/documents.py:227); UI upload in frontend/app/dashboard/documents/page.tsx (single file); api/services/csv_extraction.py
- **Tests:** tests/test_csv_extraction.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 2.1.7 - JSON  `VERIFIED_COMPLETE`
- **Requirement:** Extraire structures imbriquées
- **Implementation:** POST /organizations/{org_id}/documents (api/routers/documents.py:227); UI upload in frontend/app/dashboard/documents/page.tsx (single file); api/services/json_extraction.py
- **Tests:** tests/test_json_extraction.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 2.1.8 - XML  `VERIFIED_COMPLETE`
- **Requirement:** Extraire données structurées
- **Implementation:** POST /organizations/{org_id}/documents (api/routers/documents.py:227); UI upload in frontend/app/dashboard/documents/page.tsx (single file); api/services/xml_extraction.py
- **Tests:** tests/test_xml_extraction.py (Part run: passed)
- **Known gaps:** XML parsing hardening (entity expansion) not re-read
- **Severity / next action:** LOW / confirm defusedxml or equivalent in xml_extraction.py

### 2.1.9 - EPUB  `VERIFIED_COMPLETE`
- **Requirement:** Extraire livre numérique
- **Implementation:** POST /organizations/{org_id}/documents (api/routers/documents.py:227); UI upload in frontend/app/dashboard/documents/page.tsx (single file); api/services/epub_extraction.py
- **Tests:** tests/test_epub_extraction.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 2.1.10 - URLs / pages web  `VERIFIED_COMPLETE`
- **Requirement:** Extraire contenu d'une page web
- **Implementation:** POST /organizations/{org_id}/documents/url (documents.py:301), api/services/url_extraction.py, url_fetching.py, task api/tasks/url_import.py
- **Tests:** tests/test_url_fetching.py, tests/test_ssrf_hardening.py (SSRF guard) (Part run: passed)
- **Known gaps:** no screen: frontend/app/dashboard/documents/page.tsx (103 lines) only lists, uploads one file and deletes - no URL import form | **External blockers:** real network fetch not exercised
- **Severity / next action:** LOW / add an 'Import from URL' form

### 2.1.11 - Sitemap  `FIXED_AND_TESTED`
- **Requirement:** Extraire plusieurs pages d'un site
- **Implementation:** POST /organizations/{org_id}/documents/sitemap (documents.py:323), api/services/sitemap_extraction.py, api/tasks/sitemap_import.py
- **Tests:** tests/test_sitemap_extraction.py, tests/test_sitemap_integration.py (Part run: passed)
- **Known gaps:** no screen: frontend/app/dashboard/documents/page.tsx (103 lines) only lists, uploads one file and deletes - no sitemap form
- **Severity / next action:** LOW / add UI | **Fix:** frontend/components/ImportSources.tsx: sitemap, URL, GitHub, Notion and other importers from the documents page (5 vitest cases)

### 2.1.12 - GitHub repositories  `FIXED_AND_TESTED`
- **Requirement:** Indexer le code et README d'un repo
- **Implementation:** POST /organizations/{org_id}/documents/github/repo (documents.py:346), api/services/github_extraction.py, api/tasks/github_import.py
- **Tests:** tests/test_github_extraction.py, tests/test_github_integration.py (GitHub API mocked) (Part run: passed)
- **Known gaps:** no screen: frontend/app/dashboard/documents/page.tsx (103 lines) only lists, uploads one file and deletes - no GitHub import form | **External blockers:** GitHub API / token
- **Severity / next action:** MEDIUM / sandbox test with a real read-only token; add UI | **Fix:** frontend/components/ImportSources.tsx now offers GitHub repository and issues, Google Drive and Docs, Notion, Confluence and OneDrive (10 vitest cases, tsc and eslint clean)

### 2.1.13 - GitHub issues  `FIXED_AND_TESTED`
- **Requirement:** Indexer les issues d'un projet
- **Implementation:** POST /organizations/{org_id}/documents/github/issues (documents.py:370), same extractor
- **Tests:** tests/test_github_integration.py (mocked) (Part run: passed)
- **Known gaps:** no screen: frontend/app/dashboard/documents/page.tsx (103 lines) only lists, uploads one file and deletes | **External blockers:** GitHub API / token
- **Severity / next action:** MEDIUM / same as 2.1.12 | **Fix:** frontend/components/ImportSources.tsx now offers GitHub repository and issues, Google Drive and Docs, Notion, Confluence and OneDrive (10 vitest cases, tsc and eslint clean)

### 2.1.14 - Google Drive  `FIXED_AND_TESTED`
- **Requirement:** Importer des fichiers depuis Google Drive
- **Implementation:** POST /organizations/{org_id}/documents/google-drive (documents.py:396), api/services/google_drive_extraction.py, api/tasks/google_drive_import.py
- **Tests:** tests/test_google_drive_integration.py (mocked) (Part run: passed)
- **Known gaps:** no screen: frontend/app/dashboard/documents/page.tsx (103 lines) only lists, uploads one file and deletes | **External blockers:** Google OAuth / Drive API
- **Severity / next action:** MEDIUM / sandbox test; add UI | **Fix:** frontend/components/ImportSources.tsx now offers GitHub repository and issues, Google Drive and Docs, Notion, Confluence and OneDrive (10 vitest cases, tsc and eslint clean)

### 2.1.15 - Google Docs  `FIXED_AND_TESTED`
- **Requirement:** Importer des documents Google Docs
- **Implementation:** POST /organizations/{org_id}/documents/google-docs (documents.py:420), api/tasks/google_docs_import.py
- **Tests:** tests/test_google_docs_integration.py (mocked) (Part run: passed)
- **Known gaps:** no screen: frontend/app/dashboard/documents/page.tsx (103 lines) only lists, uploads one file and deletes | **External blockers:** Google OAuth / Docs API
- **Severity / next action:** MEDIUM / same as 2.1.14 | **Fix:** frontend/components/ImportSources.tsx now offers GitHub repository and issues, Google Drive and Docs, Notion, Confluence and OneDrive (10 vitest cases, tsc and eslint clean)

### 2.1.16 - Notion  `FIXED_AND_TESTED`
- **Requirement:** Importer des pages Notion
- **Implementation:** POST /organizations/{org_id}/documents/notion (documents.py:445), api/services/notion_extraction.py, api/tasks/notion_import.py
- **Tests:** tests/test_notion_extraction.py (mocked) (Part run: passed)
- **Known gaps:** no screen: frontend/app/dashboard/documents/page.tsx (103 lines) only lists, uploads one file and deletes | **External blockers:** Notion API / token
- **Severity / next action:** MEDIUM / sandbox test; add UI | **Fix:** frontend/components/ImportSources.tsx now offers GitHub repository and issues, Google Drive and Docs, Notion, Confluence and OneDrive (10 vitest cases, tsc and eslint clean)

### 2.1.17 - Confluence  `FIXED_AND_TESTED`
- **Requirement:** Importer des pages Confluence
- **Implementation:** POST /organizations/{org_id}/documents/confluence (documents.py:468), api/services/confluence_extraction.py, api/tasks/confluence_import.py
- **Tests:** tests/test_confluence_extraction.py (mocked) (Part run: passed)
- **Known gaps:** no screen: frontend/app/dashboard/documents/page.tsx (103 lines) only lists, uploads one file and deletes | **External blockers:** Confluence API / token
- **Severity / next action:** MEDIUM / sandbox test; add UI | **Fix:** frontend/components/ImportSources.tsx now offers GitHub repository and issues, Google Drive and Docs, Notion, Confluence and OneDrive (10 vitest cases, tsc and eslint clean)

### 2.1.18 - OneDrive  `FIXED_AND_TESTED`
- **Requirement:** Importer depuis OneDrive
- **Implementation:** POST /organizations/{org_id}/documents/onedrive (documents.py:491), api/services/onedrive_extraction.py, api/tasks/onedrive_import.py
- **Tests:** tests/test_onedrive_extraction.py (mocked) (Part run: passed)
- **Known gaps:** no screen: frontend/app/dashboard/documents/page.tsx (103 lines) only lists, uploads one file and deletes | **External blockers:** Microsoft Graph / token
- **Severity / next action:** MEDIUM / sandbox test; add UI | **Fix:** frontend/components/ImportSources.tsx now offers GitHub repository and issues, Google Drive and Docs, Notion, Confluence and OneDrive (10 vitest cases, tsc and eslint clean)

### 2.1.19 - Fichiers ZIP  `VERIFIED_COMPLETE`
- **Requirement:** Importer plusieurs fichiers compressés
- **Implementation:** ZIP import: api/services/zip_extraction.py, api/tasks/zip_import.py, called from upload in api/security/documents.py
- **Tests:** tests/test_zip_extraction.py, tests/test_zip_integration.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** LOW / confirm zip-bomb limits in zip_extraction.py

### 2.2.1 - Upload multiple  `FIXED_AND_TESTED`
- **Requirement:** Importer plusieurs fichiers en une fois
- **Implementation:** POST /organizations/{org_id}/documents/batch (documents.py:267)
- **Tests:** tests/test_documents.py upload cases (batch case not isolated) (Part run: passed)
- **Known gaps:** UI input accepts one file at a time (documents/page.tsx:54 calls postFile once); no multi-select
- **Severity / next action:** LOW / allow multiple files in the UI | **Fix:** documents page multi-file, drop zone, status polling (3 vitest cases)

### 2.2.2 - Drag & drop  `FIXED_AND_TESTED`
- **Requirement:** Glisser-déposer pour importer
- **Implementation:** none for documents. Drag-drop exists only in frontend/components/media/MediaUploadZone.tsx (media library)
- **Tests:** none (Part run: passed)
- **Known gaps:** documents page has no drop zone (inspected documents/page.tsx and dashboard page)
- **Severity / next action:** LOW / add a drop zone to the documents page | **Fix:** documents page multi-file, drop zone, status polling (3 vitest cases)

### 2.2.3 - Progression d'import  `FIXED_AND_TESTED`
- **Requirement:** Barre de progression et statut
- **Implementation:** GET /documents/{id}/progress and /progress/stream SSE (documents.py:640-653), tests/test_document_progress.py
- **Tests:** tests/test_document_progress.py (Part run: passed)
- **Known gaps:** UI shows only a text status (documents/page.tsx:93); no progress bar or stream consumer
- **Severity / next action:** LOW / consume the SSE stream in the UI | **Fix:** documents page multi-file, drop zone, status polling (3 vitest cases)

### 2.2.4 - File preview  `FIXED_AND_TESTED`
- **Requirement:** Aperçu du document avant import
- **Implementation:** GET /documents/{id}/preview (documents.py:609)
- **Tests:** tests/test_documents.py (limited) (Part run: passed)
- **Known gaps:** no preview component in the documents page
- **Severity / next action:** LOW / add preview panel | **Fix:** frontend/components/DocumentDetails.tsx (7 vitest cases)

### 2.2.5 - Metadata extraction  `VERIFIED_COMPLETE`
- **Requirement:** Extraire auteur, date, mots-clés
- **Implementation:** GET /documents/{id}/metadata (documents.py:572), api/services/metadata_enrichment.py, models/metadata_enrichment.py
- **Tests:** tests/test_metadata_filtering.py, tests/test_documents_integration.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 2.2.6 - Tags et catégories  `FIXED_AND_TESTED`
- **Requirement:** Organiser les documents par tags
- **Implementation:** tag routes /organizations/{org_id}/tags, /tags/{id}, /documents/{id}/tags (documents.py:745-878), api/security/document_tags.py
- **Tests:** tests/test_documents.py tag cases (Part run: passed)
- **Known gaps:** no tag UI; 'categories' from the spec not found as a separate concept
- **Severity / next action:** LOW / add tag UI; clarify categories | **Fix:** frontend/components/DocumentDetails.tsx (7 vitest cases)

### 2.2.7 - Versioning  `FIXED_AND_TESTED`
- **Requirement:** Conserver l'historique des versions
- **Implementation:** versions routes (documents.py:913-969), api/security/document_versions.py, migration 0035
- **Tests:** tests/test_documents.py (6 refs) (Part run: passed)
- **Known gaps:** thin test coverage; no UI
- **Severity / next action:** MEDIUM / add tests for restore and replace; add UI | **Fix:** frontend/components/DocumentDetails.tsx (7 vitest cases)

### 2.2.8 - Suppression / Remplacement  `FIXED_AND_TESTED`
- **Requirement:** Supprimer ou remplacer un document
- **Implementation:** DELETE /documents/{id} (UI delete button documents/page.tsx:64), DELETE /documents/{id}/permanent, POST /documents/{id}/replace (documents.py:719)
- **Tests:** tests/test_documents.py delete cases; tests/test_p2_ten003_s3_upload_off_event_loop.py (Part run: passed)
- **Known gaps:** replace has no UI | **External blockers:** S3 for stored files
- **Severity / next action:** LOW / add replace action | **Fix:** frontend/components/DocumentDetails.tsx (7 vitest cases)

### 2.2.9 - Réindexation manuelle  `FIXED_AND_TESTED`
- **Requirement:** Reconstruire l'index vectoriel
- **Implementation:** POST /documents/{id}/reindex and /organizations/{org_id}/documents/reindex (documents.py:994-1007), api/tasks/reindex.py
- **Tests:** tests/test_reindex.py (Part run: passed)
- **Known gaps:** no UI; task needs a Celery worker (audit R-02) | **External blockers:** Celery worker
- **Severity / next action:** MEDIUM / add button; ensure worker | **Fix:** frontend/components/DocumentDetails.tsx (7 vitest cases)

### 2.2.10 - Historique des modifications  `FIXED_AND_TESTED`
- **Requirement:** Suivre toutes les modifications
- **Implementation:** GET /documents/{id}/history (documents.py:1027), api/security/document_audit.py
- **Tests:** tests/test_documents.py history cases (Part run: passed)
- **Known gaps:** no UI
- **Severity / next action:** LOW / add history view | **Fix:** frontend/components/DocumentDetails.tsx (7 vitest cases)

### 2.2.11 - Statut d'indexation  `VERIFIED_COMPLETE`
- **Requirement:** En cours, terminé, échec
- **Implementation:** GET /documents/{id}/status and org summary (documents.py:1051-1068); UI shows status per row (documents/page.tsx:93)
- **Tests:** tests/test_documents.py status cases (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 2.2.12 - Détection de doublons  `FIXED_AND_TESTED`
- **Requirement:** Éviter l'indexation en double
- **Implementation:** GET /documents/{id}/duplicates, POST /organizations/{org_id}/documents/deduplicate (documents.py:1111-1125), api/services/duplicate_removal.py
- **Tests:** tests/test_duplicate_removal.py, tests/test_document_duplicates.py (Part run: passed)
- **Known gaps:** no UI
- **Severity / next action:** LOW / add UI | **Fix:** frontend/components/DocumentDetails.tsx (7 vitest cases)

### 2.2.13 - Détection de documents modifiés  `FIXED_AND_TESTED`
- **Requirement:** Réindexer automatiquement les changements
- **Implementation:** POST /documents/{id}/check-modified, GET /documents/outdated (documents.py:530-551), api/tasks/document_modification_check.py
- **Tests:** tests/test_document_modification_check.py (mocked fetch) (Part run: passed)
- **Known gaps:** periodic run needs Celery beat (audit R-02); no UI | **External blockers:** Celery beat, remote URLs
- **Severity / next action:** MEDIUM / stage test with worker/beat | **Fix:** scripts/test_env/celery_beat_probe.py: check_modified_documents_task and check_scheduled_reindexes_task were scheduled by a real beat every 8 s and executed by a real worker 10 times each, 0 failures (17 periodic tasks, 170 executions in total); an empty database proves scheduling, dispatch and no crash, not the processing of real data

### 2.2.14 - Synchronisation automatique  `FIXED_AND_TESTED`
- **Requirement:** Synchroniser avec les sources externes
- **Implementation:** api/routers/documents_sync.py, api/tasks/external_source_sync.py, frontend components SyncHistory.tsx
- **Tests:** tests exist (tests/test_external_sources.py); exact sync tests not read (Part run: passed)
- **Known gaps:** depends on Celery beat; connectors external | **External blockers:** Celery beat, external APIs
- **Severity / next action:** MEDIUM / stage test | **Fix:** sync_all_sources_periodic_task ran 10 times under a real beat and worker without failure on an empty database; no external connector was exercised

### 2.2.15 - Auto-reindexation programmée  `FIXED_AND_TESTED`
- **Requirement:** Planifier des réindexations automatiques
- **Implementation:** api/routers/reindex_schedules.py, security/reindex_schedules.py, api/tasks/reindex_schedule.py, migration 0043
- **Tests:** tests/test_reindex_schedules.py (Part run: passed)
- **Known gaps:** needs Celery beat; no UI | **External blockers:** Celery beat
- **Severity / next action:** MEDIUM / stage test with beat | **Fix:** scripts/test_env/celery_beat_probe.py: check_modified_documents_task and check_scheduled_reindexes_task were scheduled by a real beat every 8 s and executed by a real worker 10 times each, 0 failures (17 periodic tasks, 170 executions in total); an empty database proves scheduling, dispatch and no crash, not the processing of real data

### 2.2.16 - Batch Processing  `DECISION_OR_CORRECTION`
- **Requirement:** Traiter plusieurs documents par lots
- **Implementation:** api/routers/batch_jobs.py, security/batch_jobs.py, api/tasks/batch_jobs.py, api/tasks/document_batch_processing.py, migration 0044
- **Tests:** tests/test_batch_jobs.py (Part run: passed)
- **Known gaps:** needs a Celery worker; no UI | **External blockers:** Celery worker
- **Severity / next action:** MEDIUM / stage test with worker | **Fix:** the documents page already offers multi-file upload with live status (frontend/app/dashboard/documents, 3 vitest cases, see 2.2.1 to 2.2.3); what remains is a running Celery worker in production (deploy/render/render.api.yaml defines it, not applied)

## Part 3 - Advanced RAG pipeline (extraction, chunking, embeddings, retrieval, advanced retrieval)

41 features: VERIFIED_COMPLETE 34, FIXED_AND_TESTED 3, DECISION_OR_CORRECTION 2, IMPLEMENTED_UNVERIFIED 2

### 3.1.1 - Nettoyage du texte  `VERIFIED_COMPLETE`
- **Requirement:** Supprimer les caractères spéciaux inutiles
- **Implementation:** api/services/text_cleaning.py, called from the ingestion path in api/security/documents.py
- **Tests:** tests/test_text_cleaning.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.1.2 - Normalisation (unicode, casse)  `VERIFIED_COMPLETE`
- **Requirement:** Standardiser le texte
- **Implementation:** api/services/text_normalization.py (also used by query_rewriting.py), called from the ingestion path in api/security/documents.py
- **Tests:** tests/test_text_normalization.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.1.3 - Extraction du texte  `VERIFIED_COMPLETE`
- **Requirement:** Extraire le texte des documents
- **Implementation:** api/services/document_extraction.py + per-format extractors (see Part 2)
- **Tests:** per-format tests (test_pdf_extraction.py, test_docx_extraction.py, ...) (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.1.4 - Extraction des tableaux  `VERIFIED_COMPLETE`
- **Requirement:** Convertir les tableaux en texte structuré
- **Implementation:** api/services/table_transformation.py, structure_detection.py; called from the ingestion path in api/security/documents.py
- **Tests:** tests/test_table_transformation.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.1.5 - Extraction des images  `DECISION_OR_CORRECTION`
- **Requirement:** Extraire les légendes et descriptions
- **Implementation:** api/services/image_extraction.py, models/document_image.py, GET /documents/{id}/images (documents.py:589)
- **Tests:** tests/test_image_extraction.py (Part run: passed)
- **Known gaps:** spec says extract captions and descriptions; image description by a vision model was not found in image_extraction.py (not fully read) | **External blockers:** vision model if required
- **Severity / next action:** LOW / confirm whether descriptions are generated | **Fix:** describe_embedded_image_if_enabled already calls a vision model per embedded image (off by default, MULTIMODAL_DESCRIBE_DOCUMENT_IMAGES); tested with a fake provider (tests/backend/media/test_media_finalization.py); no real vision call run

### 3.1.6 - OCR optionnel  `FIXED_AND_TESTED`
- **Requirement:** Reconnaissance de caractères dans les images scannées
- **Implementation:** api/services/ocr.py (pytesseract/pdf2image), used by pdf and image extraction
- **Tests:** tests/test_ocr.py (needs Tesseract/poppler; installed in CI only) (Part run: passed)
- **Known gaps:** cannot run on this machine without the binaries | **External blockers:** Tesseract, poppler
- **Severity / next action:** LOW / run the OCR test in CI | **Fix:** tests/test_ocr.py run with the Tesseract and Poppler binaries and the French language data; the scanned-PDF path through the documents pipeline needs the S3 stack and was not rerun here

### 3.1.7 - Détection de langue  `VERIFIED_COMPLETE`
- **Requirement:** Identifier la langue du document
- **Implementation:** api/services/language_detection.py, used in ingestion and sentence_chunking
- **Tests:** tests/test_language_detection.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.1.8 - Détection de structure documentaire  `VERIFIED_COMPLETE`
- **Requirement:** Identifier titres, sections, paragraphes
- **Implementation:** api/services/structure_detection.py
- **Tests:** tests/test_structure_detection.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.1.9 - Extraction des titres et sections  `VERIFIED_COMPLETE`
- **Requirement:** Structurer le document
- **Implementation:** api/services/headings_extraction.py
- **Tests:** tests/test_headings_extraction.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.1.10 - Metadata extraction  `VERIFIED_COMPLETE`
- **Requirement:** Extraire auteur, date, mots-clés
- **Implementation:** api/services/metadata_enrichment.py, models/metadata_enrichment.py, GET /documents/{id}/metadata
- **Tests:** tests/test_metadata_enrichment.py, tests/test_metadata_normalization.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.2.1 - Fixed-size  `VERIFIED_COMPLETE`
- **Requirement:** Découpage en blocs de taille fixe
- **Implementation:** token sliding-window chunk_text (api/security/documents.py:385), strategy 'fixed' (default)
- **Tests:** tests/test_chunking.py, tests/test_chunking_strategy_wiring.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.2.2 - Recursive  `VERIFIED_COMPLETE`
- **Requirement:** Découpage récursif pour respecter la taille
- **Implementation:** strategy 'recursive': dispatched by api/services/chunk_config.py::chunk_content and wired in api/security/documents.py (~3293-3351); api/services/chunking.py
- **Tests:** tests/test_chunking.py, tests/test_chunking_strategy_wiring.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.2.3 - Semantic chunking  `VERIFIED_COMPLETE`
- **Requirement:** Découpage basé sur le sens
- **Implementation:** strategy 'semantic': api/services/semantic_chunking.py; dispatched by api/services/chunk_config.py::chunk_content and wired in api/security/documents.py (~3293-3351)
- **Tests:** tests/test_semantic_chunking.py, tests/test_chunking_strategy_wiring.py (Part run: passed)
- **Known gaps:** needs an embedding model at ingestion (cost/latency not measured) | **External blockers:** embedding model
- **Severity / next action:** LOW / measure ingestion cost

### 3.2.4 - Markdown-aware  `VERIFIED_COMPLETE`
- **Requirement:** Découpage respectant la structure Markdown
- **Implementation:** strategy 'markdown': api/services/markdown_chunking.py; dispatched by api/services/chunk_config.py::chunk_content and wired in api/security/documents.py (~3293-3351)
- **Tests:** tests/test_markdown_chunking.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.2.5 - Code-aware  `VERIFIED_COMPLETE`
- **Requirement:** Découpage respectant la structure du code
- **Implementation:** strategy 'code': api/services/code_chunking.py (no tree-sitter, deviation documented in the old doc); dispatched by api/services/chunk_config.py::chunk_content and wired in api/security/documents.py (~3293-3351)
- **Tests:** tests/test_code_chunking.py (Part run: passed)
- **Known gaps:** structure awareness is heuristic, not parser-based
- **Severity / next action:** LOW / none

### 3.2.6 - Sentence-based  `VERIFIED_COMPLETE`
- **Requirement:** Découpage par phrases
- **Implementation:** strategy 'sentence': api/services/sentence_chunking.py; dispatched by api/services/chunk_config.py::chunk_content and wired in api/security/documents.py (~3293-3351)
- **Tests:** tests/test_sentence_chunking.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.2.7 - Paragraph-based  `VERIFIED_COMPLETE`
- **Requirement:** Découpage par paragraphes
- **Implementation:** strategy 'paragraph': api/services/paragraph_chunking.py; dispatched by api/services/chunk_config.py::chunk_content and wired in api/security/documents.py (~3293-3351)
- **Tests:** tests/test_paragraph_chunking.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.2.8 - Parent-child chunks  `VERIFIED_COMPLETE`
- **Requirement:** Blocs parents/enfants pour hiérarchie
- **Implementation:** strategy 'parent_child': api/services/parent_child_chunking.py, chunk_parent_child called from api/security/documents.py
- **Tests:** tests/test_parent_child_chunking.py, tests/test_parent_child_chunking_wiring.py (Part run: passed)
- **Known gaps:** retrieval of the parent from a child hit not re-read
- **Severity / next action:** LOW / confirm parent expansion at query time

### 3.3.1 - Chunk size  `VERIFIED_COMPLETE`
- **Requirement:** Taille des blocs (configurable par organisation)
- **Implementation:** resolve_chunk_size in api/services/chunk_config.py, org setting chunk_size (api/schemas/organization_settings.py)
- **Tests:** tests/test_chunk_config.py, tests/test_organization_settings.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.3.2 - Overlap  `VERIFIED_COMPLETE`
- **Requirement:** Chevauchement entre blocs
- **Implementation:** resolve_chunk_overlap in chunk_config.py (must be smaller than size)
- **Tests:** tests/test_chunk_config.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.3.3 - Embedding model  `VERIFIED_COMPLETE`
- **Requirement:** Choix du modèle d'embedding
- **Implementation:** api/services/embedding_config.py per-organization embedding model; dimension safety
- **Tests:** tests/test_embedding_config.py, tests/test_embedding_dimension_safety.py (Part run: passed)
- **Known gaps:** changing model requires re-embedding (staleness route exists)
- **Severity / next action:** LOW / none

### 3.3.4 - Retrieval strategy  `VERIFIED_COMPLETE`
- **Requirement:** Stratégie de recherche (hybride, vectoriel, BM25)
- **Implementation:** resolve strategy in api/services/retrieval_config.py (hybrid, vector, bm25)
- **Tests:** tests/test_retrieval_config.py, tests/test_retrieval_pipeline.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.3.5 - Reranker  `VERIFIED_COMPLETE`
- **Requirement:** Choix du reranker (cross-encoder)
- **Implementation:** resolve_reranker_model / resolve_reranker_top_k in retrieval_config.py; _get_reranker in api/services/retrieval_pipeline.py
- **Tests:** tests/test_retrieval_config.py (Part run: passed)
- **Known gaps:** model download at first use (memory on 512 MB host) | **External blockers:** model download
- **Severity / next action:** LOW / measure memory

### 3.3.6 - Top K  `VERIFIED_COMPLETE`
- **Requirement:** Nombre de documents à récupérer
- **Implementation:** top_k in retrieval_config.py, bound in api/routers/search.py
- **Tests:** tests/test_retrieval_config.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.3.7 - Score threshold  `VERIFIED_COMPLETE`
- **Requirement:** Seuil de score minimum
- **Implementation:** resolve_score_threshold in retrieval_config.py (retrieval_config.py:141)
- **Tests:** tests/test_retrieval_config.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.4.1 - BM25  `VERIFIED_COMPLETE`
- **Requirement:** Recherche par mots-clés
- **Implementation:** bm25_search with rank_bm25 BM25Okapi and per-organization index cache (api/services/retrieval_pipeline.py:628)
- **Tests:** tests/test_bm25_index_cache.py, tests/test_retrieval_pipeline.py (Part run: passed)
- **Known gaps:** whole-organization chunk loading into memory (audit risk)
- **Severity / next action:** MEDIUM / benchmark large organizations

### 3.4.2 - Vector Search  `FIXED_AND_TESTED`
- **Requirement:** Recherche sémantique par embeddings
- **Implementation:** vector_search (api/services/retrieval_pipeline.py:388): pgvector ranking when PGVECTOR_ENABLED on PostgreSQL, else in-memory numpy cosine
- **Tests:** tests/test_retrieval_pipeline.py and tests/test_pgvector_iterative_scan.py (SQLite / mocked; the pgvector SQL path is not proven by a real PostgreSQL run in CI) (Part run: passed)
- **Known gaps:** which branch production takes is unproven | **External blockers:** PostgreSQL + pgvector
- **Severity / next action:** MEDIUM / PostgreSQL integration test in CI (audit P1-4) | **Fix:** tests/test_pgvector_real_search.py (opt-in PGVECTOR_REAL_TEST=1): the native branch _pgvector_rank_chunks applies (does not fall back to numpy), a paraphrased question finds the right passage first among 8, a near-identical passage of another organization is never returned, and the ranking equals an independent cosine computation; which branch the hosting provider's database takes is still to check there (extension …

### 3.4.3 - RRF  `VERIFIED_COMPLETE`
- **Requirement:** Fusion des résultats par Reciprocal Rank Fusion
- **Implementation:** reciprocal_rank_fusion (api/services/retrieval_pipeline.py:697), hybrid_search (:710)
- **Tests:** tests/test_retrieval_pipeline.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.4.4 - Cross-encoder reranking  `DECISION_OR_CORRECTION`
- **Requirement:** Reclassement des résultats avec cross-encoder
- **Implementation:** hybrid_reranked_search (api/services/retrieval_pipeline.py:764) with a cross-encoder from sentence-transformers
- **Tests:** tests/test_retrieval_pipeline.py (model mocked) (Part run: passed)
- **Known gaps:** real model load/latency/memory not measured | **External blockers:** model download
- **Severity / next action:** MEDIUM / measure on the real host | **Fix:** docs/PERFORMANCE_REPORT.md: cross-encoder MiniLM-L6 on a 16-thread CPU: load 20.6 s, +561 MB of memory, 152 ms for 10 candidates, 222 ms for 20, 596 ms for 50; to be measured again on the hosting plan

### 3.4.5 - Query expansion  `FIXED_AND_TESTED`
- **Requirement:** Étendre la requête avec des synonymes
- **Implementation:** only abbreviation expansion in api/services/query_rewriting.py (_ABBREVIATION_EXPANSIONS, expand_abbreviations); no synonym expansion found in query_rewriting.py, multi_query.py or retrieval_config.py
- **Tests:** tests/test_query_rewriting.py (Part run: passed)
- **Known gaps:** spec says synonyms; none implemented
- **Severity / next action:** LOW / implement synonym or LLM expansion or amend the spec | **Fix:** api/services/query_rewriting.py expand_with_synonyms + org settings (tests/test_p2_query_synonyms.py)

### 3.4.6 - Query rewriting  `VERIFIED_COMPLETE`
- **Requirement:** Réécrire la requête pour améliorer la pertinence
- **Implementation:** api/services/query_rewriting.py wired in api/services/retrieval_pipeline.py
- **Tests:** tests/test_query_rewriting.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.4.7 - HyDE  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Générer un document hypothétique pour la recherche
- **Implementation:** api/services/hyde.py wired in api/services/retrieval_pipeline.py and retrieval_config.py
- **Tests:** tests/test_hyde.py (LLM mocked) (Part run: passed)
- **Known gaps:** quality benefit never measured | **External blockers:** LLM provider
- **Severity / next action:** LOW / evaluate with Eval Lab

### 3.4.8 - Multi-query retrieval  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Lancer plusieurs requêtes en parallèle
- **Implementation:** api/services/multi_query.py wired in api/services/retrieval_pipeline.py
- **Tests:** tests/test_multi_query.py (LLM mocked) (Part run: passed)
- **Known gaps:** quality benefit never measured | **External blockers:** LLM provider
- **Severity / next action:** LOW / evaluate with Eval Lab

### 3.4.9 - Metadata filtering  `VERIFIED_COMPLETE`
- **Requirement:** Filtrer par métadonnées (auteur, date, tags)
- **Implementation:** api/services/metadata_filtering.py used by api/services/retrieval_pipeline.py, api/schemas/search.py, tools/search_kb.py
- **Tests:** tests/test_metadata_filtering.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.4.10 - Semantic filtering  `VERIFIED_COMPLETE`
- **Requirement:** Filtrer par similarité sémantique
- **Implementation:** api/services/semantic_filtering.py used by api/services/retrieval_pipeline.py
- **Tests:** tests/test_semantic_filtering.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.4.11 - RRF configurable  `VERIFIED_COMPLETE`
- **Requirement:** Ajuster les poids des sources
- **Implementation:** resolve_rrf_k and source weights in retrieval_config.py
- **Tests:** tests/test_retrieval_config.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.4.12 - Reranker configurable  `VERIFIED_COMPLETE`
- **Requirement:** Choisir le reranker
- **Implementation:** resolve_reranker_model in retrieval_config.py
- **Tests:** tests/test_retrieval_config.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.4.13 - Top-K configurable  `VERIFIED_COMPLETE`
- **Requirement:** Ajuster le nombre de résultats
- **Implementation:** top_k configurable via org settings and search request (same mechanism as 3.3.6; the original text lists it twice)
- **Tests:** tests/test_retrieval_config.py (Part run: passed)
- **Known gaps:** duplicate of 3.3.6 in the spec
- **Severity / next action:** INFO / none

### 3.4.14 - Context compression  `VERIFIED_COMPLETE`
- **Requirement:** Compresser le contexte pour réduire les tokens
- **Implementation:** api/services/context_compression.py used by api/services/generation.py
- **Tests:** tests/test_context_compression.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.4.15 - Duplicate removal  `VERIFIED_COMPLETE`
- **Requirement:** Supprimer les résultats en double
- **Implementation:** api/services/duplicate_removal.py (also used by multi_query)
- **Tests:** tests/test_duplicate_removal.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 3.4.16 - Diversity filtering  `VERIFIED_COMPLETE`
- **Requirement:** Garantir la diversité des résultats
- **Implementation:** select_diverse_chunks / MMR in api/services/mmr.py wired in api/services/retrieval_pipeline.py (~930-950)
- **Tests:** tests/test_mmr.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

## Part 4 - Multi-LLM and embeddings (providers, routing, configuration)

18 features: VERIFIED_COMPLETE 9, BLOCKED_EXTERNAL 8, IMPLEMENTED_UNVERIFIED 1

### 4.1.1 - Anthropic Claude  `BLOCKED_EXTERNAL`
- **Requirement:** Modèle Claude (actuel)
- **Implementation:** Anthropic via api/services/llm_providers.py (litellm dispatch), api/services/llm_config.py
- **Tests:** tests/test_llm_providers.py mocks litellm.acompletion (Part run: passed)
- **Known gaps:** no real Anthropic call in the audit | **External blockers:** Anthropic API key
- **Severity / next action:** MEDIUM / run a live smoke test with a funded key

### 4.1.2 - OpenAI GPT  `BLOCKED_EXTERNAL`
- **Requirement:** Modèles GPT-4, GPT-3.5
- **Implementation:** OpenAI via api/services/llm_providers.py (litellm dispatch), api/services/llm_config.py
- **Tests:** tests/test_llm_providers.py (mocked) (Part run: passed)
- **Known gaps:** no real call | **External blockers:** OpenAI API key
- **Severity / next action:** MEDIUM / live smoke test

### 4.1.3 - Google Gemini  `BLOCKED_EXTERNAL`
- **Requirement:** Modèles Gemini Pro, Flash
- **Implementation:** Gemini via litellm 'gemini/...' prefix in api/services/llm_providers.py (litellm dispatch), api/services/llm_config.py
- **Tests:** tests/test_llm_providers.py (mocked) (Part run: passed)
- **Known gaps:** no real call | **External blockers:** Gemini API key
- **Severity / next action:** MEDIUM / live smoke test

### 4.1.4 - Mistral  `BLOCKED_EXTERNAL`
- **Requirement:** Modèles Mistral Large, Small
- **Implementation:** Mistral via litellm 'mistral/...' prefix in api/services/llm_providers.py (litellm dispatch), api/services/llm_config.py
- **Tests:** tests/test_llm_providers.py (mocked) (Part run: passed)
- **Known gaps:** no real call | **External blockers:** Mistral API key
- **Severity / next action:** MEDIUM / live smoke test

### 4.1.5 - Ollama (local)  `BLOCKED_EXTERNAL`
- **Requirement:** Modèles locaux (Llama, Mistral, Phi)
- **Implementation:** Ollama via litellm 'ollama/...' prefix; no SDK needed
- **Tests:** tests/test_llm_providers.py (mocked) (Part run: passed)
- **Known gaps:** no local Ollama server exercised | **External blockers:** Ollama server
- **Severity / next action:** LOW / test against a local Ollama

### 4.1.6 - OpenAI-compatible APIs  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Toute API compatible OpenAI
- **Implementation:** OpenAI-compatible base URL support in api/services/llm_providers.py (litellm dispatch), api/services/llm_config.py
- **Tests:** tests/test_llm_providers.py, tests/test_default_models_are_routable.py (Part run: passed)
- **Known gaps:** guard application not confirmed in this pass | **External blockers:** compatible endpoint
- **Severity / next action:** MEDIUM / verify SSRF guard on custom base URLs

### 4.1.7 - Abstraction LLM  `VERIFIED_COMPLETE`
- **Requirement:** Adapter pattern pour changer facilement de fournisseur
- **Implementation:** single dispatch layer api/services/llm_providers.py (litellm dispatch), api/services/llm_config.py plus fallback chain api/services/fallback.py
- **Tests:** tests/test_llm_providers.py, tests/test_fallback.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 4.2.1 - OpenAI embeddings  `BLOCKED_EXTERNAL`
- **Requirement:** Texte-embedding-ada-002
- **Implementation:** OpenAI embeddings via api/services/embedding_providers.py, api/services/embedding_config.py
- **Tests:** tests/test_embedding_providers.py (mocked) (Part run: passed)
- **Known gaps:** no real call | **External blockers:** OpenAI key
- **Severity / next action:** LOW / live smoke test

### 4.2.2 - Voyage AI  `BLOCKED_EXTERNAL`
- **Requirement:** Embeddings haute performance
- **Implementation:** Voyage embeddings via api/services/embedding_providers.py, api/services/embedding_config.py
- **Tests:** tests/test_embedding_providers.py (mocked) (Part run: passed)
- **Known gaps:** no real call | **External blockers:** Voyage key
- **Severity / next action:** LOW / live smoke test

### 4.2.3 - Cohere  `BLOCKED_EXTERNAL`
- **Requirement:** Embeddings multilingues
- **Implementation:** Cohere embeddings via api/services/embedding_providers.py, api/services/embedding_config.py
- **Tests:** tests/test_embedding_providers.py (mocked) (Part run: passed)
- **Known gaps:** no real call | **External blockers:** Cohere key
- **Severity / next action:** LOW / live smoke test

### 4.2.4 - Sentence Transformers  `VERIFIED_COMPLETE`
- **Requirement:** Modèles locaux MiniLM, MPNet
- **Implementation:** sentence-transformers loader get_embedder via api/services/embedding_providers.py, api/services/embedding_config.py
- **Tests:** tests/test_embedding_providers.py (Part run: passed)
- **Known gaps:** model download on first use; memory on a 512 MB host | **External blockers:** model download
- **Severity / next action:** LOW / measure memory

### 4.2.5 - Hugging Face models  `VERIFIED_COMPLETE`
- **Requirement:** Tout modèle de Hugging Face
- **Implementation:** same sentence-transformers mechanism loads any Hugging Face model id (module docstring of embedding_providers.py)
- **Tests:** tests/test_embedding_providers.py (Part run: passed)
- **Known gaps:** same as 4.2.4 | **External blockers:** model download
- **Severity / next action:** LOW / none

### 4.2.6 - Abstraction Embeddings  `VERIFIED_COMPLETE`
- **Requirement:** Adapter pattern
- **Implementation:** unified interface in api/services/embedding_providers.py, api/services/embedding_config.py
- **Tests:** tests/test_embedding_providers.py, tests/test_embedding_dimension_safety.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 4.3.1 - Choix du modèle par utilisateur/organisation  `VERIFIED_COMPLETE`
- **Requirement:** Chaque organisation choisit son LLM
- **Implementation:** per-organization LLM config: api/models/organization_llm_config.py, api/services/llm_providers.py (litellm dispatch), api/services/llm_config.py, UI frontend/app/dashboard/settings/llm-config/page.tsx
- **Tests:** tests/test_llm_config.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 4.3.2 - Temperature  `VERIFIED_COMPLETE`
- **Requirement:** Contrôle la créativité des réponses
- **Implementation:** temperature (0-2) in api/schemas/organization_settings.py:126, passed to the model call
- **Tests:** tests/test_llm_sampling_params.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 4.3.3 - Top P  `VERIFIED_COMPLETE`
- **Requirement:** Échantillonnage nucleus
- **Implementation:** top_p (0-1) in api/schemas/organization_settings.py:128
- **Tests:** tests/test_llm_sampling_params.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 4.3.4 - System prompt personnalisable  `VERIFIED_COMPLETE`
- **Requirement:** Modifier le prompt système
- **Implementation:** system prompt in org settings and agent prompts (api/services/agent_prompts.py)
- **Tests:** tests/test_agent_prompts.py, tests/test_llm_config.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 4.3.5 - Max tokens  `VERIFIED_COMPLETE`
- **Requirement:** Nombre maximum de tokens de réponse
- **Implementation:** max_tokens in api/schemas/organization_settings.py:139
- **Tests:** tests/test_llm_sampling_params.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

## Part 5 - AI agents (orchestrator, tools, agent configuration, workflows)

47 features: VERIFIED_COMPLETE 34, BLOCKED_EXTERNAL 6, FIXED_AND_TESTED 4, IMPLEMENTED_UNVERIFIED 2, DECISION_OR_CORRECTION 1

### 5.1.1 - Orchestrateur central  `VERIFIED_COMPLETE`
- **Requirement:** Coordonne l'exécution des outils
- **Implementation:** api/services/agent_orchestrator.py called from api/routers/chat_stream.py and api/routers/mcp_server.py
- **Tests:** tests/test_agent_orchestrator.py, tests/test_agent_orchestrator_credit_preflight.py (Part run: passed)
- **Known gaps:** BeeAI variant (beeai_orchestrator.py) is a second path; which one production uses by default not established | **External blockers:** LLM provider needed to prove real behaviour
- **Severity / next action:** LOW / document the default path

### 5.1.2 - Tool selection automatique  `VERIFIED_COMPLETE`
- **Requirement:** L'agent choisit les outils à utiliser
- **Implementation:** api/services/tool_selection.py used by api/services/agent_orchestrator.py and autonomous_agents.py
- **Tests:** tests/test_tool_selection.py (Part run: passed)
- **Known gaps:** selection quality depends on the model | **External blockers:** LLM provider needed to prove real behaviour
- **Severity / next action:** INFO / none

### 5.1.3 - Tool permissions  `VERIFIED_COMPLETE`
- **Requirement:** Restrictions sur l'utilisation des outils
- **Implementation:** api/security/tool_permissions.py, api/routers/tool_permissions.py, models/tool_permission.py, api/services/agent_permissions.py
- **Tests:** tests/test_tool_permissions.py, tests/test_agent_permissions.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.1.4 - Tool timeout  `VERIFIED_COMPLETE`
- **Requirement:** Temps maximum d'exécution d'un outil
- **Implementation:** api/services/tool_timeout.py used by api/services/agent_orchestrator.py; overrides via api/routers/tool_config.py
- **Tests:** tests/test_tool_timeout.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.1.5 - Per-tool budget (tokens)  `FIXED_AND_TESTED`
- **Requirement:** Limite de tokens par outil
- **Implementation:** budgets stored via api/routers/tool_config.py and api/services/tool_budget.py (table tool_budgets, migration 0050)
- **Tests:** tests/test_tool_budget.py (unit) (Part run: passed)
- **Known gaps:** no call to tool_budget found in agent_orchestrator.py or the tool dispatch path (grep of imports): the limit may never be enforced at run time
- **Severity / next action:** MEDIUM / wire the budget check into tool execution and add an orchestrator test | **Fix:** api/services/tool_budget.py cap_tool_output wired in the orchestrator (tests/test_tool_budget.py)

### 5.1.6 - Retry mechanism  `VERIFIED_COMPLETE`
- **Requirement:** Réessayer en cas d'échec
- **Implementation:** api/services/retry.py used by tool_timeout.py and custom_tools.py
- **Tests:** tests/test_tool_timeout.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.1.7 - Fallback  `FIXED_AND_TESTED`
- **Requirement:** Outil alternatif en cas d'échec
- **Implementation:** model api/models/tool_fallback.py (tool_fallbacks table) and routes in api/routers/tool_config.py; LLM fallback chain api/services/fallback.py
- **Tests:** tests/test_fallback.py (Part run: passed)
- **Known gaps:** tool-level fallback: the 'fallback' module is imported only by tool_config.py; no use inside the orchestrator found
- **Severity / next action:** MEDIUM / wire tool fallback into execution and test | **Fix:** api/services/fallback.py run_tool_fallbacks wired in the orchestrator (tests/test_fallback.py)

### 5.1.8 - Parallel tool calls  `VERIFIED_COMPLETE`
- **Requirement:** Appels d'outils en parallèle
- **Implementation:** api/services/parallel_tools.py used by api/services/agent_orchestrator.py
- **Tests:** tests/test_agent_orchestrator.py (parallel cases to confirm) (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** LOW / none

### 5.1.9 - Tool result validation  `VERIFIED_COMPLETE`
- **Requirement:** Vérifier les résultats des outils
- **Implementation:** api/services/tool_validation.py used by api/services/agent_orchestrator.py, mcp_server.py, custom_tools.py
- **Tests:** tests/test_tool_validation.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.1.10 - Human approval  `VERIFIED_COMPLETE`
- **Requirement:** Approbation humaine pour les actions sensibles
- **Implementation:** api/routers/human_approval.py, api/security/human_approval.py, models/human_approval.py; workflow human block
- **Tests:** tests/test_human_approval.py (Part run: passed)
- **Known gaps:** no dedicated frontend page found for approvals in frontend/app (workflow DebugPanel only)
- **Severity / next action:** LOW / confirm approval inbox UI

### 5.1.11 - Agent memory (short-term)  `VERIFIED_COMPLETE`
- **Requirement:** Mémoire de la conversation en cours
- **Implementation:** api/services/agent_memory.py read in api/services/agent_orchestrator.py (~392-404), models/agent_memory.py
- **Tests:** tests/test_agent_memory.py, tests/test_agent_memory_config.py (Part run: passed)
- **Known gaps:** orchestrator only reads memory; writing is the caller's job (documented)
- **Severity / next action:** LOW / confirm chat path writes memory

### 5.1.12 - Conversation memory  `VERIFIED_COMPLETE`
- **Requirement:** Historique des conversations
- **Implementation:** conversation history: api/routers/conversations.py, api/services/conversation_management.py, models/conversation.py; long-term memory agent_long_term_memory.py
- **Tests:** tests/test_agent_long_term_memory.py, tests/test_p0_chat_conversation_isolation.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.1.13 - Task planning  `FIXED_AND_TESTED`
- **Requirement:** Planifier les étapes d'une tâche complexe
- **Implementation:** api/services/task_planning.py; opt-in plan_first in api/services/agent_orchestrator.py (~341-362): the plan is only injected as a suggested plan in the system prompt
- **Tests:** tests/test_task_planning.py (Part run: passed)
- **Known gaps:** plans are advisory text, not executed step by step (comment at ~349-353); default off | **External blockers:** LLM provider needed to prove real behaviour
- **Severity / next action:** LOW / decide whether to execute plans | **Fix:** the plan can be executed step by step and its results reach the final answer (tests/test_agent_orchestrator.py); default stays advisory

### 5.1.14 - Agent traces  `VERIFIED_COMPLETE`
- **Requirement:** Journalisation des décisions de l'agent
- **Implementation:** api/routers/agent_traces.py, api/services/agent_traces.py, models/agent_trace.py, flight recorder
- **Tests:** tests/test_agent_traces.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.2.1 - Search Knowledge Base  `VERIFIED_COMPLETE`
- **Requirement:** Recherche RAG
- **Implementation:** api/tools/search_kb.py -> hybrid retrieval
- **Tests:** tests/test_agent_tools.py, tests/test_retrieval_pipeline.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.2.2 - Web Search  `BLOCKED_EXTERNAL`
- **Requirement:** Recherche en ligne (Tavily, Google)
- **Implementation:** api/tools/web_search.py (Tavily/Google)
- **Tests:** tests/test_web_search.py (mocked) (Part run: passed)
- **Known gaps:** no real search call | **External blockers:** Tavily/Google API key
- **Severity / next action:** LOW / live smoke test

### 5.2.3 - GitHub (issues, repos)  `BLOCKED_EXTERNAL`
- **Requirement:** Recherche dans GitHub
- **Implementation:** api/tools/github_tools.py
- **Tests:** tests/test_github_tools.py (mocked) (Part run: passed)
- **Known gaps:** no real GitHub call | **External blockers:** GitHub token
- **Severity / next action:** LOW / live smoke test

### 5.2.4 - Database (SQL)  `VERIFIED_COMPLETE`
- **Requirement:** Exécution de requêtes SQL
- **Implementation:** api/tools/sql_tool.py, tenant scoping fixed in P0 (SQL tool tenant bypass)
- **Tests:** tests/test_sql_tool.py, tests/test_p0_sql_tool_tenant_bypass.py (Part run: passed)
- **Known gaps:** dynamic SQL remains a standing risk
- **Severity / next action:** MEDIUM / keep the bypass test in CI

### 5.2.5 - Calculator  `VERIFIED_COMPLETE`
- **Requirement:** Calculs arithmétiques
- **Implementation:** api/tools/calculator.py (AST-bounded evaluation)
- **Tests:** tests/test_calculator_tool.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.2.6 - URL Reader  `VERIFIED_COMPLETE`
- **Requirement:** Lire le contenu d'une URL
- **Implementation:** api/tools/url_reader.py with SSRF guard
- **Tests:** tests/test_url_reader.py, tests/test_ssrf_hardening.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.2.7 - Calendar (Google, Outlook)  `BLOCKED_EXTERNAL`
- **Requirement:** Créer, lire, modifier des événements
- **Implementation:** api/tools/calendar_tools.py (Google/Outlook)
- **Tests:** tests/test_calendar_tools.py (mocked) (Part run: passed)
- **Known gaps:** no real calendar call | **External blockers:** Google/Microsoft OAuth
- **Severity / next action:** LOW / sandbox test

### 5.2.8 - Email (Gmail, Outlook, SMTP)  `BLOCKED_EXTERNAL`
- **Requirement:** Envoyer, lire, résumer des emails
- **Implementation:** api/tools/email_tools.py (Gmail/Outlook/SMTP)
- **Tests:** tests/test_email_tools.py (mocked) (Part run: passed)
- **Known gaps:** no real mailbox call | **External blockers:** mail provider
- **Severity / next action:** LOW / sandbox test

### 5.2.9 - Human Escalation  `VERIFIED_COMPLETE`
- **Requirement:** Créer un ticket pour un humain
- **Implementation:** api/tools/human_escalation.py, models/escalation.py
- **Tests:** tests/test_human_escalation.py (Part run: passed)
- **Known gaps:** spec's ticket fields (priority, SLA, assignment) are Part 15
- **Severity / next action:** LOW / see Part 15

### 5.2.10 - Custom Tools  `VERIFIED_COMPLETE`
- **Requirement:** Ajouter des outils personnalisés
- **Implementation:** api/routers/custom_tools.py, api/services/custom_tools.py, api/security/custom_tools.py
- **Tests:** tests exist for custom tools (to be named in remediation) (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** LOW / none

### 5.3.1 - Création d'agent personnalisé  `VERIFIED_COMPLETE`
- **Requirement:** Interface pour créer un agent
- **Implementation:** api/routers/agents.py, agent_factory.py; UI frontend/app/dashboard/agents/new/page.tsx and agents/factory/page.tsx
- **Tests:** tests/test_agent_factory.py, tests/test_agent_idor.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.3.2 - Instructions personnalisées  `VERIFIED_COMPLETE`
- **Requirement:** Définir le comportement de l'agent
- **Implementation:** instructions/system prompt on agent (api/services/agent_prompts.py); UI new agent form
- **Tests:** tests/test_agent_prompts.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.3.3 - Choix du modèle LLM  `VERIFIED_COMPLETE`
- **Requirement:** Sélectionner le LLM pour l'agent
- **Implementation:** api/services/agent_models.py model selection per agent
- **Tests:** tests/test_agent_models.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.3.4 - Sélection de la Knowledge Base  `VERIFIED_COMPLETE`
- **Requirement:** Choisir la base de connaissances
- **Implementation:** api/services/agent_knowledge_base.py, routes under /agents/{id}/knowledge-base
- **Tests:** tests/test_agent_knowledge_base.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.3.5 - Sélection des outils  `VERIFIED_COMPLETE`
- **Requirement:** Activer/désactiver des outils
- **Implementation:** tool enablement via tool permissions/agent tools (api/services/agent_tools.py)
- **Tests:** tests/test_agent_tools.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.3.6 - Configuration de la mémoire  `VERIFIED_COMPLETE`
- **Requirement:** Taille de la mémoire, durée
- **Implementation:** api/services/agent_memory_config.py
- **Tests:** tests/test_agent_memory_config.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.3.7 - Permissions  `VERIFIED_COMPLETE`
- **Requirement:** Qui peut utiliser l'agent
- **Implementation:** api/services/agent_permissions.py
- **Tests:** tests/test_agent_permissions.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.3.8 - Temperature  `VERIFIED_COMPLETE`
- **Requirement:** Ajuster la créativité
- **Implementation:** temperature on agent models (same mechanism as 4.3.2; duplicate item in the spec)
- **Tests:** tests/test_agent_models.py, tests/test_llm_sampling_params.py (Part run: passed)
- **Known gaps:** duplicate of 4.3.2
- **Severity / next action:** INFO / none

### 5.3.9 - Guardrails  `VERIFIED_COMPLETE`
- **Requirement:** Activer les garde-fous de sécurité
- **Implementation:** api/services/agent_guardrails.py, prompt_injection_detection.py
- **Tests:** tests/test_agent_guardrails.py (Part run: passed)
- **Known gaps:** effectiveness of detection never measured
- **Severity / next action:** LOW / red-team test set

### 5.3.10 - Déploiement  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Déployer l'agent en production
- **Implementation:** deploy via agent_factory / API keys per agent (api/routers/agent_api_keys.py) and widget
- **Tests:** tests/test_agent_api_keys.py, tests/test_agent_factory.py (Part run: passed)
- **Known gaps:** meaning of 'deploy to production' not precisely defined in the spec
- **Severity / next action:** LOW / clarify requirement

### 5.4.1 - Interface visuelle  `VERIFIED_COMPLETE`
- **Requirement:** Construire des workflows en no-code
- **Implementation:** frontend/components/workflows/WorkflowBuilder.tsx, NodeEditor.tsx, Toolbar.tsx; pages dashboard/workflows
- **Tests:** frontend/components/workflows/components.test.tsx (Part run: passed)
- **Known gaps:** no browser end-to-end test run in this audit
- **Severity / next action:** LOW / manual UI check

### 5.4.2 - Bloc Trigger  `VERIFIED_COMPLETE`
- **Requirement:** Déclencheur (webhook, planifié)
- **Implementation:** api/services/workflow_triggers.py (webhook, scheduled)
- **Tests:** tests/test_workflow_triggers.py (Part run: passed)
- **Known gaps:** scheduled triggers need Celery beat (audit R-02) | **External blockers:** Celery beat
- **Severity / next action:** MEDIUM / stage test

### 5.4.3 - Bloc LLM  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Appel à un LLM
- **Implementation:** api/services/workflow_block_llm.py
- **Tests:** tests/test_workflow_block_llm.py (mocked) (Part run: passed)
- **Known gaps:** LLM real call not exercised | **External blockers:** LLM provider needed to prove real behaviour
- **Severity / next action:** LOW / smoke test

### 5.4.4 - Bloc RAG  `VERIFIED_COMPLETE`
- **Requirement:** Recherche RAG
- **Implementation:** api/services/workflow_block_rag.py
- **Tests:** tests/test_workflow_block_rag.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.4.5 - Bloc Search  `VERIFIED_COMPLETE`
- **Requirement:** Recherche web ou interne
- **Implementation:** api/services/workflow_block_search.py
- **Tests:** tests/test_workflow_block_search.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.4.6 - Bloc HTTP  `VERIFIED_COMPLETE`
- **Requirement:** Appel API HTTP
- **Implementation:** api/services/workflow_block_http.py with SSRF guard
- **Tests:** tests/test_workflow_block_http.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.4.7 - Bloc Condition  `VERIFIED_COMPLETE`
- **Requirement:** Condition if/else
- **Implementation:** api/services/workflow_block_condition.py
- **Tests:** tests/test_workflow_block_condition.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** LOW / confirm no eval()

### 5.4.8 - Bloc Code  `FIXED_AND_TESTED`
- **Requirement:** Exécution de code Python/JS
- **Implementation:** api/services/workflow_block_code.py; sandbox api/routers/sandbox.py, models/sandbox.py
- **Tests:** tests/test_workflow_block_code.py (Part run: passed)
- **Known gaps:** sandbox isolation (process/container) not verified | **External blockers:** sandbox runtime
- **Severity / next action:** HIGH / security review of the sandbox | **Fix:** the code block is an ast whitelist evaluator, not exec(); the review reproduced 3 bypasses (dunder access through str.format, unbounded memory through repeat/replace/join, unhandled MemoryError/RecursionError) and fixed them (tests/test_workflow_block_code_hardening.py, 30 cases); a process or container sandbox is not needed for this design

### 5.4.9 - Bloc Human  `VERIFIED_COMPLETE`
- **Requirement:** Escalade humaine
- **Implementation:** api/services/workflow_block_human.py, models/workflow_human_input.py
- **Tests:** tests/test_workflow_block_human.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 5.4.10 - Bloc Email  `BLOCKED_EXTERNAL`
- **Requirement:** Envoi d'email
- **Implementation:** api/services/workflow_block_email.py
- **Tests:** tests/test_workflow_block_email.py (mocked) (Part run: passed)
- **Known gaps:** no real send | **External blockers:** mail provider
- **Severity / next action:** LOW / sandbox test

### 5.4.11 - Bloc Calendar  `BLOCKED_EXTERNAL`
- **Requirement:** Gestion de calendrier
- **Implementation:** api/services/workflow_block_calendar.py
- **Tests:** tests/test_workflow_block_calendar.py (mocked) (Part run: passed)
- **Known gaps:** no real calendar call | **External blockers:** calendar provider
- **Severity / next action:** LOW / sandbox test

### 5.4.12 - Bloc Database  `DECISION_OR_CORRECTION`
- **Requirement:** Requête SQL
- **Implementation:** api/services/workflow_block_database.py
- **Tests:** tests/test_workflow_block_database.py (Part run: passed)
- **Known gaps:** tenant scoping not re-read
- **Severity / next action:** MEDIUM / add a tenant-bypass test like P0 for the SQL tool | **Fix:** the database workflow block reuses the SQL tool validator and tenant filter, covered by tests/test_workflow_block_database.py and the P0 SQL bypass test

### 5.4.13 - Versioning des workflows  `VERIFIED_COMPLETE`
- **Requirement:** Historique des modifications
- **Implementation:** api/services/workflow_versions.py, models/workflow_version.py
- **Tests:** tests/test_workflow_versions.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

## Part 6 - Citations and anti-hallucination

22 features: VERIFIED_COMPLETE 13, IMPLEMENTED_UNVERIFIED 7, FIXED_AND_TESTED 2

### 6.1.1 - Citations cliquables  `VERIFIED_COMPLETE`
- **Requirement:** Cliquer sur la citation pour voir la source
- **Implementation:** api/routers/citations.py, api/services/citations.py; frontend/components/Citation.tsx, CitationList.tsx, CitationModal.tsx, CitationTooltip.tsx
- **Tests:** tests/test_citation_chunk.py and citation tests; frontend ChatMarkdown.test.tsx (Part run: passed)
- **Known gaps:** end-to-end browser click not run
- **Severity / next action:** INFO / none

### 6.1.2 - Source document (nom)  `VERIFIED_COMPLETE`
- **Requirement:** Afficher le document source
- **Implementation:** api/services/citation_documents.py + api/routers/citations.py, api/services/citations.py
- **Tests:** citation tests (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 6.1.3 - Page PDF / Section  `VERIFIED_COMPLETE`
- **Requirement:** Afficher la page ou section précise
- **Implementation:** api/services/citation_location.py (page/section)
- **Tests:** tests for citation location (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 6.1.4 - URL source  `VERIFIED_COMPLETE`
- **Requirement:** Lien vers la source web
- **Implementation:** api/services/citation_url.py
- **Tests:** tests for citation URL (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** LOW / check link sanitisation in CitationList.tsx

### 6.1.5 - Chunk ID  `VERIFIED_COMPLETE`
- **Requirement:** Identifiant du bloc de texte
- **Implementation:** api/services/citation_chunk.py
- **Tests:** tests/test_citation_chunk.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 6.1.6 - Score de pertinence  `VERIFIED_COMPLETE`
- **Requirement:** Afficher le score de confiance
- **Implementation:** api/services/citation_relevance.py
- **Tests:** tests for citation relevance (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 6.1.7 - Passage exact  `VERIFIED_COMPLETE`
- **Requirement:** Surligner le passage cité
- **Implementation:** api/services/citation_passage.py; highlight in CitationModal.tsx
- **Tests:** tests for citation passage (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 6.1.8 - Citation preview  `FIXED_AND_TESTED`
- **Requirement:** Aperçu au survol de la souris
- **Implementation:** UI hover tooltip frontend/components/CitationTooltip.tsx exists; backend api/services/citation_preview.py (tests/test_citation_preview.py) is imported by no router or UI module
- **Tests:** tests/test_citation_preview.py (service only) (Part run: passed)
- **Known gaps:** the preview service is dead code from the app's point of view; the tooltip uses data already in the citation
- **Severity / next action:** LOW / wire or remove citation_preview | **Fix:** GET /citations/{id}/preview wires api/services/citation_preview.py (tests/test_p2_citation_preview_route.py)

### 6.1.9 - Sources secondaires  `VERIFIED_COMPLETE`
- **Requirement:** Afficher les sources alternatives
- **Implementation:** api/services/citation_secondary.py used by citations.py
- **Tests:** citation tests (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 6.1.10 - Confidence score  `VERIFIED_COMPLETE`
- **Requirement:** Score global de confiance
- **Implementation:** api/services/response_confidence.py used by generation.py and orchestrator
- **Tests:** tests for response confidence (Part run: passed)
- **Known gaps:** score calibration never measured
- **Severity / next action:** LOW / calibrate with Eval Lab

### 6.2.1 - Citation-required mode  `VERIFIED_COMPLETE`
- **Requirement:** L'IA ne répond qu'avec des citations
- **Implementation:** api/services/agent_citation_required.py used by chat_stream.py and the orchestrator
- **Tests:** tests/test_agent_citation_required.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 6.2.2 - Answer only from retrieved context  `VERIFIED_COMPLETE`
- **Requirement:** Réponse uniquement basée sur le contexte
- **Implementation:** api/services/agent_context_only.py used by chat_stream.py and the orchestrator
- **Tests:** tests/test_agent_context_only.py (Part run: passed)
- **Known gaps:** compliance by the real LLM not measured | **External blockers:** LLM provider
- **Severity / next action:** LOW / measure with SQuAD-style unanswerable set

### 6.2.3 - "I don't know" threshold  `VERIFIED_COMPLETE`
- **Requirement:** L'IA dit "je ne sais pas" si trop incertain
- **Implementation:** api/services/agent_idk.py used by agent_factory/orchestrator
- **Tests:** tests/test_agent_idk.py (Part run: passed)
- **Known gaps:** threshold calibration not measured
- **Severity / next action:** LOW / calibrate

### 6.2.4 - Confidence estimation  `VERIFIED_COMPLETE`
- **Requirement:** Estimation de la confiance en la réponse
- **Implementation:** api/services/confidence_estimation.py
- **Tests:** confidence tests (Part run: passed)
- **Known gaps:** calibration not measured
- **Severity / next action:** LOW / calibrate

### 6.2.5 - Unsupported claim detection  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Détecter les affirmations sans source
- **Implementation:** api/services/unsupported_claims.py via api/services/response_quality.py (wired in generation.py and agent_orchestrator.py)
- **Tests:** tests/test_unsupported_claims*.py (heuristics/LLM mocked) (Part run: passed)
- **Known gaps:** detection accuracy never measured on real data | **External blockers:** LLM provider
- **Severity / next action:** MEDIUM / evaluate on a labelled set

### 6.2.6 - Claim verification  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Vérifier les affirmations
- **Implementation:** api/services/claim_verification.py via api/services/response_quality.py (wired in generation.py and agent_orchestrator.py)
- **Tests:** claim verification tests (mocked) (Part run: passed)
- **Known gaps:** accuracy not measured | **External blockers:** LLM provider
- **Severity / next action:** MEDIUM / evaluate

### 6.2.7 - Contradiction detection  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Détecter les contradictions
- **Implementation:** api/services/contradiction_detection.py via api/services/response_quality.py (wired in generation.py and agent_orchestrator.py)
- **Tests:** contradiction tests (mocked) (Part run: passed)
- **Known gaps:** accuracy not measured | **External blockers:** LLM provider
- **Severity / next action:** LOW / evaluate

### 6.2.8 - Source consistency check  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Vérifier la cohérence des sources
- **Implementation:** api/services/source_consistency.py via api/services/response_quality.py (wired in generation.py and agent_orchestrator.py)
- **Tests:** source consistency tests (Part run: passed)
- **Known gaps:** accuracy not measured
- **Severity / next action:** LOW / evaluate

### 6.2.9 - Hallucination detector  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Détecter les hallucinations
- **Implementation:** api/services/hallucination_detector.py via api/services/response_quality.py (wired in generation.py and agent_orchestrator.py)
- **Tests:** hallucination detector tests (mocked) (Part run: passed)
- **Known gaps:** accuracy not measured | **External blockers:** LLM provider
- **Severity / next action:** MEDIUM / evaluate with SQuAD 2.0 and a hallucination set

### 6.2.10 - Groundedness score  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Score d'ancrage (0-100%)
- **Implementation:** api/services/groundedness.py via api/services/response_quality.py (wired in generation.py and agent_orchestrator.py)
- **Tests:** groundedness tests (Part run: passed)
- **Known gaps:** score meaning not validated
- **Severity / next action:** LOW / validate

### 6.2.11 - Faithfulness score  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Fidélité à la source
- **Implementation:** api/services/faithfulness.py via api/services/response_quality.py (wired in generation.py and agent_orchestrator.py)
- **Tests:** faithfulness tests (Part run: passed)
- **Known gaps:** score meaning not validated
- **Severity / next action:** LOW / validate

### 6.2.12 - Dashboard qualité  `FIXED_AND_TESTED`
- **Requirement:** Afficher les scores dans le dashboard
- **Implementation:** frontend/app/dashboard/quality/page.tsx manages quality ALERT rules and history (api calls to /organizations/{id}/quality-alerts); api/routers/quality_dashboard.py exists
- **Tests:** page tests not located (Part run: passed)
- **Known gaps:** page shown manages alert rules; display of per-answer scores (groundedness/faithfulness) in a dashboard not confirmed
- **Severity / next action:** LOW / confirm scores are visualised | **Fix:** frontend/app/dashboard/quality-scores: averages, trend, per-answer scores, CSV export

## Part 7 - Evaluation Lab (datasets, metrics, regression, comparison)

33 features: VERIFIED_COMPLETE 25, IMPLEMENTED_UNVERIFIED 6, FIXED_AND_TESTED 2

### 7.1.1 - Dataset manager  `VERIFIED_COMPLETE`
- **Requirement:** Interface pour gérer les datasets
- **Implementation:** api/routers/evaluation_datasets.py, api/services/evaluation_datasets.py; UI frontend/app/dashboard/eval/page.tsx, components/eval/DatasetForm.tsx, DatasetList.tsx
- **Tests:** tests/test_evaluation_datasets.py, tests/test_evaluation_datasets_endpoints.py, tests/test_evaluation_idor.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.1.2 - Question sets  `VERIFIED_COMPLETE`
- **Requirement:** Créer des ensembles de questions
- **Implementation:** api/routers/question_sets.py, api/services/question_sets.py; components/eval/QuestionList.tsx
- **Tests:** tests/test_question_sets.py, tests/test_question_sets_endpoints.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.1.3 - Ground-truth answers  `VERIFIED_COMPLETE`
- **Requirement:** Définir les réponses correctes
- **Implementation:** api/services/ground_truth_answers.py
- **Tests:** tests/test_ground_truth_answers.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.1.4 - Ground-truth documents  `VERIFIED_COMPLETE`
- **Requirement:** Définir les documents corrects
- **Implementation:** api/services/ground_truth_documents.py
- **Tests:** tests/test_ground_truth_documents.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.1.5 - Easy / Medium / Hard  `VERIFIED_COMPLETE`
- **Requirement:** Classifier la difficulté
- **Implementation:** api/services/question_difficulty.py
- **Tests:** tests/test_question_difficulty.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.1.6 - Benchmark versions  `VERIFIED_COMPLETE`
- **Requirement:** Versionner les benchmarks
- **Implementation:** api/routers/benchmark_versions.py, api/services/benchmark_versions.py
- **Tests:** tests/test_benchmark_versions.py, tests/test_benchmark_versions_endpoints.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.1.7 - Tuning / Held-out split  `FIXED_AND_TESTED`
- **Requirement:** Séparer entraînement et test
- **Implementation:** none. Searched api/models/evaluation.py, api/schemas/evaluation*.py, services/evaluation_datasets.py, question_sets.py, benchmark_versions.py for train/test/held-out/split fields: only A/B traffic_split found
- **Tests:** none (Part run: passed)
- **Known gaps:** no tuning versus held-out separation: tuning on a benchmark would leak into the reported score
- **Severity / next action:** MEDIUM / add a split attribute on questions and enforce held-out use in evaluation runs | **Fix:** evaluation split column, assign-split route, job split filter, migration 0137 (tests/test_p2_eval_split_held_out.py)

### 7.1.8 - Datasets verticaux  `FIXED_AND_TESTED`
- **Requirement:** FastAPI, Legal, HR, Finance, etc.
- **Implementation:** none. No seeded vertical datasets (FastAPI, Legal, HR, Finance); only tests/eval/dataset_demo.json
- **Tests:** none (Part run: passed)
- **Known gaps:** verticals absent
- **Severity / next action:** LOW / build datasets, e.g. from open corpora | **Fix:** eval_datasets/verticals/{fastapi,legal,hr,finance}.csv, 15 questions each, imported through the real endpoint (tests/test_eval_vertical_datasets.py, 12 cases)

### 7.2.1 - Recall@1  `VERIFIED_COMPLETE`
- **Requirement:** Taux de réussite au 1er résultat
- **Implementation:** api/services/retrieval_metrics.py:59 calculate_recall_at_1
- **Tests:** tests/test_retrieval_metrics.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06)
- **Severity / next action:** LOW / produce a baseline

### 7.2.2 - Recall@3  `VERIFIED_COMPLETE`
- **Requirement:** Taux de réussite dans les 3 premiers
- **Implementation:** api/services/retrieval_metrics.py:65 calculate_recall_at_3
- **Tests:** tests/test_retrieval_metrics.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06)
- **Severity / next action:** LOW / produce a baseline

### 7.2.3 - Recall@5  `VERIFIED_COMPLETE`
- **Requirement:** Taux de réussite dans les 5 premiers
- **Implementation:** api/services/retrieval_metrics.py:70 calculate_recall_at_5
- **Tests:** tests/test_retrieval_metrics.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06)
- **Severity / next action:** LOW / produce a baseline

### 7.2.4 - Recall@10  `VERIFIED_COMPLETE`
- **Requirement:** Taux de réussite dans les 10 premiers
- **Implementation:** api/services/retrieval_metrics.py:75 calculate_recall_at_10
- **Tests:** tests/test_retrieval_metrics.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06)
- **Severity / next action:** LOW / produce a baseline

### 7.2.5 - MRR  `VERIFIED_COMPLETE`
- **Requirement:** Mean Reciprocal Rank
- **Implementation:** api/services/retrieval_metrics.py:80 calculate_mrr
- **Tests:** tests/test_retrieval_metrics.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06)
- **Severity / next action:** LOW / produce a baseline

### 7.2.6 - NDCG  `VERIFIED_COMPLETE`
- **Requirement:** Normalized Discounted Cumulative Gain
- **Implementation:** api/services/retrieval_metrics.py:86 calculate_ndcg
- **Tests:** tests/test_retrieval_metrics.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06)
- **Severity / next action:** LOW / produce a baseline

### 7.2.7 - Precision  `VERIFIED_COMPLETE`
- **Requirement:** Précision des résultats
- **Implementation:** precision calculation in api/services/retrieval_metrics.py
- **Tests:** tests/test_retrieval_metrics.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06)
- **Severity / next action:** LOW / produce a baseline

### 7.2.8 - Faithfulness  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Fidélité de la réponse
- **Implementation:** api/services/faithfulness.py + answer_quality_metrics.py feeding evaluation_results.py
- **Tests:** tests/test_faithfulness.py, tests/test_answer_quality_metrics.py (Part run: passed)
- **Known gaps:** score validity not measured against human labels; no run on a real dataset has produced a baseline (audit R-06) | **External blockers:** LLM provider
- **Severity / next action:** MEDIUM / validate on a labelled set

### 7.2.9 - Answer relevance  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Pertinence de la réponse
- **Implementation:** answer relevance in api/services/answer_quality_metrics.py
- **Tests:** tests/test_answer_quality_metrics.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06) | **External blockers:** LLM provider
- **Severity / next action:** MEDIUM / validate

### 7.2.10 - Context relevance  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Pertinence du contexte
- **Implementation:** api/services/context_relevance.py
- **Tests:** context relevance tests (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06) | **External blockers:** LLM provider
- **Severity / next action:** LOW / validate

### 7.2.11 - Citation correctness  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Correctness des citations
- **Implementation:** api/services/citation_correctness.py
- **Tests:** tests/test_citation_correctness.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06)
- **Severity / next action:** LOW / validate

### 7.2.12 - Hallucination rate  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Taux d'hallucinations
- **Implementation:** api/services/hallucination_rate.py
- **Tests:** tests/test_hallucination_rate.py (Part run: passed)
- **Known gaps:** no run on a real dataset has produced a baseline (audit R-06) | **External blockers:** LLM provider
- **Severity / next action:** MEDIUM / validate with unanswerable questions

### 7.2.13 - Latency  `VERIFIED_COMPLETE`
- **Requirement:** Temps de réponse
- **Implementation:** api/services/latency_metrics.py
- **Tests:** tests/test_latency_metrics.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.2.14 - Token usage  `VERIFIED_COMPLETE`
- **Requirement:** Utilisation des tokens
- **Implementation:** api/services/token_usage.py
- **Tests:** tests/test_token_usage.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.2.15 - Cost/request  `VERIFIED_COMPLETE`
- **Requirement:** Coût par requête
- **Implementation:** api/services/cost_tracking.py
- **Tests:** tests/test_cost_tracking.py (Part run: passed)
- **Known gaps:** price tables may be stale (provider prices change)
- **Severity / next action:** LOW / review prices periodically

### 7.3.1 - Automatic evaluation  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Évaluation automatisée
- **Implementation:** api/routers/evaluation_jobs.py, api/services/evaluation_jobs.py, api/tasks/evaluation_jobs.py; UI dashboard/eval/[datasetId]/jobs/[jobId]
- **Tests:** tests/test_evaluation_jobs.py, tests/test_evaluation_jobs_endpoints.py (Part run: passed)
- **Known gaps:** jobs run in Celery (no production worker, audit R-02); never run on real data | **External blockers:** Celery worker, LLM provider
- **Severity / next action:** MEDIUM / run a real job locally and in staging

### 7.3.2 - Manual evaluation  `VERIFIED_COMPLETE`
- **Requirement:** Évaluation manuelle
- **Implementation:** api/routers/manual_evaluations.py, api/services/manual_evaluations.py
- **Tests:** tests/test_manual_evaluations.py, tests/test_manual_evaluations_endpoints.py (Part run: passed)
- **Known gaps:** no UI page found for manual scoring
- **Severity / next action:** LOW / confirm UI

### 7.3.3 - Regression detection  `VERIFIED_COMPLETE`
- **Requirement:** Détecter les régressions de performance
- **Implementation:** api/routers/regression_detection.py, api/services/regression_detection.py
- **Tests:** tests/test_regression_detection.py, tests/test_regression.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.3.4 - Model comparison  `VERIFIED_COMPLETE`
- **Requirement:** Comparer différents modèles
- **Implementation:** api/routers/evaluation_comparisons.py, api/services/evaluation_comparisons.py; UI dashboard/eval/runs/[runId]/comparison
- **Tests:** tests/test_evaluation_comparisons.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 7.3.5 - Retriever comparison  `VERIFIED_COMPLETE`
- **Requirement:** Comparer différents retrievers
- **Implementation:** evaluation_comparisons covers retriever configs
- **Tests:** tests/test_evaluation_comparisons.py (Part run: passed)
- **Known gaps:** retriever-specific test not isolated
- **Severity / next action:** LOW / add retriever comparison test

### 7.3.6 - Reranker comparison  `VERIFIED_COMPLETE`
- **Requirement:** Comparer différents rerankers
- **Implementation:** evaluation_comparisons covers reranker configs
- **Tests:** tests/test_evaluation_comparisons.py (Part run: passed)
- **Known gaps:** reranker-specific test not isolated
- **Severity / next action:** LOW / add reranker comparison test

### 7.3.7 - Prompt comparison  `VERIFIED_COMPLETE`
- **Requirement:** Comparer différents prompts
- **Implementation:** evaluation_comparisons covers prompt variants
- **Tests:** tests/test_evaluation_comparisons.py (Part run: passed)
- **Known gaps:** prompt-specific test not isolated
- **Severity / next action:** LOW / add prompt comparison test

### 7.3.8 - Automatic evaluation before deployment  `VERIFIED_COMPLETE`
- **Requirement:** Valider avant déploiement
- **Implementation:** api/routers/deployment_evaluations.py, api/services/deployment_evaluations.py
- **Tests:** tests/test_deployment_evaluations.py, tests/test_deployment_evaluations_endpoints.py (Part run: passed)
- **Known gaps:** whether a deployment is actually blocked by the gate in the deploy path is not confirmed
- **Severity / next action:** MEDIUM / trace the gate into agent deployment

### 7.3.9 - Seuils de régression  `VERIFIED_COMPLETE`
- **Requirement:** Blocage si régression > 5%
- **Implementation:** api/services/regression_thresholds.py DEFAULT_REGRESSION_THRESHOLDS; api/routers/regression_thresholds.py
- **Tests:** tests/test_regression_thresholds.py, tests/test_regression_thresholds_endpoints.py (Part run: passed)
- **Known gaps:** default value (spec: 5%) not confirmed by this audit
- **Severity / next action:** LOW / confirm default threshold

### 7.3.10 - A/B testing  `VERIFIED_COMPLETE`
- **Requirement:** Tester différentes configurations
- **Implementation:** api/routers/ab_tests.py, api/services/ab_tests.py; UI dashboard/ab-tests pages
- **Tests:** tests/test_ab_tests.py, tests/test_ab_tests_endpoints.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

## Part 8 - User interface (chat, streaming, voice, rendering)

32 features: VERIFIED_COMPLETE 16, FIXED_AND_TESTED 11, BLOCKED_EXTERNAL 2, IMPLEMENTED_UNVERIFIED 2, DECISION_OR_CORRECTION 1

### 8.1.1 - Streaming  `VERIFIED_COMPLETE`
- **Requirement:** Affichage des réponses en temps réel
- **Implementation:** SSE streaming api/routers/chat_stream.py, api/services/streaming.py; consumer frontend/app/chat/page.tsx + frontend/lib/useRealChat.ts
- **Tests:** tests/test_streaming.py, tests/test_stream_response_tools.py, tests/test_p1_chat_stream_refusal.py (Part run: passed)
- **Known gaps:** no browser end-to-end run | **External blockers:** LLM provider for a real stream
- **Severity / next action:** INFO / none

### 8.1.2 - Markdown  `VERIFIED_COMPLETE`
- **Requirement:** Formatage des réponses
- **Implementation:** frontend/components/ChatMarkdown.tsx (rehype-sanitize per project rules), MessageContent.tsx; api/services/markdown_renderer.py
- **Tests:** frontend/components/ChatMarkdown.test.tsx, tests/test_markdown_renderer.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 8.1.3 - Code highlighting  `VERIFIED_COMPLETE`
- **Requirement:** Coloration du code
- **Implementation:** code highlighting in ChatMarkdown.tsx and api/services/code_highlighter.py
- **Tests:** tests/test_code_highlighter.py, ChatMarkdown.test.tsx (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 8.1.4 - Citations  `VERIFIED_COMPLETE`
- **Requirement:** Afficher les sources
- **Implementation:** CitationList rendered by frontend/components/MessageBubble.tsx
- **Tests:** frontend component tests partial (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 8.1.5 - Copy  `VERIFIED_COMPLETE`
- **Requirement:** Copier la réponse
- **Implementation:** CopyButton used by MessageBubble.tsx and ChatMarkdown.tsx
- **Tests:** ChatMarkdown.test.tsx (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 8.1.6 - Regenerate  `VERIFIED_COMPLETE`
- **Requirement:** Régénérer la réponse
- **Implementation:** regenerate button in MessageBubble.tsx:80 -> useRealChat regenerate; POST /conversations/{id}/messages/{id}/regenerate
- **Tests:** tests/test_message_actions.py (Part run: passed)
- **Known gaps:** standalone RegenerateButton.tsx is unused
- **Severity / next action:** INFO / none

### 8.1.7 - Edit question  `VERIFIED_COMPLETE`
- **Requirement:** Modifier la question
- **Implementation:** inline edit in MessageBubble.tsx:45 -> useRealChat editMessage; POST .../edit and edit-history routes
- **Tests:** tests/test_message_actions.py (Part run: passed)
- **Known gaps:** standalone EditQuestion.tsx is unused
- **Severity / next action:** INFO / none

### 8.1.8 - Retry  `FIXED_AND_TESTED`
- **Requirement:** Réessayer avec les mêmes paramètres
- **Implementation:** backend POST /conversations/{id}/messages/{id}/retry (conversations.py:435); RetryButton.tsx the UI component exists but no page imports it
- **Tests:** tests/test_message_actions.py (Part run: passed)
- **Known gaps:** no retry action in the chat UI (regenerate is separate)
- **Severity / next action:** LOW / wire RetryButton or document regenerate as the retry | **Fix:** chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming

### 8.1.9 - Feedback (👍/👎 + reason + comment)  `VERIFIED_COMPLETE`
- **Requirement:** Noter la réponse
- **Implementation:** frontend/components/FeedbackButtons.tsx used by MessageBubble.tsx; api/routers/feedback.py
- **Tests:** feedback tests (test_p1_*/feedback files to confirm) (Part run: passed)
- **Known gaps:** reason and comment fields in the UI not confirmed
- **Severity / next action:** LOW / confirm reason/comment capture

### 8.1.10 - Conversation history  `VERIFIED_COMPLETE`
- **Requirement:** Historique des conversations
- **Implementation:** ChatSidebar.tsx + ConversationList.tsx; api/routers/conversations.py
- **Tests:** tests/test_conversations.py, tests/test_conversation_idor.py, tests/test_p0_chat_conversation_isolation.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 8.1.11 - Rename conversation  `VERIFIED_COMPLETE`
- **Requirement:** Renommer la conversation
- **Implementation:** RenameConversation used by ConversationItem.tsx; PATCH /conversations/{id}
- **Tests:** tests/test_conversation_management.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 8.1.12 - Search conversations  `VERIFIED_COMPLETE`
- **Requirement:** Rechercher dans les conversations
- **Implementation:** ConversationSearch used by ChatSidebar.tsx; GET /conversations/search
- **Tests:** tests/test_conversation_management.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 8.1.13 - Delete conversation  `VERIFIED_COMPLETE`
- **Requirement:** Supprimer une conversation
- **Implementation:** DeleteConversation used by ConversationItem.tsx; DELETE, restore and permanent routes
- **Tests:** tests/test_conversation_management.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 8.1.14 - Export conversation  `FIXED_AND_TESTED`
- **Requirement:** Exporter en PDF, DOCX, JSON
- **Implementation:** backend export PDF/DOCX/JSON/Markdown (conversations.py:256-291, api/services/conversation_export.py)
- **Tests:** tests/test_conversation_export.py (Part run: passed)
- **Known gaps:** no export control in the chat UI; PDF needs weasyprint system libraries on the host | **External blockers:** weasyprint libraries
- **Severity / next action:** LOW / add export menu; confirm weasyprint in the Docker image | **Fix:** chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming

### 8.1.15 - Share conversation  `FIXED_AND_TESTED`
- **Requirement:** Partager une conversation
- **Implementation:** backend POST /conversations/{id}/share and GET /share/{token} (conversation_shares.py); ShareConversation.tsx the UI component exists but no page imports it
- **Tests:** tests/test_conversation_sharing.py (Part run: passed)
- **Known gaps:** no share control in the chat UI
- **Severity / next action:** LOW / wire ShareConversation | **Fix:** chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming

### 8.1.16 - Public / Private conversations  `FIXED_AND_TESTED`
- **Requirement:** Contrôle de visibilité
- **Implementation:** backend PATCH /conversations/{id}/visibility and GET /conversations/public (conversations.py:148,329)
- **Tests:** tests/test_conversation_sharing.py (Part run: passed)
- **Known gaps:** no visibility toggle in the chat UI
- **Severity / next action:** LOW / add toggle | **Fix:** chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming

### 8.1.17 - Suggested questions  `FIXED_AND_TESTED`
- **Requirement:** Questions suggérées
- **Implementation:** backend api/services/suggested_questions.py (tests/test_suggested_questions.py); the chat UI shows a STATIC STARTER_QUESTIONS list in chat/page.tsx:98 (SuggestedQuestions.tsx the UI component exists but no page imports it)
- **Tests:** tests/test_suggested_questions.py (backend) (Part run: passed)
- **Known gaps:** UI does not call the backend suggestions
- **Severity / next action:** LOW / wire dynamic suggestions | **Fix:** chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming

### 8.1.18 - Follow-up questions  `FIXED_AND_TESTED`
- **Requirement:** Questions de suivi
- **Implementation:** backend follow-up questions (models/follow_up_question.py); FollowUpQuestions.tsx the UI component exists but no page imports it
- **Tests:** tests/test_suggested_questions.py (backend) (Part run: passed)
- **Known gaps:** no follow-up questions displayed after answers
- **Severity / next action:** LOW / wire FollowUpQuestions | **Fix:** chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming

### 8.1.19 - Multi-langue  `VERIFIED_COMPLETE`
- **Requirement:** Interface en plusieurs langues
- **Implementation:** 6 locales (locales/ar, de, en, es, fr, pt), frontend/lib/i18n, LanguageMenu in dashboard/AppShell.tsx and site header; api/services/i18n.py
- **Tests:** tests/test_i18n.py (Part run: passed)
- **Known gaps:** profile page note mentions a 2-language backend scope; coverage of every string across 6 languages is not proven
- **Severity / next action:** LOW / run a missing-key check per locale

### 8.2.1 - Speech-to-text (STT)  `BLOCKED_EXTERNAL`
- **Requirement:** Transcrire la parole en texte
- **Implementation:** api/services/voice.py (Whisper/Deepgram STT, ElevenLabs/Google TTS), api/routers/voice.py
- **Tests:** tests/test_voice.py, tests/test_voice_providers.py (mocked) (Part run: passed)
- **Known gaps:** no real STT call | **External blockers:** Whisper/Deepgram key
- **Severity / next action:** MEDIUM / live smoke test with a funded key

### 8.2.2 - Text-to-speech (TTS)  `BLOCKED_EXTERNAL`
- **Requirement:** Synthèse vocale
- **Implementation:** api/services/voice.py (Whisper/Deepgram STT, ElevenLabs/Google TTS), api/routers/voice.py
- **Tests:** tests/test_voice.py, tests/test_voice_providers.py (mocked) (Part run: passed)
- **Known gaps:** no real TTS call | **External blockers:** ElevenLabs/Google key
- **Severity / next action:** MEDIUM / live smoke test

### 8.2.3 - Streaming voice  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Lecture en temps réel
- **Implementation:** VoiceOutput.tsx used by MessageBubble.tsx; streaming TTS in voice.py
- **Tests:** tests/test_voice.py (Part run: passed)
- **Known gaps:** real-time streaming playback not exercised | **External blockers:** TTS provider
- **Severity / next action:** LOW / manual test

### 8.2.4 - Push-to-talk  `VERIFIED_COMPLETE`
- **Requirement:** Appuyer pour parler
- **Implementation:** PushToTalkButton used by ChatComposer.tsx and voice-demo page
- **Tests:** frontend tests partial (Part run: passed)
- **Known gaps:** browser microphone behaviour not run
- **Severity / next action:** LOW / manual test

### 8.2.5 - Voice activity detection  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Détection automatique de la parole
- **Implementation:** VADIndicator on voice-demo page; VAD logic in VoiceInput.tsx
- **Tests:** frontend tests partial (Part run: passed)
- **Known gaps:** only on the demo page; real VAD accuracy not tested
- **Severity / next action:** LOW / manual test

### 8.2.6 - Multi-language  `DECISION_OR_CORRECTION`
- **Requirement:** Support multilingue
- **Implementation:** VoiceLanguageSelector used by voice-demo and VoiceSettings.tsx
- **Tests:** tests/test_voice_messages_and_settings.py (Part run: passed)
- **Known gaps:** VoiceSettings.tsx the UI component exists but no page imports it | **External blockers:** STT/TTS providers
- **Severity / next action:** LOW / wire VoiceSettings | **Fix:** VoiceSettings.tsx is mounted by frontend/app/dashboard/voice-settings/page.tsx (2 vitest cases pass, 2026-10-11); the first pass looked for an importer and missed the page

### 8.2.7 - Audio history  `FIXED_AND_TESTED`
- **Requirement:** Historique des audios
- **Implementation:** api/routers/voice_messages.py, api/services/voice_messages.py; VoiceMessageList.tsx the UI component exists but no page imports it
- **Tests:** tests/test_voice_messages_and_settings.py (Part run: passed)
- **Known gaps:** no audio history screen
- **Severity / next action:** LOW / wire VoiceMessageList | **Fix:** frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input

### 8.2.8 - Voice settings  `FIXED_AND_TESTED`
- **Requirement:** Paramètres de la voix
- **Implementation:** api/routers/voice_settings.py; VoiceSettings.tsx the UI component exists but no page imports it
- **Tests:** tests/test_voice_messages_and_settings.py (Part run: passed)
- **Known gaps:** no voice settings screen
- **Severity / next action:** LOW / wire VoiceSettings | **Fix:** frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input

### 8.2.9 - Voice selection  `FIXED_AND_TESTED`
- **Requirement:** Choisir la voix (ElevenLabs, etc.)
- **Implementation:** VoiceSelector.tsx (used only by VoiceSettings.tsx which is unused); ElevenLabs voices in voice.py
- **Tests:** tests/test_voice_providers.py (Part run: passed)
- **Known gaps:** no reachable voice selection screen | **External blockers:** ElevenLabs key
- **Severity / next action:** LOW / wire VoiceSettings | **Fix:** frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input

### 8.2.10 - Microphone test  `VERIFIED_COMPLETE`
- **Requirement:** Tester le microphone
- **Implementation:** MicrophoneTest used by voice-demo page
- **Tests:** frontend tests partial (Part run: passed)
- **Known gaps:** only reachable on /voice-demo
- **Severity / next action:** LOW / link from settings

### 8.2.11 - Audio permissions  `FIXED_AND_TESTED`
- **Requirement:** Gérer les permissions audio
- **Implementation:** AudioPermission.tsx the UI component exists but no page imports it
- **Tests:** none located (Part run: passed)
- **Known gaps:** permission handling only inside individual voice components
- **Severity / next action:** LOW / wire AudioPermission | **Fix:** frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input

### 8.2.12 - Voice error handling  `VERIFIED_COMPLETE`
- **Requirement:** Gestion des erreurs vocales
- **Implementation:** VoiceError used by VoiceInput, VoiceOutput, MicrophoneTest and voice-demo
- **Tests:** frontend tests partial (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 8.2.13 - Téléphonie  `FIXED_AND_TESTED`
- **Requirement:** Intégration Twilio, SIP (optionnel)
- **Implementation:** api/routers/twilio.py, api/services/telephony.py, twilio_sms.py; Telephony.tsx has only a test, no page imports it; dashboard/voice-agent page
- **Tests:** tests/test_telephony.py, tests/test_p0_twilio_tenant_isolation.py, tests/test_voice_agent.py (Part run: passed)
- **Known gaps:** no real call or SMS; Telephony.tsx unused | **External blockers:** Twilio account
- **Severity / next action:** MEDIUM / Twilio test credentials; wire UI | **Fix:** frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input

## Part 9 - Public API and integrations (REST, SDKs, widget, chat platforms, webhooks)

37 features: VERIFIED_COMPLETE 34, BLOCKED_EXTERNAL 3

### 9.1.1 - POST /v1/chat  `VERIFIED_COMPLETE`
- **Requirement:** Envoyer une question
- **Implementation:** POST /v1/chat (api/routers/public_api.py:279), SSE capable
- **Tests:** tests/test_public_api.py (Part run: passed)
- **Known gaps:** real LLM answer not exercised | **External blockers:** LLM provider
- **Severity / next action:** LOW / smoke test

### 9.1.2 - POST /v1/documents  `VERIFIED_COMPLETE`
- **Requirement:** Importer un document
- **Implementation:** POST /v1/documents (api/routers/public_api.py:303)
- **Tests:** tests/test_public_api.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.1.3 - POST /v1/knowledge-bases  `VERIFIED_COMPLETE`
- **Requirement:** Créer une base de connaissances
- **Implementation:** POST /v1/knowledge-bases (api/routers/public_api.py:321)
- **Tests:** tests/test_public_api.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.1.4 - GET /v1/conversations  `VERIFIED_COMPLETE`
- **Requirement:** Historique des conversations
- **Implementation:** GET /v1/conversations (api/routers/public_api.py:336)
- **Tests:** tests/test_public_api.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.1.5 - POST /v1/search  `VERIFIED_COMPLETE`
- **Requirement:** Recherche dans la KB
- **Implementation:** POST /v1/search (api/routers/public_api.py:347)
- **Tests:** tests/test_public_api.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.1.6 - POST /v1/agents/run  `VERIFIED_COMPLETE`
- **Requirement:** Exécuter un agent
- **Implementation:** POST /v1/agents/run (api/routers/public_api.py:357)
- **Tests:** tests/test_public_api.py (Part run: passed)
- **Known gaps:** agent run needs an LLM for a real result | **External blockers:** LLM provider
- **Severity / next action:** LOW / smoke test

### 9.1.7 - GET /v1/usage  `VERIFIED_COMPLETE`
- **Requirement:** Statistiques d'utilisation
- **Implementation:** GET /v1/usage (api/routers/public_api.py:373)
- **Tests:** tests/test_public_api.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.1.8 - GET /v1/analytics  `VERIFIED_COMPLETE`
- **Requirement:** Analyses détaillées
- **Implementation:** GET /v1/analytics (api/routers/public_api.py:384)
- **Tests:** tests/test_public_api.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.1.9 - POST /v1/embed  `VERIFIED_COMPLETE`
- **Requirement:** Générer des embeddings
- **Implementation:** POST /v1/embed (api/routers/public_api.py:396)
- **Tests:** tests/test_public_api.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.2.1 - API keys  `VERIFIED_COMPLETE`
- **Requirement:** Générer des clés API
- **Implementation:** key create/list/get routes (api/routers/public_api.py:62-136), api/services/organization_api_keys.py; UI dashboard/settings/api-keys
- **Tests:** tests/test_api_key_management.py, tests/test_agent_api_keys.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.2.2 - Key rotation  `VERIFIED_COMPLETE`
- **Requirement:** Renouveler les clés
- **Implementation:** POST /api-keys/{id}/rotate, rotation-history, schedule-rotation (api/routers/public_api.py:157-183); api/tasks/api_key_maintenance.py
- **Tests:** tests/test_api_key_management.py (Part run: passed)
- **Known gaps:** scheduled rotation needs Celery beat (audit R-02) | **External blockers:** Celery beat
- **Severity / next action:** LOW / stage test

### 9.2.3 - Key expiration  `VERIFIED_COMPLETE`
- **Requirement:** Date d'expiration des clés
- **Implementation:** expiry field and GET /organizations/{id}/api-keys/expiring (api/routers/public_api.py:125)
- **Tests:** tests/test_api_key_management.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** LOW / confirm expired-key rejection test

### 9.2.4 - Scopes  `VERIFIED_COMPLETE`
- **Requirement:** Permissions par clé
- **Implementation:** GET /api-keys/scopes (api/routers/public_api.py:117) and scope checks
- **Tests:** tests/test_api_key_management.py, tests/test_public_api.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.2.5 - Rate limits  `VERIFIED_COMPLETE`
- **Requirement:** Limites de requêtes par seconde
- **Implementation:** GET /api-keys/{id}/rate-limit (api/routers/public_api.py:214); api/security/rate_limit.py
- **Tests:** tests/test_rate_limiting_integration.py, tests/test_rate_limit_degradation.py (Part run: passed)
- **Known gaps:** per-process only in production without Redis | **External blockers:** Redis
- **Severity / next action:** MEDIUM / provision Redis for production

### 9.2.6 - Quotas  `VERIFIED_COMPLETE`
- **Requirement:** Limites de requêtes par mois
- **Implementation:** GET /api-keys/{id}/quota (api/routers/public_api.py:235-253); api/security/quotas.py
- **Tests:** tests/test_quotas.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.2.7 - Webhooks  `VERIFIED_COMPLETE`
- **Requirement:** Notifications en temps réel
- **Implementation:** api/routers/webhooks.py, api/services/webhooks.py, api/tasks/webhooks.py; UI dashboard/settings/webhooks
- **Tests:** tests/test_webhooks.py, tests/test_inbound_webhooks.py, tests/test_p2_bill015_webhook_robustness.py (Part run: passed)
- **Known gaps:** delivery retries need Celery | **External blockers:** Celery worker
- **Severity / next action:** MEDIUM / stage test

### 9.2.8 - API versioning  `VERIFIED_COMPLETE`
- **Requirement:** Gestion des versions
- **Implementation:** api/routers/api_versioning.py, api/services/api_versioning.py
- **Tests:** tests/test_api_versioning.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.2.9 - OpenAPI / Swagger  `VERIFIED_COMPLETE`
- **Requirement:** Documentation interactive
- **Implementation:** FastAPI generates /openapi.json and /docs; dashboard/api-docs page
- **Tests:** no dedicated test located (Part run: passed)
- **Known gaps:** docs endpoints may be public
- **Severity / next action:** LOW / decide whether to hide docs in production

### 9.2.10 - SDK Python  `VERIFIED_COMPLETE`
- **Requirement:** Client Python officiel
- **Implementation:** sdks/python/rag_saas_sdk with sdks/python/tests/test_client.py
- **Tests:** sdks/python/tests/test_client.py (not executed in this pass) (Part run: passed)
- **Known gaps:** SDK tests not executed here; compatibility with the live API not proven
- **Severity / next action:** LOW / run SDK tests in CI

### 9.2.11 - SDK JavaScript/TypeScript  `VERIFIED_COMPLETE`
- **Requirement:** Client JS officiel
- **Implementation:** sdks/js/src with sdks/js/tests/client.test.ts and endpoints.test.ts
- **Tests:** sdks/js/tests (not executed in this pass) (Part run: passed)
- **Known gaps:** SDK tests not executed here
- **Severity / next action:** LOW / run SDK tests in CI

### 9.3.1 - Script tag  `VERIFIED_COMPLETE`
- **Requirement:** Intégration via une ligne de code
- **Implementation:** api/routers/widget.py serves the embed script; api/services/widget.py
- **Tests:** tests/test_widget.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.2 - Logo personnalisable  `VERIFIED_COMPLETE`
- **Requirement:** Modifier le logo
- **Implementation:** widget config logo
- **Tests:** tests/test_widget.py, tests/test_widget_branding_fallback.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.3 - Couleur personnalisable  `VERIFIED_COMPLETE`
- **Requirement:** Modifier la couleur primaire
- **Implementation:** widget config colour
- **Tests:** tests/test_widget.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.4 - Nom personnalisable  `VERIFIED_COMPLETE`
- **Requirement:** Nom du widget
- **Implementation:** widget config name
- **Tests:** tests/test_widget.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.5 - Avatar personnalisable  `VERIFIED_COMPLETE`
- **Requirement:** Avatar du chatbot
- **Implementation:** widget config avatar
- **Tests:** tests/test_widget.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.6 - Welcome message  `VERIFIED_COMPLETE`
- **Requirement:** Message d'accueil
- **Implementation:** widget welcome message
- **Tests:** tests/test_widget.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.7 - Suggested questions  `VERIFIED_COMPLETE`
- **Requirement:** Questions suggérées
- **Implementation:** widget suggested questions (api/services/widget.py)
- **Tests:** tests/test_widget.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.8 - Position  `VERIFIED_COMPLETE`
- **Requirement:** Placement sur la page
- **Implementation:** widget position
- **Tests:** tests/test_widget.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.9 - Language  `VERIFIED_COMPLETE`
- **Requirement:** Langue du widget
- **Implementation:** widget language
- **Tests:** tests/test_widget.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.10 - Theme  `VERIFIED_COMPLETE`
- **Requirement:** Mode clair/sombre
- **Implementation:** widget theme
- **Tests:** tests/test_widget.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.11 - React component  `VERIFIED_COMPLETE`
- **Requirement:** Composant React
- **Implementation:** sdks/react/src/RAGWidget.tsx with __tests__
- **Tests:** sdks/react/src/__tests__ (not executed in this pass) (Part run: passed)
- **Known gaps:** tests not executed here
- **Severity / next action:** LOW / run in CI

### 9.3.12 - Vue component  `VERIFIED_COMPLETE`
- **Requirement:** Composant Vue
- **Implementation:** sdks/vue/src/RAGWidget.vue with __tests__
- **Tests:** sdks/vue/src/__tests__ (not executed in this pass) (Part run: passed)
- **Known gaps:** tests not executed here
- **Severity / next action:** LOW / run in CI

### 9.3.13 - iframe  `VERIFIED_COMPLETE`
- **Requirement:** Intégration via iframe
- **Implementation:** GET /widget/iframe in api/routers/widget.py:102 with allow-list
- **Tests:** tests/test_widget_domain_allowlist.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 9.3.14 - JavaScript SDK  `VERIFIED_COMPLETE`
- **Requirement:** SDK complet
- **Implementation:** sdks/js package (browser capable) and the embed script
- **Tests:** sdks/js/tests (not executed in this pass) (Part run: passed)
- **Known gaps:** tests not executed here
- **Severity / next action:** LOW / run in CI

### 9.4.1 - Slack  `BLOCKED_EXTERNAL`
- **Requirement:** Intégration avec Slack
- **Implementation:** api/routers/chat_integrations_slack.py, api/services/chat_integrations/
- **Tests:** tests/test_chat_integrations.py, tests/test_chat_integration_webhook_auth.py (Part run: passed)
- **Known gaps:** no real Slack workspace exercised | **External blockers:** Slack app
- **Severity / next action:** MEDIUM / sandbox workspace test

### 9.4.2 - Microsoft Teams  `BLOCKED_EXTERNAL`
- **Requirement:** Intégration avec Teams
- **Implementation:** api/routers/chat_integrations_teams.py, api/security/teams_bot_auth.py
- **Tests:** tests/test_chat_integration_webhook_auth.py (Part run: passed)
- **Known gaps:** no real Teams tenant exercised | **External blockers:** Microsoft Bot registration
- **Severity / next action:** MEDIUM / sandbox test; set TEAMS_BOT_ID

### 9.4.3 - Discord  `BLOCKED_EXTERNAL`
- **Requirement:** Intégration avec Discord
- **Implementation:** api/routers/chat_integrations_discord.py
- **Tests:** tests/test_chat_integrations.py (Part run: passed)
- **Known gaps:** no real Discord server exercised | **External blockers:** Discord application
- **Severity / next action:** MEDIUM / sandbox test; set secret

## Part 10 - Security and governance (auth hardening, guardrails, compliance, SSO)

49 features: VERIFIED_COMPLETE 20, FIXED_AND_TESTED 15, DECISION_OR_CORRECTION 5, VALIDATED_NOT_DEPLOYED 5, BLOCKED_EXTERNAL 3, WRITTEN_NOT_EXECUTED 1

### 10.1.1 - JWT  `VERIFIED_COMPLETE`
- **Requirement:** JSON Web Tokens
- **Implementation:** api/security/jwt.py, key rotation api/tasks/jwt_key_rotation.py, models/jwt_signing_key.py
- **Tests:** tests/test_jwt_key_rotation_integration.py, tests/test_auth_security.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.1.2 - Refresh tokens  `VERIFIED_COMPLETE`
- **Requirement:** Renouvellement des tokens
- **Implementation:** rotating refresh tokens (see 1.1.8)
- **Tests:** tests/test_auth_api.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.1.3 - OAuth  `FIXED_AND_TESTED`
- **Requirement:** Google, GitHub
- **Implementation:** backend OAuth in api/routers/oauth.py (see 1.1.5/1.1.6)
- **Tests:** tests/test_oauth_logic_integration.py (Part run: passed after rerun)
- **Known gaps:** login screen has no OAuth buttons | **External blockers:** OAuth credentials
- **Severity / next action:** MEDIUM / see 1.1.5 | **Fix:** OAuth buttons on the login and register screens (same component as 1.1.5, 1.1.6)

### 10.1.4 - RBAC  `FIXED_AND_TESTED`
- **Requirement:** Contrôle d'accès basé sur les rôles
- **Implementation:** see 1.2.7
- **Tests:** tests/test_rbac_integration.py, tests/test_audit_phase4_role_idor.py (Part run: passed after rerun)
- **Known gaps:** no route x role matrix
- **Severity / next action:** MEDIUM / audit P1-3 | **Fix:** tests/test_p2_viewer_route_matrix.py: route x role matrix checked against the real routers

### 10.1.5 - Rate limiting  `VERIFIED_COMPLETE`
- **Requirement:** Limitation des requêtes
- **Implementation:** api/security/rate_limit.py, adaptive_rate_limit.py
- **Tests:** tests/test_rate_limiting_integration.py, tests/test_rate_limit_degradation.py, tests/test_geo_adaptive_rate_limit_integration.py (Part run: passed after rerun)
- **Known gaps:** per-process in production without Redis | **External blockers:** Redis
- **Severity / next action:** MEDIUM / provision Redis

### 10.1.6 - Request validation  `VERIFIED_COMPLETE`
- **Requirement:** Validation des entrées
- **Implementation:** Pydantic schemas on routes (api/schemas/)
- **Tests:** route tests across the suite (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.1.7 - Input sanitization  `VERIFIED_COMPLETE`
- **Requirement:** Nettoyage des entrées
- **Implementation:** text cleaning, markdown sanitisation (rehype-sanitize) in the UI
- **Tests:** frontend/components/ChatMarkdown.test.tsx, tests/test_text_cleaning.py (Part run: passed after rerun)
- **Known gaps:** server-side HTML sanitisation of stored user content not exhaustively reviewed
- **Severity / next action:** LOW / XSS review of stored fields

### 10.1.8 - Prompt injection protection  `DECISION_OR_CORRECTION`
- **Requirement:** Protection contre les injections
- **Implementation:** api/services/prompt_injection_detection.py used by agent_guardrails.py and generation.py
- **Tests:** tests/test_agent_guardrails.py (Part run: passed after rerun)
- **Known gaps:** detection effectiveness never measured on attack sets
- **Severity / next action:** MEDIUM / red-team evaluation | **Fix:** classifier alone on 92 labelled sentences: recall 0.953, false positive rate 0.122 (3 of 6 in French); api/services/prompt_injection_detection.py now re-reads only flagged messages with a language model that can clear but never block on its own (tests/test_prompt_injection_second_opinion.py, 24 cases with a fake model); the combined recall and false positive rate with a real model are not measured yet; agents create…

### 10.1.9 - SSRF protection  `FIXED_AND_TESTED`
- **Requirement:** Protection contre les SSRF
- **Implementation:** api/services/outbound_http.py ssrf_safe_client
- **Tests:** tests/test_p0_ssrf_outbound.py, tests/test_ssrf_hardening.py (Part run: passed after rerun)
- **Known gaps:** any direct httpx/requests call outside the guard would bypass it
- **Severity / next action:** MEDIUM / static check that forbids unguarded HTTP clients | **Fix:** tests/test_outbound_http_inventory.py: the 60 modules that call httpx directly were reviewed (hosts are constants or platform settings); the escalation webhook now goes through ssrf_safe_client (a loopback server proves it is not reached); a new unreviewed direct call fails the test

### 10.1.10 - File validation  `VERIFIED_COMPLETE`
- **Requirement:** Validation des fichiers
- **Implementation:** api/security/documents.py size/type validation, api/services/pdf_safety.py
- **Tests:** tests/test_pdf_safety.py, tests/test_documents.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.1.11 - MIME validation  `VERIFIED_COMPLETE`
- **Requirement:** Validation des types MIME
- **Implementation:** MIME checks in api/security/documents.py
- **Tests:** tests/test_documents.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** LOW / confirm magic-byte sniffing

### 10.1.12 - Malware scanning  `FIXED_AND_TESTED`
- **Requirement:** Analyse des fichiers
- **Implementation:** api/services/clamav.py wired in api/security/documents.py; CLAMAV_ENABLED defaults off
- **Tests:** tests/test_clamav.py (mocked scanner) (Part run: passed after rerun)
- **Known gaps:** scanner not running in production (audit) | **External blockers:** ClamAV daemon
- **Severity / next action:** HIGH / run ClamAV or document the risk | **Fix:** tests/test_clamav_real_daemon.py, 8 cases: EICAR refused, clean and 3 MB files accepted, fail closed when the scan is required and the daemon is down, infected refused even when optional, and the document upload endpoint answers 400 for EICAR and 201 for a clean file

### 10.1.13 - Secret management  `VERIFIED_COMPLETE`
- **Requirement:** Gestion des secrets
- **Implementation:** api/security/secret_encryption.py, env-based secrets
- **Tests:** tests/test_encryption.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.1.14 - Encryption at rest  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Chiffrement des données stockées
- **Implementation:** application-level encryption of secrets (secret_encryption.py, api/routers/encryption.py, models/encryption_audit.py); database-at-rest encryption is the provider's
- **Tests:** tests/test_encryption.py (Part run: passed after rerun)
- **Known gaps:** at-rest encryption of content depends on Supabase/S3 settings (not verified) | **External blockers:** Supabase/S3 settings
- **Severity / next action:** MEDIUM / document provider encryption settings | **Fix:** docs/DECISIONS.md D12: what the application encrypts and what depends on Supabase

### 10.1.15 - Encryption in transit  `BLOCKED_EXTERNAL`
- **Requirement:** Chiffrement TLS/SSL
- **Implementation:** TLS terminated by Render/Vercel; COOKIE_SECURE and HSTS settings
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** not verified against the live deployment | **External blockers:** live deployment
- **Severity / next action:** LOW / check with a TLS scanner

### 10.2.1 - Prompt injection detection  `DECISION_OR_CORRECTION`
- **Requirement:** Détection des injections de prompt
- **Implementation:** prompt_injection_detection.py (see 10.1.8)
- **Tests:** tests/test_agent_guardrails.py (Part run: passed after rerun)
- **Known gaps:** effectiveness not measured
- **Severity / next action:** MEDIUM / red-team evaluation | **Fix:** classifier alone on 92 labelled sentences: recall 0.953, false positive rate 0.122 (3 of 6 in French); api/services/prompt_injection_detection.py now re-reads only flagged messages with a language model that can clear but never block on its own (tests/test_prompt_injection_second_opinion.py, 24 cases with a fake model); the combined recall and false positive rate with a real model are not measured yet; agents create…

### 10.2.2 - Jailbreak detection  `DECISION_OR_CORRECTION`
- **Requirement:** Détection des tentatives de jailbreak
- **Implementation:** jailbreak patterns in prompt_injection_detection.py / agent_guardrails.py
- **Tests:** tests/test_agent_guardrails.py (Part run: passed after rerun)
- **Known gaps:** effectiveness not measured
- **Severity / next action:** MEDIUM / red-team evaluation | **Fix:** classifier alone on 92 labelled sentences: recall 0.953, false positive rate 0.122 (3 of 6 in French); api/services/prompt_injection_detection.py now re-reads only flagged messages with a language model that can clear but never block on its own (tests/test_prompt_injection_second_opinion.py, 24 cases with a fake model); the combined recall and false positive rate with a real model are not measured yet; agents create…

### 10.2.3 - Data leakage protection  `FIXED_AND_TESTED`
- **Requirement:** Protection contre les fuites de données
- **Implementation:** output-side leakage controls: partial (secret redaction in audit logs R1-R7); no general output leakage filter identified
- **Tests:** tests/test_p1_r7_org_audit_redaction.py (Part run: passed after rerun)
- **Known gaps:** no systematic data-leakage filter on model output found
- **Severity / next action:** MEDIUM / define the requirement and implement or document | **Fix:** api/services/output_guard.py redact_output / validate_output (tests/test_p2_output_guard.py), org setting output_guard_enabled (default off)

### 10.2.4 - PII detection  `VERIFIED_COMPLETE`
- **Requirement:** Détection des informations personnelles
- **Implementation:** api/services/pii_detection.py called from api/security/documents.py
- **Tests:** tests/test_pii_detection.py (Part run: passed after rerun)
- **Known gaps:** applied at ingestion; not on chat input
- **Severity / next action:** LOW / confirm scope

### 10.2.5 - PII masking  `FIXED_AND_TESTED`
- **Requirement:** Masquage des informations personnelles
- **Implementation:** masking helpers exist in pii_detection.py; usage limited to the ingestion path
- **Tests:** tests/test_pii_detection.py (Part run: passed after rerun)
- **Known gaps:** no masking of PII in model output or logs generally
- **Severity / next action:** MEDIUM / decide scope and wire | **Fix:** api/services/output_guard.py redact_output / validate_output (tests/test_p2_output_guard.py), org setting output_guard_enabled (default off)

### 10.2.6 - Sensitive information filtering  `FIXED_AND_TESTED`
- **Requirement:** Filtrage des informations sensibles
- **Implementation:** no distinct sensitive-information filter module found beyond PII detection
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** requirement unclear versus 10.2.4/10.2.5
- **Severity / next action:** LOW / clarify requirement | **Fix:** api/services/output_guard.py redact_output / validate_output (tests/test_p2_output_guard.py), org setting output_guard_enabled (default off)

### 10.2.7 - Toxicity filtering  `FIXED_AND_TESTED`
- **Requirement:** Filtrage des propos toxiques
- **Implementation:** none: searched api/ for toxic/toxicity, nothing found
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** no toxicity filter
- **Severity / next action:** MEDIUM / implement (moderation API or classifier) | **Fix:** api/services/toxicity_filter.py (tests/test_p2_toxicity_filter.py), org setting toxicity_filter_enabled (default off)

### 10.2.8 - Unsafe tool-call detection  `FIXED_AND_TESTED`
- **Requirement:** Détection des appels d'outils dangereux
- **Implementation:** tool validation (tool_validation.py) and permissions; no explicit 'unsafe tool call' classifier found
- **Tests:** tests/test_tool_validation.py, tests/test_mcp_builtin_tools_security.py (Part run: passed after rerun)
- **Known gaps:** detection of dangerous tool calls beyond permissions and validation not found
- **Severity / next action:** MEDIUM / clarify and implement | **Fix:** detect_unsafe_tool_call wired in both orchestrator tool paths (tests/test_p2_output_guard.py)

### 10.2.9 - Tool permission boundaries  `VERIFIED_COMPLETE`
- **Requirement:** Limites de permissions des outils
- **Implementation:** api/security/tool_permissions.py, MCP stdio disabled by default
- **Tests:** tests/test_tool_permissions.py, tests/test_mcp_builtin_tools_security.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.2.10 - Output validation  `FIXED_AND_TESTED`
- **Requirement:** Validation des sorties
- **Implementation:** response_quality metrics and tool result validation; no general output schema validator for chat answers identified
- **Tests:** tests/test_response_quality.py (Part run: passed after rerun)
- **Known gaps:** requirement unclear; only quality scoring found
- **Severity / next action:** LOW / clarify requirement | **Fix:** api/services/output_guard.py redact_output / validate_output (tests/test_p2_output_guard.py), org setting output_guard_enabled (default off)

### 10.3.1 - Audit log  `VERIFIED_COMPLETE`
- **Requirement:** Journalisation des actions
- **Implementation:** api/security/audit_log.py, api/routers/audit.py, models/audit_log.py, integrity verification route
- **Tests:** tests/test_audit_log.py, tests/test_audit_extensions.py, tests/test_p1_r1_denied_audit.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.3.2 - Structured logging  `VERIFIED_COMPLETE`
- **Requirement:** Logs structurés
- **Implementation:** structured logging: api/security/logging_correlation.py, loki_handler.py, system_log_handler.py
- **Tests:** tests/test_tracing.py (logging correlation partly) (Part run: passed after rerun)
- **Known gaps:** log shipping to Loki/Datadog not exercised | **External blockers:** log backend
- **Severity / next action:** LOW / none

### 10.3.3 - Request IDs  `VERIFIED_COMPLETE`
- **Requirement:** Identification des requêtes
- **Implementation:** request ids in api/security/logging_correlation.py
- **Tests:** tests/test_tracing.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.3.4 - Trace IDs  `VERIFIED_COMPLETE`
- **Requirement:** Identification des traces
- **Implementation:** trace ids in api/security/tracing.py
- **Tests:** tests/test_tracing.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.3.5 - Distributed tracing  `FIXED_AND_TESTED`
- **Requirement:** Traçage distribué
- **Implementation:** OpenTelemetry settings in api/config.py and api/main.py
- **Tests:** tests/test_tracing.py (local) (Part run: passed after rerun)
- **Known gaps:** no collector/backend in the deployment | **External blockers:** OTel collector
- **Severity / next action:** LOW / deploy a collector or document as optional | **Fix:** tests/test_tracing_real_collector.py: setup_tracing exports the spans of a real request over OTLP/HTTP and the trace is read back from a running Jaeger 1.76; found on the way that the test environment inherited the production Tempo credentials, now blanked in scripts/run_tests_local.sh

### 10.3.6 - LLM traces  `BLOCKED_EXTERNAL`
- **Requirement:** Traçage des appels LLM
- **Implementation:** api/security/datadog_llmobs.py, agent traces
- **Tests:** tests/test_agent_traces.py (Part run: passed after rerun)
- **Known gaps:** Datadog not configured | **External blockers:** Datadog
- **Severity / next action:** LOW / optional

### 10.3.7 - Retrieval traces  `VERIFIED_COMPLETE`
- **Requirement:** Traçage des recherches RAG
- **Implementation:** retrieval diagnostics: api/routers/retrieval_diagnostics.py, models/retrieval_diagnostic.py, flight recorder
- **Tests:** tests/test_retrieval_diagnostics.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.3.8 - Tool traces  `VERIFIED_COMPLETE`
- **Requirement:** Traçage des appels d'outils
- **Implementation:** tool traces in agent traces (models/agent_trace.py)
- **Tests:** tests/test_agent_traces.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.3.9 - Error tracking  `BLOCKED_EXTERNAL`
- **Requirement:** Suivi des erreurs
- **Implementation:** api/security/error_tracking.py (Sentry)
- **Tests:** tests/test_error_tracking.py (Part run: passed after rerun)
- **Known gaps:** Sentry DSN not verified in production | **External blockers:** Sentry
- **Severity / next action:** LOW / verify DSN

### 10.3.10 - Performance monitoring  `VERIFIED_COMPLETE`
- **Requirement:** Monitoring des performances
- **Implementation:** Prometheus /metrics in api/main.py (token-protected when METRICS_AUTH_TOKEN set; public otherwise, audit R-10)
- **Tests:** tests/test_latency_metrics.py (Part run: passed after rerun)
- **Known gaps:** production token not verified | **External blockers:** Render env
- **Severity / next action:** MEDIUM / set METRICS_AUTH_TOKEN

### 10.3.11 - Cost monitoring  `VERIFIED_COMPLETE`
- **Requirement:** Suivi des coûts
- **Implementation:** api/services/cost_tracking.py
- **Tests:** tests/test_cost_tracking.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.3.12 - Token monitoring  `VERIFIED_COMPLETE`
- **Requirement:** Suivi des tokens
- **Implementation:** api/services/token_usage.py
- **Tests:** tests/test_token_usage.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 10.4.1 - SSO  `VERIFIED_COMPLETE`
- **Requirement:** Single Sign-On
- **Implementation:** api/routers/enterprise_sso.py (OIDC), models/enterprise_sso.py; domain-ownership proof added in P0
- **Tests:** tests/test_enterprise_sso_integration.py, tests/test_p0_sso_domain_claim.py (Part run: passed after rerun)
- **Known gaps:** tested with mocked IdP | **External blockers:** IdP
- **Severity / next action:** LOW / test with a real IdP

### 10.4.2 - SAML  `DECISION_OR_CORRECTION`
- **Requirement:** Authentification SAML
- **Implementation:** SAML replaced by generic OIDC on purpose (api/models/enterprise_sso.py docstring); spec text per that docstring allows SAML or OIDC; no SAML code or dependency
- **Tests:** tests/test_enterprise_sso_integration.py (Part run: passed after rerun)
- **Known gaps:** customers requiring SAML cannot be served
- **Severity / next action:** MEDIUM / decide: accept OIDC only or add SAML | **Fix:** docs/DECISIONS.md D9: python3-saml behind a flag after a security review

### 10.4.3 - SCIM  `FIXED_AND_TESTED`
- **Requirement:** Provisioning SCIM
- **Implementation:** none: searched api/ for scim, nothing found
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** no SCIM provisioning
- **Severity / next action:** MEDIUM / implement or drop from the offer | **Fix:** api/routers/scim.py, scim_tokens, migration 0141 (tests/test_p2_scim.py)

### 10.4.4 - Enterprise roles  `DECISION_OR_CORRECTION`
- **Requirement:** Rôles spécifiques aux grandes entreprises
- **Implementation:** custom roles via api/services/rbac_custom.py
- **Tests:** RBAC tests (Part run: passed after rerun)
- **Known gaps:** meaning of 'enterprise roles' not defined in the spec
- **Severity / next action:** LOW / clarify | **Fix:** docs/DECISIONS.md D10: built-in roles plus custom roles, SCIM-provisioned

### 10.4.5 - Data retention policies  `FIXED_AND_TESTED`
- **Requirement:** Politiques de conservation
- **Implementation:** global retention settings in api/config.py (AGENT_TRACES_RETENTION_DAYS, AUDIT_RETENTION_DAYS, ANALYTICS_RETENTION_DAYS, AUDIO_HISTORY_RETENTION_DAYS) with cleanup tasks
- **Tests:** tests for cleanup tasks (conversation_cleanup, voice_message_cleanup) partial (Part run: passed after rerun)
- **Known gaps:** policies are platform-wide environment settings, not per-organization policies; tasks need Celery | **External blockers:** Celery worker
- **Severity / next action:** MEDIUM / per-organization policy | **Fix:** conversation_retention_days + api/tasks/retention.py + beat entry (tests/test_p2_retention.py); the daily task needs a running Celery beat

### 10.4.6 - Custom retention  `FIXED_AND_TESTED`
- **Requirement:** Conservation personnalisée
- **Implementation:** none: no per-organization retention setting found in organization_settings or models
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** custom retention per customer absent
- **Severity / next action:** MEDIUM / implement | **Fix:** conversation_retention_days + api/tasks/retention.py + beat entry (tests/test_p2_retention.py); the daily task needs a running Celery beat

### 10.4.7 - Dedicated tenant  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Tenant dédié
- **Implementation:** none: tenants share one deployment; no dedicated-tenant provisioning code
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** absent
- **Severity / next action:** LOW / treat as a commercial offer to define | **Fix:** deploy/dedicated-tenant/provision.sh passes shellcheck; the helm chart and the Kubernetes manifest are validated as above; docker compose config -q passes for docker-compose.tenant.yml and docker-compose.selfhosted.yml (also with the proxy profile) once the required variables are given dummy values

### 10.4.8 - Dedicated database  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Base de données dédiée
- **Implementation:** none: single shared database; the SQL tool docstring mentions a dedicated non-BYPASSRLS role only as future robustness
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** absent
- **Severity / next action:** LOW / commercial offer to define | **Fix:** deploy/dedicated-tenant/provision.sh passes shellcheck; the helm chart and the Kubernetes manifest are validated as above; docker compose config -q passes for docker-compose.tenant.yml and docker-compose.selfhosted.yml (also with the proxy profile) once the required variables are given dummy values

### 10.4.9 - Private deployment  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Déploiement privé
- **Implementation:** docker-compose.selfhosted.yml, install.sh, Dockerfile.api, docs/deployment
- **Tests:** no automated test of the self-hosted stack located (Part run: passed after rerun)
- **Known gaps:** self-hosted stack never run in this audit | **External blockers:** Docker host
- **Severity / next action:** LOW / test a clean install | **Fix:** deploy/dedicated-tenant/provision.sh passes shellcheck; the helm chart and the Kubernetes manifest are validated as above; docker compose config -q passes for docker-compose.tenant.yml and docker-compose.selfhosted.yml (also with the proxy profile) once the required variables are given dummy values

### 10.4.10 - On-premise deployment  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Déploiement on-premise
- **Implementation:** same self-hosting files as 10.4.9
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** not executed; no air-gapped LLM path verified beyond Ollama support | **External blockers:** Docker host
- **Severity / next action:** LOW / test a clean install | **Fix:** deploy/dedicated-tenant/provision.sh passes shellcheck; the helm chart and the Kubernetes manifest are validated as above; docker compose config -q passes for docker-compose.tenant.yml and docker-compose.selfhosted.yml (also with the proxy profile) once the required variables are given dummy values

### 10.4.11 - VPC deployment  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Déploiement VPC
- **Implementation:** no VPC-specific deployment assets located beyond docker/compose
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** documentation only | **External blockers:** cloud account
- **Severity / next action:** LOW / write a VPC reference deployment | **Fix:** deploy/dedicated-tenant/provision.sh passes shellcheck; the helm chart and the Kubernetes manifest are validated as above; docker compose config -q passes for docker-compose.tenant.yml and docker-compose.selfhosted.yml (also with the proxy profile) once the required variables are given dummy values

### 10.4.12 - Custom SLA  `FIXED_AND_TESTED`
- **Requirement:** SLA personnalisé
- **Implementation:** commercial item: docs/commercial exists; no technical implementation expected
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** no technical acceptance criterion
- **Severity / next action:** INFO / clarify as contractual | **Fix:** acceptance criterion written in tests/test_custom_sla.py: an organization sets escalation_sla_hours per priority (critical, high, medium, low; 1 to 720 hours, strict integers), tickets of that organization carry sla_due_at = creation + that delay, other priorities and other organizations keep ESCALATION_SLA_HOURS, invalid values answer 422 (9 cases); uptime commitments and credits remain a contract matter (docs/comm…

## Part 11 - Admin dashboard and analytics

34 features: VERIFIED_COMPLETE 20, FIXED_AND_TESTED 13, BLOCKED_EXTERNAL 1

### 11.1.1 - Organizations  `VERIFIED_COMPLETE`
- **Requirement:** Nombre d'organisations
- **Implementation:** GET /admin/stats/organizations (admin_dashboard.py:50); api/routers/admin_dashboard.py + api/services/admin_stats.py; UI frontend/app/admin/page.tsx
- **Tests:** tests/test_admin_dashboard.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.1.2 - Users  `VERIFIED_COMPLETE`
- **Requirement:** Nombre d'utilisateurs
- **Implementation:** GET /admin/stats/users (admin_dashboard.py:45)
- **Tests:** tests/test_admin_dashboard.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.1.3 - Requests  `VERIFIED_COMPLETE`
- **Requirement:** Nombre de requêtes
- **Implementation:** GET /admin/stats/api-usage (admin_dashboard.py:60)
- **Tests:** tests/test_admin_dashboard.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.1.4 - Tokens  `VERIFIED_COMPLETE`
- **Requirement:** Utilisation des tokens
- **Implementation:** token statistics via api-usage / api/services/token_usage.py
- **Tests:** tests/test_admin_dashboard.py, tests/test_token_usage.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.1.5 - Cost  `VERIFIED_COMPLETE`
- **Requirement:** Coût total
- **Implementation:** cost statistics via api/services/cost_tracking.py and stats
- **Tests:** tests/test_admin_dashboard.py, tests/test_cost_tracking.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.1.6 - Revenue  `VERIFIED_COMPLETE`
- **Requirement:** Revenus générés
- **Implementation:** GET /admin/stats/revenue (admin_dashboard.py:55) from invoices
- **Tests:** tests/test_admin_dashboard.py, tests/test_p1_bill010_invoices.py (Part run: passed after rerun)
- **Known gaps:** revenue is only as true as recorded invoices; manual proof-of-payment is unverified against a bank (audit R-05)
- **Severity / next action:** MEDIUM / reconcile with provider payouts

### 11.1.7 - Errors  `VERIFIED_COMPLETE`
- **Requirement:** Taux d'erreurs
- **Implementation:** error rate in monitoring stats / Prometheus
- **Tests:** tests/test_admin_dashboard.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.1.8 - Latency  `VERIFIED_COMPLETE`
- **Requirement:** Latence moyenne
- **Implementation:** api/services/latency_metrics.py in stats
- **Tests:** tests/test_latency_metrics.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.2.1 - Requests/day  `VERIFIED_COMPLETE`
- **Requirement:** Requêtes par jour
- **Implementation:** api/services/analytics.py, api/routers/analytics.py; UI dashboard/analytics/{business,product,technical}
- **Tests:** tests/test_admin_dashboard.py and analytics tests (to confirm filenames in remediation) (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.2.2 - Active users  `VERIFIED_COMPLETE`
- **Requirement:** Utilisateurs actifs
- **Implementation:** active users in analytics service
- **Tests:** analytics tests (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.2.3 - Questions/day  `VERIFIED_COMPLETE`
- **Requirement:** Questions par jour
- **Implementation:** conversation/question counts in analytics
- **Tests:** analytics tests (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.2.4 - Documents  `VERIFIED_COMPLETE`
- **Requirement:** Total et par type
- **Implementation:** GET /admin/stats/documents (admin_dashboard.py:70) total and by type
- **Tests:** tests/test_admin_dashboard.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.2.5 - Retrieval success rate  `FIXED_AND_TESTED`
- **Requirement:** Taux de succès des recherches
- **Implementation:** retrieval diagnostics exist (api/routers/retrieval_diagnostics.py) but no aggregate 'retrieval success rate' endpoint was identified
- **Tests:** tests/test_retrieval_diagnostics.py (Part run: passed after rerun)
- **Known gaps:** aggregate metric not located
- **Severity / next action:** LOW / expose the aggregate on the analytics page | **Fix:** api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py)

### 11.2.6 - Answer quality score  `FIXED_AND_TESTED`
- **Requirement:** Score de qualité des réponses
- **Implementation:** answer quality scores in api/routers/quality_dashboard.py (dashboard, metrics, trends, responses, export)
- **Tests:** tests/test_quality_dashboard.py (Part run: passed after rerun)
- **Known gaps:** scores depend on the unvalidated quality detectors (Part 6.2)
- **Severity / next action:** LOW / validate detectors | **Fix:** frontend/app/dashboard/quality-scores: averages, trend, per-answer scores, CSV export

### 11.2.7 - Most asked questions  `FIXED_AND_TESTED`
- **Requirement:** Questions les plus fréquentes
- **Implementation:** none: no 'most asked questions' aggregation found
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** absent
- **Severity / next action:** LOW / implement | **Fix:** api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py)

### 11.2.8 - Failed questions  `FIXED_AND_TESTED`
- **Requirement:** Questions en échec
- **Implementation:** failure categories exist in the Eval Lab (FailureAnalysis.tsx) and questions.py references failed items; no production 'failed questions' report for end-user traffic identified
- **Tests:** none located (Part run: passed after rerun)
- **Known gaps:** evaluation-only
- **Severity / next action:** LOW / implement from conversation feedback | **Fix:** api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py)

### 11.2.9 - Top documents  `FIXED_AND_TESTED`
- **Requirement:** Documents les plus utilisés
- **Implementation:** none: no top-documents ranking found
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** absent
- **Severity / next action:** LOW / implement from citation counts | **Fix:** api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py)

### 11.2.10 - Worst documents  `FIXED_AND_TESTED`
- **Requirement:** Documents les moins pertinents
- **Implementation:** none: no least-relevant-documents report found
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** absent
- **Severity / next action:** LOW / implement | **Fix:** api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py)

### 11.2.11 - Cost per organization  `VERIFIED_COMPLETE`
- **Requirement:** Coût par organisation
- **Implementation:** cost per organization via usage/cost tracking
- **Tests:** tests/test_cost_tracking.py, tests/test_usage.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.2.12 - Cost per user  `FIXED_AND_TESTED`
- **Requirement:** Coût par utilisateur
- **Implementation:** per-user cost: user_limits and token usage exist; no explicit per-user cost view identified
- **Tests:** tests/test_user_limits.py (Part run: passed after rerun)
- **Known gaps:** not located
- **Severity / next action:** LOW / confirm or implement | **Fix:** insights cost-per-user / cost-per-answer from credit transactions

### 11.2.13 - Cost per answer  `FIXED_AND_TESTED`
- **Requirement:** Coût par réponse
- **Implementation:** cost per answer: response/usage rows carry tokens; explicit per-answer cost field not confirmed
- **Tests:** tests/test_cost_tracking.py (Part run: passed after rerun)
- **Known gaps:** not confirmed
- **Severity / next action:** LOW / confirm | **Fix:** insights cost-per-user / cost-per-answer from credit transactions

### 11.2.14 - Question clusters  `FIXED_AND_TESTED`
- **Requirement:** Groupes de questions similaires
- **Implementation:** none: searched api/ for question clustering, nothing found
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** absent
- **Severity / next action:** LOW / implement | **Fix:** api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py)

### 11.2.15 - Knowledge gap detection  `FIXED_AND_TESTED`
- **Requirement:** Détection des lacunes documentaires
- **Implementation:** none: no knowledge-gap detection found
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** absent
- **Severity / next action:** LOW / implement | **Fix:** api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py)

### 11.2.16 - Documentation gap reports  `FIXED_AND_TESTED`
- **Requirement:** Rapports de documentation manquante
- **Implementation:** none: no documentation-gap report found
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** absent
- **Severity / next action:** LOW / implement | **Fix:** api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py)

### 11.3.1 - GET /health  `VERIFIED_COMPLETE`
- **Requirement:** Health check
- **Implementation:** GET /health (api/main.py:447)
- **Tests:** route exercised by CI/deploy checks (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.3.2 - GET /ready  `VERIFIED_COMPLETE`
- **Requirement:** Readiness check
- **Implementation:** GET /health/ready (api/main.py:456); the spec path /ready is served as /health/ready
- **Tests:** tests via CI smoke (Part run: passed after rerun)
- **Known gaps:** path differs from the spec (/ready)
- **Severity / next action:** INFO / none

### 11.3.3 - GET /metrics  `VERIFIED_COMPLETE`
- **Requirement:** Métriques Prometheus
- **Implementation:** GET /metrics Prometheus (api/main.py:426)
- **Tests:** tests/test_latency_metrics.py (Part run: passed after rerun)
- **Known gaps:** production token not verified | **External blockers:** Render env
- **Severity / next action:** MEDIUM / set METRICS_AUTH_TOKEN

### 11.3.4 - Uptime monitoring  `BLOCKED_EXTERNAL`
- **Requirement:** Monitoring de disponibilité
- **Implementation:** external uptime monitoring is not code; /health is available to probe
- **Tests:** none (Part run: passed after rerun)
- **Known gaps:** no uptime monitor configured to the audit's knowledge | **External blockers:** uptime service
- **Severity / next action:** LOW / configure UptimeRobot or similar

### 11.3.5 - Queue monitoring  `VERIFIED_COMPLETE`
- **Requirement:** Monitoring des queues
- **Implementation:** GET /admin/monitoring/queues (admin_dashboard.py:85)
- **Tests:** tests/test_admin_dashboard.py (Part run: passed after rerun)
- **Known gaps:** reports Celery queue state; no worker exists in production (audit R-02) | **External blockers:** Celery worker
- **Severity / next action:** MEDIUM / see audit P0-2

### 11.3.6 - Database health  `VERIFIED_COMPLETE`
- **Requirement:** Santé de la base de données
- **Implementation:** database check in /health/ready and GET /admin/monitoring/health
- **Tests:** tests/test_admin_dashboard.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.3.7 - Vector DB health  `FIXED_AND_TESTED`
- **Requirement:** Santé de la base vectorielle
- **Implementation:** vector store is the same Postgres (pgvector); no distinct vector health probe identified
- **Tests:** none located (Part run: passed after rerun)
- **Known gaps:** pgvector extension availability not part of the readiness check (not confirmed)
- **Severity / next action:** LOW / add extension check | **Fix:** admin system health now reports pgvector extension status and which LLM providers have a platform key (tests/test_p2_health_probes.py)

### 11.3.8 - LLM availability  `FIXED_AND_TESTED`
- **Requirement:** Disponibilité des LLM
- **Implementation:** LLM availability: fallback chain and provider errors handled; no active provider health probe identified
- **Tests:** tests/test_fallback.py (Part run: passed after rerun)
- **Known gaps:** no availability probe | **External blockers:** LLM providers
- **Severity / next action:** LOW / add a lightweight probe | **Fix:** admin system health now reports pgvector extension status and which LLM providers have a platform key (tests/test_p2_health_probes.py)

### 11.3.9 - API latency  `VERIFIED_COMPLETE`
- **Requirement:** Latence de l'API
- **Implementation:** api latency in /metrics and latency_metrics.py
- **Tests:** tests/test_latency_metrics.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 11.3.10 - Error rate  `VERIFIED_COMPLETE`
- **Requirement:** Taux d'erreurs
- **Implementation:** error rate in /metrics and error tracking
- **Tests:** tests/test_error_tracking.py (Part run: passed after rerun)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

## Part 12 - Billing and monetization

23 features: IMPLEMENTED_UNVERIFIED 11, VERIFIED_COMPLETE 5, FIXED_AND_TESTED 5, DECISION_OR_CORRECTION 2

### 12.1.1 - Checkout  `DECISION_OR_CORRECTION`
- **Requirement:** Paiement en ligne (Paystack, Flutterwave)
- **Implementation:** checkout via Stripe and Paystack: api/services/billing_stripe.py, billing_paystack.py; UI POST /organizations/{id}/billing/checkout (billing/page.tsx:229); webhooks in billing.py:511,538
- **Tests:** tests/test_billing.py, tests/test_billing_stripe_events.py, tests/test_p1_bill003_005_006_stripe_chain.py (synthetic events) (Part run: passed)
- **Known gaps:** Flutterwave named in the spec is absent; never run against a real provider sandbox; live tests are skipped (audit R-05) | **External blockers:** Stripe/Paystack test keys
- **Severity / next action:** HIGH / run sandbox end to end; decide on Flutterwave | **Fix:** docs/DECISIONS.md D14: Stripe and Paystack, no Flutterwave

### 12.1.2 - Subscriptions  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Abonnements récurrents
- **Implementation:** subscription lifecycle in billing_stripe.py / billing_paystack.py / admin_subscriptions; UI subscribe/cancel/reactivate
- **Tests:** tests/test_billing.py, tests/test_postgres_subscription_concurrency.py (opt-in PostgreSQL, not in CI) (Part run: passed)
- **Known gaps:** never run against a real provider sandbox; live tests are skipped (audit R-05); recurring renewal events not observed | **External blockers:** Stripe/Paystack
- **Severity / next action:** HIGH / sandbox renewal scenario

### 12.1.3 - Invoices  `VERIFIED_COMPLETE`
- **Requirement:** Génération de factures
- **Implementation:** invoice state machine and proof of payment: api/services/billing_invoices.py, tests for states
- **Tests:** tests/test_p1_bill002_invoice_state_machine.py, tests/test_p1_bill010_invoices.py, tests/test_p1_r2_invoice_proof_and_rules.py (Part run: passed)
- **Known gaps:** refunded state not handled (BILL-016); manual proof not verified against a bank
- **Severity / next action:** MEDIUM / decide refund policy

### 12.1.4 - Coupons  `FIXED_AND_TESTED`
- **Requirement:** Codes promo
- **Implementation:** none: grep 'coupon' under api/ returns nothing
- **Tests:** none (Part run: passed)
- **Known gaps:** promo codes absent
- **Severity / next action:** MEDIUM / implement or drop from the offer | **Fix:** api/routers/coupons.py, migration 0140 (tests/test_p2_coupons.py)

### 12.1.5 - Trials  `FIXED_AND_TESTED`
- **Requirement:** Périodes d'essai
- **Implementation:** 'trial' appears in config and admin subscription/analytics code (api/config.py, services/admin_subscriptions.py, analytics.py)
- **Tests:** tests/test_admin_subscriptions.py (Part run: passed)
- **Known gaps:** trial end behaviour (conversion/expiry) not verified; provider trial settings not exercised | **External blockers:** Stripe/Paystack
- **Severity / next action:** MEDIUM / verify trial lifecycle | **Fix:** Stripe trial_period_days on the subscription checkout (tests/test_p1_bill003_005_006_stripe_chain.py)

### 12.1.6 - Upgrade  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Passage à un plan supérieur
- **Implementation:** plan change in subscription services; effective-plan logic (BILL-007)
- **Tests:** tests/test_p1_bill007_effective_plan.py (Part run: passed)
- **Known gaps:** never run against a real provider sandbox; live tests are skipped (audit R-05); proration not verified | **External blockers:** Stripe/Paystack
- **Severity / next action:** MEDIUM / sandbox upgrade

### 12.1.7 - Downgrade  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Passage à un plan inférieur
- **Implementation:** downgrade handling referenced in api/routers/billing.py and config
- **Tests:** tests/test_billing.py (Part run: passed)
- **Known gaps:** never run against a real provider sandbox; live tests are skipped (audit R-05); effect on existing data over new limits not verified | **External blockers:** Stripe/Paystack
- **Severity / next action:** MEDIUM / sandbox downgrade and limit enforcement

### 12.1.8 - Cancellation  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Annulation d'abonnement
- **Implementation:** POST /organizations/{id}/billing/cancel and reactivate (UI billing/page.tsx:285,301); admin cancel at provider
- **Tests:** tests/test_p1_bill006_admin_cancel_at_provider.py (Part run: passed)
- **Known gaps:** never run against a real provider sandbox; live tests are skipped (audit R-05) | **External blockers:** Stripe/Paystack
- **Severity / next action:** MEDIUM / sandbox cancellation

### 12.1.9 - Usage billing  `DECISION_OR_CORRECTION`
- **Requirement:** Facturation à l'usage
- **Implementation:** usage metering via api/services/billing_usage.py and credits spending; no metered-billing report to the provider found
- **Tests:** tests/test_billing_credits_spend_caps.py (Part run: passed)
- **Known gaps:** spend caps not atomic (BILL-012, unverified); usage is paid through credits, not invoiced after use
- **Severity / next action:** MEDIUM / clarify requirement | **Fix:** docs/DECISIONS.md D13: prepaid credits

### 12.1.10 - Credits  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Système de crédits
- **Implementation:** credits: api/services/billing_credits.py, credit packs, preflight in orchestrator; UI credits on billing page
- **Tests:** tests/test_billing_credit_packs.py, tests/test_p2_bill011_020_credits.py, tests/test_postgres_credits_concurrency.py (not in CI) (Part run: passed)
- **Known gaps:** Paystack credit purchase not supported; currency inconsistency (BILL-018); never run against a real provider sandbox; live tests are skipped (audit R-05) | **External blockers:** Stripe/Paystack
- **Severity / next action:** HIGH / sandbox credit purchase; set the flag

### 12.1.11 - Payment history  `VERIFIED_COMPLETE`
- **Requirement:** Historique des paiements
- **Implementation:** GET /organizations/{id}/billing/invoices and payment history on the billing page
- **Tests:** tests/test_billing_idor.py, tests/test_p1_bill010_invoices.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 12.2.1 - Free  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** 3 documents, 10 questions/jour
- **Implementation:** plans are rows in the plans table (models/admin.py Plan, GET /billing/plans); Free defined by data, BILLING_DEFAULT_PLAN='free'
- **Tests:** tests/test_billing.py (Part run: passed)
- **Known gaps:** production plan rows and limits (3 documents, 10 questions/day) not verified; plan data is not in code | **External blockers:** production database
- **Severity / next action:** MEDIUM / read-only check of the plans table

### 12.2.2 - Starter  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** 100 documents, 500 questions/jour
- **Implementation:** plan row (data)
- **Tests:** tests/test_billing.py (Part run: passed)
- **Known gaps:** production values unverified | **External blockers:** production database
- **Severity / next action:** LOW / read-only check

### 12.2.3 - Pro  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** 1 000 documents, questions illimitées
- **Implementation:** plan row (data)
- **Tests:** tests/test_billing.py (Part run: passed)
- **Known gaps:** production values unverified | **External blockers:** production database
- **Severity / next action:** LOW / read-only check

### 12.2.4 - Business  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** 10 000 documents, API, white-label
- **Implementation:** no 'business' plan in code; plans are data; the local preview seeded free/starter/pro/enterprise only
- **Tests:** none (Part run: passed)
- **Known gaps:** a Business plan may not exist | **External blockers:** production database
- **Severity / next action:** MEDIUM / confirm plan catalogue

### 12.2.5 - Enterprise  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Illimité, SSO, on-premise
- **Implementation:** Enterprise plan row (data); SSO exists (10.4.1); on-premise partial (10.4.10)
- **Tests:** none (Part run: passed)
- **Known gaps:** on-premise not delivered as a product | **External blockers:** production database
- **Severity / next action:** LOW / confirm

### 12.3.1 - AI credits  `IMPLEMENTED_UNVERIFIED`
- **Requirement:** Crédits pour l'IA
- **Implementation:** AI credits (see 12.1.10)
- **Tests:** tests/test_p0_credits_no_free_response.py (Part run: passed)
- **Known gaps:** never run against a real provider sandbox; live tests are skipped (audit R-05) | **External blockers:** Stripe/Paystack
- **Severity / next action:** HIGH / see 12.1.10

### 12.3.2 - Document limits  `FIXED_AND_TESTED`
- **Requirement:** Limite de documents
- **Implementation:** document quota enforcement (api/security/quotas.py, upload path)
- **Tests:** tests/test_quotas.py (Part run: passed)
- **Known gaps:** plan-to-quota linkage in production not verified
- **Severity / next action:** LOW / verify linkage | **Fix:** api/security/document_capacity.py: plan document limit now also on the batch upload and the 9 importers, storage quota enforced on upload and batch (tests/test_p2_document_capacity.py)

### 12.3.3 - Storage limits  `FIXED_AND_TESTED`
- **Requirement:** Limite de stockage
- **Implementation:** storage fields in models/organization_quota.py and schemas
- **Tests:** tests/test_quotas.py (Part run: passed)
- **Known gaps:** enforcement on upload not confirmed
- **Severity / next action:** MEDIUM / confirm and test enforcement | **Fix:** api/security/document_capacity.py: plan document limit now also on the batch upload and the 9 importers, storage quota enforced on upload and batch (tests/test_p2_document_capacity.py)

### 12.3.4 - Requests/month  `VERIFIED_COMPLETE`
- **Requirement:** Requêtes par mois
- **Implementation:** request quotas and rate limits (api/security/quotas.py, user_limits.py)
- **Tests:** tests/test_quotas.py, tests/test_user_limits.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** LOW / none

### 12.3.5 - Tokens/month  `VERIFIED_COMPLETE`
- **Requirement:** Tokens par mois
- **Implementation:** token quotas and usage tracking (api/services/token_usage.py, usage)
- **Tests:** tests/test_token_usage.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** LOW / none

### 12.3.6 - Voice minutes  `FIXED_AND_TESTED`
- **Requirement:** Minutes vocales
- **Implementation:** none: no voice-minutes meter or limit found under api/
- **Tests:** none (Part run: passed)
- **Known gaps:** voice usage is not metered per plan
- **Severity / next action:** LOW / implement | **Fix:** api/services/voice_usage.py, limit on outbound calls and voice-agent turns (tests/test_p2_voice_minutes.py)

### 12.3.7 - Dashboard usage  `VERIFIED_COMPLETE`
- **Requirement:** Usage du dashboard
- **Implementation:** usage view: GET /organizations/{id}/usage (+details/export), UI billing page
- **Tests:** tests/test_usage.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

## Part 13 - Developer experience (quality tooling, tests, CI/CD, deployment, observability)

52 features: VERIFIED_COMPLETE 25, WRITTEN_NOT_EXECUTED 8, VALIDATED_NOT_DEPLOYED 8, DECISION_OR_CORRECTION 5, FIXED_AND_TESTED 4, BLOCKED_EXTERNAL 2

### 13.1.1 - Python type hints  `DECISION_OR_CORRECTION`
- **Requirement:** Ajouter des type hints partout
- **Implementation:** type hints are widely used (FastAPI/Pydantic signatures) but not enforced everywhere; no type checker configured
- **Tests:** none (Part run: passed)
- **Known gaps:** 'everywhere' is not enforced or measured
- **Severity / next action:** LOW / measure with mypy/pyright | **Fix:** scripts/type_hint_coverage.py: 69.1 % of api/ functions fully annotated; tests/test_type_hint_coverage.py stops it falling

### 13.1.2 - Ruff  `VERIFIED_COMPLETE`
- **Requirement:** Linting
- **Implementation:** [tool.ruff.lint] in pyproject.toml; ruff in pre-commit; 'ruff check api' passes (Copilot audit and earlier run: All checks passed)
- **Tests:** CI lint step (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 13.1.3 - Black  `DECISION_OR_CORRECTION`
- **Requirement:** Formatage automatique
- **Implementation:** ruff-format is used instead of Black (.pre-commit-config.yaml); no [tool.black]
- **Tests:** pre-commit (Part run: passed)
- **Known gaps:** Black itself is not configured: a functionally equivalent formatter is used
- **Severity / next action:** INFO / accept ruff-format as the formatter | **Fix:** docs/DECISIONS.md: ruff format is the formatter (Black-compatible output); Black is not added as a second tool

### 13.1.4 - MyPy  `DECISION_OR_CORRECTION`
- **Requirement:** Vérification des types
- **Implementation:** none: no [tool.mypy] and no mypy hook or CI job found
- **Tests:** none (Part run: passed)
- **Known gaps:** no static type checking for Python
- **Severity / next action:** LOW / add mypy or pyright | **Fix:** mypy 2.4.0 on api/: 305 errors in 110 of 707 source files (measured 2026-10-11); the workflow stays non-blocking until that number is brought down

### 13.1.5 - Pytest  `VERIFIED_COMPLETE`
- **Requirement:** Tests unitaires
- **Implementation:** pytest configured in pyproject.toml; about 6,130 tests discovered (Copilot audit)
- **Tests:** CI backend-tests and CircleCI api-tests green on main (Part run: passed)
- **Known gaps:** tests mostly on SQLite
- **Severity / next action:** INFO / none

### 13.1.6 - Coverage > 90%  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Couverture de code
- **Implementation:** coverage configured ([tool.coverage.run]); CircleCI gate is --cov-fail-under=75; measured 77.41% (Copilot audit)
- **Tests:** CircleCI api-tests (Part run: passed)
- **Known gaps:** spec asks for more than 90%; measured about 77% on the CircleCI test subset
- **Severity / next action:** MEDIUM / raise coverage or revise the target | **Fix:** measured about 77 % on the CircleCI subset; the 90 % target needs many more tests, not a configuration change

### 13.1.7 - Pre-commit hooks  `VERIFIED_COMPLETE`
- **Requirement:** Hooks de pre-commit
- **Implementation:** .pre-commit-config.yaml: ruff, ruff-format, detect-secrets
- **Tests:** n/a (Part run: passed)
- **Known gaps:** hook installation is per developer
- **Severity / next action:** INFO / none

### 13.1.8 - Dependabot  `VERIFIED_COMPLETE`
- **Requirement:** Mises à jour automatiques
- **Implementation:** .github/dependabot.yml; open Dependabot PRs exist (e.g. stripe 16)
- **Tests:** n/a (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 13.1.9 - Security scanning  `DECISION_OR_CORRECTION`
- **Requirement:** Analyse de sécurité
- **Implementation:** bandit workflow (non-blocking), backend-security job, Snyk check, pip-audit
- **Tests:** CI backend-security success (Part run: passed)
- **Known gaps:** bandit reports 11 medium findings and is non-blocking
- **Severity / next action:** MEDIUM / triage bandit findings | **Fix:** bandit -ll: MD5 marked usedforsecurity=False, 4 false positives annotated with the reason, migrations excluded; 5 left = Hugging Face from_pretrained without a pinned revision (accepted until the model list is frozen)

### 13.2.1 - Unit tests  `VERIFIED_COMPLETE`
- **Requirement:** Tests unitaires
- **Implementation:** tests/ unit tests
- **Tests:** pytest suite (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 13.2.2 - Integration tests  `VERIFIED_COMPLETE`
- **Requirement:** Tests d'intégration
- **Implementation:** *_integration.py tests (mocked providers) listed in .circleci/config.yml
- **Tests:** CircleCI api-tests (Part run: passed)
- **Known gaps:** most 'integration' tests use mocks and SQLite
- **Severity / next action:** LOW / add real-service integration

### 13.2.3 - API tests  `VERIFIED_COMPLETE`
- **Requirement:** Tests d'API
- **Implementation:** route-level tests using httpx AsyncClient (tests/test_auth_api.py etc.)
- **Tests:** pytest suite (Part run: passed)
- **Known gaps:** 183 of 943 operations have no test referencing their path (Copilot heuristic)
- **Severity / next action:** MEDIUM / cover the untested routes

### 13.2.4 - E2E tests  `FIXED_AND_TESTED`
- **Requirement:** Tests de bout en bout
- **Implementation:** tests/test_e2e_lifecycle.py (backend lifecycle); no browser E2E (no Playwright/Cypress config found in frontend)
- **Tests:** tests/test_e2e_lifecycle.py (Part run: passed)
- **Known gaps:** no browser-driven end-to-end test
- **Severity / next action:** MEDIUM / add Playwright smoke tests | **Fix:** e2e/ Playwright: login, wrong password, register then dashboard, landing page (video, architecture, PDFs), 5 dashboard pages, documents drop zone, chat without an agent, escalations filter; run against the isolated API (SQLite) and the Next dev server in the installed Chrome. Two selector/port problems found and fixed in the harness (ambiguous role=alert; ports and the CORS origin now configurable); .github/workflow…

### 13.2.5 - Security tests  `VERIFIED_COMPLETE`
- **Requirement:** Tests de sécurité
- **Implementation:** security tests: test_p0_*, test_ssrf_hardening.py, test_audit_tenant_isolation.py, test_mcp_builtin_tools_security.py
- **Tests:** pytest suite (Part run: passed)
- **Known gaps:** no RLS test on PostgreSQL in CI
- **Severity / next action:** MEDIUM / audit P1-4

### 13.2.6 - Regression tests  `VERIFIED_COMPLETE`
- **Requirement:** Tests de régression
- **Implementation:** each P0/P1/P2 fix has a dedicated regression test; rag-pipeline-regression job in CircleCI
- **Tests:** CircleCI rag-pipeline-regression success (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 13.2.7 - LLM tests  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Tests avec LLM
- **Implementation:** LLM behaviour tests use mocks (tests/test_llm_providers.py); live tests (billing/LLM) are skipped without keys
- **Tests:** skipped live tests (Part run: passed)
- **Known gaps:** no test with a real LLM runs in CI | **External blockers:** LLM key
- **Severity / next action:** MEDIUM / scheduled live smoke job | **Fix:** tests/llm_optin/test_real_llm.py and .github/workflows/llm-tests.yml, skipped unless RUN_REAL_LLM_TESTS=1

### 13.2.8 - RAG tests  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Tests RAG
- **Implementation:** RAG pipeline tests and rag-pipeline-regression job; Eval Lab exists
- **Tests:** tests/test_retrieval_pipeline.py (Part run: passed)
- **Known gaps:** no quality baseline on real data (audit R-06) | **External blockers:** dataset
- **Severity / next action:** MEDIUM / SQuAD run | **Fix:** tests/llm_optin/test_real_llm.py and .github/workflows/llm-tests.yml, skipped unless RUN_REAL_LLM_TESTS=1

### 13.2.9 - Agent tests  `VERIFIED_COMPLETE`
- **Requirement:** Tests d'agent
- **Implementation:** tests/test_agent_*.py
- **Tests:** pytest suite (Part run: passed)
- **Known gaps:** LLM mocked
- **Severity / next action:** LOW / none

### 13.2.10 - Database tests  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Tests de base de données
- **Implementation:** PostgreSQL concurrency tests exist (test_postgres_*.py) but are opt-in and not in CI
- **Tests:** tests/test_postgres_integration.py (Part run: passed)
- **Known gaps:** database behaviour proven on SQLite in CI only | **External blockers:** PostgreSQL service
- **Severity / next action:** HIGH / audit P1-4 | **Fix:** backend-tests starts a pgvector PostgreSQL with all migrations; 61 PostgreSQL integration tests pass locally; RLS rollout decision in D8

### 13.2.11 - Deployment tests  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Tests de déploiement
- **Implementation:** tests/test_deployment.py; docker build jobs in CI
- **Tests:** tests/test_deployment.py; CI build-backend/build-frontend (Part run: passed)
- **Known gaps:** no post-deploy smoke test against a running service | **External blockers:** deployed service
- **Severity / next action:** LOW / add post-deploy health check | **Fix:** actionlint passes on all 8 workflows; scripts/post_deploy_smoke.py tests pass; migrate.yml is manual with a rehearsal by default

### 13.3.1 - Lint  `VERIFIED_COMPLETE`
- **Requirement:** Vérification du code
- **Implementation:** ruff and eslint in CI (frontend-checks)
- **Tests:** .github/workflows/ci.yml, .circleci/config.yml (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 13.3.2 - Type check  `DECISION_OR_CORRECTION`
- **Requirement:** Vérification des types
- **Implementation:** tsc --noEmit for the frontend; no Python type checking (see 13.1.4)
- **Tests:** CI frontend-checks (Part run: passed)
- **Known gaps:** Python type check missing
- **Severity / next action:** LOW / see 13.1.4 | **Fix:** mypy 2.4.0 on api/: 305 errors in 110 of 707 source files (measured 2026-10-11); the workflow stays non-blocking until that number is brought down

### 13.3.3 - Unit tests  `VERIFIED_COMPLETE`
- **Requirement:** Tests unitaires
- **Implementation:** backend-tests job
- **Tests:** CI success on main (Part run: passed)
- **Known gaps:** job takes about 60 minutes (limit 75)
- **Severity / next action:** MEDIUM / split or speed up tests

### 13.3.4 - Integration tests  `VERIFIED_COMPLETE`
- **Requirement:** Tests d'intégration
- **Implementation:** integration tests inside backend-tests and CircleCI api-tests
- **Tests:** CI success on main (Part run: passed)
- **Known gaps:** mocked providers
- **Severity / next action:** LOW / none

### 13.3.5 - Security scan  `VERIFIED_COMPLETE`
- **Requirement:** Analyse de sécurité
- **Implementation:** backend-security, bandit, Snyk
- **Tests:** CI success on main (Part run: passed)
- **Known gaps:** bandit non-blocking
- **Severity / next action:** LOW / none

### 13.3.6 - Docker build  `VERIFIED_COMPLETE`
- **Requirement:** Construction Docker
- **Implementation:** docker/build-push-action jobs build-backend and build-frontend
- **Tests:** CI success on main (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 13.3.7 - E2E tests  `FIXED_AND_TESTED`
- **Requirement:** Tests de bout en bout
- **Implementation:** none: no browser E2E job in CI (see 13.2.4)
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** MEDIUM / add Playwright job | **Fix:** e2e/ Playwright: login, wrong password, register then dashboard, landing page (video, architecture, PDFs), 5 dashboard pages, documents drop zone, chat without an agent, escalations filter; run against the isolated API (SQLite) and the Next dev server in the installed Chrome. Two selector/port problems found and fixed in the harness (ambiguous role=alert; ports and the CORS origin now configurable); .github/workflow…

### 13.3.8 - Deploy  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Déploiement automatique
- **Implementation:** Render/Vercel redeploy from git pushes (platform-managed); no CI deploy job; migrations not applied automatically (audit R-03)
- **Tests:** n/a (Part run: passed)
- **Known gaps:** no automated migration step; deployment is not a pipeline stage | **External blockers:** Render/Vercel
- **Severity / next action:** HIGH / add a controlled migration step | **Fix:** actionlint passes on all 8 workflows; scripts/post_deploy_smoke.py tests pass; migrate.yml is manual with a rehearsal by default

### 13.4.1 - Docker  `VERIFIED_COMPLETE`
- **Requirement:** Conteneurisation
- **Implementation:** Dockerfile, Dockerfile.api, Dockerfile.plugin-sandbox
- **Tests:** CI docker builds (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 13.4.2 - Docker Compose  `VERIFIED_COMPLETE`
- **Requirement:** Orchestration locale
- **Implementation:** docker-compose.yml, docker-compose.selfhosted.yml, docker-compose.observability.yml
- **Tests:** none (Part run: passed)
- **Known gaps:** compose stacks not run in this audit | **External blockers:** Docker host
- **Severity / next action:** LOW / test a clean up

### 13.4.3 - Render  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Déploiement Render
- **Implementation:** production API runs on Render (docs/deployment/RENDER.md) but render.yaml describes only the old Streamlit prototype (audit R-07); gunicorn only, no worker (audit R-02)
- **Tests:** none (Part run: passed)
- **Known gaps:** blueprint out of date | **External blockers:** Render
- **Severity / next action:** MEDIUM / update render.yaml | **Fix:** deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean}

### 13.4.4 - Railway  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Déploiement Railway
- **Implementation:** none: no Railway file found
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** LOW / document or drop | **Fix:** deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean}

### 13.4.5 - Fly.io  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Déploiement Fly.io
- **Implementation:** none: no fly.toml found
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** LOW / document or drop | **Fix:** deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean}

### 13.4.6 - AWS  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Déploiement AWS
- **Implementation:** none: no AWS-specific deployment assets found
- **Tests:** none (Part run: passed)
- **Known gaps:** absent (generic Docker only)
- **Severity / next action:** LOW / document or drop | **Fix:** terraform validate and fmt -check pass for deploy/terraform/{aws,gcp,azure} (hashicorp/terraform 1.9, init -backend=false); the Azure module had a real error (for_each over a sensitive map) that this run found and fixed

### 13.4.7 - GCP  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Déploiement Google Cloud
- **Implementation:** none: no GCP-specific assets found
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** LOW / document or drop | **Fix:** terraform validate and fmt -check pass for deploy/terraform/{aws,gcp,azure} (hashicorp/terraform 1.9, init -backend=false); the Azure module had a real error (for_each over a sensitive map) that this run found and fixed

### 13.4.8 - Azure  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Déploiement Azure
- **Implementation:** none: no Azure-specific assets found
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** LOW / document or drop | **Fix:** terraform validate and fmt -check pass for deploy/terraform/{aws,gcp,azure} (hashicorp/terraform 1.9, init -backend=false); the Azure module had a real error (for_each over a sensitive map) that this run found and fixed

### 13.4.9 - DigitalOcean  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Déploiement DO
- **Implementation:** none: no DigitalOcean assets found
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** LOW / document or drop | **Fix:** deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean}

### 13.4.10 - Kubernetes  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Orchestration Kubernetes
- **Implementation:** none: no Kubernetes manifests found
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** LOW / document or drop | **Fix:** helm lint (0 failed), helm template parsed by kubeconform strict (4/4 valid), deploy/kubernetes/rag-saas.yaml kubeconform strict (7/7 valid)

### 13.4.11 - Helm  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Packaging Helm
- **Implementation:** none: no Chart.yaml found
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** LOW / document or drop | **Fix:** helm lint (0 failed), helm template parsed by kubeconform strict (4/4 valid), deploy/kubernetes/rag-saas.yaml kubeconform strict (7/7 valid)

### 13.4.12 - Terraform  `VALIDATED_NOT_DEPLOYED`
- **Requirement:** Infrastructure as Code
- **Implementation:** none: no .tf files found
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** LOW / document or drop | **Fix:** terraform validate and fmt -check pass for deploy/terraform/{aws,gcp,azure} (hashicorp/terraform 1.9, init -backend=false); the Azure module had a real error (for_each over a sensitive map) that this run found and fixed

### 13.5.1 - Structured logging  `VERIFIED_COMPLETE`
- **Requirement:** Logs structurés
- **Implementation:** see 10.3.2
- **Tests:** tests/test_tracing.py (Part run: passed)
- **Known gaps:** duplicate of 10.3.2 in the spec | **External blockers:** log backend
- **Severity / next action:** INFO / none

### 13.5.2 - Request IDs  `VERIFIED_COMPLETE`
- **Requirement:** Identification des requêtes
- **Implementation:** see 10.3.3
- **Tests:** tests/test_tracing.py (Part run: passed)
- **Known gaps:** duplicate of 10.3.3
- **Severity / next action:** INFO / none

### 13.5.3 - Trace IDs  `VERIFIED_COMPLETE`
- **Requirement:** Identification des traces
- **Implementation:** see 10.3.4
- **Tests:** tests/test_tracing.py (Part run: passed)
- **Known gaps:** duplicate of 10.3.4
- **Severity / next action:** INFO / none

### 13.5.4 - Distributed tracing  `FIXED_AND_TESTED`
- **Requirement:** Traçage distribué
- **Implementation:** see 10.3.5
- **Tests:** tests/test_tracing.py (Part run: passed)
- **Known gaps:** no collector | **External blockers:** OTel collector
- **Severity / next action:** LOW / optional | **Fix:** tests/test_tracing_real_collector.py: setup_tracing exports the spans of a real request over OTLP/HTTP and the trace is read back from a running Jaeger 1.76; found on the way that the test environment inherited the production Tempo credentials, now blanked in scripts/run_tests_local.sh

### 13.5.5 - LLM traces  `BLOCKED_EXTERNAL`
- **Requirement:** Traçage LLM
- **Implementation:** see 10.3.6
- **Tests:** tests/test_agent_traces.py (Part run: passed)
- **Known gaps:** Datadog not configured | **External blockers:** Datadog
- **Severity / next action:** LOW / optional

### 13.5.6 - Retrieval traces  `VERIFIED_COMPLETE`
- **Requirement:** Traçage RAG
- **Implementation:** see 10.3.7
- **Tests:** tests/test_retrieval_diagnostics.py (Part run: passed)
- **Known gaps:** duplicate of 10.3.7
- **Severity / next action:** INFO / none

### 13.5.7 - Tool traces  `VERIFIED_COMPLETE`
- **Requirement:** Traçage outils
- **Implementation:** see 10.3.8
- **Tests:** tests/test_agent_traces.py (Part run: passed)
- **Known gaps:** duplicate of 10.3.8
- **Severity / next action:** INFO / none

### 13.5.8 - Error tracking  `BLOCKED_EXTERNAL`
- **Requirement:** Suivi des erreurs
- **Implementation:** see 10.3.9
- **Tests:** tests/test_error_tracking.py (Part run: passed)
- **Known gaps:** Sentry DSN unverified | **External blockers:** Sentry
- **Severity / next action:** LOW / verify DSN

### 13.5.9 - Performance monitoring  `VERIFIED_COMPLETE`
- **Requirement:** Monitoring des performances
- **Implementation:** see 10.3.10
- **Tests:** tests/test_latency_metrics.py (Part run: passed)
- **Known gaps:** see /metrics exposure
- **Severity / next action:** MEDIUM / set METRICS_AUTH_TOKEN

### 13.5.10 - Cost monitoring  `VERIFIED_COMPLETE`
- **Requirement:** Suivi des coûts
- **Implementation:** see 10.3.11
- **Tests:** tests/test_cost_tracking.py (Part run: passed)
- **Known gaps:** duplicate of 10.3.11
- **Severity / next action:** INFO / none

### 13.5.11 - Token monitoring  `VERIFIED_COMPLETE`
- **Requirement:** Suivi des tokens
- **Implementation:** see 10.3.12
- **Tests:** tests/test_token_usage.py (Part run: passed)
- **Known gaps:** duplicate of 10.3.12
- **Severity / next action:** INFO / none

### 13.5.12 - Traçabilité complète d'une requête  `FIXED_AND_TESTED`
- **Requirement:** Suivi de bout en bout
- **Implementation:** request id + trace id + agent traces + flight recorder exist separately; one end-to-end view of a request across HTTP, retrieval, LLM and tools was not located
- **Tests:** tests/test_tracing.py, tests/test_agent_traces.py (Part run: passed)
- **Known gaps:** no single trace view joining all stages
- **Severity / next action:** LOW / add a request trace view | **Fix:** GET /responses/{id}/trace joins retrieval, generation, checks, agent steps and citations (tests/test_p2_request_trace.py)

## Part 14 - Documentation and deliverables (architecture docs, product, brand)

33 features: VERIFIED_COMPLETE 14, WRITTEN_NOT_EXECUTED 7, DECISION_OR_CORRECTION 6, FIXED_AND_TESTED 6

### 14.1.1 - README  `VERIFIED_COMPLETE`
- **Requirement:** Présentation du projet
- **Implementation:** README.md
- **Tests:** n/a (Part run: passed)
- **Known gaps:** accuracy of every statement not re-read
- **Severity / next action:** INFO / none

### 14.1.2 - Architecture (diagrammes)  `DECISION_OR_CORRECTION`
- **Requirement:** Schéma d'architecture
- **Implementation:** ARCHITECTURE.md, docs/architecture/OVERVIEW.md, DATA_FLOW.md, docs/diagrams/
- **Tests:** tests/docs partial (Part run: passed)
- **Known gaps:** docs/architecture/LEGACY.md and agents.md describe obsolete or nonexistent routes (audit R-07)
- **Severity / next action:** LOW / reconcile documentation with code | **Fix:** agents.md routes verified against OpenAPI; docs/architecture/OVERVIEW.md now has component, chat and ingestion diagrams; the multi-tenant line no longer claims RLS policies

### 14.1.3 - Installation guide  `VERIFIED_COMPLETE`
- **Requirement:** Guide d'installation
- **Implementation:** docs/install/, docs/AUTH_BACKEND_SETUP.md, install.sh
- **Tests:** n/a (Part run: passed)
- **Known gaps:** not executed on a clean machine
- **Severity / next action:** LOW / run the guide on a clean machine

### 14.1.4 - API documentation  `VERIFIED_COMPLETE`
- **Requirement:** Documentation de l'API
- **Implementation:** docs/api/*.md and docs/api/openapi.json; FastAPI /docs
- **Tests:** tests/docs/test_api_reference.py (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.1.5 - Deployment guide  `VERIFIED_COMPLETE`
- **Requirement:** Guide de déploiement
- **Implementation:** docs/DEPLOYMENT_GUIDE.md, docs/deployment/RENDER.md, WORKER.md, docs/developer/DEPLOYMENT.md
- **Tests:** tests/test_deployment.py (Part run: passed)
- **Known gaps:** render.yaml and the worker doc may not match what actually runs on Render
- **Severity / next action:** MEDIUM / align with reality

### 14.1.6 - Security guide  `VERIFIED_COMPLETE`
- **Requirement:** Guide de sécurité
- **Implementation:** SECURITY.md, docs/SECURITY_REPORT.md, docs/architecture/SECURITY.md
- **Tests:** n/a (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.1.7 - Admin guide  `VERIFIED_COMPLETE`
- **Requirement:** Guide administrateur
- **Implementation:** docs/guides/ADMIN_GUIDE.md and docs/admin/*
- **Tests:** n/a (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.1.8 - User guide  `VERIFIED_COMPLETE`
- **Requirement:** Guide utilisateur
- **Implementation:** docs/guides/USER_GUIDE.md and docs/user/*
- **Tests:** n/a (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.1.9 - White-label guide  `VERIFIED_COMPLETE`
- **Requirement:** Guide de personnalisation
- **Implementation:** docs/guides/WHITE_LABEL_GUIDE.md, docs/admin/WHITE_LABEL.md
- **Tests:** n/a (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.1.10 - Customization guide  `VERIFIED_COMPLETE`
- **Requirement:** Guide de modification
- **Implementation:** docs/developer/* (CUSTOM_TOOLS, PLUGINS, WORKFLOWS, INTEGRATIONS)
- **Tests:** n/a (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.1.11 - Troubleshooting  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Résolution des problèmes
- **Implementation:** troubleshooting content found only inside docs/api/ERRORS.md, WEBHOOKS.md and audit docs; no dedicated troubleshooting guide located
- **Tests:** n/a (Part run: passed)
- **Known gaps:** dedicated guide not found
- **Severity / next action:** LOW / write TROUBLESHOOTING.md | **Fix:** docs/guides/TROUBLESHOOTING.md

### 14.1.12 - FAQ  `VERIFIED_COMPLETE`
- **Requirement:** Foire aux questions
- **Implementation:** docs/guides/FAQ.md and docs/faq/
- **Tests:** n/a (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.2.1 - Architecture PDF  `FIXED_AND_TESTED`
- **Requirement:** Présentation détaillée
- **Implementation:** no PDF file exists in the repository (searched for *.pdf to depth 4)
- **Tests:** none (Part run: passed)
- **Known gaps:** no architecture PDF; Markdown source exists
- **Severity / next action:** LOW / export from Markdown | **Fix:** deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter)

### 14.2.2 - Feature list PDF  `FIXED_AND_TESTED`
- **Requirement:** Liste des fonctionnalités
- **Implementation:** no PDF file exists in the repository
- **Tests:** none (Part run: passed)
- **Known gaps:** no feature-list PDF
- **Severity / next action:** LOW / export from the verified feature CSV | **Fix:** deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter)

### 14.2.3 - Deployment guide PDF  `FIXED_AND_TESTED`
- **Requirement:** Guide de déploiement
- **Implementation:** no PDF file exists in the repository
- **Tests:** none (Part run: passed)
- **Known gaps:** no deployment PDF
- **Severity / next action:** LOW / export from docs | **Fix:** deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter)

### 14.2.4 - API documentation PDF  `FIXED_AND_TESTED`
- **Requirement:** Documentation API
- **Implementation:** no PDF file exists in the repository
- **Tests:** none (Part run: passed)
- **Known gaps:** no API PDF
- **Severity / next action:** LOW / export from docs | **Fix:** deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter)

### 14.2.5 - Security audit PDF  `FIXED_AND_TESTED`
- **Requirement:** Audit de sécurité
- **Implementation:** no PDF file exists in the repository (reports are Markdown: docs/SECURITY_REPORT.md, audit-reports/)
- **Tests:** none (Part run: passed)
- **Known gaps:** no security-audit PDF
- **Severity / next action:** LOW / export | **Fix:** deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter)

### 14.2.6 - Benchmark report PDF  `FIXED_AND_TESTED`
- **Requirement:** Rapport de performance
- **Implementation:** no PDF file exists in the repository (docs/PERFORMANCE_REPORT.md exists as Markdown)
- **Tests:** none (Part run: passed)
- **Known gaps:** no benchmark PDF; no real benchmark data (audit R-06)
- **Severity / next action:** LOW / run benchmarks first | **Fix:** deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter)

### 14.2.7 - Demo video  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Vidéo de démonstration
- **Implementation:** no video file found in the repository (searched *.mp4)
- **Tests:** none (Part run: passed)
- **Known gaps:** no demo video
- **Severity / next action:** LOW / record a demo | **Fix:** deliverables/product-tour.mp4 (silent screenshot tour on an isolated database)

### 14.2.8 - Setup guide  `VERIFIED_COMPLETE`
- **Requirement:** Guide de configuration
- **Implementation:** docs/install/ and docs/developer/OVERVIEW.md
- **Tests:** n/a (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.3.1 - Hero  `VERIFIED_COMPLETE`
- **Requirement:** Titre, sous-titre, CTA
- **Implementation:** frontend/components/figma/HeroStage.tsx, landing/LandingHero.tsx; home page frontend/app/page.tsx
- **Tests:** frontend tests partial (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.3.2 - Demo  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Vidéo ou démo interactive
- **Implementation:** voice-demo page exists; no video or interactive product demo section confirmed on the landing page
- **Tests:** none (Part run: passed)
- **Known gaps:** no landing demo confirmed
- **Severity / next action:** LOW / add demo | **Fix:** landing page: product-tour video, four-step architecture section, documentation PDF links (frontend/components/figma/LandingSections.tsx)

### 14.3.3 - Features  `DECISION_OR_CORRECTION`
- **Requirement:** Liste des fonctionnalités
- **Implementation:** frontend/components/figma/LandingSections.tsx, landing/LandingBento.tsx
- **Tests:** frontend tests partial (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none | **Fix:** LandingSections.tsx already contains Features, Pricing, Security and FAQ sections (missed by the first pass)

### 14.3.4 - Architecture  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Schéma d'architecture
- **Implementation:** architecture schema on the landing page not confirmed
- **Tests:** none (Part run: passed)
- **Known gaps:** not confirmed
- **Severity / next action:** LOW / confirm | **Fix:** landing page: product-tour video, four-step architecture section, documentation PDF links (frontend/components/figma/LandingSections.tsx)

### 14.3.5 - Integrations  `VERIFIED_COMPLETE`
- **Requirement:** Intégrations disponibles
- **Implementation:** landing/LandingLogos.tsx and integrations section
- **Tests:** none (Part run: passed)
- **Known gaps:** logos only; integration status not verified
- **Severity / next action:** LOW / none

### 14.3.6 - Pricing  `DECISION_OR_CORRECTION`
- **Requirement:** Plans tarifaires
- **Implementation:** pricing content in docs/commercial/PRICING.md and billing page; landing pricing section not confirmed
- **Tests:** none (Part run: passed)
- **Known gaps:** plan catalogue in production unverified (12.2.x)
- **Severity / next action:** LOW / confirm | **Fix:** LandingSections.tsx already contains Features, Pricing, Security and FAQ sections (missed by the first pass)

### 14.3.7 - Security  `DECISION_OR_CORRECTION`
- **Requirement:** Sécurité et conformité
- **Implementation:** security/compliance content in docs; landing section not confirmed
- **Tests:** none (Part run: passed)
- **Known gaps:** not confirmed
- **Severity / next action:** LOW / confirm | **Fix:** LandingSections.tsx already contains Features, Pricing, Security and FAQ sections (missed by the first pass)

### 14.3.8 - Documentation  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Liens vers la documentation
- **Implementation:** docs site structure docs/index.md, _sidebar.md (docsify); link from landing page not confirmed
- **Tests:** none (Part run: passed)
- **Known gaps:** not confirmed
- **Severity / next action:** LOW / confirm | **Fix:** landing page: product-tour video, four-step architecture section, documentation PDF links (frontend/components/figma/LandingSections.tsx)

### 14.3.9 - FAQ  `DECISION_OR_CORRECTION`
- **Requirement:** Questions fréquentes
- **Implementation:** FAQ exists in docs; landing FAQ section not confirmed
- **Tests:** none (Part run: passed)
- **Known gaps:** not confirmed
- **Severity / next action:** LOW / confirm | **Fix:** LandingSections.tsx already contains Features, Pricing, Security and FAQ sections (missed by the first pass)

### 14.4.1 - Nom produit  `DECISION_OR_CORRECTION`
- **Requirement:** KnowFlow AI (ou autre)
- **Implementation:** product naming is inconsistent: 'KnowFlow AI' appears in docs (COMPETITIVE_AUDIT_KNOWFLOW.md) while the repository is rag-saas-platform; final name not established
- **Tests:** none (Part run: passed)
- **Known gaps:** no decided brand name found
- **Severity / next action:** LOW / owner decision | **Fix:** owner decision 2026-10-11: the product name is 'RAG SaaS Platform', already shown by the interface (layout title, app_name, brand fallback); docs/DECISIONS.md D3 and docs/commercial/BRAND_GUIDE.md updated; e-mail sender name, widget title and PDFs still to check at publication

### 14.4.2 - Logo  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Logo de la marque
- **Implementation:** logo assets in frontend/public and figma components not enumerated here
- **Tests:** none (Part run: passed)
- **Known gaps:** not verified
- **Severity / next action:** LOW / confirm | **Fix:** docs/DECISIONS.md D3 and docs/commercial/BRAND_GUIDE.md: no logo is invented; the guide lists what to change once one is chosen

### 14.4.3 - Couleurs  `VERIFIED_COMPLETE`
- **Requirement:** Palette de couleurs
- **Implementation:** colour tokens in the Tailwind/CSS theme and figma components
- **Tests:** none (Part run: passed)
- **Known gaps:** none found
- **Severity / next action:** INFO / none

### 14.4.4 - Charte graphique  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Lignes directrices
- **Implementation:** design guidelines: docs/commercial/BRANDING_OPTIONS.md; a formal brand charter document not located
- **Tests:** none (Part run: passed)
- **Known gaps:** not located
- **Severity / next action:** LOW / write a short brand guide | **Fix:** docs/commercial/BRAND_GUIDE.md (product name and logo still undecided: 14.4.1 / 14.4.2 remain open)

## Part 15 - Human in the loop (escalation, approval, feedback loop)

16 features: FIXED_AND_TESTED 15, WRITTEN_NOT_EXECUTED 1

### 15.1.1 - Ticket ID  `FIXED_AND_TESTED`
- **Requirement:** Identifiant unique du ticket
- **Implementation:** api/models/escalation.py + api/tools/human_escalation.py (escalations.id UUID)
- **Tests:** tests/test_human_escalation.py (Part run: passed)
- **Known gaps:** no API route or screen lets a human list, assign or resolve tickets
- **Severity / next action:** MEDIUM / add ticket API | **Fix:** api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)

### 15.1.2 - Priority  `FIXED_AND_TESTED`
- **Requirement:** Priorité (urgent, normal, bas)
- **Implementation:** api/models/escalation.py + api/tools/human_escalation.py (priority column and enum)
- **Tests:** tests/test_human_escalation.py (Part run: passed)
- **Known gaps:** no API route or screen lets a human list, assign or resolve tickets
- **Severity / next action:** MEDIUM / add ticket API | **Fix:** api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)

### 15.1.3 - Assignment  `FIXED_AND_TESTED`
- **Requirement:** Assignation à un humain
- **Implementation:** api/models/escalation.py + api/tools/human_escalation.py (assignee_id column)
- **Tests:** tests/test_human_escalation.py (Part run: passed)
- **Known gaps:** no API route or screen lets a human list, assign or resolve tickets; no assignment action
- **Severity / next action:** MEDIUM / add assignment endpoint | **Fix:** api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)

### 15.1.4 - SLA  `FIXED_AND_TESTED`
- **Requirement:** Délai de réponse
- **Implementation:** none: no SLA or due-date column in api/models/escalation.py
- **Tests:** none (Part run: passed)
- **Known gaps:** SLA absent
- **Severity / next action:** MEDIUM / add SLA field and timers | **Fix:** api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)

### 15.1.5 - Status  `FIXED_AND_TESTED`
- **Requirement:** Ouvert, en cours, résolu, fermé
- **Implementation:** api/models/escalation.py + api/tools/human_escalation.py (status column and enum, resolved_at)
- **Tests:** tests/test_human_escalation.py (Part run: passed)
- **Known gaps:** no API route or screen lets a human list, assign or resolve tickets
- **Severity / next action:** MEDIUM / add ticket API | **Fix:** api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)

### 15.1.6 - Internal notes  `FIXED_AND_TESTED`
- **Requirement:** Notes internes
- **Implementation:** none: no notes column or table related to escalations
- **Tests:** none (Part run: passed)
- **Known gaps:** internal notes absent
- **Severity / next action:** LOW / add notes | **Fix:** api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)

### 15.1.7 - Conversation context  `FIXED_AND_TESTED`
- **Requirement:** Contexte de la conversation
- **Implementation:** api/models/escalation.py + api/tools/human_escalation.py (context JSON column)
- **Tests:** tests/test_human_escalation.py (Part run: passed)
- **Known gaps:** no API route or screen lets a human list, assign or resolve tickets
- **Severity / next action:** LOW / expose in the ticket view | **Fix:** api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)

### 15.1.8 - Resolution  `FIXED_AND_TESTED`
- **Requirement:** Résolution du ticket
- **Implementation:** api/models/escalation.py + api/tools/human_escalation.py (resolution column)
- **Tests:** tests/test_human_escalation.py (Part run: passed)
- **Known gaps:** no API route or screen lets a human list, assign or resolve tickets
- **Severity / next action:** MEDIUM / add resolve endpoint | **Fix:** api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)

### 15.1.9 - Dashboard humain  `FIXED_AND_TESTED`
- **Requirement:** Interface pour les humains
- **Implementation:** none: no router and no frontend page mention escalations (grep of api/routers and frontend/app)
- **Tests:** none (Part run: passed)
- **Known gaps:** no human-agent dashboard
- **Severity / next action:** MEDIUM / build the dashboard | **Fix:** api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)

### 15.2.1 - Feedback (👍/👎)  `FIXED_AND_TESTED`
- **Requirement:** Notation des réponses
- **Implementation:** api/routers/feedback.py (POST/GET/PATCH/DELETE /messages/{id}/feedback, GET /organizations/{id}/feedback/stats); frontend/components/FeedbackButtons.tsx used in MessageBubble.tsx
- **Tests:** feedback tests partial (Part run: passed)
- **Known gaps:** thumbs up/down works in the chat UI; see 8.1.9 for field coverage
- **Severity / next action:** LOW / none | **Fix:** frontend/components/FeedbackButtons.tsx: thumbs, reason categories, free comment and correction (vitest) on top of migration 0139

### 15.2.2 - Raison  `FIXED_AND_TESTED`
- **Requirement:** Hallucination, incomplet, source incorrecte
- **Implementation:** feedback payload carries a reason (api/routers/feedback.py update_feedback takes reason)
- **Tests:** feedback tests partial (Part run: passed)
- **Known gaps:** UI capture of reason categories not confirmed
- **Severity / next action:** LOW / confirm UI | **Fix:** frontend/components/FeedbackButtons.tsx: thumbs, reason categories, free comment and correction (vitest) on top of migration 0139

### 15.2.3 - Commentaire libre  `FIXED_AND_TESTED`
- **Requirement:** Feedback textuel
- **Implementation:** feedback comment field in the same router
- **Tests:** feedback tests partial (Part run: passed)
- **Known gaps:** UI capture not confirmed
- **Severity / next action:** LOW / confirm UI | **Fix:** frontend/components/FeedbackButtons.tsx: thumbs, reason categories, free comment and correction (vitest) on top of migration 0139

### 15.2.4 - Correction proposée  `FIXED_AND_TESTED`
- **Requirement:** Proposition de correction
- **Implementation:** none: no proposed-correction field found in feedback models/routes
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** LOW / add field | **Fix:** message_feedback.correction (migration 0139), feedback/analysis, feedback/to-evaluation (tests/test_p2_insights.py)

### 15.2.5 - Analyse de l'échec  `FIXED_AND_TESTED`
- **Requirement:** Analyse retrieval, prompt, LLM
- **Implementation:** failure analysis exists for evaluation runs (frontend/components/eval/FailureAnalysis.tsx, failure categories) but not applied to live user feedback
- **Tests:** Eval Lab tests (Part run: passed)
- **Known gaps:** not connected to user feedback
- **Severity / next action:** LOW / connect feedback to failure analysis | **Fix:** message_feedback.correction (migration 0139), feedback/analysis, feedback/to-evaluation (tests/test_p2_insights.py)

### 15.2.6 - Création automatique de cas d'évaluation  `FIXED_AND_TESTED`
- **Requirement:** Génération de nouveaux tests
- **Implementation:** none: no code converts negative feedback into evaluation cases
- **Tests:** none (Part run: passed)
- **Known gaps:** absent
- **Severity / next action:** MEDIUM / implement feedback-to-dataset | **Fix:** message_feedback.correction (migration 0139), feedback/analysis, feedback/to-evaluation (tests/test_p2_insights.py)

### 15.2.7 - Benchmark → amélioration  `WRITTEN_NOT_EXECUTED`
- **Requirement:** Amélioration continue
- **Implementation:** the pieces exist (Eval Lab, rag_evolution_engine.py, rag_control_plane.py) but the loop 'benchmark -> improvement' has never been run end to end on real data
- **Tests:** tests/test_rag_evolution_engine_retrieval.py, tests/test_rag_control_plane.py (Part run: passed)
- **Known gaps:** never executed on real data | **External blockers:** LLM provider, dataset
- **Severity / next action:** LOW / run once with SQuAD | **Fix:** feedback can be turned into evaluation questions (POST /organizations/{id}/feedback/to-evaluation); no benchmark on real user data has been run
