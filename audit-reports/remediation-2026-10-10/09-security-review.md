# 09 — Revue de sécurité API et accès

Périmètre : lecture du code, exécution de tests locaux (SQLite et PostgreSQL jetable). Aucune exploitation, aucun scan actif, aucun service distant.

## Routes : classement
Source : `audit-reports/radiographie-2026-10-10/04_API_ENDPOINTS.csv` (943 opérations), arbre de dépendances FastAPI. Résultat des contrôles de cette session :
| Contrôle | Résultat | Preuve |
|---|---|---|
| Opérations avec `{org_id}` dans le chemin | **374** ; toutes déclarent une garde d'appartenance / permission / rôle / admin plateforme, sauf **2 publiques par conception** (`GET /organizations/{org_id}/branding` : branding white-label affiché sur la page de connexion d'un domaine personnalisé ; `GET …/domains/verify/{token}` : protégée par le jeton secret du chemin) | `tests/test_p0_tenant_route_contract.py` (4) ; vérifié aussi que le détecteur échoue sur un routeur non gardé |
| Opérations sans dépendance d'authentification détectée | 84 (audit précédent) | classées ci-dessous |
| Routes publiques à ne pas « corriger » | login/register/refresh/logout, reset de mot de passe, OAuth/SSO callbacks, WebAuthn (options/verify), vérification d'e-mail, `/health*`, `/metrics`, `/billing/plans*`, `/billing/*/webhook`, `/integrations/*/(events|interactions|webhook|callback)`, `/twilio/*`, widget (`/widget/*`), `/share/{token}`, `/webhooks/{trigger_id}`, `/license/validate`, `/partners/register`, `/r/{code}`, `/marketplace/*` (lecture), `/i18n/*`, `/api/versions*`, `/invitations/accept`, compliance `data-deletion` | liste de l'audit du 2026-10-10 |
| À vérifier une à une (auth par mécanisme non reconnu par le scanner) | `/account/*` (me, export, export-csv, consent/withdraw, accept-updated-terms, DELETE me), `/auth/2fa/*` (setup/enable/disable/recovery), `/sessions`, `/auth/webauthn/credentials*` | tests `test_auth_api.py`, `test_auth_security.py` couvrent la plupart ; relecture individuelle **NOT_VERIFIED** |
| Webhooks entrants | signature + anti-rejeu : Stripe/Paystack (tests) ; Slack/Discord/Teams/Twilio : contrôles propres à chaque canal (`test_p0_twilio_tenant_isolation.py`, tests des intégrations) | exhaustivité NOT_VERIFIED |
| MCP / A2A | `stdio` désactivé par défaut et réservé au superadmin ; SSRF des transports HTTP couvert (75 tests `test_p0_ssrf_outbound.py`) ; isolation A2A (`test_a2a_idor.py`) | |
| Admin / superadmin | `require_admin` (admin + superadmin) / `require_superadmin` ; écritures financières superadmin seul (SADM-005) ; refus audité seulement pour un admin de plateforme (R1) | tests réussis en CI |

## Constats de cette session
| ID | Sévérité | Constat | Statut |
|---|---|---|---|
| REM-001 | P0 | aperçu local pouvant atteindre la base hébergée | PARTIAL (garde + lanceur ; configuration développeur non versionnée) |
| REM-002/003 | P0/P1 | RLS non contraignant ; pas de contexte tenant | PARTIAL (pilote + propagation ; rôle d'exécution = BLOCKED_EXTERNAL) |
| REM-004 | P1 | garde des routes d'organisation | FIXED (contrat) — résultat positif |
| REM-012 | P2 | `/metrics` public sans jeton | PARTIAL (option fail-closed ; valeur de production inconnue) |
| REM-021 | P2 | IDOR par identifiant de ressource (`/documents/{id}` etc.) non audité exhaustivement | NOT_VERIFIED |

## Rate limiting
Redis (`RATE_LIMIT_REDIS_URL`) ; **repli sur un limiteur en mémoire de processus** si Redis est injoignable (observé dans les journaux de tests) — non partagé entre instances et remis à zéro à chaque redémarrage. Un limiteur distribué existe déjà quand Redis est joignable : l'exigence « solution distribuée » est donc **satisfaite en configuration normale** ; le risque est le repli. Non modifié : changer le comportement de repli (refuser plutôt que dégrader) est une décision de disponibilité à prendre. Limites par catégorie (auth, génération, ingestion, export, facturation) : présentes pour auth/inscription/upload/licence/chat public ; exhaustivité NOT_VERIFIED.

## `/metrics`
Jeton Bearer optionnel (`METRICS_AUTH_TOKEN`). Nouveau `METRICS_REQUIRE_AUTH` (défaut `false`) : sans jeton configuré, répond 503 au lieu d'être public. Cardinalité des labels, secrets dans les métriques : non audité dans cette session (NOT_VERIFIED).

## Paramètres sensibles
`docs/devops/SENSITIVE_SETTINGS.md` (valeurs par défaut sûres épinglées par `tests/test_sensitive_settings.py`) ; valeurs réelles de production non vérifiables depuis le dépôt (BLOCKED_EXTERNAL).

## Dépendances et secrets
pip-audit en CI avec une exception ciblée (diskcache, PYSEC-2026-2447) ; mises à jour majeures (stripe 16, sqlalchemy 2.1, typescript 7) non traitées (une par une, avec tests). Balayage de secrets sur les diffs de cette session : 0 occurrence. `.env` jamais ouvert.
