# PHASE 0 — Audit de sécurité en lecture seule (2026-10-12)

Projet : RAG SaaS Platform · dépôt `naomytcheums-dotcom/rag-saas-platform` · worktree audité `C:\Users\NITROV15\rag-work\wt-gaps` (branche `bob/auto-fix-20261010-gaps`, HEAD `c04100e`).
Nature : investigation en lecture seule. Aucune correction, migration, écriture en base, test, fusion, poussée, déploiement ni modification de variable. Seul fichier créé : ce rapport.
Légende des statuts : **Confirmé** (preuve directe consultée aujourd'hui) · **Probable** (déduction forte) · **Suspecté** (indice faible) · **NON VÉRIFIÉE — ACTION EXPLICITE REQUISE** (exige un accès externe ou une opération susceptible d'écrire).
Aucune valeur secrète n'est reproduite : les types, emplacements et risques seulement.

---

## A. Résumé exécutif

**État de sécurité.** Le contrôle d'isolation entre organisations est applicatif uniquement ; la base n'impose rien. Les tests ne peuvent plus (depuis le 2026-10-10 20:30 +01:00) atteindre une base distante par la CI GitHub, mais la protection ne couvre pas tout. L'état réel de la production (révision de schéma, rôle de connexion, données) **n'a pas pu être établi** : aucun accès à Supabase.

**Risques critiques**
1. **Révision de la base de production indéterminée et documents contradictoires** : le runbook la dit en `0130`, le dossier de transmission en `0143` (appliquée le 2026-10-11). Or `origin/main` contient déjà du code qui lit des colonnes ajoutées après `0130` (voir MIG-002). Si un déploiement suit `main` sans que la base soit à jour, la connexion des utilisateurs casse.
2. **Sauvegarde de production dans le worktree, non ignorée par Git** : `backups/prod_backup.dump` (27 Mo). Un `git add -A` la mettrait dans un commit.
3. **Isolation multi-tenant 100 % applicative** : 103 `ENABLE ROW LEVEL SECURITY`, **0 politique**, **0 `FORCE`** ; rôle de connexion historiquement `postgres` avec `BYPASSRLS`.

**Risques confirmés** : exposition CI du 2026-09-19 au 2026-10-10 (connexion à une base distante et `DELETE` démontrés ; perte de données non démontrée) ; worker Celery planifié qui tourne avec les secrets de production sur des runners GitHub ; collision de numéro de migration `0137` entre deux branches ; secrets déjà partagés en conversation (rotation non prouvée).

**Risques incertains** : que `DATABASE_URL` du dépôt GitHub pointait bien vers la production Supabase (très probable) ; protections réelles de l'environnement `production-migrations` ; politique de déploiement de Render/Vercel ; échec CircleCI `api-tests` (cause inaccessible).

