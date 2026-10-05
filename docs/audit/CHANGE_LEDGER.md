# Change Ledger

## 2026-10-05 — Mise en coherence et resultats finaux du run complet

- JUnit `mission-backend-confirmation.xml` : 5,408 collectes,
  5,354 passes, 54 ignorees, zero echec et 23 deselections en
  10,680.761 s. `.venv\Scripts\python.exe`; debut
  20:51:26.534212 +01:00, fin calculee 23:49:27.295212 +01:00,
  le 2026-10-04. Les runs precedents ci-dessous restent historiques.
- Les 54 tests conditionnels ignores et les 23 deselections ne sont pas
  certifies comme passes. Les integrations externes manquantes restent
  bloquees/non verifiees.
- `.gitignore` exclut `/storage/` et le fichier parasite litteral
  `/requirements-api.txt;C`; `git check-ignore -v` confirme les deux regles.
- Test des policies staging conditionne par
  `RAG_EXPECT_STAGING_RLS_POLICIES=1`. Le runner staging definit lui-meme
  la variable; la commande d'integration peut aussi choisir explicitement
  le profil PostgreSQL par defaut. Les deux commandes ciblees ont ete
  bloquees avant pytest car aucun credential staging n'est provisionne
  localement; aucun acces DB n'a eu lieu.
- Le plan de migration production recommande migration 0131 puis 0132,
  verification des roles, puis deploiement applicatif; aucune production
  n'a ete contactee.

## 2026-10-04 - Parallel feature run completed

- 109 existing assertion-based feature alternatives PASS plus eight
  diagnostic staging API probes completed: total 117, zero failures/errors/
  skips, 1438.999s. Probes do not assert live success; outcomes classified
  explicitly in PARALLEL_TASKS_REPORT.md / UI_FEATURE_REPORT.md.
- Chat stream's 200 carries missing-Anthropic SSE error, not generated text.
  STT/TTS 400 provider errors, TXT/PNG missing-S3 OSError remain blocked.
  Seeded document progress, empty workflow validation and jobs list are
  partial controls; minimal evaluation question creation returns 201.
  No production provider or object store credentials used.

## 2026-10-04 - Parallel native backup and restore attempt

- Actual native pg_dump staging backup exit 0: 911502 bytes, 178 public
  CREATE TABLE statements, ignored timestamped SQL file. No secrets/data
  rows printed. Procedure/hash in BACKUP_RESTORE.md.
- Strict dotenv attempt refused placeholder; user supplied credential
  again, used only in memory. This is documented, not falsely described
  as a populated staging dotenv.
- Second Supabase project blocked by free-project limit, user authorized
  Docker. Docker CLI works, both daemon endpoints time out; no container
  created, no restore claimed, shared services left unchanged.
- Feature API/isolated alternatives launched independently of full suite.
  Exact original eight retained; no mocked test relabeled live success.
  See PARALLEL_TASKS_REPORT.md for evidence and pending result.

## 2026-10-04 - Authorized Resend and RLS contract follow-up

- User explicitly authorized using the local Resend key and updating the
  old zero-policy test. Key read privately from dotenv, never logged.
  Live key is supplied only to the two Resend integration calls; unrelated
  tests retain isolated credentials.
- Both formerly blocked Resend cases PASS. Their contract allows actual
  provider 4xx permission/domain rejections; this does not prove delivery.
  Together with the new RLS assertion: 3/3 PASS in 22.09s.
- Renamed PostgreSQL test to `test_rls_policies_exist_on_staging`, asserting
  at least 77 public policies. This is an explicitly requested new staging
  contract, not a hidden suppression of a historical failure.
- Complete post-correction run launched, including opt-in staging tests
  and original browser A/B identities. Final counts PENDING, not fabricated.
- WindowsApps winget alias works despite missing PATH entry. Requested
  unversioned PostgreSQL package ID does not exist; valid versioned
  PostgreSQL.PostgreSQL.17 selected. Client-only installation initiated,
  with server/pgAdmin/stackbuilder disabled. Completion not yet verified.

## 2026-10-04 - Full backend failure follow-up

- Full run completed: 5262 passed, 44 failed, 65 skipped, 23 deselected,
  2948.90 seconds. Not a green full-suite result.
- Individual causes, corrections and external blockers for every failure:
  [BACKEND_FAILURE_REGISTER.md](./BACKEND_FAILURE_REGISTER.md).
- Targeted final replay: 77 passed, 2 failed, zero skips/errors, 131.686s.
  42/44 original failures now pass; two live Resend cases remain
  BLOCKED_EXTERNAL (sandbox credential absent). All 44 classified individually.
- Driver-safe synchronous PostgreSQL URL helper added; task and system-log
  engines preserve SSL mode and escaped credentials.
- Isolated replay profile corrected for libpq/asyncpg SSL compatibility;
  synthetic keys supplied only to existing mocked email/DeepEval unit calls.
  No existing test assertion changed; no production credential reused.
- Frontend 32 warnings corrected: lint zero errors/warnings, type-check PASS,
  116/116 tests PASS. Translation hook dependencies, router navigation,
  workflow state callbacks and unused import corrected without suppression.
