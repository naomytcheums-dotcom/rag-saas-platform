# Rapport staging Supabase

## Etat verifie — 2026-10-04

Production non contactee. Les resultats de cette section remplacent le
verdict historique BLOCKED_EXTERNAL conserve plus bas.

### Cible et backend

- Projet confirme par l'utilisateur et dans le navigateur :
  `<STAGING_PROJECT_REF>`, Plateforme RAG-SAAS-STAGING.
- Session pooler : `<STAGING_POOLER_HOST>:5432`,
  utilisateur `<STAGING_DB_USER>`, base `postgres`, SSL requis.
- `.env.staging` ignore par Git pointe desormais vers ce pooler.
  Le mot de passe reste un placeholder dans ce fichier : le credential
  autorise est injecte dans `STAGING_DATABASE_URL` en memoire au lancement,
  jamais copie dans le code, les rapports ou les arguments de processus.
- Backend local : `http://127.0.0.1:18039`, avec
  `RAG_ENV_FILE=.env.staging`, profil isole, aucun fallback `.env`,
  aucune URL transaction alternative ni credential fournisseur de production.
- Frontend : `http://127.0.0.1:13039`, API configuree sur ce backend.
  `FRONTEND_URL` autorise cette origine precise, sans wildcard.
  Cookies non Secure uniquement pour cette verification HTTP loopback.
- `/health/ready` repond :
  `{"database":"ok","rate_limit_redis":"ok","cache_redis":"ok"}`.
  PostgreSQL est Supabase staging; Redis est une instance native jetable
  loopback sur le port 16389. Aucun PostgreSQL Docker utilise pour ces preuves.

### Migrations et verification visuelle

- La tentative unique initiale a perdu la connexion pendant la revision
  0034; sa transaction n'a pas abouti. Aucun succes attribue a cet echec.
- Reprise par lots Alembic commits separes, sans modifier les migrations :
  succes, `alembic current = 0132 (head)` sur le pooler staging.
- Verification directe dans le Table Editor authentifie :
  `public.alembic_version`, une ligne `version_num = 0132`.
- Catalogue staging : PostgreSQL 17.11, 178 tables publiques (177 tables
  applicatives et `alembic_version`), pgvector 0.8.2, colonne
  `document_chunks.embedding_vector`, index HNSW
  `ix_document_chunks_embedding_vector_hnsw`.
- Contraintes publiques : 178 PK, 309 FK, 63 uniques, 1 check.
  Ces comptes ne sont pas une preuve de toutes les regles metier.
- Catalogue initial avant le suivi RLS : aucune policy. Etat actuel :
  77 policies pour le role lab, test DB A/B et neuf IDOR passants (11/11).
  Voir la section "Current RLS evidence" ci-dessous pour les limites :
  API/worker sous `postgres` restent BYPASS et ne sont pas certifies par
  ces policies.

### Comptes et organisations crees dans le navigateur

Les deux inscriptions ont traverse le vrai formulaire frontend et le backend
connecte a Supabase; l'organisation par defaut et son Owner sont crees
atomiquement par le flux d'inscription existant.

| Tenant | User ID | Organization ID |
|---|---|---|
| A | `1f3e045a-99b5-48b0-8fb3-3ee4206f56b9` | `80ba8171-61b4-4f49-bb6e-db93a9a4125c` |
| B | `168e21cd-7c02-4b80-8ef8-d4feade0e820` | `b00ca118-819f-4d9d-a094-02061fd1ed0a` |

- Inscriptions reussies et dashboards accessibles; B : POST register 201.
- Reconnexion par mot de passe : A et B, POST login 200, dashboard affiche.
- GET organizations retourne uniquement l'organisation de l'utilisateur.
- B lit l'organisation A : 404. A lit l'organisation B : 404.
- Defaut reel trouve : `api.post("/auth/logout")` n'envoyait pas le header
  double-submit CSRF et recevait 403, alors que le frontend effacait son token.
  Corrige dans `frontend/lib/api.ts` pour les POST logout/refresh uniquement.
  Deconnexions navigateur A/B apres correctif : 200.
- Le catalogue de traduction se charge de facon asynchrone : les cles
  apercues avant chargement ont laisse place aux libelles anglais.
  Pas de changement i18n attribue a ce constat.
- Pas de Resend configure : aucune livraison email revendiquee.
  Les comptes A/B sont conserves sur staging pour la reproduction.
  Aucun mot de passe de ces comptes ni token JWT inclus dans ce rapport.

### IDOR : neuf surfaces, memes tenants A/B

`tests/test_staging_full_idor.py` existait deja. La fixture
`tests/staging_support.py` peut maintenant recevoir les quatre identifiants
ci-dessus via `RAG_STAGING_USER_A/B` et `RAG_STAGING_ORG_A/B`.
Elle exige deux paires completes et distinctes, retrouve les vraies lignes
PostgreSQL et verifie les memberships Owner. Pas de tenants SQLite de remplacement.

