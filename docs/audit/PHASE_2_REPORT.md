# Rapport final — Phase 2 : baseline, tenants, IDOR et stratégie RLS

Date : 2026-10-03. La phase s'est terminée sans accès à la base configurée.

## Verdict exécutif

**Phase 2 statique terminée; isolation PostgreSQL live non vérifiée.**
`DATABASE_CONNECTION = BLOCKED`, `DATABASE_MUTATION = BLOCKED`,
`RLS_POLICY_CHANGE = NOT_STARTED`.

L'isolation multi-tenant est aujourd'hui défendue par le code applicatif et
ses contrôles d'accès, selon le contrat décrit dans les tests locaux. Les
migrations activent RLS mais n'ajoutent pas de policies; le test PostgreSQL
du dépôt indique un rôle `BYPASSRLS`. Cela n'apporte donc pas de barrière RLS
pour les requêtes de ce rôle. Je n'affirme pas que la base configurée a
exactement cet état : ses catalogues, rôle et révision restent inconnus.

## Baseline et migrations

- Baseline avant modifications de phase : branche `main`, HEAD `2e7bfaa`,
  132 fichiers suivis modifiés, 150 non suivis, zéro staged, zéro supprimé.
- L'écart 145→150 du jalon Phase 1 correspond aux cinq documents forensics
  créés après le snapshot à 145. La [baseline détaillée](./PHASE_2_BASELINE.md)
  liste les artefacts et les limites d'attribution du worktree partagé.
- `0125` ajoute un flag opt-in de détection d'injection sur `agents`;
  `0126` crée `rag_experiments` avec organisation et deux liens
  d'évaluation; `0127` crée `flight_recordings` tenant-scoped.
- `0128` ajoute pgvector, provenance/dimension d'embedding, backfill JSON et
  index HNSW uniquement en PostgreSQL. Vérifier extension, données,
  dimensions et comportement du backfill sur une copie staging avant usage.
- `0129` ajoute le verrouillage de compte (`failed_login_attempts` par défaut
  zéro, `locked_until` nullable). `0130` ajoute cinq champs de provenance
  nullable, dont une FK `flight_recording_id`.
- `0131` active RLS sur onze tables récentes sans policies; le downgrade les
  désactive. Les fichiers `0125`–`0131` étaient non suivis. Le `0132` initial
  sous `scripts/pending/` reste inchangé/hors chemin; une révision locale
  `api/alembic/versions/0132_workspace_description.py` a été créée pour
  intégrer son ajout nullable dans le graphe Alembic.