- Staging tenant role guard now rejects LOGIN, privileged flags, memberships
  and public-table ownership before granting RLS access. Live policies and
  DB isolation are not yet certified by this change.
- Follow-up: trusted current bypass administrator membership is permitted,
  with explicit SET TRUE and INHERIT FALSE; all untrusted memberships and
  memberships granting privileges to the tenant role remain rejected.
  PostgreSQL 17 creator membership initially lacked SET; actual test failed
  rather than hiding permission denial. Fixed grant and replay: 11/11 live
  RLS/IDOR cases pass, zero skips, 202.76s. 77 policies applied on staging.
  Guard/runner 29/29; targeted Ruff PASS. Specialist follow-up: no finding.
- Backup/restore remains BLOCKED_EXTERNAL: native clients absent, Docker
  server probe unresponsive, no disposable restore destination. No Supabase
  dump or restore claimed. Production plan updated without production access.

Registre chronologique des interventions de cette session sur le workspace.
Le dépôt était déjà sale; ce journal ne s'attribue pas les autres changements.

## 2026-10-04 — Backend staging, navigateur A/B et IDOR

- `.env.staging` ignore : cible remplacee par le session pooler officiellement
  confirme pour `<STAGING_PROJECT_REF>`, configuration CORS loopback exacte,
  cookies HTTP locaux et Redis loopback dedie. Credential DB injecte en
  memoire au lancement; placeholder conserve dans le fichier.
- Migrations 0001-0132 appliquees au vrai Supabase staging par lots apres
  coupure de connexion/rollback initial; aucune migration historique modifiee.
  Table Editor authentifie : alembic_version affiche 0132.
  Catalogue : 178 tables publiques, pgvector 0.8.2, HNSW.
- Backend 18039 connecte a ce pooler, frontend 13039, readiness DB/Redis/cache OK.
  Deux utilisateurs et leurs organisations crees dans les formulaires navigateur,
  connexions par mot de passe 200 et refus inter-organisation 404 dans les deux sens.
- `frontend/lib/api.ts` : echo du cookie CSRF pour POST logout/refresh;
  corrige le vrai logout 403 trouve dans le navigateur, sans affaiblir le backend.
  Nouveau `frontend/lib/api.test.ts` : 4 passants, type-check et lint cibles verts.
  Deconnexions A/B confirmees 200 apres correctif.
- `tests/staging_support.py` : reutilisation explicite des User/Org IDs du
  navigateur avec verification Owner; ressources rollback uniquement.
  `tests/test_staging_full_idor.py` : neuf surfaces bidirectionnelles,
  plus substitution org attaquante/resource victime MCP et Billing.
- `scripts/staging_validate.py` : mode explicite `--idor-only`,
  propagation des quatre IDs, JUnit ignore, plugin pytest-asyncio explicite.
  Redaction limitee aux vraies cles secretes : le flag HF TOKEN=1 ne doit
  plus masquer tous les chiffres 1 des rapports.
- Premier run live IDOR : 9 passed, zero failure/skip, 193.96 s.
  Rejeu final avec substitutions MCP/Billing : 9 passed, zero failure/error/skip,
  223.40 s; JUnit ignore verifie. SQL post-test confirme les deux Owners et
  zero ressource temporaire/API key dans les neuf tables controlees.
  Guard/config/runner : 23 passed, Ruff cible vert.
- Limites : IDOR ASGI sur vrai PostgreSQL, pas tous les verbes/routes;
  aucune policy RLS observee, aucune certification globale.
  Email/fournisseurs sandbox non verifies. Aucune production contactee.
- Details et reproduction : [STAGING_TEST_REPORT.md](./STAGING_TEST_REPORT.md).

## Baseline observée

- Branche `main`, HEAD `2e7bfaa` (2026-09-27).
- Avant les interventions documentées ici : 130 fichiers suivis modifiés,
  140 non suivis.
- Secrets locaux / caches ignorés présents. Valeurs jamais lues/copieuses.
- Worktree non isolé et non propre; aucune réinitialisation, suppression,
  stash ou changement de branche.

## Audit initial et correctifs autorisés après audit

Demandés/acceptés dans le dialogue précédent; le défaut de top-up puis le
débit A2A ont été corrigés avant ce jalon Phase 1.

| Domaine | Fichiers touchés par nos interventions | Changement / preuve |
|---|---|---|
| Top-up | `api/config.py`, `tests/test_config.py`, `tests/test_billing.py`, `docs/admin/BILLING.md` | `CREDITS_ALLOW_UNPAID_TOPUP` par défaut `False`; opt-in explicite pour self-hosted. |
| Atomicité du débit | `api/services/billing_credits.py` | `SELECT ... FOR UPDATE`, actualisation du solde verrouillé avant vérification/débit. |
| A2A billing | `api/routers/a2a.py`, `tests/test_a2a_router.py` | Préflight du coût forfaitaire complet; débit pré-exécution et commit en succès, rollback si agent échoue; BYOK exempt. Tests pour solde insuffisant, ordre débit/appel et rollback. |
| Rapports de l'audit initial | `docs/audit/INITIAL_SYSTEM_AUDIT.md`, `FEATURE_MATRIX.md`, `DATABASE_AUDIT.md`, `SECURITY_AUDIT.md`, `PRODUCTION_BLOCKERS.md` | Cinq rapports initiaux ajoutés et actualisés après corrections. |