Premier run : **9 passed, zero failure, zero skip**, 193.96 s.
Rejeu final incluant les substitutions MCP/Billing :
**9 passed, zero failure, zero error, zero skip**, 223.40 s.
JUnit verifie directement : tests=9, failures=0, errors=0, skipped=0.
Chaque test verifie le controle proprietaire 200 puis le refus 403/404
dans les deux directions.

| Surface | Route representative |
|---|---|
| Document | GET `/documents/{id}` |
| Agent | GET `/agents/{id}` |
| Workflow | GET `/workflows/{id}` |
| Conversation | GET `/conversations/{id}` |
| Evaluation | GET `/datasets/{id}` |
| Media | GET `/media/{id}` |
| MCP | GET `/organizations/{org}/mcp-servers/{id}/tools` |
| A2A | GET `/a2a/{org}/.well-known/agent-card.json` avec API keys A/B |
| Billing | GET `/organizations/{org}/billing/invoices/{id}` |

MCP et Billing incluent aussi la substitution de l'organisation attaquante
dans l'URL tout en conservant l'identifiant de la ressource victime.
Les ressources de test et API keys sont semees dans une transaction
PostgreSQL avec savepoints puis rollback; les utilisateurs et organisations
du navigateur ne sont pas recrees ni supprimes.
Verification SQL apres le rejeu : les deux memberships Owner existent
toujours; documents, agents, workflows, conversations, datasets, media,
MCP configs, invoices et API keys de ces deux organisations ont chacun
zero ligne apres rollback.

Les tests IDOR passent par ASGITransport en processus, avec des tokens
signes pour ces memes User IDs et une session PostgreSQL staging.
Ils ne prouvent pas tous les endpoints, les mutations, les listes, le serveur
MCP externe, l'execution de tasks A2A ni les paiements chez un fournisseur.
Le parcours navigateur utilise, lui, le serveur HTTP effectivement demarre.

### Reproduction et preuves

Avec `.env.staging`/`STAGING_DATABASE_URL` provisionne de facon privee :

```powershell
$env:RAG_STAGING_USER_A = "1f3e045a-99b5-48b0-8fb3-3ee4206f56b9"
$env:RAG_STAGING_ORG_A = "80ba8171-61b4-4f49-bb6e-db93a9a4125c"
$env:RAG_STAGING_USER_B = "168e21cd-7c02-4b80-8ef8-d4feade0e820"
$env:RAG_STAGING_ORG_B = "b00ca118-819f-4d9d-a094-02061fd1ed0a"
.\.venv\Scripts\python.exe -m scripts.staging_validate tests --idor-only --execute
.\.venv\Scripts\python.exe -m scripts.staging_validate current --execute
```

`--idor-only` selectionne les neuf surfaces; le test RLS separe n'est pas
assimile a un PASS ni masque. Sans cette option, les onze cas historiques
sont selectionnes, avec leur prerequis de role/policies RLS.
Le runner produit `staging-artifacts/idor-browser-tenants.xml` (ignore).
Captures navigateur conservees (ignorees egalement) :
`staging-artifacts/supabase-alembic-0132.png` et
`staging-artifacts/browser-tenant-a-dashboard.png`.
Quatre regressions CSRF frontend passantes; type-check et lint des deux
fichiers frontend modifies verts. Guard/config/runner : 23 tests passants;
Ruff cible vert. Aucune suite complete post-changement revendiquee.

Revue specialisee en lecture seule : aucune vulnerabilite signalee dans
les changements examines; pas de certification de securite globale.

## Historique — 2026-10-03 (avant deblocage IPv4)

## Verdict historique (2026-10-03)

**BLOCKED_EXTERNAL, staging non validé. Production non contactée.**
Le projet/ref exact autorisé est `<STAGING_PROJECT_REF>`.
« Base vide » et « production à 0130 » viennent du message utilisateur,
pas d'un catalogue SQL consulté.

## Preuves réellement exécutées

- `.env.staging` créé avec URL asyncpg et `ENVIRONMENT=staging`; mot de
  passe placeholder, aucun credential divulgué enregistré.
- `.gitignore` affiché, puis `git check-ignore .env.staging` retourne
  `.env.staging`. Dossier `staging-artifacts/` également ignoré.
- `socket.getaddrinfo(host,5432)` : `gaierror 11001`.
- Resolver alternatif `Resolve-DnsName -Server 1.1.1.1 -Type AAAA` :
  IPv6 résolue. Pas d'adresse A exploitable dans la sortie alternative.
- Socket IPv6 vers cette adresse et port 5432 : `OSError errno=10051`,
  réseau inaccessible; aucune authentification.
- `scripts/staging_validate.py current --execute` : exit 2, credential
  non provisionné localement, **aucune connexion**.
