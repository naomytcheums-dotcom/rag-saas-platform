# 07 — Authentification, autorisations, isolation multi-tenant, sécurité

Audit du 2026-10-10, HEAD `59d5ec9`. Analyse **statique** + lecture de tests ; aucune exploitation, aucun scan actif. **Le schéma réel de la base n'est pas vérifié.** Les identifiants `SEC-AUD-xxx` viennent d'une exploration automatisée (annexe) ; les identifiants `SEC-00x`, `TEN-`, `SADM-` viennent des audits antérieurs (`11_AUDITS_CONSTATS.csv`).

## Faits établis
| Sujet | Constat | Statut |
|---|---|---|
| Rôles | utilisateurs : `user`, `admin`, `superadmin` (+ rôles d'organisation owner/admin/manager/member/viewer) ; `require_admin` accepte admin et superadmin ; `require_superadmin` exige exactement `superadmin` | OBSERVÉ |
| Permissions d'organisation | 52 clés `ressource:action` (13 ressources × read/write/delete/manage), `require_permission(...)`, rôles personnalisés | OBSERVÉ, tests `test_rbac_custom.py`, `test_roles_and_permissions.py` |
| Écritures financières plateforme | réservées au **superadmin** (SADM-005) : 10 routes abonnements/plans/synchro + 2 routes factures ; refus audité seulement pour un admin de plateforme (R1) | CODE LU + tests réussis en CI |
| Suspension d'organisation | 403 sur les chemins par organisation et les clés API (TEN-002/SADM-004) | tests `test_p1_backoffice_and_suspension.py` réussis en CI |
| Viewer et workflows | un viewer ne peut plus lancer un workflow (TEN-012, `eb2e8e5`, commit de l'utilisatrice) | test `test_p2_ten012_viewer_cannot_run_workflow.py` ; CI success sur HEAD |
| Audit d'organisation | la vue de l'organisation masque IP, user-agent, référence de paiement et motif d'annulation du personnel (V5, R7) | tests réussis |
| JWT / refresh / CSRF | JWT avec `jti`, rotation de clé, refresh en cookie + CSRF double-submit ; liste de révocation | OBSERVÉ ; tests `test_auth_security.py`, `test_jwt_key_rotation_integration.py` |
| 2FA / WebAuthn / SSO / OAuth | TOTP, codes de récupération, récupération de blocage (délai), WebAuthn, SSO enterprise OIDC ; OAuth Google/GitHub | OBSERVÉ ; SAML distinct : NON TROUVÉ |
| Clés API / comptes de service | clés d'organisation et d'agents avec scopes | OBSERVÉ ; couverture fonctionnelle complète non prouvée |
| Webhooks entrants | signature Stripe/Paystack, anti-rejeu par id (`payment_events`) | OBSERVÉ + tests synthétiques ; **jamais confronté à un vrai fournisseur** |
| Rate limiting | Redis ; **repli sur un limiteur en mémoire de processus si Redis est injoignable** (journaux de tests) — non partagé entre workers | OBSERVÉ (correction d'une affirmation « fail-open » du sous-agent) |
| Audit log | chaîne de hachage HMAC + verrou consultatif PostgreSQL ; endpoint de vérification d'intégrité | OBSERVÉ |
| RGPD | export JSON/CSV, suppression avec délai de 30 jours, consentement versionné, réactivation par jeton, purges planifiées | OBSERVÉ ; exécution des purges en production dépend d'un beat non garanti |
| `/metrics` | jeton Bearer **optionnel** (`METRICS_AUTH_TOKEN`) : public si la variable est absente | OBSERVÉ ; valeur en production : NON VÉRIFIÉE |

## Isolation multi-tenant — conclusion de l'audit
1. **PostgreSQL RLS n'est pas une barrière** : 57 migrations `ENABLE ROW LEVEL SECURITY`, **0** `FORCE`, **0** `CREATE POLICY`, rôle applicatif documenté comme `postgres` à droit de contournement. → CONFIRMÉ par lecture du code et de la documentation du projet ; le rôle réel n'a pas été inspecté.
2. L'isolation repose donc sur des **filtres applicatifs** (`organization_id`) répétés dans 101 routeurs et 284 services. Il n'existe pas de mécanisme central empêchant un oubli. Mitigations observées : tests IDOR ciblés (`test_document_idor.py`, `test_a2a_idor.py`, `test_billing_idor.py`, suites `test_p0_*`) et **518 tests de non-régression dans 43 fichiers `test_p0_/test_p1_/test_p2_*`** (collecte du 2026-10-10).
3. **Aucun IDOR n'est confirmé par cet audit**, aucun n'a été infirmé exhaustivement : les 80 tables à `organization_id` et les 97 tables sans cette colonne n'ont pas été auditées table par table. Candidats à examiner en priorité (non confirmés) : `api/routers/admin_users_management.py`, `api/routers/agent_api_keys.py`, `api/security/document_versions.py`, tâches Celery recevant un simple identifiant, clés Redis sans organisation.

## Constats de sécurité historiques (registre complet : `11_AUDITS_CONSTATS.csv`)
- **SEC-001 à SEC-005** (revue statique du 2026-10-07 : contournement du filtre tenant de l'outil SQL, commande OS via MCP `stdio`, écriture de fichier via nom de média, routes Twilio sans tenant, SSRF avec lecture de réponse) : chacun a un commit et un test dédié (`tests/test_p0_sql_tool_tenant_bypass.py`, `test_p0_mcp_stdio_disabled.py`, `test_p0_media_filename_path.py`, `test_p0_twilio_tenant_isolation.py`, `test_p0_ssrf_outbound.py` — 75 tests) ; la suite réussit en CI. Statut : CORRIGÉ — TEST RÉUSSI (indirect). `stdio` n'est possible que si `MCP_STDIO_ENABLED` et pour un superadmin.
- `api/tools/sql_tool.py` construit toujours du SQL dynamique via `text()` (candidat à confirmer, borné par la validation de table/colonnes et le filtre `organization_id`) : **risque résiduel** à faire relire par un tiers.
- `eval()` dans `api/tools/calculator.py` avec validation AST : à tester contre les contournements (`agents.md` interdit eval/exec).
- Dépendances : `pip-audit` réussit en CI avec 1 exception documentée (diskcache 5.6.3, PYSEC-2026-2447, aucune version corrigée) ; Bandit tourne en non-bloquant (rapports non lus) ; `snyk.exe` (55 Mo) est présent à la racine du dépôt, non exécuté.
- SSRF : protection dédiée (`ssrf_safe_client`) et 75 tests ; exhaustivité des appels HTTP bruts : NON ÉTABLIE.
- Secrets : `.env` et `.env.staging` existent dans le répertoire de travail, **ignorés par Git** (`.gitignore` lignes 1-2, vérifié par `git check-ignore`) et non suivis (seuls `.env.example`, `.env.staging.example`, `frontend/.env.local.example` le sont) ; non ouverts par cet audit ; **aucune valeur n'est reproduite**. Le `.env` local de développement pointe vers des services distants réels (base, Redis) : risque d'exécution accidentelle de tests contre eux, déjà rencontré (voir `15`).

## Non établi
Contrôle des téléchargements S3 par organisation (clés prédictibles `documents/{org}/{doc}/…`, privés), chiffrement effectif au repos, en-têtes de sécurité, CORS en production, rotation réelle des secrets, comportement exact des tâches Celery vis-à-vis du tenant, RLS réelle côté Supabase.

---
## Annexe — Exploration automatisée sécurité/auth/tenant (sous-agent, lecture seule)
*(deux affirmations sont corrigées dans le corps du rapport : SADM-005 est bien présent dans le code ; le rate limiting se dégrade, il n'est pas inopérant)*

<!-- ANNEXE_AJOUTEE -->
### Audit statique de sécurité — `rag-saas-platform`

Périmètre lu : `api/`, `tests/`, `api/alembic/versions/`. Aucun fichier modifié. Le schéma réel de la base n’a pas été inspecté.

#### 1. Authentification et comptes

- **SEC-AUD-001 — JWT, expiration, rotation — low**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  JWT avec `sub`, `jti`, `iat`, `exp`, algorithme configurable ; vérification avec clé courante, `JWT_PREVIOUS_SECRET_KEYS` et clés DB encore retenues après rotation.  
  `api/security/jwt.py:70-145`, symboles `_verification_keys`, `refresh_jwt_key_cache`, `_create_token`.

- **SEC-AUD-002 — Révocation/blacklist des access tokens — medium**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  Le `jti` est associé à une session et vérifié contre les tokens révoqués.  
  `api/security/jwt.py:8-25`, `api/dependencies.py:55-139`; migration `api/alembic/versions/0008_access_token_revocation.py`.

- **SEC-AUD-003 — Login, rate limiting et verrouillage — low**  
  **TEST PRÉSENT (`tests/test_rate_limiting_integration.py`, `tests/test_auth_security.py`).**  
  Login limité par IP et email ; verrouillage persistant DB ; comparaison avec hash factice pour limiter l’énumération temporelle.  
  `api/routers/auth.py:197-330`, symbole `login`; `api/security/rate_limit.py`.

- **SEC-AUD-004 — Refresh cookie et CSRF — medium**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  `/auth/refresh` et logout exigent le double-submit CSRF ; le cookie CSRF utilise `COOKIE_SECURE`.  
  `api/routers/auth.py:331-408`, `api/security/csrf.py:28-74`, symboles `verify_csrf`, `set_csrf_cookie`.  
  Le comportement effectif dépend de la configuration déployée.

- **SEC-AUD-005 — TOTP, WebAuthn, recovery et lockout recovery — low**  
  **TEST PRÉSENT (`tests/test_auth_security.py`, tests WebAuthn/OIDC présents sous `tests/`).**  
  Le login bascule vers un token MFA temporaire si TOTP ou WebAuthn est activé ; migrations dédiées pour recovery codes et lockout recovery.  
  `api/routers/auth.py:310-321`, `api/alembic/versions/0003_two_factor_recovery_codes.py`, `0006_two_factor_lockout_recovery_tokens.py`.

- **SEC-AUD-006 — OAuth Google/GitHub, SSO/OIDC/SAML — low**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  Provider OAuth Google/GitHub dans `0001`; SSO enterprise/OIDC/WebAuthn dans `0013`; tests OIDC et SSO présents.  
  `api/alembic/versions/0001_create_auth_tables.py:18-57`, `0013_jwt_webauthn_enterprise_sso.py`, `tests/oidc_test_idp.py`.  
  Aucun résultat probant trouvé pour une implémentation SAML distincte : **NON TROUVÉ**.

- **SEC-AUD-007 — Vérification email, reset password, restauration, consentement, invitations — low**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  Tables et routes dédiées présentes : tokens de vérification/reset/restore/reactivation, invitations et suppression différée.  
  `api/alembic/versions/0001_create_auth_tables.py:60-90`, `0005_account_restore_tokens.py`, `0007_consent_reactivation_tokens.py`, `0020_invitations.py`, `api/routers/account.py:374-582`.

- **SEC-AUD-008 — API keys/service accounts — medium**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  API keys d’organisation et d’agents, scopes et migrations dédiées. Le hachage/expiration existent dans les modèles/services, mais la couverture fonctionnelle complète n’est pas prouvée par une exécution.  
  `api/alembic/versions/0061_agent_api_keys.py`, `0083_organization_api_keys.py`, `api/routers/agent_api_keys.py`.

- **SEC-AUD-009 — Superadmin/admin et comptes suspendus — medium**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  `require_admin` accepte admin/superadmin ; `require_superadmin` exige exactement `UserRole.superadmin`. Routes de suspension/activation présentes.  
  `api/dependencies.py:139-180`, `api/models/user.py:25`, `api/routers/admin_organizations.py:79-114`.  
  Les règles nommées `SADM-005` ne sont pas retrouvées explicitement : **NON TROUVÉ**.

#### 2. RBAC et endpoints

- **SEC-AUD-010 — RBAC organisationnel et rôles custom — low**  
  **TEST PRÉSENT (`tests/test_rbac_custom.py`, `tests/test_roles_and_permissions.py`).**  
  `require_permission`, `require_any_permission`, `require_all_permissions`, `require_role`; Owner/Admin obtiennent toutes les permissions, les autres rôles ont des ensembles par défaut et peuvent recevoir des permissions custom.  
  `api/security/permissions.py:55-180`.

- **Clés de permission — IMPLÉMENTATION OBSERVÉE.**  
  Ressources : `documents`, `agents`, `conversations`, `api_keys`, `webhooks`, `widget`, `integrations`, `evaluation`, `billing`, `members`, `settings`, `security`, `audit_logs`.  
  Actions : `read`, `write`, `delete`, `manage` — 52 clés au total.  
  `api/security/permission_catalog.py:15-55`.

- **SEC-AUD-011 — Routes sans dépendance d’authentification — medium**  
  **NON DÉTERMINÉ** pour l’inventaire exhaustif statique : plusieurs routeurs utilisent des dépendances au niveau fonction ou routeur et ne peuvent pas être classés correctement par simple motif.  
  Routes publiques explicitement observées :  
  - `GET /.well-known/agent-card.json` et `POST /{org_id}` A2A avec clé d’API publique : `api/routers/a2a.py:103-119`.  
  - OAuth callback Slack sans utilisateur courant : `api/routers/chat_integrations_slack.py:44-46`.  
  - Health checks dans `api/main.py:468-495`.  
  Ces routes doivent rester publiques uniquement si leur validation spécifique est effectivement appliquée.

#### 3. Isolation multi-tenant / RLS / IDOR

- **SEC-AUD-012 — RLS activé sur les tables — high**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  Les migrations activent RLS sur les tables historiques, documents et tables ajoutées ultérieurement.  
  `api/alembic/versions/0002_enable_row_level_security.py:28-38`, `0032_documents_row_level_security.py:29-35`, `0098_rls_coverage_gap.py:21-81`, `0131_enable_rls_on_remaining_tables.py:48-53`.

- **SEC-AUD-013 — RLS ne constitue pas actuellement une isolation prouvée — high**  
  **CONFIRMÉ PAR LECTURE DU CODE.**  
  `0098` documente que l’application se connecte comme `postgres`, rôle susceptible de posséder `rolbypassrls`; aucune commande `FORCE ROW LEVEL SECURITY`, `CREATE POLICY`, `BYPASSRLS` ou `set_config/current_setting` d’organisation n’a été trouvée dans les migrations ciblées.  
  `api/alembic/versions/0098_rls_coverage_gap.py:1-12`.  
  **Schéma réel non vérifié.** L’absence de policies applicatives signifie que l’isolation repose principalement sur les filtres/service-layer.

- **SEC-AUD-014 — Requêtes SQL dynamiques — medium**  
  **HYPOTHÈSE, candidat à confirmer.**  
  `api/tools/sql_tool.py:255-272` construit du SQL via `text(final_query)` et f-string, avec noms de table/colonnes dynamiques. La requête filtre `organization_id`, mais la sûreté dépend entièrement de la validation préalable de `table` et `columns`.

- **SEC-AUD-015 — Candidats IDOR — medium**  
  **NON DÉTERMINÉ / candidat à confirmer.**  
  Plusieurs endpoints prennent seulement un identifiant (`document_id`, `agent_id`, `user_id`, `org_id`) ; les contrôles sont parfois déportés dans des dépendances/service-layer. Exemples à vérifier en priorité :  
  `api/routers/admin_users_management.py:107-151`, `api/routers/agent_api_keys.py:32-74`, `api/security/document_versions.py:111`.  
  Aucun IDOR n’est confirmé sans test d’accès cross-organisation.

- **SEC-AUD-016 — Tâches Celery, caches et téléchargements tenant-aware — NON DÉTERMINÉ.**  
  Le dépôt contient de nombreuses tâches et clés Redis ; aucune conclusion exhaustive fiable n’est possible avec les résultats ciblés. Les tests `tests/test_a2a_idor.py` couvrent au moins l’isolation A2A par clé d’organisation.

#### 4. Contrôles statiques

- **SEC-AUD-017 — SSRF — medium**  
  **NON DÉTERMINÉ.**  
  Des protections SSRF sont mentionnées dans `api/config.py:1812-1817`, mais plusieurs appels HTTP existent dans les services. Une revue endpoint-par-endpoint des URLs contrôlées par utilisateur est nécessaire pour distinguer appels protégés et appels bruts.

- **SEC-AUD-018 — Désérialisation dangereuse — low**  
  **NON TROUVÉ** pour `pickle`, `yaml.load`, `exec`.  
  `eval()` est utilisé dans le calculateur avec validation AST documentée : `api/tools/calculator.py:6,104`; risque résiduel à confirmer par tests de contournement.

- **SEC-AUD-019 — Injection SQL — medium**  
  **HYPOTHÈSE, candidat à confirmer.**  
  Le seul candidat concret identifié est `api/tools/sql_tool.py:255-272`; aucun secret ou valeur sensible n’est exposé dans ce rapport.

- **SEC-AUD-020 — Audit log et chaîne d’intégrité — low**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  Fonction de vérification de l’intégrité et endpoint admin présents.  
  `api/security/audit_log.py:89`, `api/routers/audit.py:196`, migration `0012_audit_log.py`.

- **SEC-AUD-021 — Rate limiting fail-open — medium**  
  **CONFIRMÉ PAR LECTURE DU CODE.**  
  `api/main.py:468-495` indique que si Redis est indisponible, le rate limiting n’est plus effectivement appliqué. Le login possède toutefois un verrouillage DB indépendant.  
  `api/routers/auth.py:197-230`.

- **SEC-AUD-022 — XSS/Markdown, headers, CORS, chiffrement au repos — NON DÉTERMINÉ.**  
  Des recherches ciblées ont trouvé la configuration CORS, Markdown et `ENCRYPTION_MASTER_KEY`, mais pas assez de contexte pour confirmer la sanitisation, les headers de sécurité ou le chiffrement effectif. Aucun `dangerouslySetInnerHTML` probant n’a été identifié dans le périmètre retourné.

- **SEC-AUD-023 — Secrets/logging/hard-coded credentials — medium**  
  **NON DÉTERMINÉ.**  
  Des valeurs de configuration par défaut de développement existent, notamment URLs Redis localhost : `api/config.py:975-982`. Aucun secret n’est reproduit ici. La présence de valeurs sensibles en clair dans les fichiers de configuration doit être vérifiée séparément sans ouvrir `.env`.

#### 5. GDPR

- **SEC-AUD-024 — Export, suppression, grâce et purge — low**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  Export account data, suppression avec délai configuré à 30 jours, rappels et tâches de purge présents.  
  `api/routers/account.py:582`, `api/config.py:166-175`, `api/alembic/versions/0009_deletion_reminder.py`.

- **SEC-AUD-025 — Consentement et réactivation — low**  
  **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ.**  
  Consentement initial, `consent_withdrawn_at`, réactivation par token et blocage si version des conditions obsolète.  
  `api/alembic/versions/0004_consent_withdrawn_at.py`, `0007_consent_reactivation_tokens.py`, `api/dependencies.py:120-139`.

#### 6. Tests de sécurité existants

- `tests/test_auth_security.py`
- `tests/test_rate_limiting_integration.py`
- `tests/test_rbac_custom.py`
- `tests/test_roles_and_permissions.py`
- `tests/test_a2a_idor.py`
- `tests/test_security_scan.py`
- `tests/test_security_alerts.py`
- `tests/test_mcp_builtin_tools_security.py`
- `tests/test_enterprise_sso_integration.py`
- `tests/oidc_test_idp.py`
- Tests WebAuthn sous `tests/` et tests frontend OAuth sous `frontend/app/oauth-callback/page.test.tsx`.

#### Questions non établies

1. Le schéma réel possède-t-il des `CREATE POLICY` non représentés par les migrations, et le rôle runtime possède-t-il réellement `rolbypassrls` ?
2. Chaque route identifiée comme publique valide-t-elle correctement sa signature, clé ou secret ?
3. Les services HTTP utilisent-ils systématiquement `ssrf_safe_client` pour toutes les URLs utilisateur ?
4. Les endpoints d’identifiants (`document_id`, `agent_id`, `user_id`, téléchargements) résistent-ils aux accès cross-organisation ?
5. La sanitisation Markdown/XSS, les headers HTTP, le CORS de production et le chiffrement au repos sont-ils effectivement actifs dans l’environnement déployé ?
6. Les tâches de purge, révocation, rotation JWT et rétention des logs sont-elles exécutées avec succès en production ?