Tests ciblés réalisés après corrections :

```
pytest tests/test_a2a_router.py tests/test_billing.py
tests/test_billing_credits_spend_caps.py tests/test_config.py
tests/test_agent_orchestrator_credit_preflight.py tests/test_agent_factory.py
tests/test_rag_control_plane_router.py -x
84 passed; 2 PytestUnraisableExceptionWarning (A2A ActiveTask)
```

Ruff complet sur ces fichiers retourne 19 constats : champs `Settings`
redéclarés existants, `Depends` FastAPI conventionnels (B008), imports/tests
préexistants. Sous-contrôles limités sur `billing_credits.py`, `test_config.py`
et tri d'import A2A passent. Ruff/tests ne valident ni PostgreSQL concurrent
ni les fournisseurs en production.

## Phase 1 forensics (jalon courant)

- Créés : `WORKSPACE_FORENSICS.md`, `DATABASE_FORENSICS.md`,
  `RLS_FORENSICS.md`, ce `CHANGE_LEDGER.md`, `PHASE_1_REPORT.md`.
- Aucun code, test, modèle, stratégie RLS, configuration ou migration modifié
  dans cette phase forensics.
- Commandes de lecture : inventaire Git/worktree/ignore; graphe Alembic;
  classification non sensible du type/host DB; comptage de métadonnées ORM;
  scans statiques migrations/RLS/pgvector; inspections locales de fichiers.
- `alembic heads/history/branches` local, sans DB : 131 révisions, une tête
  `0131`, une base, aucun merge/parent manquant.
- Aucun test applicatif, SQL live, migration ou benchmark exécuté en Phase 1.
- Cible configurée : Supabase non-local, type d'environnement inconnu.
  `DATABASE_MUTATION = BLOCKED`.

## État Git à la clôture du jalon

- Branche toujours `main`, HEAD toujours `2e7bfaa`; aucun commit créé.
- État Git observé : 132 chemins suivis modifiés et 145 non suivis.
  Ce total inclut changements préexistants, corrections autorisées ci-dessus,
  rapports et fichiers ajoutés avant cette phase. Il ne signifie pas que seuls
  les fichiers mentionnés dans ce journal sont modifiés.
- Les 0125–0131 du workspace et scripts pending 0132 sont non suivis. Ils n'ont
  pas été ajoutés/stagés.
- Les fichiers non suivis préexistants n'ont pas été lus exhaustivement ou
  réattribués; préserver leur provenance avant toute suite.

## Phase 2 — baseline, tenant, IDOR et RLS

- Baseline de départ confirmée : 132 suivis modifiés, 150 non suivis,
  zéro staged/supprimé; détail et réconciliation 145→150 dans
  `PHASE_2_BASELINE.md`.
- Branche locale créée : `bob/auto-fix-20261003-1518`, HEAD parent
  `2e7bfaa`. Aucun commit/push; base DB toujours non identifiée.
- Rapports ajoutés : `PHASE_2_BASELINE.md`, `PHASE_2_REPORT.md`,
  `../security/TENANT_ISOLATION_MATRIX.md`,
  `../security/RLS_TARGET_ARCHITECTURE.md`,
  `../security/RLS_POLICY_DESIGN.md`.
- Correctif workspace/public Knowledge Base : ajout nullable de
  `Workspace.description`, écriture et lecture depuis le service public,
  réponse POST issue de l'entité persistée; test API create→GET ajouté.
- Révision locale `api/alembic/versions/0132_workspace_description.py`
  ajoutée au graphe; le fichier préexistant
  `scripts/pending/0132_workspace_description.py` n'a pas été déplacé ni
  modifié. Upgrade/downgrade non exécutés.
- Test ciblé IDOR (balayage cross-tenant, workspaces, agent public étranger
  et create→GET description) : 24 passed; 1 avertissement plugin pytest.
  Email OTP neutralisé en mémoire pour cette invocation; aucun provider email
  ni PostgreSQL sollicité.
- Alembic local sans DB : une tête `0132`, chaîne `0131 -> 0132`.
- Ruff : modèle et nouvelle révision propres; 4 diagnostics préexistants
  dans le service public (imports/date.today); routeur/tests entiers restent
  non propres avec constats de style préexistants. Aucun de ces constats n'est
  présenté comme une validation Ruff complète.
- RLS policy/architecture uniquement documentée. Aucun SQL/catalogue live,
  aucun changement de rôle, aucune migration appliquée et aucune policy créée.

## Phase 2 corrective - P2C-1 a P2C-9 (2026-10-03)

Perimetre exclusif : neuf nouveaux tests, neuf preuves texte, ajout a ce
registre et a `PHASE_2_REPORT.md`. Branche verifiee :
`bob/auto-fix-20261003-1518`. Aucun correctif applicatif, migration, acces DB
live, commit/push, ni modification de ROADMAP/HANDOVER. Les anciennes entrees
restent historiques et ne sont pas effacees.