- `scripts/staging_validate.py inspect --execute` : même refus fermé.
- `scripts/staging_validate.py backup --execute` : exit 2, `pg_dump` absent.
- Docker CLI existe, daemon indisponible (`dockerDesktopLinuxEngine` absent).
- Outils/tests nouveaux : Ruff ciblé vert.
- Config/guard/loader ciblés : **18 passed**, tests staging non activés :
  **11 skipped**, pas 11 preuves de sécurité.

## Tableau des 15 tâches

| # | Tâche | Statut | Preuve / limite |
|---|---|---|---|
| 1 | `.env.staging` fonctionnel et ignoré | BLOCKED | Template créé et ignoré, mais credential non provisionné. |
| 2 | `alembic current` sur base vierge | BLOCKED | Commande gardée refusée avant connexion; sortie vide DB non démontrée. |
| 3 | État initial/version/user/tables/vector | BLOCKED | Aucune requête SQL; ni état vierge ni version vérifiés. |
| 4 | Installer pgvector si absent | BLOCKED | Aucune extension créée; état initial inconnu. |
| 5 | Migrations jusqu'à head | BLOCKED | Aucun `upgrade` live, aucun head appliqué établi. |
| 6 | Compter tables staging | BLOCKED | 177 est metadata ORM, pas un compte DB. |
| 7 | `workspaces.description` | BLOCKED | Migration 0132 locale existe; colonne DB inconnue. |
| 8 | Colonnes vector/HNSW | BLOCKED | SQL préparé; aucun résultat live. |
| 9 | Décision RLS | PASS | `docs/security/RLS_STAGING_DECISION.md`, rôle restreint et limites explicites. |
| 10 | Policies staging | BLOCKED | Script transactionnel prêt, aucune policy appliquée. |
| 11 | Test IDOR A/B PostgreSQL | BLOCKED | Deux fichiers de tests créés; 11 cas live skippés, aucun test PG exécuté. |
| 12 | Backup staging | BLOCKED | `pg_dump` absent et transport inaccessible; aucun dump ni taille inventée. |
| 13 | Restore sur deuxième DB | BLOCKED | Aucune URL restore/DB jetable; daemon Docker indisponible; aucun restore. |
| 14 | Rapport de résultats | PASS | Ce document, preuves et limites datées. |
| 15 | Plan production, sans exécution | PASS | `PRODUCTION_MIGRATION_PLAN.md`; aucune validation staging revendiquée. |

## Garde-fous ajoutés

`scripts/staging_target.py` valide host, port, user, database, driver et
absence de query override. Rejette URL production, hostname suffixé,
autre DB, autre user et credential placeholder.
`scripts/staging_validate.py` ne connecte sans `--execute`; actions
current/vector/upgrade/inspect/policies/tests/backup séparées.

`RAG_ENV_FILE` sélectionne uniquement dotenv staging dans les sous-processus.
Les variables héritées sont filtrées; transaction pooler, providers de
production et `.env` principal ne sont pas repris. Secrets locaux de test
JWT/HMAC sont générés par processus et jamais imprimés.

## Déblocage sans repli risqué

Il faut un chemin réseau IPv6 fonctionnel vers le host exact ou une cible
pooler staging officiellement confirmée puis ajoutée explicitement à
l'allowlist. **Aucun hostname pooler ou project name n'est deviné.**
Un nouveau credential local sûr est requis après rotation du secret partagé.
La rotation elle-même n'a pas été effectuée et n'est pas automatisable
sans accès autorisé au contrôle Supabase.

L'absence de mot de passe local n'est pas un diagnostic d'authentification
Supabase : aucune tentative d'authentification n'a eu lieu.
# Current RLS evidence - 2026-10-04

- Exactly 77 policies applied on direct UUID `organization_id` tables,
  targeted only to `rag_staging_tenant`, not PUBLIC.
- Role: NOLOGIN, NOSUPERUSER, NOBYPASSRLS, NOCREATEDB, NOCREATEROLE.
  No public-table ownership; untrusted memberships rejected.
- PostgreSQL 17 grants the creator administrative membership without SET.
  Initial DB test correctly failed `permission denied to set role`.
  Explicit SET TRUE / INHERIT FALSE granted only to the already-bypassing
  staging administrator `postgres`; no application login role introduced.
- Final live replay: **11 passed, zero failures/skips, 202.76 seconds**.
  Includes document API A/B, actual DB role isolation, and nine full IDOR
  surfaces using the original browser-created tenants.
- DB test proves missing tenant context returns zero documents, A and B
  each read only their own document, and moving A's document into B raises
  a PostgreSQL policy error. Resources roll back after testing.
- Limits: runtime API/worker still use a bypass role; tenant GUC is supplied
  by the trusted caller, not identity-bound. Indirect tenancy and excluded
  global/audit tables are not covered by these 77 policies. This is a lab
  RLS proof, not application-wide DB isolation certification.
- Role guard/runner regressions: 29 passed. Targeted Ruff: PASS.
  Follow-up specialist review of role guards and URL conversion reported
  no new exploitable finding. The earlier unsafe-existing-role finding was
  addressed; this does not certify the whole project.