**Opérations à ne surtout pas lancer avant clarification**
* `pytest` ou n'importe quel script `api.*` (dont `scripts/export_openapi.py`, `measure_injection_two_stage.py`, `alembic`) avec le `.env` présent dans le worktree : il contient les variables des services réels. Seul `scripts/run_tests_local.sh` vide ces variables.
* `git add -A` / `git commit -a` dans `wt-gaps` tant que `backups/` n'est pas ignoré.
* Fusionner la PR #25 ou la branche `bob/auto-fix-20261010-1555` ; `scripts/migrate.py --apply` ; le workflow `migrate.yml` en mode « apply » ; lancer manuellement `celery-worker.yml`.
* `tests/test_postgres_integration.py` & co avec un `DATABASE_URL` autre que jetable ; `tests/llm_optin/test_real_llm.py` avec son fournisseur par défaut (il appelle l'API Anthropic payante avec la clé du `.env`).

---

## B. Tableau des preuves

### B.1 CI et base de production (P0)

Niveaux demandés, établis pour la fenêtre 2026-09-19 08:18 UTC → 2026-10-10 19:30 UTC (runs GitHub `ci.yml` n°1 à n°194) :

| Niveau | Établi ? | Preuve |
|---|---|---|
| Risque théorique | Oui | `tests/test_postgres_integration.py`, `test_jwt_key_rotation_integration.py` : `DELETE`/`INSERT` sur `settings.DATABASE_URL` |
| Chemin d'exécution possible | **Oui, confirmé** | diff du commit `beebb48` : l'ancien `backend-tests` recevait `DATABASE_URL: ${{ secrets.DATABASE_URL }}` et 14 autres secrets |
| Connexion à une base réelle (distante) démontrée | **Oui** | run n°193 (job `114275293389`, 2026-10-10 17:50 UTC) : les tests PostgreSQL JWT ne sont pas ignorés (ils s'ignorent quand la base est injoignable, `pytest.skip` dans `pg_engine`) et échouent sur des assertions |
| Opération d'écriture démontrée | **Oui (déduction directe)** | dans ce run, le fixture automatique `_clean_jwt_signing_keys_table` (`DELETE` sans filtre + `commit`) s'est exécuté avant chaque test, puis 8 tests ont échoué sur des états inattendus (`StaleDataError … 0 were matched`, `assert 2 == 1`) |
| Perte de données démontrée | **Non** | aucune preuve ni de perte ni d'absence de perte ; contenu réel de `jwt_signing_keys` inconnu |
| Identité « production » de cette base | **Probable, non démontrée** | le secret est lu par `migrate.yml` (`production-migrations`) et `celery-worker.yml` ; commentaires du projet ; valeur du secret illisible |

| ID | Prio | Constat | Preuve | Statut | Impact | Action proposée | Vérification |
|---|---|---|---|---|---|---|---|
| CI-001 | P0 | Du 2026-09-19 au 2026-10-10, `backend-tests` s'exécutait avec les secrets de dépôt (base, Redis/Celery, S3, e-mail, clés JWT et de chiffrement) | `git show beebb48 -- .github/workflows/ci.yml` ; `git log --diff-filter=A` : `ci.yml` créé en `47e726d` | Confirmé | Lecture/écriture/suppression sur la base du secret ; e-mails et S3 réels | Rotation des secrets concernés (décision propriétaire) ; télécharger les journaux avant expiration (90 j par défaut) | Journaux Supabase et Actions comparés aux créneaux des runs |
| CI-002 | P0 | Opérations destructrices : `DELETE` **sans filtre** sur `jwt_signing_keys` (avant/après chaque test) ; `DELETE` ciblés sur `users`, `organizations` ; insertions dans `credits`, `credit_transactions`, `invoices`, `subscriptions`, `audit_logs`, `documents`, `document_chunks`, `custom_domains`, `ssl_certificates`, jetons ; écriture dans `system_logs` par le gestionnaire de logs (moteur synchrone de `DATABASE_URL`) | `tests/test_jwt_key_rotation_integration.py:62,66,176` ; `test_postgres_integration.py` (≈88 occurrences) ; `test_postgres_*_concurrency.py` ; `test_admin_dashboard.py` ; `api/security/system_log_handler.py:45-49` | Confirmé (code) | Voir CI-001 | Documenté en B.1 ; aucune exécution | — |
| CI-003 | P0 | Aucun mécanisme d'annulation de transaction : ces tests valident (`commit`) puis nettoient à la main ; un échec en cours de test laisse des lignes (déjà arrivé : `docs/CAHIER_DES_CHARGES.md`, test `system_log_handler`) | lecture des fixtures `pg_engine`, `pg_session` | Confirmé (code) | Pollution persistante d'une base partagée | Voir E, phase 2 | — |
| CI-004 | P0 | Pollution de test constatée dans la base réelle : 1 523 organisations sur 1 576 nommées « test » (créées du 11/09 au 02/10), 63 utilisateurs sur 71 en `@example.com` | `docs/FINAL_STATUS.md` (observation lecture seule du 2026-10-06) | Confirmé comme déclaré, **non revérifié** | Les lignes commencent avant le 19/09 : la CI n'en est pas la seule cause (suites locales avec le `.env`) | Requêtes de comptage lecture seule (voir C.2) | Comptages comparés à la sauvegarde du 10-06 |
| CI-005 | P0 | Protection actuelle : `tests/_remote_guard.py` + `tests/conftest.py:24-33` refusent de démarrer si `DATABASE_URL`, `DATABASE_URL_TRANSACTION`, Redis, Celery, `S3_ENDPOINT_URL` ne sont pas locaux ou si `RESEND_API_KEY` / clés Stripe-Paystack « live » sont réelles | fichiers cités ; `tests/test_remote_guard.py` | Confirmé (code) | Bon garde-fou, mais partiel | — | — |
| CI-006 | P0 | Limites du garde-fou : (a) ne couvre ni `LOKI_*`, `TEMPO_*`, `LANGFUSE_*`, `SENTRY_DSN`, ni les clés LLM payantes, Twilio, webhooks ; incidents réels : span envoyé au Tempo de production (2026-10-11), appels à l'API Anthropic (2026-10-11 et mon propre run du 11/10) ; (b) contournable par `ALLOW_REMOTE_TEST_SERVICES=1` ; (c) n'agit que sous pytest : les scripts `api.*` (`export_openapi.py`, `measure_injection_two_stage.py`, `migrate*.py`, `run_maintenance_tasks.py`, `retrieval_benchmark_pg.py`) n'ont pas de garde ; (d) `DATABASE_URL_TRANSACTION` du `.env` prime sur `DATABASE_URL` (journal `RUNTIME_DB_CONFIG … port=6543` observé lors de mon `export_openapi.py` du 2026-10-12, sans écriture attendue) | `tests/_remote_guard.py` ; `scripts/run_tests_local.sh` ; commits `eb7d460`, `beebb48` | Confirmé | Un script lancé avec le `.env` peut viser la production | Voir E, phase 2 | — |
| CI-007 | P1 | Chaque test PostgreSQL choisit sa base par `settings.DATABASE_URL` (≈22 fichiers) ; seuls 3 fichiers de concurrence exigent `RAG_DISPOSABLE_PG_URL` + confirmation du nom + hôte local (`tests/disposable_pg_guard.py`) ; le test SQL-tool exige `P0_PG_TEST_URL` contenant `/pytest_` et `127.0.0.1` | grep des variables dans `tests/` | Confirmé (code) | Les 22 fichiers dépendent uniquement du garde global | Étendre le garde disposable à tous les tests qui écrivent | — |
| CI-008 | P1 | `celery-worker.yml` : planifié (cron), exécute un vrai worker Celery avec les secrets de production sur des runners GitHub, sur le code de `main` (`78ab2b7`). 139 exécutions ; dernière réussie 2026-10-12 01:03 UTC ; une en échec (exit 137, arrêt mémoire) le 2026-10-11 18:02 UTC | API Actions ; journal du run `38162140673` (`RUNTIME_DB_CONFIG source=TRANSACTION_DATABASE`, tâches exécutées) | Confirmé | Surface d'exposition des secrets de production ; tâches de purge/maintenance sur base réelle ; consommation de minutes | Héberger le worker hors CI (décision déjà ouverte) ; en attendant, limiter le secret à un environnement protégé | Tâches observées dans les journaux Supabase |
| CI-009 | P1 | `migrate.yml` utilise le secret de production dans `environment: production-migrations` ; `workflow_dispatch` seulement, répétition par défaut (rollback), `--apply` sur case à cocher. Règles de protection de l'environnement (relecteur obligatoire) non consultables | fichier ; commentaire d'en-tête | Confirmé (fichier) · protections **NON VÉRIFIÉE** | Une application accidentelle ou malveillante par un collaborateur | Exiger un relecteur sur l'environnement | Capture des réglages GitHub |
| CI-010 | P2 | Les workflows des PR du même dépôt s'exécutent avec les secrets du dépôt : une modification de workflow dans une branche de PR peut lire `secrets.DATABASE_URL` tant qu'il est défini au niveau du dépôt | `ci.yml` (`pull_request` sur `main`) ; `celery-worker.yml` | Probable | Exfiltration possible par un collaborateur | Déplacer les secrets de production vers des secrets d'environnement avec relecteurs | — |
| CI-011 | P1 | CircleCI `api-tests` : échec sur `c04100e` (build 603) ; `resource_class: xlarge` avec `parallelism: 4` (4 conteneurs xlarge par exécution) ; le fichier mentionne un plan gratuit. Cause de l'échec inaccessible (connexion requise). La classe xlarge pourrait ne pas être disponible sur le plan : **hypothèse non vérifiée** | `.circleci/config.yml:44-45` ; statut de commit | Confirmé (échec) · cause **NON VÉRIFIÉE** | Coût en crédits ; pas de signal de non-régression | Consulter les journaux CircleCI | Run 603 |
| CI-012 | P2 | Tous les services de test CircleCI sont des conteneurs jetables (`pgvector/pgvector:pg16`, Redis, MinIO) avec valeurs « CI-only » ; aucun contexte CircleCI ; artefact = `coverage.xml` ; le journal Celery n'est affiché qu'en échec | config entière lue | Confirmé | Faible | — | — |
| CI-013 | P2 | `llm-tests.yml` : manuel, injecte `ANTHROPIC_API_KEY` du dépôt (coût) et une base SQLite | fichier | Confirmé | Coût / fuite si le journal affiche des réponses | Garder manuel | — |

### B.2 Secrets et chiffrement (P0/P1)

| ID | Prio | Constat | Preuve | Statut | Impact | Action proposée | Vérification |
|---|---|---|---|---|---|---|---|
| SEC-001 | P0 | **Sauvegarde de production** `backups/prod_backup.dump` (27 049 027 octets, 2026-10-11 18:19) dans le worktree ; `git check-ignore` retourne « non ignoré » ; `git status` la montre en `??` | `Get-ChildItem backups` ; `.gitignore` (aucune règle `backups`, `*.dump`) | Confirmé | Un `git add -A` publierait des données clients | Ajouter l'ignore (phase 1) et déplacer le fichier hors du dépôt, chiffré | `git check-ignore -v backups/…` |
| SEC-002 | P0 | `.env` avec les variables des services réels présent dans `wt-gaps` et dans l'extraction principale : base (+ pooleur), e-mail, S3, Loki/Tempo, Twilio (dont comptes de test), Redis de limitation de débit, LLM. Noms seulement relevés, valeurs non affichées | liste de noms (sans valeurs) | Confirmé | Tout script/test lancé dans ces dossiers lit ces valeurs | Voir CI-006 et E | — |
| SEC-003 | P1 | Secrets déjà partagés en conversation : mot de passe de la base de staging, clés « bac à sable » ; rotation décrite comme prérequis, jamais prouvée | `docs/security/RLS_STAGING_DECISION.md:16` ; `docs/PROMPT_COPILOT_RESTE_A_FAIRE.md:42` ; `docs/SECURITY_REPORT.md:8` | Confirmé (déclaration) · rotation **NON VÉRIFIÉE** | Compromission possible de la base de staging et des clés de test | Rotation (voir ordre plus bas) | Test d'échec d'authentification avec l'ancien secret |
| SEC-004 | P1 | Secrets de production ayant transité par la CI du 2026-09-19 au 2026-10-10 (base, e-mail, S3, JWT, chiffrement) | CI-001 | Confirmé | GitHub masque les secrets dans les journaux mais les tests les ont utilisés ; une clé JWT/chiffrement n'est pas « fuitée » pour autant | Décision propriétaire ; rotation prudente (ordre plus bas) | — |
| SEC-005 | P1 | Clés Fernet « CI-only » commises en clair dans `ci.yml` (`ENCRYPTION_MASTER_KEY`), `llm-tests.yml` et `.circleci/config.yml` (`SECRET_ENCRYPTION_KEY`) ; mots de passe de service `postgres:postgres`, `minioadmin` | fichiers cités (valeurs masquées) | Confirmé · usage « jetable » déclaré | Si une de ces clés servait ailleurs, les données chiffrées seraient lisibles par quiconque lit le dépôt | Vérifier qu'aucune n'est utilisée en production (comparaison par empreinte par la propriétaire) | Empreintes distinctes |
| SEC-006 | P2 | `.gitignore` racine ne couvre que `.env` et `.env.staging` ; le futur `.env.sandbox` prévu par le plan ne serait pas ignoré (le `frontend/.gitignore` couvre `.env*`) | fichiers | Confirmé | Commit accidentel de clés sandbox | Ignorer `.env.*` sauf `*.example` | `git check-ignore` |
| SEC-007 | P2 | Analyse par motifs des 690 commits locaux et de HEAD : **aucun secret réel détecté** ; correspondances = fixtures (`tests/test_p2_output_guard.py`, `test_security_scan.py`, `test_chat_integrations.py`), exemple JWT dans la documentation FastAPI (`data/processed/*.json`) | `git grep` / `git log -G` (clés Anthropic, URL de base avec mot de passe, Resend, Stripe live, AWS, clés privées, fichiers `.env`) | Confirmé pour ces motifs | Limites : motifs seulement ; branches distantes non récupérées ; alertes « secret scanning » de GitHub non consultées | Consulter GitHub Secret Scanning ; passer gitleaks hors ligne | — |
| SEC-008 | P2 | Branche locale `backup/pre-redaction-20261005` (jamais poussée) : contenu non vérifié en profondeur (pas de `.env` ni dump dans ses fichiers, mais l'historique « avant rédaction » est conservé) | `git ls-tree` | Suspecté | Une rédaction d'historique implique qu'un secret y a figuré | Examiner avant toute suppression de la branche | — |
| SEC-009 | P2 | Journaux : `system_logs` stocke en base chaque log ERROR du processus ; Loki/Tempo/Sentry hébergés reçoivent des logs réels ; une redaction existe (`api/security/error_tracking.py:42`) mais n'a pas été auditée ici | `api/security/system_log_handler.py` ; config | Suspecté | PII ou secrets dans les logs | Audit de redaction (phase 5) | — |
| SEC-010 | P2 | Aucune utilisation de client Supabase ni de clé « service role » dans le code ; variables `NEXT_PUBLIC_*` limitées à `API_URL`, `ENVIRONMENT`, `SENTRY_DSN` | grep | Confirmé | Positif | — | — |

### B.3 Isolation multi-tenant et RLS (P0/P1)

| ID | Prio | Constat | Preuve | Statut | Impact | Action proposée | Vérification |
|---|---|---|---|---|---|---|---|
| TEN-001 | P0 | Les migrations activent RLS (103 `ENABLE ROW LEVEL SECURITY`, 143 fichiers) mais **ne créent aucune politique** et n'utilisent jamais `FORCE ROW LEVEL SECURITY` | `Select-String` sur `api/alembic/versions` : 0 `CREATE POLICY`, 0 `FORCE` | Confirmé | « Activé sans politique » est sans effet pour le propriétaire des tables ou un rôle `BYPASSRLS` | Voir E, phase 3 | Catalogue `pg_policies` (lecture seule) |
| TEN-002 | P0 | Le rôle de connexion de l'application contourne RLS (`postgres`, `rolbypassrls = true`) | `docs/FINAL_STATUS.md` (observation du 2026-10-06 sur la base du `.env`, « not repeated ») ; `test_the_apps_own_role_bypasses_rls` exige `True` ; le code n'impose aucun rôle | Confirmé historiquement · état actuel **NON VÉRIFIÉE** | L'isolation repose entièrement sur l'application | `SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user;` par la propriétaire | Résultat de la requête |
| TEN-003 | P0 | Aucun contexte de tenant n'est transmis à la base dans cette branche (pas de `set_config`/`app.current_org*`, seulement `SET LOCAL hnsw.*` et `statement_timeout`) | grep `api/` | Confirmé | Aucune barrière de repli même avec des politiques | Voir E, phase 3 | — |
| TEN-004 | P1 | Isolation « par discipline » : des fonctions de service acceptent un identifiant sans organisation (ex. `api/security/conversations.py:99,109`, `api/services/citation_documents.py:31`, `api/security/documents.py:803`) ; la vérification vit chez l'appelant. Échantillon de 5 routeurs de conversations : tous vérifient `conversation.user_id != user.id`. Une heuristique signale 77 recherches par identifiant sans marqueur d'organisation à ±8 lignes ; **non triées une à une** | script d'analyse statique (lecture) ; lecture des appelants | Probable (structurel) · exploitabilité **NON VÉRIFIÉE** | Un nouvel appelant oubliant le contrôle expose des données | Revue des 77 candidats ; tests IDOR par domaine ; politiques RLS en second rideau | Suite de contrats IDOR par route |
| TEN-005 | P1 | Tâches asynchrones : `run_evaluation_job(db, job_id)` et le retraitement de document chargent l'objet par identifiant sans vérifier l'organisation ; la frontière de confiance est le courtier Redis | `api/services/evaluation_jobs.py:87` ; `api/security/documents.py:803` | Confirmé (code) | Un message de file falsifié ou mal routé traite le mauvais tenant | Passer `organization_id` signé/persisté et le vérifier dans chaque tâche | Tests de tâches avec identifiant d'une autre organisation |
| TEN-006 | P1 | 77 tables sur 182 n'ont ni `organization_id` ni `user_id` directs (comptage par expression régulière, à confirmer) : tenant indirect via parent (`evaluation_questions`, `conversation_messages`, `workflow_runs`, `document_versions`, …) ou tables globales | analyse statique de `api/models/` ; `docs/security/INDIRECT_TENANT_AUDIT.md`, `TENANT_ISOLATION_MATRIX.md` | Probable | Chaque accès doit joindre le parent ; une politique RLS devra le faire aussi | Valider la classification table par table avec le propriétaire du domaine | Matrice validée |
| TEN-007 | P1 | Exposition PostgREST/`anon`/`authenticated` du schéma public de Supabase : aucune preuve ; l'application n'utilise pas le SDK Supabase | grep ; `docs/AUTH_BACKEND_SETUP.md` | **NON VÉRIFIÉE** (droits et API REST à consulter dans Supabase) | Si l'API REST est active, seuls RLS + politiques protègent | Lecture des droits `anon`/`authenticated` et de l'état de l'API REST | Capture / requêtes de catalogue |
| TEN-008 | P1 | Pilote RLS (`4b4063b`, migration `0137_tenant_rls_policies_pilot`, `api/db_tenant_context.py`, politiques sur 6 tables, **sans `FORCE`**) existe seulement sur la branche locale `bob/auto-fix-20261010-1555` ; inerte pour un rôle contournant RLS ; en conflit de numéro avec `0137_evaluation_split` | `git show 4b4063b` ; analyse du graphe | Confirmé | Travail utile mais non intégrable tel quel | Renuméroter dans une phase dédiée (jamais en modifiant une migration existante) | Chaîne Alembic à une seule tête |
| TEN-009 | P2 | Un laboratoire staging a reçu 77 politiques pour un rôle de test `rag_staging_tenant` (non migrations) ; ne doit pas aller en production | `docs/audit/STAGING_TEST_REPORT.md` ; `PRODUCTION_MIGRATION_PLAN.md` | Confirmé (document) · état du staging **NON VÉRIFIÉE** | — | — | — |
| TEN-010 | P2 | SQL brut : 10 appels `text(`, 2 avec f-string (`retrieval_pipeline.py:445`, `sql_tool.py:272`), tous deux avec `int(...)` | grep | Confirmé | Faible | — | — |

### B.4 Migrations, Git et déploiement (P0/P1)

| ID | Prio | Constat | Preuve | Statut | Impact | Action proposée | Vérification |
|---|---|---|---|---|---|---|---|
| MIG-001 | P0 | Contradiction sur la révision de production : runbook `docs/RELEASE_RUNBOOK_2026-10-11.md:16` (« 0130, non vérifiée ; il faut 0131 à 0143 ») et `PRODUCTION_MIGRATION_PLAN.md` ; dossier de transmission `00`, `07`, `10`, `14` (« migrée en 0143 le 2026-10-11 par la propriétaire après sauvegarde ») ; confirmations du prompt de reprise restées `[OUI / NON]` ; seule trace locale : `backups/prod_backup.dump` du 2026-10-11 18:19 | documents cités | Contradictoire · révision réelle **NON VÉRIFIÉE** | Mauvaise décision de déploiement/fusion | `SELECT version_num FROM alembic_version;` par la propriétaire ; corriger la documentation | Valeur de `alembic_version` |
| MIG-002 | P0 | `origin/main` (merge de la PR #24, 2026-10-10 23:29 +01:00, tête de migration **0142**) mappe déjà `users.job_title` (0142) et d'autres colonnes ajoutées après 0130. Si un déploiement suit `main` et que la base est en 0130, toute requête `select(User)` échoue. Le déclencheur du déploiement (Render, Vercel) n'est pas consultable ; `render.yaml` à la racine décrit un ancien prototype (`nova-fastapi-assistant`, `/_stcore/health`) | `git show origin/main:api/models/user.py` ; `render.yaml` ; `deploy/render/render.api.yaml` | Confirmé (code) · déploiement **NON VÉRIFIÉE** | Panne de connexion des utilisateurs | Confirmer d'abord la révision (MIG-001) | Journaux de déploiement Render |
| MIG-003 | P0 | Collision `0137` : `0137_evaluation_split` (main, gaps) et `0137_tenant_rls_policies_pilot` (branche 1555) portent le même `revision = "0137"` et le même parent `0136` ; chaque branche a une chaîne linéaire propre, mais leur fusion produirait un doublon d'identifiant / deux têtes | analyse des graphes (script lecture seule) | Confirmé | Alembic échoue ; risque de migration partielle | Renuméroter le pilote en phase 4, jamais modifier l'existant | `alembic heads` = une tête, en base jetable |
| MIG-004 | P1 | PR #25 : ouverte, non fusionnée, `mergeable_state = unstable`, 43 commits, 196 fichiers (+17 880/−370) ; ajoute seulement `0143` par rapport à `origin/main` | API GitHub (lecture) | Confirmé | Les chiffres du dossier de transmission (168 fichiers, +8 421) sont périmés | Mettre à jour la description | — |
| MIG-005 | P1 | `main` local en retard de 44 commits sur `origin/main` ; `bob/auto-fix-20261010-1555` : 12 commits propres, 44 de retard sur `origin/main` ; `gaps` : 43 commits d'avance, 1 commit de `origin/main` absent (le merge de la PR #24) | `git rev-list --left-right --count` | Confirmé | Confusion de base de comparaison | Documenter la base de chaque branche | — |
| MIG-006 | P1 | Extraction principale (autre session) : 5 fichiers modifiés non commités (`api/security/system_log_handler.py`, `scripts/run_isolated_tests.py`, 3 tests) et fichiers non suivis (`FGbmsPryLaJXqu5hfC24RTZe`, `audit-reports/functional-audit-2026-10-10/`, `scripts/pending/`, …) ; 2 commits locaux non poussés (`0c4dfcf`, `52a357d`) selon le prompt de reprise | `git status` lecture seule | Confirmé | Travail non sauvegardé ; fichier inexpliqué à la racine | Le propriétaire de cette session doit commiter ou archiver | — |
| MIG-007 | P1 | CI modifiée récemment : `beebb48` (isolation), `b24fd59`, `0c94c54` (outil de migration), `13c5322` (e2e nocturne), CircleCI `f2c95c0`, `4ca7480`, `c9ef1e6`, `549a919` (xlarge, lots de 10 fichiers) ; sur 1555 seulement : `1e6c5a0` (job PostgreSQL dédié, aller-retour 0137), `0c4dfcf` | `git log -- .github .circleci` | Confirmé | Les deux branches ont des CI différentes | Réconcilier en phase 2 | — |
| MIG-008 | P1 | Le dossier de transmission contient des affirmations marquées « [R] » (exécuté) non reproductibles ici, notamment la migration de production (MIG-001) | chapitres 00/07/14 | Non vérifié | Fausse assurance pour l'assistant suivant | Corriger l'étiquette en « déclaré par la propriétaire » | — |

### B.5 Intégrations externes (P1)

| Intégration | Niveau le plus élevé établi | Preuve | Validation en production ? |
|---|---|---|---|
| PostgreSQL / pgvector | Intégration réelle **locale** (conteneur jetable) | tests `test_pgvector_real_search`, `test_postgres_*` (opt-in) | Non démontrée |
| Redis / Celery / MinIO / ClamAV / Jaeger | Intégration réelle locale (conteneurs) | `test_e2e_lifecycle`, `test_clamav_real_daemon`, `test_tracing_real_collector` | Non démontrée |
| LLM Ollama (`ollama`, `openai_compatible`) | Intégration réelle locale | `tests/llm_optin/test_local_llm_providers.py` (13 réussis le 2026-10-11) | Sans objet |
| LLM Anthropic / OpenAI / Gemini / Mistral | Mocks ; 2 appels réels Anthropic accidentels | `tests/test_llm_providers.py` ; `tests/llm_optin/test_real_llm.py` | Non démontrée |
| Stripe / Paystack | Mocks ; tests « live » ignorés sans clés de test | `test_billing_stripe_events.py` (4 marqueurs de mock), `test_billing_*_live.py` (`skipif`) | Non démontrée |
| Connecteurs (GitHub, Notion, Drive, OneDrive, Confluence, Slack/Teams/Discord) | Mocks (19 à 37 marqueurs par fichier ; aucun ne contacte le service) | `tests/test_*_integration.py` | Non démontrée |
| SSO / SCIM | Mocks | `test_enterprise_sso_integration.py` | Non démontrée |
| E-mail Resend, Twilio, Sentry, Loki/Tempo, Langfuse | Configuration seulement ; un envoi de trace réel vers Tempo a eu lieu par accident (2026-10-11) | `scripts/run_tests_local.sh`, journal | Seule l'exposition accidentelle est démontrée |
| CinetPay | Non implémenté (décision D16) | `docs/DECISIONS.md` | Non |
| Déploiements Render / Vercel / Supabase | Vercel : déploiements de prévisualisation réussis sur la PR ; reste non consultable | statuts de commit | Production **NON VÉRIFIÉE** |

---

## C. Analyse de la base de données

### C.1 Conclusions fondées sur le code et les migrations
* 143 migrations, une seule racine (`0001`), une seule tête (`0143`) sur `gaps` ; aucun identifiant dupliqué, aucun parent manquant, aucune bifurcation (script en lecture seule).
* 182 tables dans les modèles ; 83 avec `organization_id` direct ; 22 avec `user_id` seulement ; 77 sans l'un ni l'autre (tenant indirect ou tables globales).
* RLS : 103 activations, 0 politique, 0 `FORCE` (TEN-001).
* Aucun rôle SQL n'est créé par les migrations ; le rôle d'exécution est celui de l'URL de connexion (TEN-002).
* Les migrations `0131`–`0143` sont additives selon le runbook, sauf deux effets de comportement à ne pas manquer : `0134` impose une nouvelle preuve DNS TXT pour les connexions SSO existantes ; `0133` crée des déclencheurs SQL.

### C.2 Vérifications qui exigent un accès **en lecture seule** à Supabase (toutes **NON VÉRIFIÉE — ACTION EXPLICITE REQUISE**)
Requêtes de lecture proposées, à lancer par la propriétaire :
1. `SELECT version_num FROM alembic_version;`
2. `SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;`
3. `SELECT count(*) FROM pg_policies WHERE schemaname = 'public';` et `SELECT count(*) FROM pg_tables WHERE schemaname='public' AND NOT rowsecurity;`
4. `SELECT grantee, count(*) FROM information_schema.role_table_grants WHERE table_schema='public' AND grantee IN ('anon','authenticated') GROUP BY grantee;`
5. `SELECT count(*), min(created_at), max(created_at) FROM jwt_signing_keys;`
6. `SELECT count(*) FROM organizations WHERE name = 'test';` et `SELECT count(*) FROM users WHERE email LIKE '%@example.com';`
7. Journaux Supabase (connexions, requêtes) sur les créneaux des runs CI n°1–n°194 ; statut de l'API REST du projet.
8. Restauration d'essai de la sauvegarde (jamais faite, d'après les documents).

---

## D. Analyse Git et migrations

```
origin/main 78ab2b7 (merge PR #24, 2026-10-10 23:29)  ── tête migration 0142
   │
   ├── bob/auto-fix-20261010-gaps  c04100e  (PR #25, 43 commits d'avance) ── 0137_evaluation_split … 0143  (tête 0143)
   │
   └── (base commune 6619bc5) ── bob/auto-fix-20261010-1555 691f950 (12 commits propres, autre session, locale)
                                   └─ 0137_tenant_rls_policies_pilot  (tête 0137)   ⚠ même "0137" que ci-dessus
main (local) 6619bc5 : 44 commits de retard sur origin/main
```
| Branche / worktree | HEAD | Remarques |
|---|---|---|
| `wt-gaps` · `bob/auto-fix-20261010-gaps` | `c04100e` | synchronisée avec `origin` ; non suivis : `backups/`, `rag-saas-project-handover.zip` |
| principal · `bob/auto-fix-20261010-1555` | `691f950` | 5 modifications et plusieurs fichiers non suivis (MIG-006) ; 12 commits non poussés (`0c4dfcf`, `52a357d` selon la reprise) |
| `wt-ci`, `wt-20`, `wt-sec`, 5 worktrees `agent-*`, `claude/magical-dewdney-8084a4` | divers | non examinés en détail |
| `backup/pre-redaction-20261005` | `dae7b2d` | locale, jamais poussée (SEC-008) |

Révisions déclarées : runbook `0130 → 0143` ; `FINAL_STATUS.md` `0130` (2026-10-06) ; dossier de transmission `0143` ; code `gaps` `0143`, `origin/main` `0142`, branche 1555 `0137`. **La révision réellement appliquée à Supabase ne peut pas être établie sans lecture de `alembic_version`.**
Risques de fusion : collision `0137` (MIG-003) ; CI différentes (MIG-007) ; `users.job_title` & co dans `main` (MIG-002).

---

## E. Plan de remédiation (non appliqué)

| Phase | Contenu | Dépendances | Critères d'acceptation | Risques de régression |
|---|---|---|---|---|
| 1. Préservation des preuves et sécurisation | Télécharger les journaux Actions n°1–194 ; exporter les journaux Supabase ; ignorer `backups/`, `*.dump`, `.env.*` ; déplacer la sauvegarde hors dépôt et la chiffrer ; sauvegarder le travail non commité de l'autre session ; relever `alembic_version`, rôle, politiques (C.2) | Accès propriétaire | Preuves archivées ; `git check-ignore` positif ; rapport C.2 rempli | Aucun (lecture/ignore) |
| 2. Isolation des tests et de la CI | Une base jetable unique (hôte local + nom marqué + confirmation) pour **tous** les tests qui écrivent ; garde étendu (Loki, Tempo, Langfuse, Sentry, LLM payants, Twilio, webhooks) ; garde partagé par les scripts `api.*` ; tests PostgreSQL en transaction annulée ou schéma temporaire ; supprimer le secret de production du niveau dépôt, secrets d'environnement avec relecteur ; sortir le worker Celery de la CI ; réconcilier les deux CI (job PostgreSQL de 1555) ; plafonner CircleCI | Phase 1 | Aucun test ne démarre avec une URL non jetable (test de contrat) ; CI sans secret de production ; CircleCI et GitHub verts sur un commit | Tests qui supposaient la base partagée ; temps de CI |
| 3. Isolation multi-tenant et privilèges | Rôle applicatif sans `BYPASSRLS`, non propriétaire ; rôle migrations séparé ; `app.current_org` posé par transaction ; politiques table par table (`USING` + `WITH CHECK`), `FORCE` en dernier ; revue des 77 candidats et des tâches Celery ; staging d'abord, jamais directement en production | Phases 1-2, décision D2/D8 | Suite d'isolation A/B verte sous rôle sans bypass ; zéro requête sans contexte ; plan de retour arrière | Verrouillage de tous les clients si un chemin n'a pas de contexte ; workers, clés d'API, widget public, webhooks entrants, tâches planifiées, routes superadmin |
| 4. Cohérence des migrations | Renuméroter le pilote RLS ; aligner la documentation sur `alembic_version` ; vérifier le chemin 0130→0143 en base jetable (aller-retour) ; ne jamais modifier une migration existante | Phase 1 (MIG-001) | `alembic heads` = 1 ; `upgrade head` et `downgrade` en base jetable ; documents cohérents | Données SSO (0134), déclencheurs BM25 (0133) |
| 5. Corrections fonctionnelles et de sécurité | Redaction des logs ; contrôles d'organisation dans les tâches ; rotation des secrets (ordre ci-dessous) ; erreurs LLM d'embeddings (même défaut que `llm_providers`) | Phases 2-3 | Tests ciblés, chaque correction avec un test qui échoue sans elle | Selon la correction |
| 6. Tests d'intégration isolés | Pile locale jetable (PG, Redis, MinIO, ClamAV, Jaeger, Ollama) ; couverture mesurée honnêtement | Phase 2 | Résultats reproductibles par script | Durée |
| 7. Vérifications externes et validation de production | Comptes sandbox (Stripe, Paystack, LLM, Slack…) ; déploiement de staging ; smoke de production ; sauvegarde restaurée à blanc | Phases 1-6, comptes propriétaire | Preuves exécutées par service | Coûts, quotas |
| 8. Documentation et critères de mise en service | Mise à jour du dossier de transmission (étiquettes de preuve), runbook, décisions | Toutes | Revue propriétaire ; liste d'exceptions explicite | — |

**Ordre de rotation proposé (sans afficher de clé)** : (1) clés de staging et de bac à sable déjà partagées ; (2) mot de passe de la base de production et URL du pooleur, puis redémarrage des services ; (3) clés S3 et Resend ; (4) clé de chiffrement principale — **avec** `ENCRYPTION_MASTER_KEY_PREVIOUS` pour déchiffrer l'existant puis rechiffrement ; (5) clé JWT — ancienne clé en `JWT_PREVIOUS_SECRET_KEYS` seulement si elle n'est pas compromise (sinon tous les jetons deviennent invalides, effet voulu) ; (6) mettre à jour GitHub, Render, Vercel. Dépendances : fenêtre de maintenance, sauvegarde préalable restaurable.

---

## F. Registre des fonctionnalités à préserver

Aucune suppression n'est proposée. Fonctionnalités susceptibles d'être touchées par les corrections futures :

| Correction | Fonctionnalités concernées | Précaution |
|---|---|---|
| RLS + contexte tenant (phase 3) | Documents et chunks, recherche (hybride, HyDE, multi-requêtes, GraphRAG, MMR), conversations et mémoire, évaluations (jeux, jobs, résultats, comparaison), crédits, factures, abonnements, clés d'API, MCP, A2A, BeeAI, SQL-tool, widget public, webhooks entrants, SCIM/SSO, domaine personnalisé/marque blanche, tâches Celery et planifiées, routes superadmin | Contexte posé partout avant tout rôle restreint ; chemins globaux explicitement séparés |
| Isolation des tests (phase 2) | 6 300+ tests, fixtures SQLite, tests PostgreSQL, tests « live » | Aucun test supprimé ni affaibli ; ceux qui lisaient la base partagée migrent vers la pile jetable |
| Sortie du worker de la CI | Purge de compte (1.1.10), tâches planifiées, traitement de documents | Garder la cadence ; autre hébergeur à décider |
| Migrations (phase 4) | SSO entreprise (0134 : nouvelle preuve DNS), BM25 (0133), connecteurs par organisation (0143, D17), coupons, SCIM, SLA d'escalade | Communiquer l'effet 0134 aux clients concernés |
| Rotation des clés | Données chiffrées (secrets de webhooks, identifiants de connecteurs), sessions | Double clé temporaire |
| Observabilité | Sentry, Loki, Tempo, Langfuse | Garder, mais jamais depuis les tests |

Fonctionnalités partielles à conserver et à intégrer au plan : remboursements (BILL-016), coupons en pourcentage, connecteur CinetPay (non construit), OAuth Drive/OneDrive par bouton, SAML (non construit, D1), voix, GraphRAG, A2A, BeeAI, mémoire, SDK Python/JS/React/Vue. « Présent dans le code » n'a pas été assimilé à « opérationnel » dans ce rapport.

---

## G. Informations manquantes (intervention ou accès nécessaire)

1. Résultats des requêtes C.2 sur Supabase (révision, rôle, politiques, droits `anon`/`authenticated`, API REST, comptages de test).
2. Vers quelle base pointait le secret GitHub `DATABASE_URL` (comparaison du nom d'hôte seulement) ; règles de protection de l'environnement `production-migrations` ; liste complète des secrets du dépôt.
3. Journaux GitHub Actions et Supabase des runs n°1–n°194 ; journaux de l'échec CircleCI 603 (connexion requise).
4. Configuration de déploiement Render et Vercel (branche suivie, déploiement automatique, variables).
5. Statut de la rotation des secrets déjà partagés en conversation.
6. Confirmation que les clés « CI-only » des fichiers de CI ne servent pas en production.
7. Contenu et destination de `FGbmsPryLaJXqu5hfC24RTZe` et de `backup/pre-redaction-20261005` ; état du travail non commité de l'autre session.
8. Visibilité du dépôt GitHub (privé selon un commentaire de la config CircleCI, non vérifié) et alertes « secret scanning ».
9. Décision sur la restauration d'essai de la sauvegarde.

---

## Annexe — Méthode, limites et incidents à déclarer

* **Méthode** : lecture de fichiers, `git log/show/grep/rev-list/ls-tree/status` (sans fetch ni changement de branche), analyse statique Python en lecture seule (graphe des migrations, comptage des tables, heuristique des recherches par identifiant), API GitHub en lecture (PR, statuts, workflows, runs, journaux), lecture de noms de variables du `.env` sans afficher leurs valeurs.
* **Aucun test exécuté dans cette phase.** Aucune connexion à une base n'a été ouverte par cette phase.
* **Limites** : état de Supabase, Render, Vercel, CircleCI (détails), GitHub (secrets, environnements) non consultables ; heuristique de la section TEN-004 non triée ; analyse de secrets par motifs ; 5 worktrees secondaires non examinés.
* **Incidents antérieurs de ma part (sessions précédentes), déclarés par transparence** : (1) le 2026-10-12, `scripts/export_openapi.py` lancé avec `DATABASE_URL` jetable mais sans vider `DATABASE_URL_TRANSACTION` : le journal affichait le port 6543 du `.env`; aucune écriture n'est attendue (import et génération de schéma), non prouvée ; (2) le 2026-10-11, `tests/llm_optin/test_real_llm.py` a effectué 2 appels réels à l'API Anthropic avec la clé du `.env`.

### Fichiers consultés (principaux)
`.github/workflows/{ci,celery-worker,migrate,e2e,post-deploy-smoke,llm-tests,bandit,mypy}.yml` · `.circleci/config.yml` · `render.yaml`, `deploy/render/render.api.yaml` · `tests/{conftest,_remote_guard,disposable_pg_guard,test_postgres_integration,test_jwt_key_rotation_integration,test_admin_dashboard,test_p0_sql_tool_tenant_bypass}.py` et la liste des tests de connecteurs/paiement · `api/config.py`, `api/security/{system_log_handler,quotas,rate_limit,conversations,documents}.py`, `api/services/{evaluation_jobs,citation_documents,llm_providers}.py`, `api/routers/{conversations,feedback,questions,voice_messages}.py`, `api/models/*` · `api/alembic/versions/*` (143 fichiers) et celles de `origin/main` et de la branche 1555 · `docs/{DECISIONS,FINAL_STATUS,RELEASE_RUNBOOK_2026-10-11,PRODUCTION_MIGRATION_PLAN,CAHIER_DES_CHARGES,AUTH_BACKEND_SETUP,RESUME_COPILOT_POUR_CHATGPT,PROMPT_REPRISE_CLAUDE,SECURITY_REPORT}.md` · `docs/security/{RLS_STAGING_DECISION,RLS_TARGET_ARCHITECTURE}.md` · `docs/audit/*` (recherche) · `docs/project-handover/*` (chapitres 00, 01, 07, 09, 10, 11, 14 et annexes) · `.gitignore`, `frontend/.gitignore`, `.env.example` (noms) · scripts `scripts/*.py` (recherche d'imports) · API GitHub (PR n°25, runs n°1–n°232 de `ci.yml`, runs du worker, journaux de jobs).