Execution : un processus pytest par tache, dans l'ordre 1 a 9, puis rejeu
final du meme ordre, sans parallelisme. Chaque preuve conserve les commandes
PowerShell/bootstrap exactes, stdout/stderr, code de sortie et dates ISO avec
offset. OTP neutralise par `api.routers.auth.create_and_send_email_otp =
AsyncMock()` AVANT pytest, et aussi dans le setup des tests. Ressources et
identites persistees dans SQLite en memoire via les fixtures existantes;
controle positif du proprietaire, validation de route enregistree avant les
attaques et comparaison SQL de toutes les colonnes des lignes protegees.

Limite contractuelle : la piece jointe detaillee n'est pas disponible dans
ce contexte. Les PASS concernent les chemins enumeres dans les preuves, pas
une certification exhaustive du document joint. Les aliases Eval/MCP du
contrat onboarding sont absents; P2C-5/P2C-7 restent INCOMPLETE, meme si les
tests des routes effectivement implementees passent.

### P2C-1 - Document

- Date finale : 2026-10-03T17:25:44.7438314+01:00.
- Fichiers : `tests/test_document_idor.py`,
  `docs/audit/PHASE_2_EVIDENCE/TASK_01_document_idor.txt`.
- Test : `tests/test_document_idor.py::test_document_idor`.
- Donnees/actions : Document + DocumentChunk A; utilisateur et organisation
  B reels; GET/detail/metadata/preview/status/versions/SSE/listing, reindex et
  DELETE refuses. Document et chunk inchanges; stockage et Celery non appeles.
- Validation finale : `1 passed, 1 warning in 1.75s`; exit 0.
- Statut : PASS (perimetre exerce). Aucun bug applicatif corrige.
- Historique conserve : Python global sans pgvector; premier garde reseau
  incompatible avec le socketpair asyncio Windows; utilisation du .venv
  existant et exception limitee au self-pipe local. Aucun package installe.
- Helpers communs conserves dans ce fichier pour ne pas modifier conftest :
  tenants, API key, route/denial et snapshot SQL resistant a un rollback.

### P2C-2 - Agent

- Date finale : 2026-10-03T17:26:38.3524683+01:00.
- Fichiers : `tests/test_agent_idor.py`,
  `docs/audit/PHASE_2_EVIDENCE/TASK_02_agent_idor.txt`.
- Test : `tests/test_agent_idor.py::test_agent_idor`.
- Donnees/actions : Agent A reel; GET/configuration, PATCH, lifecycle,
  memory/clear et DELETE depuis B refuses en 404; /v1/chat et /v1/agents/run
  depuis une cle B refuses en 400 avec "Agent not found".
- Validation finale : `1 passed, 1 warning in 40.16s`; exit 0; Agent inchange;
  mocks provider et retrieval non appeles.
- Statut : PASS (perimetre exerce). Aucun bug applicatif corrige.
- Historique conserve : setup API key ajuste au contrat HTTP 200 reel;
  snapshot ajuste a l'identite ORM pour eviter MissingGreenlet apres rollback.
  Aucune assertion de securite affaiblie. Une tentative d'import LiteLLM de
  charger sa cost map distante a ete bloquee par le garde de connexion;
  `LITELLM_LOCAL_MODEL_COST_MAP=True` ensuite. Pas de requete provider reussie;
  DNS n'est pas instrumente par ce garde.

### P2C-3 - Workflow

- Date finale : 2026-10-03T17:26:51.6045537+01:00.
- Fichiers : `tests/test_workflow_idor.py`,
  `docs/audit/PHASE_2_EVIDENCE/TASK_03_workflow_idor.txt`.
- Test : `tests/test_workflow_idor.py::test_workflow_idor`.
- Donnees/actions : Workflow, WorkflowTrigger, WorkflowRun et human block A
  reels; CRUD/export/triggers/runs/trace/SSE/human submit refuses a B; webhook
  refuse en 401 avec mauvais secret (son authentification est token-scoped).
- Validation finale : `1 passed, 1 warning in 1.57s`; exit 0; quatre lignes
  inchangees, un seul run, schedule/resume non appeles.
- Statut : PASS (perimetre exerce). Aucun bug applicatif corrige.

### P2C-4 - Conversation

- Date finale : 2026-10-03T17:27:05.8482173+01:00.
- Fichiers : `tests/test_conversation_idor.py`,
  `docs/audit/PHASE_2_EVIDENCE/TASK_04_conversation_idor.txt`.
- Test : `tests/test_conversation_idor.py::test_conversation_idor`.
- Donnees/actions : deux conversations privees user-owned, message A et
  MessageEditHistory A reels; lecture/mutation/export/share/delete directes
  refusees. JSON export retourne 400 avec detail not-found.
- Premier run : `1 failed, 1 warning in 2.53s`; exit 1.
- Defaut reproduit : GET /conversations/{conversation_B}/messages/{message_A}/
  edit-history retourne 200 et le contenu prive de l'historique A. Les lignes
  restent inchangees et les mocks generation/retry ne sont pas appeles.
- Correction locale : `api/routers/conversations.py` charge le message et
  vérifie `message.conversation_id == conversation.id` avant de lire
  l'historique; sinon 404. Cette vérification lie l'ID message à la ressource
  autorisée de la requête.
