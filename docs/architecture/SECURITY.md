# Security Model

Modele de securite multi-tenant, RBAC, permissions tools et audit.
Pour les composants, voir OVERVIEW.md.

## Multi-tenancy

Principe : chaque table tenant-scoped porte un org_id, et la
plupart appliquent RLS PostgreSQL en plus des checks applicatifs.

### Double verification

1. Applicatif : require_permission("resource:action") sur chaque endpoint sensible.
2. DB : RLS (org_id = current_setting), activee sur les tables critiques
   via migrations Alembic (0087_enable_row_level_security_remaining_tables.py).

Benefice : un bug applicatif ne peut pas exposer les donnees d une
autre org -- la DB refuse.

### Isolation cross-agent

- Long-term memory : cle (agent_id, user_id, key), cross-run mais isolee par agent.
- Short-term memory : session_id (string), pas de fuite cross-session.
- Tools : ToolPermission per-agent-per-tool.

## RBAC granulaire

52 permissions organisees par ressource (api/security/permission_catalog.py).

### Roles built-in

| Role | Scope |
|------|-------|
| owner | Tout, y compris billing + suppression org |
| admin | Tout sauf billing critique |
| member | Lecture + ecriture selon permissions explicites |
| viewer | Lecture seule |

### Resource permissions

En plus des roles, ResourcePermission permet des permissions
par ressource individuelle.

## Tool permissions (agents)

Chaque agent a des ToolPermission par tool :
- allow : le tool peut etre execute.
- deny : le tool est refuse (meme si selectionne par le LLM).

Verification : check_tool_permission(...) avant chaque execution de tool.

## Auth

### Sessions

- Cookie HttpOnly, Secure (si COOKIE_SECURE=true), SameSite=Lax.
- Session store cote serveur (Redis ou DB).
- Expiration configurable.

### API keys

- Format sk_live_... / sk_test_...
- Hashees en DB (jamais en clair).
- Scope par organisation.
- Revocation immediate.

### SSO / Enterprise

- OIDC / SAML via enterprise_sso.py.
- Mapping des groupes IdP -> roles org.

### 2FA / WebAuthn

- TOTP (two_factor.py).
- WebAuthn (cles physiques, biometrie).
- Recovery codes.

## Audit

- AuditLog : chaque action sensible (login, permission change, billing, suppression).
- Champs : actor_id, action, resource_type, resource_id, metadata, ip, user_agent, timestamp.
- Retention configurable.

## Chiffrement

### Secrets en transit

- TLS partout (HTTPS only en prod).
- Webhooks : signature HMAC verifiee (Stripe, Paystack).

### Secrets au repos

- STRIPE_SECRET_KEY, PAYSTACK_SECRET_KEY, etc. : variables d environnement, jamais en DB.
- BYOK (Bring Your Own Key) : cles LLM par organisation, chiffrees en DB (Fernet ou equivalent).
- Mots de passe : bcrypt / argon2.

## Scanning

### CI backend-security

- pip-audit sur les dependances (12 CVE fixees dans la session SSRF epingle).
- Scan automatique a chaque PR.

### Runtime

- Rate limiting par IP + par org.
- Detection d anomalies (optionnel, via Sentry).

## Conformite

- RGPD : droit a l effacement (DELETE /organizations/{id}), export de donnees.
- SOC 2 (en cours, voir docs/compliance/).
- Data breach notification : api/tasks/compliance.py.

## Voir aussi

- docs/admin/RBAC.md -- roles et permissions
- docs/admin/SSO.md -- configuration SSO
- docs/diagrams/AUTH_FLOW.md -- flux auth
- docs/diagrams/MULTI_TENANCY.md -- isolation tenant