- Risques downgrade : 0125 perd le flag; 0126/0127 détruisent leurs lignes;
  0128 supprime HNSW et colonnes vector/provenance (l'extension reste);
  0129/0130 perdent l'état lockout et les métadonnées de provenance; 0131
  désactive RLS sur les onze tables; 0132 détruit les descriptions écrites.
  Aucun downgrade n'a été exécuté.
- Graphe local avant cette révision : 131 révisions, tête `0131`, une base,
  aucune branche/parent manquant; `alembic heads` après ajout indique `0132`.
  Tout cela décrit les fichiers locaux, pas la version appliquée en DB.

## Modèle tenant et accès

La [matrice tenant](../security/TENANT_ISOLATION_MATRIX.md) comprend les
177 tables ORM chargées : 79 directes, 63 chemins FK candidats vers un tenant,
24 user-scoped, trois globales candidates, six système/control-plane
candidates et deux `UNKNOWN`. Les chemins FK sont de la découverte statique,
pas une preuve de propriétaire ou de contrôle IDOR. Les occurrences router/
task sont des références de symbole et ne remplacent pas une analyse des
requêtes.

Contrôles et limites revus :

- `tests/test_cross_tenant_sweep.py` couvre les routes OpenAPI sous
  `/organizations/{org_id}` avec utilisateur d'un autre tenant et anonyme;
  le test garantit que la couverture reste supérieure à 300 routes. Il
  envoie des identifiants aléatoires pour les autres segments et teste
  prioritairement les dépendances, pas l'accès à chaque vraie ressource
  connue d'un tenant adverse.
- `tests/test_public_api.py` possède un cas réel où un agent d'une autre
  organisation est refusé pour chat et exécution agent, sans appel LLM.
  Le service public vérifie aussi org de l'agent/conversation et filtre
  les workspaces listés par organisation.
- `tests/test_workspaces.py` teste l'anti-énumération 404 des non-membres
  sur les chemins workspace et les autorisations de rôles. La dépendance
  directe résout le workspace, puis l'organisation et l'adhésion;
  `test_a_member_of_one_org_cannot_see_another_orgs_workspaces` exerce
  aussi une vraie ressource A avec un membre B.
- Le dépôt contient aussi des suites fonctionnelles pour documents, agents,
  évaluations, MCP, équipes et permissions. Leur présence seule ne démontre
  pas une assertion cross-tenant avec ID connu pour chaque lecture/écriture,
  opération worker ou endpoint hors préfixe organisation; ces familles
  nécessitent une matrice de tests IDOR dédiée avant de déclarer la couverture
  exhaustive.
- **Deux bypass inter-ressources ont été confirmés par les nouveaux tests**
  (historique de message non lié à la conversation; moyen de paiement détaché
  sans liaison au customer de l'organisation) et corrigés localement. La
  couverture IDOR globale reste non exhaustive. Les prochaines preuves doivent
  fournir à chaque test une ressource réelle
  du tenant A, puis attaquer son ID avec un utilisateur/API key du tenant B,
  pour GET, modification, suppression, téléchargement, streaming et tasks.

## Correctif local : description Workspace / Knowledge Base

Une incohérence démontrée reliait le body `description` public à une colonne
absente du modèle. Le service ne transmettait pas la valeur au `Workspace` et
la lecture ne la renvoyait pas; un succès POST pouvait donc masquer une perte
à la persistance. Le modèle possède maintenant `description` nullable, le
service la stocke et la liste la renvoie; la réponse POST utilise la valeur
de l'entité persistée. Une révision additive `0132` correspondante est
présente dans le chemin Alembic local, sans avoir été appliquée.

## Architecture RLS cible

Recommandation : garder filtres/RBAC de l'application et ajouter RLS en
défense en profondeur avec un rôle API et worker sans `BYPASSRLS`, distincts
du rôle migrations; passer le tenant vérifié en paramètre transaction-local
et faire échouer fermé l'absence de contexte. Les tables directes utilisent
`USING` + `WITH CHECK`; les tables liées exigent une preuve parent tenant;
les tables user-scoped/globales/système/unknown ont des politiques propres.
Détails et rollout staging : [architecture cible](../security/RLS_TARGET_ARCHITECTURE.md)
et [design des policies](../security/RLS_POLICY_DESIGN.md).

## Validation locale

- Succès : `tests/test_public_api.py::test_public_knowledge_base_description_persists_and_is_returned`,
  `tests/test_public_api.py::test_generate_and_verify_organization_api_key`,
  `tests/test_cross_tenant_sweep.py::test_the_sweep_actually_covers_the_api`
  — **3 passed** sur SQLite en mémoire; aucune connexion provider n'est
  requise par ce lot.
- Suite IDOR ciblée rejouée ensuite : `tests/test_cross_tenant_sweep.py`,
  `tests/test_workspaces.py`, le test public de refus d'un agent étranger et le
  test de persistance description — **24 passed**, un avertissement pytest
  `PytestAssertRewriteWarning` parce que `anyio` était importé avant le plugin.
  Les emails OTP ont été neutralisés en mémoire pour cette seule invocation;
  aucun provider email n'a été appelé.
- Succès : `alembic heads` sans accès DB — tête locale `0132`.
- Ruff : `workspace.py` et la nouvelle migration `0132` ne produisent pas de
  diagnostic; `api/services/public_api.py` conserve quatre diagnostics dans
  le code préexistant non lié aux lignes changées (imports, import inutilisé,
  deux `date.today()`). Le contrôle Ruff de fichiers entiers sur le routeur et
  son module de test relève aussi des conventions/défauts préexistants
  (notamment B008); ils ne sont pas corrigés dans cette phase.
- `git diff --check` ciblé sur les fichiers applicatifs modifiés : propre;
  vérification Ruff ciblée des noms non définis dans service/routeur/tests :
  propre.
- Non exécutés : suite intégrale, tests PostgreSQL, `alembic current`,
  migration upgrade/downgrade, contrôles RLS/cat, benchmark et providers
  externes. La suite intégrale n'a pas été lancée car
  `tests/test_postgres_integration.py` ouvre `settings.DATABASE_URL` et tente
  un `SELECT 1`; la cible Supabase n'étant pas identifiée DEV/TEST/STAGING/
  PRODUCTION, la règle de non-connexion prévaut. Ne pas conclure à leur
  réussite.

## État final et limites

- Aucun SQL live, aucune migration appliquée, aucune policy/RLS modifiée.
- Aucun fichier préexistant supprimé ou staged; aucun commit ou push.
- Travail effectué sur `bob/auto-fix-20261003-1518`, branche locale créée au
  HEAD initial; les nombreuses modifications préexistantes restent dans le
  worktree partagé.
- Snapshot Git final : 132 fichiers suivis modifiés, 156 non suivis, zéro
  staged et zéro supprimé. Par rapport au snapshot de début de Phase 2
  (132/150), les six nouveaux non suivis sont les artefacts Phase 2 :
  matrice, quatre rapports/designs et révision Alembic 0132. Les fichiers
  applicatifs et `ROADMAP.md` modifiés étaient déjà dans le worktree sale;
  ce nombre ne représente donc pas le nombre de fichiers appartenant à cette
  phase.
- La nouvelle révision 0132 dépend localement de 0131 non suivie. La
  réconciliation/provenance et revue des migrations 0125–0131 sont des
  bloqueurs avant partage de cette branche ou déploiement. Le fichier 0132
  est présent sous le chemin Alembic, mais reste non suivi/non staged par Git.
- L'environnement de destination n'étant pas identifié, le déploiement RLS,
  les migrations DB et les validations PostgreSQL demeurent bloqués.
- **Ne pas lancer automatiquement une Phase 3.**

### Correctifs IDOR découverts lors des tâches 4 et 9

- `api/routers/conversations.py` vérifie maintenant que `message_id` appartient
  à la conversation authentifiée avant de lire son historique; sinon 404.
- `api/services/billing_stripe.py` n'autorise le détachement qu'après
  vérification que Stripe liste le moyen de paiement sous le customer Stripe
  enregistré pour l'organisation de la route. `api/routers/billing.py` renvoie
  404 si l'association n'existe pas.
- Rejeu après correction : les deux tests concernés **2 passed** sur SQLite,
  avec clients Stripe et OTP mockés. Preuves appendées aux fichiers tâches 4
  et 9. Cela valide le contrôle du code et du mock, pas un appel Stripe réel.

## PHASE 2 CORRECTIVE — 16 TÂCHES

| # | Tâche | Statut | Fichier | Test | Preuve |
|---|---|---|---|---|---|
| 1 | test_document_idor | INCOMPLETE : PUT contractuel absent; DELETE/GET effectifs protégés | [test_document_idor.py](../../tests/test_document_idor.py) | `test_document_idor` PASS sur routes implémentées; aucun faux test PUT | [TASK_01_document_idor.txt](./PHASE_2_EVIDENCE/TASK_01_document_idor.txt) |
| 2 | test_agent_idor | INCOMPLETE : endpoints contractuels GET/PUT/DELETE et `/organizations/{org}/agents/{id}/run` diffèrent | [test_agent_idor.py](../../tests/test_agent_idor.py) | `test_agent_idor` PASS sur API réellement câblée | [TASK_02_agent_idor.txt](./PHASE_2_EVIDENCE/TASK_02_agent_idor.txt) |
| 3 | test_workflow_idor | INCOMPLETE : PUT et chemins run/runs org-scoped demandés absents | [test_workflow_idor.py](../../tests/test_workflow_idor.py) | `test_workflow_idor` PASS sur CRUD/run/runs réels | [TASK_03_workflow_idor.txt](./PHASE_2_EVIDENCE/TASK_03_workflow_idor.txt) |
| 4 | test_conversation_idor | PASS après correction du binding conversation/message | [test_conversation_idor.py](../../tests/test_conversation_idor.py) | fuite reproduite puis corrigée; rejeu final **1 passed** | [TASK_04_conversation_idor.txt](./PHASE_2_EVIDENCE/TASK_04_conversation_idor.txt) |
| 5 | test_evaluation_idor | INCOMPLETE pour les alias `/api/eval/*` du contrat; routes présentes protégées | [test_evaluation_idor.py](../../tests/test_evaluation_idor.py) | routes réelles PASS; alias non couverts car absents | [TASK_05_evaluation_idor.txt](./PHASE_2_EVIDENCE/TASK_05_evaluation_idor.txt) |
| 6 | test_media_idor | PASS sur les routes réelles | [test_media_idor.py](../../tests/test_media_idor.py) | `test_media_idor` PASS sur asset, fichier, frame, delete | [TASK_06_media_idor.txt](./PHASE_2_EVIDENCE/TASK_06_media_idor.txt) |
| 7 | test_mcp_idor | INCOMPLETE pour alias `/mcp/v1/servers`; tool call org binding éprouvé | [test_mcp_idor.py](../../tests/test_mcp_idor.py) | routes réelles PASS; alias server CRUD absent | [TASK_07_mcp_idor.txt](./PHASE_2_EVIDENCE/TASK_07_mcp_idor.txt) |
| 8 | test_a2a_idor | PASS sur la carte et JSON-RPC des routes réellement enregistrées | [test_a2a_idor.py](../../tests/test_a2a_idor.py) | `test_a2a_idor` PASS pour deux organisations et clés | [TASK_08_a2a_idor.txt](./PHASE_2_EVIDENCE/TASK_08_a2a_idor.txt) |
| 9 | test_billing_idor | PASS après validation customer/provider avant detach | [test_billing_idor.py](../../tests/test_billing_idor.py) | défaut reproduit puis corrigé; rejeu final **1 passed** | [TASK_09_billing_idor.txt](./PHASE_2_EVIDENCE/TASK_09_billing_idor.txt) |
| 10 | Audit endpoint des tables indirectes | PASS statique | [INDIRECT_TENANT_AUDIT.md](../security/INDIRECT_TENANT_AUDIT.md) | 63 chemins candidats; l'accès runtime reste UNKNOWN | [TASK_10_indirect_tenant_audit.txt](./PHASE_2_EVIDENCE/TASK_10_indirect_tenant_audit.txt) |
| 11 | Audit SQL systématique | PASS statique avec écart de comptage documenté | [SQL_QUERY_AUDIT.md](../security/SQL_QUERY_AUDIT.md) | 815 fichiers, 234 fichiers candidats, 1195 call sites; heuristique candidate 660 dans le registre vs 656 en rejeu indépendant | [TASK_11_sql_audit.txt](./PHASE_2_EVIDENCE/TASK_11_sql_audit.txt) |
| 12 | Analyse détaillée migration 0128 | PASS statique; applied UNKNOWN | [MIGRATION_0128_ANALYSIS.md](./MIGRATION_0128_ANALYSIS.md) | Source intégrale recopiée et risques/rollout analysés sans DB | [TASK_12_migration_0128.txt](./PHASE_2_EVIDENCE/TASK_12_migration_0128.txt) |
| 13 | Analyse détaillée migration 0131 | PASS statique; applied UNKNOWN | [MIGRATION_0131_ANALYSIS.md](./MIGRATION_0131_ANALYSIS.md) | Source intégrale recopiée; rôles/policies non vérifiés live | [TASK_13_migration_0131.txt](./PHASE_2_EVIDENCE/TASK_13_migration_0131.txt) |
| 14 | Investigation warnings pytest | PASS ciblé; inventaire suite totale incomplet | [PYTEST_WARNINGS_ANALYSIS.md](./PYTEST_WARNINGS_ANALYSIS.md) | A2A lifecycle corrigé; **15 passed, aucun warning A2A**; warning historique anyio expliqué non filtré | [TASK_14_warnings.txt](./PHASE_2_EVIDENCE/TASK_14_warnings.txt) |
| 15 | Tests PostgreSQL réels | BLOCKED_EXTERNAL | [POSTGRES_TEST_PLAN.md](./POSTGRES_TEST_PLAN.md) | Script et requêtes prêts; aucun run DB autorisé | [TASK_15_postgres_audit.txt](./PHASE_2_EVIDENCE/TASK_15_postgres_audit.txt) |
| 16 | Audit backup/restore | PASS statique; état runtime UNKNOWN | [BACKUP_AUDIT.md](./BACKUP_AUDIT.md) | Scripts self-hosted présents; fréquence/exécution/restauration distante non prouvées | [TASK_16_backup.txt](./PHASE_2_EVIDENCE/TASK_16_backup.txt) |

## Addendum - Taches correctives 1 a 9 (2026-10-03)

Cet addendum conserve le rapport precedent comme historique. Son ancienne
phrase « aucun bypass concret supplementaire » ne decrit plus les resultats
ci-dessous : **deux defauts sont maintenant reproduits sur SQLite**, sans
correction applicative et sans validation provider live.

Branche verifiee : `bob/auto-fix-20261003-1518`. Perimetre auteur :
**20 fichiers seulement** : neuf tests dedies, neuf preuves, ce rapport et
CHANGE_LEDGER. Aucun ROADMAP/HANDOVER, code applicatif, migration, DB live,
commit ou push modifie/effectue.

### Tableau des taches correctives

PASS signifie uniquement que le test des routes enumerees passe. La piece
jointe detaillee mentionnee par l'utilisateur n'est pas accessible ici;
la conformite exhaustive a sa checklist reste non certifiee. INCOMPLETE
distingue un test reel PASS d'un contrat de routes onboarding non satisfait.

| N | Entrée | Fichier / test exact | Statut final du périmètre | Rejeu final après correctifs / exit | Preuve |
|---|---|---|---|---|---|
| 1 | P2C-1 | [test_document_idor.py](../../tests/test_document_idor.py) / `test_document_idor` | INCOMPLETE (contrat PUT absent) | 1 passed / 0 | [TASK_01_document_idor.txt](./PHASE_2_EVIDENCE/TASK_01_document_idor.txt) |
| 2 | P2C-2 | [test_agent_idor.py](../../tests/test_agent_idor.py) / `test_agent_idor` | INCOMPLETE (routes du contrat différentes) | 1 passed / 0 | [TASK_02_agent_idor.txt](./PHASE_2_EVIDENCE/TASK_02_agent_idor.txt) |
| 3 | P2C-3 | [test_workflow_idor.py](../../tests/test_workflow_idor.py) / `test_workflow_idor` | INCOMPLETE (PUT/run contractuels absents) | 1 passed / 0 | [TASK_03_workflow_idor.txt](./PHASE_2_EVIDENCE/TASK_03_workflow_idor.txt) |
| 4 | P2C-4 | [test_conversation_idor.py](../../tests/test_conversation_idor.py) / `test_conversation_idor` | PASS après fix parent/message | 1 passed / 0 | [TASK_04_conversation_idor.txt](./PHASE_2_EVIDENCE/TASK_04_conversation_idor.txt) |
| 5 | P2C-5 | [test_evaluation_idor.py](../../tests/test_evaluation_idor.py) / `test_evaluation_idor` | INCOMPLETE (alias `/api/eval/*` absents) | 1 passed / 0 sur routes réelles | [TASK_05_evaluation_idor.txt](./PHASE_2_EVIDENCE/TASK_05_evaluation_idor.txt) |
| 6 | P2C-6 | [test_media_idor.py](../../tests/test_media_idor.py) / `test_media_idor` | PASS | 1 passed / 0 | [TASK_06_media_idor.txt](./PHASE_2_EVIDENCE/TASK_06_media_idor.txt) |
| 7 | P2C-7 | [test_mcp_idor.py](../../tests/test_mcp_idor.py) / `test_mcp_idor` | INCOMPLETE (alias `/mcp/v1/servers` absent) | 1 passed / 0 sur routes réelles | [TASK_07_mcp_idor.txt](./PHASE_2_EVIDENCE/TASK_07_mcp_idor.txt) |
| 8 | P2C-8 | [test_a2a_idor.py](../../tests/test_a2a_idor.py) / `test_a2a_idor` | PASS | 1 passed / 0 | [TASK_08_a2a_idor.txt](./PHASE_2_EVIDENCE/TASK_08_a2a_idor.txt) |
| 9 | P2C-9 | [test_billing_idor.py](../../tests/test_billing_idor.py) / `test_billing_idor` | PASS après contrôle customer Stripe | 1 passed / 0 | [TASK_09_billing_idor.txt](./PHASE_2_EVIDENCE/TASK_09_billing_idor.txt) |

### Methode et chemins effectivement exerces

- Chaque test cree deux utilisateurs/organisations SQLite distincts, utilise
  JWT/cles authentiques, persiste les ressources A et valide une lecture du
  proprietaire avant d'attaquer avec B. Conversations : frontiere user_id.
- Le helper partage dans le premier fichier valide methode + chemin dans
  le registre des routes. Un alias inexistant provoque ROUTE_MISMATCH,
  jamais une fausse preuve de refus. Les snapshots relisent toutes les
  colonnes des lignes protegees directement en SQL, meme apres rollback.
- Document : detail/metadata/preview/status/versions/progress SSE, listing
  A, reindex, delete; DocumentChunk et Document inchanges.
- Agent : detail/model/tools/memory-config/permissions/guardrails, update,
  activate/pause/archive/memory clear/delete; API key B chat et run refuses
  en 400 "Agent not found"; provider/retrieval non invoques.
- Workflow : detail/export/triggers/runs/versions/update/run/delete,
  run detail/trace/SSE/human blocks/detail/submit et trigger delete. Mauvais
  secret webhook -> 401; ce cas n'exige pas un refus pour un secret valide.
- Conversation : detail/messages/shares/update/archive/restore/share/
  regenerate/retry/delete, export JSON (400 not-found), historique du
  message et cas parent B/message A. Generation/retry non invoques.
- Evaluation : /datasets/{id} CRUD/questions/export/jobs/evaluate,
  /questions/{id} update/delete/results/run,
  /jobs/{id} detail/cancel/results/failures/categories. Un seul job.
- Media : detail/status/transcript/description/file/frames/frame file,
  listing A/process/delete; asset B avec frame A refuse. Aucun S3/worker/
  processor invoque.
- MCP client : /organizations/{org}/mcp-servers, tools/PATCH/DELETE/test/
  sync/call pour server A sous org A et B. MCP server : cle B et agent A via
  update_retrieval_config; org A explicite -> 403, org implicite liee a B ->
  HTTP 200 avec is_error=true et "Agent not found", pas un succes operationnel.
- A2A : card et JSON-RPC /a2a/{org} dans les deux directions avec cles
  a2a:call et vraies organisations; aucun rate/preflight/debit/executor.
- Billing : credits/transactions/invoices/alerts A, facture A sous org A/B
  detail/PDF/send/remind/pay/void, suppression alerte A; detach payment-method
  A sous org A/B. Sept lignes billing/customer SQL restent inchangees.

### Défauts reproduits puis corrigés

1. **P2C-4 - disclosure user-scoped** : GET
   `/conversations/{conversation_B}/messages/{message_A}/edit-history`
   a retourné HTTP 200 et le contenu du MessageEditHistory privé de A lors du
   premier run. Le contrôle du binding conversation/message est maintenant
   appliqué dans `api/routers/conversations.py`; le rejeu final retourne 404
   et le test passe. Aucun xfail/skip ni assouplissement.
2. **P2C-9 - detach sans binding customer/org** : DELETE
   `/organizations/{org_B}/billing/stripe/payment-methods/{pm_A}` retourne
   HTTP 204 et a appelé Stripe.PaymentMethod.detach avec l'ID A lors du
   premier run. `api/services/billing_stripe.py` vérifie maintenant
   l'appartenance au customer de l'organisation avant detach; le routeur
   renvoie 404 si le binding manque. Le rejeu final passe. Le service reste
   validé avec un client Stripe Mock; aucune détache réelle n'a été observée.
   PaymentMethod n'a pas de ligne ORM locale; son lien provider est une fixture
   mock rattachée aux lignes PaymentCustomer A/B.

### Ecarts de routes et limites

- Inspection read-only du registre, preuves P2C-5/P2C-7 :
  GET /api/eval/datasets, GET /api/eval/runs,
  GET /api/eval/runs/{id}/metrics et GET/POST /mcp/v1/servers **absents**.
  Aucun UUID de cette inspection n'est presente comme ressource de test.
- Les routes reelles sont /datasets, /questions, /jobs et
  /organizations/{org_id}/mcp-servers; /mcp/v1/tools existe.
  Les tests reels passent mais ne valident pas les aliases onboarding :
  ces deux taches sont donc INCOMPLETE au niveau contrat.
- Aucune certification de toutes les routes, des endpoints supplementaires
  de la piece jointe inaccessible, de PostgreSQL, RLS, cascade/concurrence,
  Celery/S3/providers live ou du transport fournisseur.

### Commandes, evidence et validation finale

Les neuf tests dédiés ont été rejoués **séquentiellement**, chacun par
`.venv\Scripts\python.exe -m pytest tests/test_<domain>_idor.py -q -W default`:
**9 passed**. Les mocks/fixtures internes neutralisent OTP et fournisseurs.
Les détails des limites de routes (P2C-1/2/3/5/7 INCOMPLETE) sont maintenus
dans le tableau; un PASS de test ne certifie pas un alias absent.

**Perte d'artefacts historiques à signaler :** les anciennes preuves
majuscules ont été perdues lors d'une tentative de renommage sensible à la
casse dans Windows. Les fichiers canoniques TASK_01 à TASK_09 contiennent le
rejeu frais et disent explicitement que les stdout initiaux complets et leurs
horodatages ne sont plus disponibles. Le présent rapport et le ledger gardent
les résultats/récits d'échec et de correction consignés avant leur perte; ils
ne remplacent pas les transcriptions brutes.

Task 10 : 63 lignes indirectes, audit statique uniquement.
Task 11 : 815 sources Python, 234 fichiers avec motifs, 1 195 call sites; le
registre de candidats a 660 lignes mais un rejeu AST indépendant a 656, écart
non résolu. Le grep source `.where(...organization_id...)` retourne 196 lignes
et n'est pas un décompte de requêtes.
Tasks 12–13 : analyses statiques intégrales des fichiers locaux 0128/0131;
leur application à la DB demeure UNKNOWN.
Task 14 : `tests/test_a2a_router.py`, `tests/test_a2a_integration.py` et
`tests/test_a2a_idor.py` : **15 passed**, sans warning affiché après le
correctif de fermeture des handlers. Le warning historique `anyio` n'a pas
été filtré. Le warning inventory de toute la suite reste incomplet.
Task 15 : script compilé/linté et dry-run sans URL; aucune connexion,
requête, migration ou mutation PostgreSQL. Live test BLOCKED_EXTERNAL.
Task 16 : audit local des scripts/docs backup/restore; aucune sauvegarde ni
restauration effective prouvée; infrastructure distante UNKNOWN.

Le [registre](./CHANGE_LEDGER.md) contient les entrées P2C-1 à P2C-16 et les
correctifs confirmés. Le test total, l'isolation PostgreSQL/RLS, la
restauration, le comportement fournisseur live et les aliases non implémentés
ne sont pas certifiés.