- Rejeu : test conversation + billing, **2 passed, 1 warning in 4.00s**;
  voir ajout FINAL FIX REPLAY dans la preuve tâche 4.
- Statut final : PASS après correction. SQLite valide le chemin applicatif;
  aucune DB distante.

### P2C-5 - Evaluation

- Date finale : 2026-10-03T17:27:20.6435955+01:00.
- Fichiers : `tests/test_evaluation_idor.py`,
  `docs/audit/PHASE_2_EVIDENCE/TASK_05_evaluation_idor.txt`.
- Test : `tests/test_evaluation_idor.py::test_evaluation_idor`.
- Donnees/actions : Dataset, Question, Job, Result et Failure A reels;
  /datasets, /questions et /jobs : lectures/export/modifications/suppression/
  lancement/cancel/resultats/failures refuses a B.
- Validation finale : `1 passed, 1 warning in 2.36s`; exit 0; cinq lignes
  inchangees, un seul job, evaluation/provider et schedule non appeles.
- Ecart de route : GET /api/eval/datasets, GET /api/eval/runs et
  GET /api/eval/runs/{id}/metrics non enregistres, confirme par inspection
  read-only du registre le 2026-10-03; sortie exacte dans la preuve.
- Statut : INCOMPLETE pour le contrat onboarding; test des routes reelles
  PASS. Aucun 404 d'alias absent presente comme preuve IDOR.

### P2C-6 - Media

- Date finale : 2026-10-03T17:27:36.1042126+01:00.
- Fichiers : `tests/test_media_idor.py`,
  `docs/audit/PHASE_2_EVIDENCE/TASK_06_media_idor.txt`.
- Test : `tests/test_media_idor.py::test_media_idor`.
- Donnees/actions : assets A/B, transcript et frame A reels; GET/status/
  transcript/description/file/frames, process et DELETE refuses; asset B
  associe au frame A egalement refuse.
- Validation finale : `1 passed, 1 warning in 3.55s`; exit 0; quatre lignes
  inchangees; stream/delete S3, process et schedule mocks non appeles.
- Statut : PASS (perimetre exerce). Aucun bug applicatif corrige.

### P2C-7 - MCP

- Date finale : 2026-10-03T17:27:50.6305988+01:00.
- Fichiers : `tests/test_mcp_idor.py`,
  `docs/audit/PHASE_2_EVIDENCE/TASK_07_mcp_idor.txt`.
- Test : `tests/test_mcp_idor.py::test_mcp_idor`.
- Donnees/actions : MCPServerConfig, MCPToolCache et Agent A reels; chemins
  org A et org B refuses pour tools/PATCH/DELETE/test/sync/call. Cle MCP B
  refuse organisation A en 403; agent A sans org explicite retourne une
  erreur protocolaire HTTP 200, is_error=true et "Agent not found".
- Validation finale : `1 passed, 1 warning in 2.09s`; exit 0; trois lignes
  inchangees; aucun mock connexion/sync/call externe invoque.
- Ecart de route : GET/POST /mcp/v1/servers non enregistres; CRUD reel sous
  /organizations/{org_id}/mcp-servers; outils internes sous /mcp/v1/tools.
- Statut : INCOMPLETE pour le contrat onboarding; test des routes reelles
  PASS. Aucun appel externe HTTP/subprocess.

### P2C-8 - A2A

- Date finale : 2026-10-03T17:28:06.8073768+01:00.
- Fichiers : `tests/test_a2a_idor.py`,
  `docs/audit/PHASE_2_EVIDENCE/TASK_08_a2a_idor.txt`.
- Test : `tests/test_a2a_idor.py::test_a2a_idor`.
- Donnees/actions : organisations, cles a2a:call et credits A/B reels;
  GET agent-card et POST JSON-RPC cross-tenant dans les deux sens refuses
  en 404; card proprietaire accessible en 200.
- Validation finale : `1 passed, 1 warning in 2.48s`; exit 0; organisations
  et credits inchanges, nombre transactions inchange; rate/preflight/debit/
  executor non appeles.
- Statut : PASS (perimetre exerce). Aucun agent/LLM lance.

### P2C-9 - Billing

- Date finale : 2026-10-03T17:28:23.1353003+01:00.
- Fichiers : `tests/test_billing_idor.py`,
  `docs/audit/PHASE_2_EVIDENCE/TASK_09_billing_idor.txt`.
- Test : `tests/test_billing_idor.py::test_billing_idor`.
- Donnees/actions : Invoice/InvoiceLine/Credit/CreditTransaction/UsageAlert
  A et PaymentCustomer A/B reels; acces cross-org et IDs A sous org B
  refuses pour facture/PDF/send/remind/pay/void/alert.
- Premier run : `1 failed, 1 warning in 3.54s`; exit 1.
- Defaut reproduit : DELETE /organizations/{org_B}/billing/stripe/
  payment-methods/{pm_A} retourne 204 et invoque Stripe.PaymentMethod.detach.
  Le client Stripe est integralement un Mock; l'association pm_A -> client A
  est une fixture provider rattachee aux vraies lignes PaymentCustomer,
  pas une ligne SQLite PaymentMethod (ce modele n'existe pas).
- Les sept lignes SQL restent inchangees et les emails ne sont pas appeles.
- Correction locale : `api/services/billing_stripe.py` charge le
  `PaymentCustomer` Stripe de l'organisation et s'assure que le moyen demandé
  figure dans la liste retournée pour ce customer avant detach. L'absence de
  client/association produit une erreur not-found; le routeur traduit en 404.
- Rejeu : test billing + conversation, **2 passed, 1 warning in 4.00s**;
  voir ajout FINAL FIX REPLAY dans la preuve tâche 9. Aucun appel Stripe réel.
- Statut final : PASS après correction. Le test valide le contrôle avec
  Stripe Mock; le comportement provider live n'a pas été observé.

### Validation commune et cloture corrective

- Premier rejeu final avant correctifs : sept PASS, deux FAIL. Après deux
  correctifs IDOR et rejeu des tests concernés : neuf tests locaux des routes
  réelles ont un passage, avec deux contrats d'alias toujours INCOMPLETE
  (évaluation et MCP).
- Une PytestAssertRewriteWarning anyio par invocation, conservee dans les
  preuves (bootstrap importe auth avant la decouverte du plugin).
- Ruff existant : `.venv\Scripts\python.exe -m ruff check --select
  E9,F63,F7,F82` sur les neuf fichiers de test -> `All checks passed!`.
  Ce sous-controle ne constitue pas un lint exhaustif.
- Les commandes/retries ne modifient que les fichiers autorises; aucun
  nouveau helper/conftest, dependance ou fichier applicatif. Caches pytest/
  Python habituels possibles; aucune modification preexistante annulee.
- Aucune verification PostgreSQL/RLS, migration ou validation provider live.
  Pas de certification complete de la piece jointe inaccessible ni de la
  matrice de toutes les routes. Ne pas lancer une autre phase automatiquement.

### Correctifs de sécurité issus des tests IDOR

#### P2C-FIX-4 — Liaison historique message/conversation

- ID: P2C-FIX-4
- DATE: 2026-10-03
- PHASE: 2-corrective
- FILE: `api/routers/conversations.py`
- PROBLEM: un propriétaire pouvait requêter l'historique d'un message étranger en combinant son propre conversation_id et le message_id de l'autre utilisateur.
- ROOT CAUSE: la route authentifiait la conversation, mais appelait `get_edit_history` avec le seul message_id.
- CHANGE: charger le message et rejeter 404 lorsque son `conversation_id` ne correspond pas à la conversation autorisée.
- TEST: `tests/test_conversation_idor.py::test_conversation_idor`.
- RESULT: PASS, rejoué avec `test_billing_idor`; 2 passed, 1 PytestAssertRewriteWarning.
- RISK: contrôle validé en SQLite en mémoire, pas sur PostgreSQL live.
- ROLLBACK: ne pas retirer le binding message/conversation; si rollback du correctif requis, rétablir le code antérieur uniquement avec une approbation de sécurité et remplacer par une vérification équivalente testée.

#### P2C-FIX-9 — Propriété Stripe PaymentMethod

- ID: P2C-FIX-9
- DATE: 2026-10-03
- PHASE: 2-corrective
- FILE: `api/services/billing_stripe.py`, `api/routers/billing.py`
- PROBLEM: un manager d'organisation pouvait demander le détachement d'un identifiant PaymentMethod appartenant à une autre organisation.
- ROOT CAUSE: le service detach prenait seulement le payment_method_id et appelait Stripe sans comparer au customer de l'organisation.
- CHANGE: lire le PaymentCustomer Stripe de l'organisation, rechercher le PaymentMethod dans les méthodes attachées à ce customer, rejeter si absent, puis détacher.
- TEST: `tests/test_billing_idor.py::test_billing_idor`.
- RESULT: PASS avec Stripe Mock après correction; 2 tests conversation/billing passés en un run, aucun provider live.
- RISK: le mapping réel entre PaymentMethod et PaymentCustomer doit encore être éprouvé contre Stripe en environnement test identifié.
- ROLLBACK: ne pas revenir au detach par ID libre; tout rollback de code exige une alternative avec contrôle d'appartenance au customer.

### Note de conservation des preuves P2C-1 à P2C-9

- Les fichiers de preuve d'origine étaient nommés avec suffixes majuscules.
  Une tentative de renommage sensible à la casse a vidé le dossier sur ce
  workspace Windows.
- Les neuf tests ont été rejoués séquentiellement le 2026-10-03, chacun avec
  `.venv\Scripts\python.exe -m pytest tests/test_<domain>_idor.py -q -W default`;
  les nouveaux fichiers canoniques TASK_01 à TASK_09 contiennent ces sorties.
- Les sommaires des premiers échecs et des corrections restent dans ce ledger
  et `PHASE_2_REPORT.md`, mais les anciens stdout complets et leurs
  timestamps précis ne sont plus disponibles. Les nouvelles preuves ne les
  présentent pas comme des sorties historiques.
- Neuf tests ont passé au rejeu, mais P2C-1/2/3/5/7 restent INCOMPLETE pour
  les routes/aliases contractuels absents ou différents.

### P2C-10 — Inventaire des tables indirectes

- Fichier : `docs/security/INDIRECT_TENANT_AUDIT.md`.
- Résultat : 63 lignes de tables avec chemin FK candidat, dénombrées avec
  `Select-String -CaseSensitive`; `UNKNOWN` conservé lorsque l'accès/guard
  runtime n'est pas prouvé.
- Aucune base ni requête runtime n'a été utilisée.
- Preuve : `docs/audit/PHASE_2_EVIDENCE/TASK_10_indirect_tenant_audit.txt`.

### P2C-11 — Audit des call sites SQLAlchemy

- Fichier : `docs/security/SQL_QUERY_AUDIT.md`.
- Rejeu AST : 815 fichiers Python, 234 fichiers avec motifs, 682 `select`,
  392 `db.get`, 121 `db.execute`, total 1 195; un-liner
  `.where(...organization_id...)` = 196 lignes sources.
- Écart conservé : registre d'origine = 660 candidats; replay AST indépendant
  avec le texte de fonction/call = 656. L'outil générateur initial n'existe
  pas comme script persistant; quatre lignes restent à réconcilier. Ce sont
  des candidats statiques, pas des vulnérabilités établies.
- Preuve : `docs/audit/PHASE_2_EVIDENCE/TASK_11_sql_audit.txt`.

### P2C-12 — Analyse migration 0128

- Fichier d'analyse : `docs/audit/MIGRATION_0128_ANALYSIS.md`.
- La migration locale est recopiée en entier; dimension effective, backfill,
  index HNSW/cosinus, verrous, entrées invalides, downgrade et rollout sont
  analysés statiquement.
- État appliqué : UNKNOWN. Aucune migration ou connexion DB exécutée.
- Preuve : `docs/audit/PHASE_2_EVIDENCE/TASK_12_migration_0128.txt`.

### P2C-13 — Analyse migration 0131

- Fichier d'analyse : `docs/audit/MIGRATION_0131_ANALYSIS.md`.
- La migration locale est recopiée en entier; onze tables, zéro policy,
  implications de rôles/BYPASSRLS, workers, opérateurs et tests sont
  documentés. L'affirmation de docstring n'est pas considérée comme une
  observation live.
- État appliqué, rôles effectifs et policies : UNKNOWN.
- Preuve : `docs/audit/PHASE_2_EVIDENCE/TASK_13_migration_0131.txt`.

### P2C-14 — Warning lifecycle A2A

- Défaut observé : des `ActiveTask._run_consumer` / `_run_producer` du SDK
  restaient en attente lorsque le handler JSON-RPC par requête n'était pas
  fermé.
- Correction : `api/routers/a2a.py` ferme le handler après transmission de
  chaque réponse (background task), et lors d'un échec avant réponse.
- Rejeu A2A : 15 passed, aucun warning affiché. Le warning historique
  `PytestAssertRewriteWarning: anyio` reste expliqué mais non filtré.
- Aucune validation provider, streaming réseau ou PostgreSQL live.
- Preuve : `docs/audit/PHASE_2_EVIDENCE/TASK_14_warnings.txt`.

### P2C-15 — Préparation audit PostgreSQL en lecture seule

- Fichiers : `docs/audit/POSTGRES_TEST_PLAN.md`,
  `scripts/postgres_readonly_audit.py`,
  `scripts/postgres_readonly_audit.sql`.
- Le script a été compilé et lancé uniquement sans `--execute`; il confirme
  `DRY RUN: no database connection`. Exécution future exige un environnement
  DEV/TEST/STAGING explicite et une variable d'approbation, et force une
  transaction read-only, timeouts et catalogue seulement.
- Cible actuelle UNKNOWN; aucune connexion/SQL/migration exécutée.
- Statut live : BLOCKED_EXTERNAL.
- Preuve : `docs/audit/PHASE_2_EVIDENCE/TASK_15_postgres_audit.txt`.

### P2C-16 — Audit backup/restore

- Fichier : `docs/audit/BACKUP_AUDIT.md`.
- Les scripts self-hosted existent (`scripts/backup.sh`,
  `scripts/restore.sh`); `pg_dump` ne couvre pas les objets S3/media,
  l'upload S3/R2 est opt-in, le scheduling central n'est pas fourni et aucun
  backup/restore effectif n'a été prouvé. La rétention distante peut toucher
  tout objet sous le prefix.
- Configuration SaaS distante, fréquence réelle, dernière sauvegarde,
  restauration, RTO/RPO : UNKNOWN.
- Preuve : `docs/audit/PHASE_2_EVIDENCE/TASK_16_backup.txt`.

## Mission autonome staging — 2026-10-03

- Branche vérifiée créée : `bob/auto-fix-20261003-191324`; HEAD
  `2e7bfaa3c3fbca3b1a66ad26f9c9ce5ad19d15a2`.
- `.env.staging` template seulement; ignoré avec `staging-artifacts/`.
  Aucun secret du chat recopié, aucun credential production lu/chargé.
- Modifications code : sélection opt-in RAG_ENV_FILE dans API et loader
  historique; nouvelles commandes exact-host staging; nouveaux tests
  d'URL, sélection dotenv et IDOR/RLS PostgreSQL opt-in.
- Modifications frontend : prompt initial par lazy useState, dépendance
  `t` du loader; échappement de guillemets sans changement de texte rendu.
- Validation : 18 tests guard/config/loader passés, 11 live skips; 112
  tests frontend passés, type-check vert, lint 0 erreur / 32 warnings.
- Premier pytest complet : six erreurs de collection causées par
  ChromaDB/googleapiclient/mem0/Streamlit absents. Packages rétablis aux
  versions déjà déclarées, aucun manifest modifié; pip check vert.
- Résultats du replay complet : voir `docs/AUTONOMOUS_AUDIT_06_TESTS.md`.
  Aucun test existant supprimé ou modifié pour contourner un échec.
- Résultat complet final : 4 993 passed, 125 failed, 208 skipped,
  23 deselected, exit 1. Rejeux ciblés : 104 échecs initiaux passants;
  pas de nouveau PASS global. Config/retest 307 pass/4 fail/13 skip,
  média/observabilité 40 pass/11 skip, email unit 23 pass,
  framework/guards 34 pass.
- Profil isolé : clés Fernet/AES éphémères et PYTHON_DOTENV_DISABLED=1,
  avec test réel de non-chargement dotenv tiers. Aucun fichier secret lu.
- SDK déclarés restaurés : ultralytics/faiss, Sentry/OpenLineage et
  BeeAI/LightRAG; PyTorch CPU conservé, pip check vert. Restauration
  Presidio/DeepEval/Docling refusée sous contraintes des pins installés
  (NumPy/Click/Typer); DSPy absent des manifests, à réconcilier.
- Outil inventory ajouté : sources/markers, 936 opérations via les route
  contexts de FastAPI 0.141, 177 tables ORM; aucun catalogue live inféré.
- Staging : resolver alternatif AAAA disponible, transport IPv6 10051,
  pas de DB connectée; `pg_dump` absent, daemon Docker indisponible.
  Pas de backup/restore, aucune modification migration historique.
- Étude voix : clone public LiveKit externe, SHA `96341b0`, évaluation et
  plan; aucune dépendance/provider RTC intégré.
- Rapports ajoutés : staging/décision RLS/plans production, discovery,
  sécurité, IDOR, fixes/tests, backup/restore, performance et bilan.
- Aucun commit ni push. L'inventaire worktree inclut des modifications
  préexistantes et n'est pas une attribution à cette seule mission.

## Lot SDK et runner — 2026-10-04

- `scripts/staging_validate.py` : import relatif si lancé en module,
  import local si lancé en script. ModuleNotFoundError reproduit puis
  corrigé; deux tests entrypoint dans `tests/test_staging_target.py`.
  Validation guard/config/loader : 22 pass, Ruff PASS.
- `requirements-api.txt` : DSPy 3.4.0 déclaré pour le service existant.
- Docling/Presidio/DeepEval/DSPy installés ensemble après dry-run
  conservant les pins embeddings/Torch CPU. Résolution des dépendances
  transitives NumPy/Click/Typer/Rich/Hugging Face; pip check PASS.
- Rejeu SDK/extraction/guard : 63 pass, zéro skip, 30.793 s. Huit
  échecs initiaux supplémentaires ont un rejeu passant; pas un run
  complet ni huit corrections de code métier.
- PII réelle en cours; DNS staging retesté 11001, aucune DB contactée.
- Sitemap réseau rejoué : 4/4 sans skip; échec initial non reproduit,
  aucun changement de code. 113/125 échecs initiaux passants au rejeu,
  sans annoncer une suite complète verte.
- PII réelle finalisée : 4/4 sans skip, modèle en_core_web_lg 3.8.0;
  831.040 s incluant provisioning, pip check PASS. Bilan des échecs
  initiaux rejoués passants : 117/125; huit cas non résolus.

## CI Celery — travail parallèle au run backend, 2026-10-04

- `.github/workflows/celery-worker.yml` : suppression du `|| true`
  inconditionnel; propagation des erreurs, timeout TERM et grace 60 s.
  0/124 acceptés pour le burst planifié, SIGKILL et erreurs échouent.
- `tests/test_celery_worker_workflow.py` : neuf codes testés dans le
  bloc Bash réel du YAML, 9 passed/1.43 s, Ruff PASS.
- Harness initial WSL incompatible corrigé par sélection Git Bash
  natif Windows. Aucun test historique changé.
- Aucun workflow distant lancé, aucun worker réel ni production contactés.
  Suite complète existante laissée active; nouveau test hors collection
  de ce run, validation distincte.

## Scripts backup/restore — 2026-10-04

- Backup : temporaire avec nettoyage EXIT, gzip vérifié, publication
  par lien dur sans écrasement; aucun dump incomplet nommé valide.
- Restore : contrôle gzip avant accès Docker; ON_ERROR_STOP=1.
  Erreur SQL ne produit plus une réussite du script.
- Six tests shell sans base réelle, groupe CI+backup 15/15 en 3.90 s,
  Ruff PASS. Documentation install/operations/fixes/tests actualisée.
- Pas de backup/restore staging, RTO/RPO ou rollback réel validés.
  Aucun script mutateur lancé contre Docker ou production.
