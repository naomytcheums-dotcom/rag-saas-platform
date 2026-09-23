# Roadmap

This file tracks what's genuinely planned next, as distinct from what's
already built. For the full history of what has been delivered — audited,
built, tested — see [`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md),
which covers all 25 development parts.

## Shipped

All 25 planned development parts are complete as of this documentation
pass (Partie 25). Core platform, multi-tenancy, billing, RBAC, RAG
pipeline, agents, autonomous agents, workflows, evaluation lab,
fine-tuning, media/vision (YOLO, CLIP), A/B testing, analytics,
white-labeling, marketplace/plugins, security/compliance, admin
dashboard, and now documentation are all built and tested. See
[`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md) for the
itemized breakdown of each part.

## Known, honestly-documented gaps

- **[VÉRIFIÉ, Phase 5 Étape 11] API/Developer Platform existait déjà,
  bien au-delà du périmètre demandé.** Audit complet avant tout code :
  API keys réelles (`OrganizationAPIKey`, hash, scopes, rotation,
  quotas, rate-limit -- Partie 9.1/9.2), auth `X-API-Key` réelle,
  rate limiting réel (fenêtre glissante Redis), **webhooks CRUD
  complets** (`Webhook`/`WebhookDelivery`, signature HMAC, retry, test,
  logs de livraison -- Partie 9.2.7), documentation API réelle
  (OpenAPI + Redoc, régénérée et vérifiée à l'Étape 10). **Au-delà du
  spec demandé : 3 vrais SDK déjà présents et testés** (`sdks/python/`,
  `sdks/js/`, `sdks/react/`, chacun avec ses propres tests réels). Seul
  vrai gap trouvé : pas de Sandbox Environment isolé -- tracé ci-dessous.
- **[TRACÉE, P2] Pas de Sandbox Environment isolé (données de test
  séparées de la prod, TTL automatique).** Investigation menée avant
  de coder (question posée à l'utilisateur) : un vrai sandbox isolé
  demanderait de taguer `is_sandbox` sur quasiment CHAQUE modèle
  existant qui accepte des données créées via API (documents,
  conversations, agents, workflows...) et de filtrer ce flag à CHAQUE
  point de lecture -- une chirurgie transversale, pas un ajout additif
  comme les deux autres gaps de cette étape. **Pourquoi pas construit**
  : une version partielle (juste un modèle `SandboxEnvironment` sans
  vraie isolation des autres ressources) donnerait une fausse
  impression de sécurité/isolation aux développeurs externes qui s'y
  fieraient -- pire que ne rien avoir. **Priorité : P2** (les
  développeurs externes peuvent déjà tester contre une organisation
  réelle dédiée aux tests, juste sans isolation ni purge automatique).
  **Complexité estimée : substantielle** -- un vrai plan concret :
  (1) ajouter `is_sandbox: bool` à `OrganizationAPIKey` (une clé
  `pk_test_...` vs `pk_live_...`, comme Stripe) ; (2) propager ce flag
  dans le contexte de chaque requête authentifiée par API key ; (3)
  ajouter une colonne `is_sandbox` aux tables réellement créables via
  l'API publique (documents, conversations, messages -- pas toutes les
  ~200 tables du schéma, seulement celles réellement exposées par
  `api/routers/public_api.py`) ; (4) filtrer par défaut dans chaque
  requête de lecture publique ; (5) une tâche Celery planifiée de purge
  après le TTL. Un vrai projet de plusieurs jours, pas une passe.
- **[CORRIGÉE, Phase 5 Étape 11] Observability : 2 vrais gaps trouvés
  et fermés.** Audit complet d'abord : traces agent (`AgentTrace`),
  tokens/coût par organisation (`OrganizationUsage`), latence
  (`latency_metrics.py`), dashboards Grafana, alerting (channels/rules/
  incidents) existaient déjà, tous vérifiés réels. **(1) Traces
  workflow par nœud** -- `WorkflowRun` n'avait que `context`/
  `current_node_id` (l'état courant), jamais un historique réel,
  queryable, par nœud (contrairement à `AgentTrace` pour les agents).
  Fermé : `WorkflowNodeExecution` (migration `0120`, appliquée et
  vérifiée en aller-retour réel contre Postgres), câblé dans la vraie
  boucle d'exécution (`api/services/workflow_engine.py`'s own
  `_advance`), couvrant les 3 chemins réels (succès, échec, pause sur
  bloc `human`). `GET /workflows/runs/{run_id}/trace` réel. Testé
  (4 tests réels, y compris l'isolation entre deux runs distincts).
  **(2) Diagnostics retrieval pour les requêtes live** -- seul Eval Lab
  avait une vraie visibilité par question (`EvaluationResult`), aucune
  pour une conversation de chat réelle. Fermé : `RetrievalDiagnostic`
  (migration `0121`, appliquée et vérifiée), câblé dans le vrai point
  d'entrée de génération (`api/services/generation.generate_response`),
  `GET /organizations/{org_id}/retrieval-diagnostics` réel, org-scopé
  et vérifié isolé (5 tests réels, y compris un test explicite prouvant
  qu'aucun contenu de chunk n'est dupliqué dans la table diagnostic).
  **Scope honnête, documenté dans le code** : capture la requête, la
  stratégie résolue, les chunks finaux avec scores, et la latence --
  PAS une décomposition avant/après-reranking détaillée (instrumenter
  individuellement les 5 fonctions de stratégie + 3 couches
  d'amélioration optionnelles de `retrieval_pipeline.py`'s own déjà
  testé aurait été invasif pour un gain marginal face à la vraie
  question "cette organisation a-t-elle un problème de retrieval" que
  ce scope répond déjà).
- **[TRACÉE, P0 -- hypothèse infirmée, cause réelle toujours inconnue]
  Le service Redis ajouté à `backend-tests` (`ci.yml`) N'A PAS résolu
  les ~15 échecs auth/SSO CI-only tracés à l'Étape 10.** Vérifié
  rigoureusement, pas supposé : un vrai run CI complet a été déclenché
  après l'ajout du service `redis:7-alpine` + `RATE_LIMIT_REDIS_URL=
  redis://localhost:6379/0` -- le run est allé jusqu'au bout cette fois
  (22m37s, plus de timeout), mais **exactement les mêmes tests
  échouent, avec exactement les mêmes assertions** (`assert 403 == 200`,
  `assert 200 == 401`, etc.) -- l'hypothèse "Redis injoignable/pollué"
  de l'Étape 10 est donc réellement fausse, pas juste non confirmée --
  ce n'est PAS un problème de Redis. **Impact réel** : `backend-tests`
  reste rouge sur chaque push/PR vers `main`, ce qui masque le vrai
  signal de tout AUTRE test qui casserait réellement (un vrai
  régression future se noierait dans ces ~15 échecs déjà connus) --
  un vrai risque opérationnel pour la fiabilité du CI, pas cosmétique.
  **Nouvelle piste, non testée** : ces ~2200+ tests tournent tous dans
  UN SEUL process pytest sur ce runner (contrainte CPU réelle, 2 cœurs
  sur un runner GitHub Actions standard), alors qu'en local ils ont
  toujours été exécutés isolément (`pytest tests/test_auth_api.py`
  seul) -- un vrai state partagé entre tests (event loop asyncio,
  cache JWT en mémoire de `api/security/jwt.py`, un mock de temps non
  réinitialisé) pourrait ne se manifester que sous cette combinaison
  précise de volume + concurrence + ordre d'exécution. **Priorité :
  P0** (inchangée -- bloque toujours `backend-tests` de passer au
  vert). **Plan concret révisé, en 2 temps** : (1) diagnostic --
  ajouter un vrai logging détaillé (état de `jwt_signing_keys`, contenu
  réel du cache JWT, timestamp serveur) juste avant chaque assertion
  qui échoue en CI, lancer `pytest tests/test_auth_api.py
  tests/test_enterprise_sso_integration.py
  tests/test_oauth_logic_integration.py` SEULS (pas la suite complète)
  sur le MÊME runner GitHub Actions pour comparer directement contre le
  comportement local déjà confirmé correct (171/171) ; (2) une fois la
  vraie cause confirmée par ce diagnostic, corriger le code réel (pas
  le test) si c'est un vrai bug de state partagé, ou isoler
  proprement le state entre tests si c'est un problème de fixture.
  **Complexité : moyenne** -- le diagnostic lui-même est rapide (un
  run CI ciblé, quelques lignes de logging temporaire), mais la
  correction finale dépend de ce que ce diagnostic révèle réellement,
  d'où le classement "moyenne" plutôt que "faible" tant que la cause
  exacte n'est pas confirmée.
- **[CORRIGÉE, Phase 5 Étape 11] `docs/api/openapi.json` était de
  nouveau obsolète** -- les 2 nouveaux endpoints de cette étape
  (`GET /workflows/runs/{run_id}/trace`,
  `GET /organizations/{org_id}/retrieval-diagnostics`) n'avaient pas
  été suivis d'une régénération. Confirmé par le même run CI ci-dessus
  (`test_committed_openapi_export_matches_live_app` a re-échoué).
  Régénéré (712 chemins réels, +2 vs l'Étape 10). **Leçon retenue** :
  ce test existe précisément pour attraper ça -- chaque étape qui
  ajoute un routeur doit régénérer avant de pousser, pas seulement au
  moment où le test le signale.
- **[CORRIGÉE, Phase 5 Étape 10] `docs/api/openapi.json` était
  réellement obsolète** (confirmé par le test dédié
  `tests/docs/test_api_reference.py::test_committed_openapi_export_matches_live_app`,
  jamais exécuté avec succès en CI avant cette étape -- ferme
  exactement le gap "openapi.json drift" tracé P3 à l'Étape 8, ET
  répond à sa propre recommandation ("un test CI qui échoue si le
  fichier commité diffère du schéma généré en live" existait déjà,
  il suffisait qu'un vrai run CI l'exécute). Régénéré réellement
  depuis `api.main.app.openapi()` (710 chemins réels), test repassé
  en vert (38/38 dans `tests/docs/` + `tests/test_api_key_management.py`).
- **[CORRIGÉE, Phase 5 Étape 10] Vrai bug d'oubli de l'Étape 9 :
  `PUBLIC_API_SCOPES` compte 13 scopes réels depuis l'ajout de
  `"mcp:tools"`, mais 2 tests avaient toujours `== 12` en dur.**
  Trouvé par ce même premier vrai run CI. Corrigé
  (`tests/test_api_key_management.py`, les deux assertions + une
  nouvelle assertion explicite `"mcp:tools" in scopes`).
- **[TRACÉE, P0] ~15 tests réels de `tests/test_auth_api.py` +
  `tests/test_enterprise_sso_integration.py` échouent SEULEMENT sur le
  runner CI, jamais en local.** Vérifié rigoureusement, pas supposé :
  `python -m pytest tests/test_auth_api.py` en local → **171/171
  passent** ; le même fichier sur le runner GitHub Actions → ~15
  échecs réels, tous de la même famille (`assert 403 == 401`,
  `assert 200 == 401`, `assert 403 == 200`, un `RuntimeError: coroutine
  raised StopIteration`) -- des flux de session/refresh/blacklist/CSRF
  qui se comportent différemment selon l'environnement. **Cause
  probable, non confirmée** : `backend-tests` ne démarre aucun service
  Redis réel, alors que `RATE_LIMIT_REDIS_URL` (un vrai secret GitHub,
  configuré) doit pointer vers quelque chose -- soit une instance
  injoignable depuis ce runner (comportement de repli différent d'un
  environnement local où Redis tourne réellement), soit une instance
  RÉELLE et PARTAGÉE dont l'état (sessions/blacklist déjà présents
  d'un run précédent) pollue ce run. **Pourquoi pas diagnostiqué plus
  loin dans cette passe** : confirmer laquelle des deux hypothèses est
  réelle demanderait d'inspecter la valeur réelle du secret
  `RATE_LIMIT_REDIS_URL` (jamais fait par principe -- les secrets ne
  doivent jamais être exposés/manipulés directement) et/ou de modifier
  l'infrastructure CI (ajouter un vrai service `redis:` au job,
  générer une URL de test dédiée) -- un vrai changement d'infra, pas
  un correctif de code. **Priorité : P0** (bloque `backend-tests` de
  passer au vert sur CI, même si ça ne bloque PAS `build-backend`,
  découplé exprès -- voir plus bas). **Plan concret** : ajouter un
  vrai service `redis:7-alpine` au job `backend-tests` de `ci.yml`
  (`services: redis: image: redis:7-alpine`) et pointer
  `RATE_LIMIT_REDIS_URL` vers `redis://localhost:6379/0` pour CE job
  spécifiquement (pas le secret partagé), puis relancer et confirmer.
  **Complexité : faible** -- un bloc `services:` YAML de 5 lignes
  (même syntaxe que les services Postgres/Redis déjà réels dans
  `.github/workflows.disabled/regression.yml`/`.circleci/config.yml`,
  rien de nouveau à inventer), suivi d'un simple `git push` de
  vérification -- aucun changement de code applicatif requis.
- **[ACCEPTÉE] `build-backend` ne dépend plus de `backend-tests`
  (`needs:` retiré volontairement).** Le job `build-backend` existe
  spécifiquement pour vérifier qu'une image Docker se construit,
  vérification indépendante de la santé de la suite de tests --
  bloquer la vérification du build P0 sur un problème réel mais
  distinct (l'investigation Redis ci-dessus) mélangerait deux
  préoccupations différentes. `build-frontend`, lui, dépend de
  `frontend-checks` (déjà vert, aucune raison de découpler).
- **[VÉRIFIÉ, Phase 5 Étape 10] Eval Lab existait déjà, bien au-delà du
  périmètre demandé par cette étape.** Audit complet mené avant tout
  code (règle PROMPT CATCH) : `EvaluationDataset`/`EvaluationQuestion`
  (ground truth réel : `expected_documents`, `expected_answer`,
  difficulté/catégorie)/`QuestionSet`+`QuestionSetItem`/
  `BenchmarkVersion` (snapshots versionnés) `api/models/evaluation.py`.
  Métriques réelles et calculées (pas de placeholder) : Recall@1/3/5/10,
  MRR, NDCG, Precision, Hit Rate (`api/services/retrieval_metrics.py` +
  `api/services/ground_truth_documents.py`). Batch evaluation réel via
  Celery (`api/services/evaluation_jobs.py`), avec annulation réelle
  (`POST /jobs/{id}/cancel`). Comparaison réelle
  (`ComparisonJob`, 4 types : model/retriever/reranker/prompt).
  **Au-delà du spec demandé** : détection de régression automatique
  entre deux jobs (`RegressionDetection`/`RegressionThreshold`, par
  organisation), gate d'évaluation avant déploiement d'un agent
  (`DeploymentEvaluation`), évaluation manuelle humaine
  (`ManualEvaluation`), A/B testing EN PRODUCTION avec statistiques
  réelles (p-value, intervalle de confiance -- `ABTest`/
  `ABTestAssignment`/`ABTestResult`). 65 endpoints réels au total sur
  10 routeurs. Multi-tenant réel et vérifié
  (`require_org_admin`+`require_dataset_admin`/`require_question_admin`,
  même convention "ressource puis rôle" que le reste du codebase).
  Import/export de questions déjà réels. Coût par résultat déjà tracé
  (réutilise `api/services/cost_tracking.py`). 24 fichiers de tests
  réels. **Aucune construction nécessaire cette étape** -- le travail
  a consisté à auditer, vérifier, et tracer les 3 gaps réels restants
  ci-dessous plutôt qu'à reconstruire quelque chose de déjà mature.
- **[TRACÉE, P2] Eval Lab n'a pas d'UI frontend dédiée.** Seul
  `frontend/components/fine-tuning/ModelEvaluation.tsx` existe, sans
  rapport avec ce module. Aucune page dataset/run/comparaison/graphique
  n'existe pour ce module pourtant très complet côté backend.
  **Pourquoi pas construit dans cette passe** : une UI complète
  (listes, détail de run, comparaison avec deltas, graphiques Recall@K/
  MRR, export) est un vrai travail frontend substantiel, hors du
  périmètre "corrections + vérifications" de cette étape combinée
  Docker CI + Eval Lab, et cette session a déjà consommé un temps très
  important sur les étapes précédentes. **Priorité : P2** (le module
  est pleinement utilisable via l'API dès aujourd'hui -- Postman/script
  -- juste pas via une UI dédiée). **Complexité estimée : substantielle**
  (plusieurs pages + composants + graphiques, à l'image de
  `frontend/components/ab-tests/` qui existe déjà comme précédent réel
  à suivre pour le style).
- **[TRACÉE, P3] Pas de progression en temps réel (SSE) pour un
  `EvaluationJob` en cours -- seul le polling via `progress`/
  `completed_questions`/`total_questions` existe.** **Priorité : P3**
  (fonctionnel, juste moins réactif qu'un push). **Complexité estimée :
  faible** (réutiliser le pattern SSE déjà établi par
  `api/services/streaming.py`/le stream d'exécution de workflow).
- **[TRACÉE, P3] Pas de budget/coût plafonné par `EvaluationJob`** --
  le coût est réellement calculé et rapporté après coup
  (`calculate_cost_per_request`), mais rien n'arrête un run en cours
  de route si un budget est dépassé. **Priorité : P3** (visibilité
  déjà réelle, juste pas de coupe-circuit). **Complexité estimée :
  faible** (un champ `max_cost` sur `EvaluationJob` + une vérification
  dans la boucle Celery existante).
- **[TRACÉE, P2] Eval Lab — analyse d'échecs catégorisée
  (retrieval/génération/hallucination) non implémentée.** Vérifié par
  audit (Étape 10) : `EvaluationResult.metrics` stocke bien les scores
  réels par question (recall/mrr/precision/ndcg/faithfulness/etc.),
  mais rien ne catégorise AUTOMATIQUEMENT un échec donné comme "le
  retrieval n'a pas trouvé le bon document" vs "le document était là
  mais la génération l'a mal utilisé" vs "l'agent a halluciné" -- un
  opérateur doit encore inspecter les métriques brutes lui-même pour
  comprendre POURQUOI une question a échoué, question par question.
  **Impact réel** : les métriques d'échec sont déjà visibles et
  exploitables aujourd'hui (rien de caché), mais le diagnostic reste
  manuel -- pas de vue "voici vos N échecs, groupés par cause probable"
  pour prioriser les corrections. **Priorité : P2** (utile pour
  accélérer l'itération qualité, pas bloquant -- le module Eval Lab
  reste pleinement fonctionnel sans ça). **Complexité estimée :
  moyenne** -- une règle de classification réelle existe déjà comme
  précédent partiel à réutiliser (`recall_at_k` bas + `expected_documents`
  non vide ⇒ probable échec de retrieval ; `recall_at_k` haut mais
  `faithfulness`/`groundedness` bas ⇒ probable échec de génération/
  hallucination), à formaliser en une vraie fonction
  `categorize_failure(result: EvaluationResult) -> str` + un endpoint
  d'agrégation (`GET /eval/runs/{id}/failures?category=...`), à traiter
  dans une passe future dédiée.
- **[CORRIGÉE, Phase 5 Étape 10] Le premier vrai run CI (déclenché par
  cette étape elle-même) a trouvé 3 vrais bugs, invisibles en local,
  que la promesse "runner CI stable" de cette étape a justement
  révélés.** (1) `mcp==2.0.0` avait été `pip install`é dans
  l'environnement de dev pendant l'Étape 9 mais jamais déclaré dans
  `requirements-api.txt` -- `ModuleNotFoundError` sur tout checkout
  propre (CI, Docker, production réelle), corrigé. (2)
  `app/layout.tsx` utilise le type `LayoutProps<"/">` généré par Next.js
  (typed routes), présent seulement après un `next dev`/`next build`
  local -- absent sur un checkout CI propre. Corrigé en ajoutant `npx
  next typegen` avant `tsc --noEmit` dans `ci.yml` (vérifié réellement :
  `rm -rf .next && npx next typegen && npx tsc --noEmit` reproduit puis
  résout l'erreur exacte du CI). (3) `pip-audit` a trouvé 15
  vulnérabilités réelles dans 3 paquets -- `bleach` corrigé (bump mineur
  6.2.0→6.4.0, sans risque, régression ciblée passée) ; `transformers`
  et `weasyprint` tracés ci-dessous (bump majeur, risque réel de
  rupture).
- **[TRACÉE, P1] `transformers==4.57.6` a 7 avis de sécurité réels
  (PYSEC-2025-217, PYSEC-2026-2288/2289/2290/3929), correction
  seulement à partir de `5.0.0`/`5.3.0`/`5.5.0`/`5.10.0`.** **Impact
  réel** : la version installée en production reste exposée à 7
  vulnérabilités connues et publiées tant que le bump n'est pas fait --
  `pip-audit` (CI `backend-security`) continue de le signaler en rouge
  à chaque run tant que ce n'est pas corrigé, un vrai signal, pas un
  faux positif. **Pourquoi pas corrigé dans cette passe** : un saut de
  version majeure (4.x→5.x) sur une dépendance ML aussi profondément
  intégrée (`sentence-transformers`, embeddings, citations) a un vrai
  risque de rupture d'API -- le bump à l'aveugle sous contrainte de
  temps contredirait la discipline "mesurer deux fois" de cette même
  session. **Priorité : P1** (vulnérabilités de sécurité réelles, pas
  cosmétiques). **Complexité estimée : substantielle** -- bump vers
  `5.10.0`, relancer la suite complète de tests retrieval/embeddings/
  citations, vérifier les breaking changes documentés par HuggingFace
  entre 4.x et 5.x.
- **[TRACÉE, P1] `weasyprint==63.1` a 5 avis de sécurité réels
  (PYSEC-2026-2034/3412/3940), correction seulement à partir de
  `68.0`/`70.0`.** **Impact réel** : même exposition -- signalé en
  rouge par `pip-audit`/CI `backend-security` à chaque run tant que non
  corrigé ; utilisé pour la génération de PDF (exports), une surface
  réelle bien que plus restreinte que `transformers`. Même raisonnement
  que `transformers` ci-dessus : bump
  majeur (63→70), utilisé pour la génération de PDF (exports), risque
  de régression non négligeable sous contrainte de temps. **Priorité :
  P1**. **Complexité estimée : modérée** -- bump + tests des
  fonctionnalités d'export PDF existantes.
- **[CORRIGÉE, Phase 5 Étape 9] MCP (Model Context Protocol) n'existait
  pas du tout** (confirmé par audit : zéro fichier, zéro dépendance,
  zéro doc avant cette étape). Ajouté réellement, dans les deux sens :
  **MCP Client** (`api/services/mcp/client.py`, utilise le vrai SDK
  officiel `mcp==2.0.0`, déjà installé -- `ClientSession`/
  `stdio_client`/`sse_client`/`streamable_http_client` réels, jamais de
  JSON-RPC réinventé à la main) -- un agent peut appeler un tool
  exposé par un serveur MCP externe enregistré par l'organisation
  (`MCPServerConfig`/`MCPToolCache`, migration `0119`, appliquée et
  vérifiée en aller-retour réel contre Postgres). **MCP Server**
  (`api/routers/mcp_server.py`) expose le vrai tool registry statique
  de la plateforme (`api/services/tools.py`) à des clients MCP
  externes, sur une vraie surface `tools/list`/`tools/call` au format
  MCP réel (vérifié contre les vrais noms de champs du SDK installé,
  `input_schema`/`is_error`, pas devinés -- deux vrais bugs de nommage
  trouvés et corrigés pendant le développement des tests : le SDK
  utilise `input_schema`/`is_error`, pas les anciens noms camelCase
  `inputSchema`/`isError`). **Aucun nouveau mécanisme d'auth** : le
  serveur MCP réutilise `require_public_api_scope("mcp:tools")`, le
  même `X-API-Key` org-scopé, rate-limité et quota-suivi que chaque
  autre endpoint public `/v1/*` existant. Intégré au tool registry des
  agents (`api/services/agent_tools.py`'s own `_build_mcp_tool`) via
  la convention `mcp:{server_id}:{tool_name}`, résolu par run, jamais
  mis en cache entre organisations. Testé contre un VRAI serveur MCP
  de test (`tests/mcp_test_server.py`, un vrai serveur stdio utilisant
  le même SDK, pas un mock du protocole) : 23 tests, tous passants
  (7 client + 10 routeur client + 6 routeur serveur), couvrant
  discovery/call/erreur-de-tool/tool-inconnu/isolation-multi-tenant/
  auth-manquante/scope-manquant.
- **[TRACÉE, P2] MCP n'expose pas les tools custom (webhooks
  org-spécifiques) ni les tools par-run (ex. `execute_sql_query`).**
  Décision délibérée de cette étape, pas un oubli : `execute_sql_query`
  lie `db`/`organization_id` par fermeture (voir l'entrée Étape 6 sur
  `tool_wiring.py`) -- l'exposer génériquement à un client MCP externe
  via `/mcp/v1/tools` demanderait une revue de sécurité par-tool
  distincte (quelle organisation ce client représente-t-il ? déjà
  répondu pour le sens CLIENT via `X-API-Key`, pas encore conçu pour
  le sens SERVER sans dupliquer cette même logique). **Priorité : P2**
  (le tool registry statique déjà exposé couvre le cas d'usage
  principal -- calculs, GitHub, calendrier, email, HTTP). **Complexité
  estimée : modérée** (étendre `/mcp/v1/tools` pour n'inclure les
  tools custom d'une organisation que lorsque la clé API appelante
  appartient à CETTE organisation -- déjà vrai pour l'auth, il manque
  le filtrage par org dans `list_tools_endpoint`/`call_tool_endpoint`).
- **[CORRIGÉE, Phase 5 Étape 10] Build Docker backend ET frontend
  enfin vérifiés pour de vrai, sur un vrai runner GitHub Actions.**
  `build-backend` ✓ en 8m44s (job 107291194496, run 35893399884),
  `build-frontend` ✓ en 22s (grâce au cache GHA, 2e confirmation
  consécutive après un premier ✓ à 3m26s). Fermeture définitive du P0
  ouvert depuis l'Étape 7 : après 4 tentatives locales infructueuses
  (bcrypt/torch/ddtrace/ReadTimeoutError, toutes confirmées comme de
  l'instabilité réseau locale, jamais un vrai défaut de code), le
  déplacement de la vérification vers un runner CI stable -- exactement
  la recommandation de cette étape -- a réellement tranché la question.
  Aucun changement de code Dockerfile n'a été nécessaire : les deux
  images se construisent avec le code existant, une fois sur un réseau
  fiable.
- **[HISTORIQUE, résolu ci-dessus] Build Docker backend ET frontend
  toujours non vérifiés de bout en bout après un 3e cycle de tentatives
  (Étape 7 :
  2 essais : bcrypt puis torch, réseau ; Étape 9 : 2 essais
  supplémentaires chacun).**
  **Backend, essai 1 (Étape 9)** : réseau nettement plus stable
  (bcrypt ET torch résolus sans erreur cette fois, contrairement à
  l'Étape 7), mais échec plus loin sur `ERROR: No matching
  distribution found for ddtrace` -- vérifié indépendamment
  (`pip install --dry-run ddtrace` réussit localement, `ddtrace==4.14.0`
  déjà installé) : encore un faux positif réseau, un paquet réel
  différent à chaque essai étant le signe distinctif de ce pattern.
  **Backend, essai 2 (dernier autorisé)** : échec quasi immédiat, sur
  le tout premier paquet (`fastapi==0.141.1`), avec cette fois un
  `ReadTimeoutError` explicite et non ambigu dans le log lui-même --
  confirmation directe, pas déduite, que la cause est réseau.
  **Frontend, essai 1 (Étape 9)** : `npm ci` a échoué immédiatement
  (`EUSAGE`, lockfile désynchronisé) -- cause réelle et corrigée :
  `npm install` n'avait jamais été relancé après le correctif
  `@types/node` de l'Étape 7 (le précédent `npm install` avait été
  interrompu -- `TaskStop` -- faute de progression). `npm install`
  relancé avec succès (528 paquets, 0 vulnérabilité).
  **Frontend, essai 2 (dernier autorisé)** : contrairement à tous les
  essais précédents (qui produisaient au moins un flux de couches
  Docker), celui-ci n'a produit STRICTEMENT AUCUNE sortie pendant une
  durée très anormalement longue -- pas même le chargement initial du
  Dockerfile, normalement instantané. Interrompu explicitement
  (`TaskStop`), pas laissé tourner indéfiniment (règle de gestion des
  tokens). **Facteur environnemental identifié** : un conteneur
  `airbyte-abctl-control-plane` tourne sur cette même machine depuis
  plusieurs heures (`docker ps -a`), une infra de développement sans
  rapport, candidate plausible à la contention réseau/ressources
  observée sur les deux services (Docker Hub, PyPI, npm) tout au long
  des Étapes 7 et 9.
  **Impact réel** : ni l'image backend ni l'image frontend n'ont
  encore été prouvées buildables de bout en bout dans CET
  environnement de développement précis -- la syntaxe reste vérifiée
  (`docker compose config`, `nginx -t`), et le seul vrai bug de code
  jamais trouvé sur ce chemin (`@types/node`, Étape 7) est déjà
  corrigé. **Priorité : P0** (un déploiement réel ne doit jamais
  reposer sur "ça devrait marcher"). **Plan concret** : relancer les
  deux builds (`docker build -f Dockerfile.api -t rag-saas-api .` /
  `docker build -f frontend/Dockerfile -t rag-saas-frontend
  ./frontend`) sur une machine/réseau différent de cet environnement
  de développement précis (un runner CI, un autre poste) -- rien
  côté code n'a été identifié comme cause probable après 4 tentatives
  distinctes touchant 4 paquets différents, tous vérifiés réels.
- **[TRACÉE, P2] Le branding d'organisation (`OrganizationBranding`)
  n'est appliqué nulle part dans l'UI globale du frontend, et le
  widget a son propre système de branding totalement découplé.**
  Trouvé lors de l'audit Étape 8 : `frontend/app/layout.tsx` (et tous
  les `layout.tsx`) ne référencent jamais `useWhiteLabel`/le branding
  d'org -- seule la page `frontend/app/dashboard/whitelabel/page.tsx`
  (config + preview) lit ces données. Un client configure logo/couleurs
  et ne les voit appliqués nulle part dans l'app elle-même. Par
  ailleurs `api/routers/widget.py` a son propre `WidgetConfig`
  (logo/thème/couleurs indépendants), zéro référence à
  `OrganizationBranding` -- deux systèmes de branding parallèles.
  **Impact réel** : la promesse "White Label" n'est tenue que pour les
  emails (partiellement, voir l'entrée P2 existante ci-dessous) et le
  domaine custom -- pas pour l'apparence de l'application elle-même,
  ce qui est probablement l'attente n°1 d'un client White Label.
  **Priorité : P2** (fonctionnalité vendue mais non appliquée
  visuellement, pas une faille de sécurité). **Complexité estimée** :
  modérée -- lire `OrganizationBranding` dans le layout serveur
  (`layout.tsx`), injecter les couleurs en CSS custom properties,
  conditionner le logo affiché ; unifier ou documenter explicitement
  pourquoi le widget reste un système séparé (cas d'usage différent :
  embarqué sur un site tiers, pas le dashboard).
- **[TRACÉE, P2] Aucune suite `stripe_live` équivalente à
  `tests/test_billing_paystack_live.py`.** Trouvé lors de l'audit
  Étape 8 : `grep -rln "paystack_live\|stripe_live" tests/` ne retourne
  qu'un seul fichier, côté Paystack. Stripe est testé unitairement
  (mocks) mais n'a pas de suite marquée `stripe_live`/`skipif` pour
  vérifier contre de vraies clés Stripe test quand elles sont
  disponibles -- asymétrie réelle entre les deux providers.
  **Impact** : un bug d'intégration Stripe réel (format de payload
  webhook qui change, signature réelle) ne serait détecté qu'en
  production, contrairement à Paystack qui a ce filet. **Priorité :
  P2**. **Complexité estimée** : faible -- même pattern que
  `test_billing_paystack_live.py` (`pytestmark`, `skipif` sur clés
  d'env absentes), dupliqué pour Stripe.
- **[TRACÉE, P3] Aucune vraie mesure de performance p50/p95 en continu,
  pas de cache applicatif Redis.** Trouvé lors de l'audit Étape 8 :
  `api/services/latency_metrics.py`/`tests/test_latency_metrics.py`
  est le SEUL outil de mesure de latence réel du repo (percentiles
  calculés sur des runs chronométrés), mais c'est un outil ponctuel
  d'évaluation, pas un dashboard de production. Redis n'est utilisé
  que pour le rate-limiting et le pub/sub temps réel (notifications/
  workflow), jamais comme cache applicatif (`grep` ne trouve aucun
  `redis.get/set` de mémoïsation). Eager loading SQLAlchemy
  (`selectinload`/`joinedload`) limité à 5 fichiers sur l'ensemble du
  code -- risque de N+1 non traité ailleurs. **Impact** : pas de
  visibilité continue sur la latence réelle en production au-delà de
  ce qu'expose `/metrics` (Prometheus, compteurs de requêtes HTTP, pas
  de percentiles LLM/retrieval dédiés) ; performance potentiellement
  dégradée sous charge sans cache. **Priorité : P3** (fonctionnel
  aujourd'hui, mais pas observable/optimisé pour l'échelle).
  **Complexité estimée** : modérée à substantielle (ajouter un vrai
  cache Redis pour les embeddings/résultats de retrieval fréquents,
  auditer les relations SQLAlchemy chaudes pour l'eager loading,
  exposer des percentiles LLM/retrieval réels dans `/metrics`).
- **[TRACÉE, P3] Pas de documentation d'architecture système globale.**
  `docs/architecture/` ne contient qu'un seul fichier
  (`LEGACY.md`), qui documente le statut de `src/` (prototype legacy)
  vs `api/`, pas une vue d'ensemble des composants/flux/stack.
  `docs/diagrams/{MULTI_TENANCY,DATABASE}.md` compensent partiellement.
  **Priorité : P3** (la doc opérationnelle -- install/admin/user/
  sécurité -- est déjà complète et confirmée ; c'est une vue d'ensemble
  transverse qui manque). **Complexité estimée** : faible à modérée
  (un document + éventuellement un diagramme, pas de nouveau code).
- **[TRACÉE, P3] `docs/api/openapi.json` est un instantané statique,
  non régénéré automatiquement.** FastAPI génère l'OpenAPI en direct
  à `/openapi.json` (`api/main.py`), mais aucun script/job CI ne
  resynchronise `docs/api/openapi.json` avec le schéma réel -- vérifié
  par `grep` vide sur `scripts/` et `.github/workflows/*.yml`.
  **Impact** : le fichier documenté peut dériver silencieusement du
  schéma réel à chaque changement de route non suivi d'une régénération
  manuelle. **Priorité : P3**. **Complexité estimée** : faible (un
  script `scripts/export_openapi.py` + une étape CI qui échoue si le
  fichier commité diffère du schéma généré en live).
- **[VÉRIFIÉ, non un gap] SSRF sur les intégrations webhook (Airbyte,
  Discord, Slack) sans `ssrf_safe_client`.** Un audit initial (Étape 8)
  avait signalé `api/services/airbyte_client.py`,
  `api/services/chat_integrations/{discord,slack}.py` comme utilisant
  `httpx.AsyncClient` directement. **Vérifié en détail, ce n'est PAS
  un vrai gap** : chaque appel cible une constante fixe
  (`_SLACK_POST_MESSAGE_URL`, `_DISCORD_API_BASE`,
  `settings.AIRBYTE_API_URL`), jamais une URL fournie par un tenant ou
  extraite d'un payload externe -- seuls des segments de chemin
  (`channel_id`/`message_id`, des IDs Discord/Slack réels, pas des
  URLs) sont interpolés. `ssrf_safe_client()` protège spécifiquement
  les chemins où l'HÔTE lui-même est contrôlable par un tenant (outils
  custom, bloc HTTP de workflow, extraction Confluence/Notion/etc.) --
  ces trois fichiers n'en font pas partie par construction. Documenté
  ici pour éviter qu'un futur audit re-signale le même faux positif.
- **[ACCEPTÉE] Le JWT applicatif ne porte pas de claim `aud`/`iss`.**
  Vérifié (`api/security/jwt.py`) : le payload ne contient que
  `sub`/`purpose`/`jti`/`exp`. **Accepté car** : ce système a UNE
  seule audience (cette API elle-même valide ses propres tokens, pas
  de fédération vers un service tiers qui recevrait le même JWT) --
  `aud`/`iss` protègent contre un token émis pour un service rejoué
  contre un autre, un scénario qui n'existe pas ici. Le scoping réel
  se fait via le claim `purpose` (access vs refresh vs reset, etc.),
  vérifié côté serveur à chaque usage. Deviendrait un vrai gap si une
  fédération multi-services validant les mêmes tokens était introduite.
- **[Phase 5, Étape 8 -- opérationnel, pas un gap de code] 148
  fichiers modifiés/nouveaux non commités au moment de cet audit**
  (dernier commit réel : `40db65c`, 2026-09-19) -- tout le travail des
  Étapes 6/7/8 (long-term memory, function calling, Sentry, nginx,
  ainsi que des fichiers pré-existants au tout début de la session)
  vit dans le working tree, pas dans l'historique git. Signalé pour
  que l'utilisateur commite avant tout déploiement basé sur le dépôt
  distant -- aucune action de commit prise ici (règle : ne jamais
  committer sans demande explicite de l'utilisateur).
- **[CORRIGÉE, Phase 5 Étape 8] Dossier parasite vide
  `nginx/templates;C/`** trouvé pendant l'audit White Label/Déploiement
  (artefact d'une commande `mkdir` mal interprétée sous Git Bash à
  l'Étape 7) -- supprimé (`rmdir`), aucune référence ailleurs dans le
  repo, aucun impact fonctionnel.

- **[CORRIGÉE, Phase 5 Étape 7] Tout GitHub Actions (CI + le worker
  Celery planifié `celery-worker.yml`) échouait en 3 secondes sur
  chaque run depuis le 19/09/2026** -- confirmé réel, pas un bug de
  code, via `gh run view` : "recent account payments have failed or
  your spending limit needs to be increased" (blocage de facturation du
  compte GitHub, pas du repo). **Corrigé en passant le repo en public**
  (`gh repo view` confirme `"visibility":"PUBLIC"`) -- un repo public
  a des minutes GitHub Actions gratuites illimitées sur les runners
  standard, contournant le blocage de facturation entièrement. Vérifié
  pour de vrai, pas juste supposé : un run manuel déclenché après coup
  (`gh workflow run celery-worker.yml`) a dépassé l'échec instantané
  précédent, atteint `Install dependencies` puis la vraie étape
  d'exécution Celery (les runs précédents échouaient tous en 3s avant
  même `Set up job`). **Ceci ferme aussi la correction reportée
  "Worker Celery non testé" (P1, Étape 5)** -- le worker planifié
  lui-même (`.github/workflows/celery-worker.yml`) est un vrai
  "plan B" documenté (fenêtre bornée de 7 min sur un runner GitHub
  Actions jetable, pas un worker persistant) choisi consciemment
  parce que Render (l'hébergement cible réel) n'a pas de tier gratuit
  pour un Background Worker séparé, et co-localiser Celery dans le
  même conteneur web a réellement fait OOM le service (voir
  `docker-entrypoint.sh`'s own docstring) -- ce n'est PAS le pattern
  "worker Celery persistant dans docker-compose" du spec section 3.1
  pour cet hébergement précis, mais un vrai, testé, fonctionnel
  substitut pour ce contrainte réelle. `docker-compose.selfhosted.yml`
  possède lui, séparément, de vrais services `celery-worker`/
  `celery-beat` persistants pour un opérateur self-hosted qui n'a pas
  la contrainte Render free-tier.
- **[ACCEPTÉE] Pas de CD "SSH vers un serveur unique" ni de déploiement
  blue-green/rolling, contrairement au spec section 3.10.** Décision
  explicite avec l'utilisateur (question posée avant de coder) : ce
  produit est **self-hosted** -- chaque client fait tourner
  `docker compose -f docker-compose.selfhosted.yml` sur SA PROPRE
  machine (voir `install.sh`/`update.sh`/`uninstall.sh`, réels et
  fonctionnels), il n'y a pas UN serveur de production que cette
  plateforme opère elle-même vers lequel un CD SSH générique aurait un
  sens. **Accepté car**: `update.sh` EST le vrai mécanisme de
  déploiement pour ce modèle (pull → rebuild → migrate, avec un vrai
  backup pg_dump pris automatiquement avant, et les instructions de
  restore affichées si la migration échoue -- voir
  `docs/install/UPGRADING.md`) ; un opérateur qui exploite lui-même une
  offre SaaS centralisée sur cette base de code ajouterait son propre
  job SSH-deploy, hors du périmètre de ce qui peut être livré
  générique dans le repo public. `render.yaml` existe déjà mais cible
  l'ancien prototype Streamlit (`Dockerfile` racine), pas ce produit.
- **[ACCEPTÉE] Pas de rollback automatique par `alembic downgrade` ni
  de redéploiement automatique de l'image précédente.** Décision
  intentionnelle, pas un oubli : un downgrade Alembic automatique sur
  échec de migration est un vrai risque (perte de données sur certains
  types de migration, ex. colonne supprimée), plus dangereux que le
  vrai mécanisme déjà en place -- `update.sh` prend un vrai backup
  `pg_dump` AVANT toute migration et affiche la commande
  `scripts/restore.sh` exacte si quelque chose échoue (rollback manuel,
  déclenché par un humain, sur des données réelles plutôt qu'une
  tentative automatique risquée sur une DB en production).
- **[CORRIGÉE, Phase 5 Étape 7] Sentry (error tracking) n'existait pas
  du tout** (confirmé par audit : zéro `sentry_sdk` importé, zéro
  mention même en documentation). Ajouté réellement :
  `api/security/error_tracking.py` (`setup_error_tracking`), même
  convention "code réel, no-op tant que non configuré" que
  `api/security/tracing.py` (OpenTelemetry) juste au-dessus dans le
  lifespan de `api/main.py` -- `SENTRY_DSN` vide (défaut) = vrai no-op
  inerte, `SENTRY_DSN` réel = vraie capture d'erreurs backend + Celery
  (`CeleryIntegration`/`FastApiIntegration`/`StarletteIntegration`
  réels, vérifiés importables avec `sentry-sdk==2.40.0` réellement
  installé et testé, pas supposé). `send_default_pii=False` explicite
  (une requête de login/API-key peut porter un secret dans son body/
  ses headers). Proven par 5 tests réels
  (`tests/test_error_tracking.py`), y compris un test qui initialise
  un vrai client Sentry contre un DSN factice et vérifie ses options
  réelles (`client.is_active()`, `client.options[...]`), pas un mock
  de la surface. **Scope de cette étape** : backend uniquement (décidé
  avec l'utilisateur) -- Celery est déjà couvert par
  `CeleryIntegration` côté backend (le worker importe le même
  `api.security.error_tracking`), mais le frontend Next.js n'a pas
  reçu `@sentry/nextjs` -- voir la limite tracée ci-dessous.
- **[TRACÉE, P2] Sentry frontend (`@sentry/nextjs`) non ajouté.**
  Exclu explicitement du périmètre de cette étape (décision utilisateur
  : "Backend uniquement"). **Impact** : une erreur JS/React côté client
  n'est capturée nulle part aujourd'hui (ni logs centralisés, ni
  Sentry) -- seules les erreurs qui remontent jusqu'à un appel API
  backend sont visibles. **Complexité estimée** : faible (`npx
  @sentry/wizard@latest -i nextjs`, un DSN frontend distinct du DSN
  backend, même pattern "no-op si DSN absent").
- **[CORRIGÉE, Phase 5 Étape 7] Aucun reverse-proxy nginx livré**
  (confirmé par audit : seul un exemple en prose dans
  `docs/DEPLOYMENT_GUIDE.md`, aucun service/config réel). Ajouté
  réellement : `nginx/templates/default.conf.template` +
  `nginx/templates/00-limit_req_zone.conf.template` (rendu via le
  mécanisme officiel `envsubst`-au-démarrage de l'image `nginx:alpine`,
  pas un entrypoint custom), services `nginx`+`certbot` dans
  `docker-compose.selfhosted.yml` sous un profil Compose **opt-in**
  (`--profile proxy`) -- un opérateur déjà derrière son propre proxy
  n'en a pas un second forcé. Couvre réellement : HTTP→HTTPS redirect,
  HSTS/X-Frame-Options/X-Content-Type-Options/Referrer-Policy, gzip,
  rate limiting (`limit_req_zone`, 10 req/s/IP, burst 20), et le
  renouvellement Let's Encrypt automatique (boucle réelle `certbot
  renew` toutes les 12h dans le service `certbot`). Vérifié pour de
  vrai : `docker compose ... config --quiet` valide la syntaxe YAML ;
  les templates ont été réellement rendus et testés avec
  `nginx -t` dans un vrai conteneur `nginx:1.29-alpine` (`envsubst`
  confirmé fonctionnel sur les deux templates, `limit_req_zone` chargé
  avant son usage) -- la seule erreur restante ("host not found in
  upstream 'api'") est attendue et non un défaut : ce test isolé n'a
  pas les conteneurs `api`/`frontend` sur le même réseau Docker, ce qui
  sera réellement le cas dans la stack Compose complète. Documenté dans
  `nginx/README.md` (émission initiale du certificat en 3 étapes,
  HTTP-only temporaire → vraie émission webroot → bascule HTTPS).
- **[CORRIGÉE, Phase 5 Étape 7] `scripts/backup.sh` n'avait aucune
  rétention/purge** (confirmé par audit et par
  `docs/install/BACKUP_AND_RESTORE.md`'s own honest admission).
  Ajouté : purge réelle des backups locaux de plus de
  `BACKUP_RETENTION_DAYS` (défaut 30, spec section 3.6), désactivable
  (`=0`). **Reste tracé** : aucun upload S3/R2 automatique (le script
  reste local-only par design -- voir la limite ci-dessous) et aucun
  déclenchement planifié central (voir ci-dessous, raison
  architecturale self-hosted).
- **[TRACÉE, P2] `scripts/backup.sh` n'upload jamais vers S3/R2.**
  Le spec section 3.6 le demande explicitement. **Pourquoi pas corrigé
  dans cette étape** : un upload S3/R2 nécessite des credentials que ce
  script self-hosted n'a aucune raison de connaître par défaut (chaque
  opérateur a son propre bucket/ses propres clés, contrairement à
  `api/services/url_fetching.py`'s own centrally-managed S3 config pour
  les documents utilisateur) -- ajouter ceci sans un vrai retour de
  l'opérateur sur SON provider (AWS/R2/Backblaze, région, bucket)
  serait une implémentation non testable de bout en bout dans cet
  environnement. **Complexité estimée** : faible une fois les
  credentials réels connus (`aws s3 cp` ou équivalent après le
  `pg_dump`, comme le pseudo-code du spec section 5.5 le montre déjà).
- **[ACCEPTÉE] Aucun cron/systemd timer ne lance `backup.sh`
  automatiquement -- géré par documentation, pas par le repo.**
  Décision architecturale, pas un oubli : dans le modèle self-hosted de
  ce produit, le cron doit tourner sur LA machine du client, que cette
  plateforme ne peut pas centralement programmer pour lui (contrairement
  à un SaaS géré par nous où un scheduler central existerait). Un vrai
  exemple crontab réel a été ajouté à
  `docs/install/BACKUP_AND_RESTORE.md` (`0 3 * * * cd ... && ./scripts/backup.sh`).
  `update.sh` continue de déclencher un backup automatiquement une fois
  avant chaque mise à jour, indépendamment de ce cron.
- **[ACCEPTÉE] Pas de `deploy.sh`/`rollback.sh` sous ce nom exact
  (spec section 4.10).** `install.sh`/`update.sh`/`uninstall.sh` +
  `scripts/backup.sh`/`scripts/restore.sh` couvrent déjà, réellement et
  fonctionnellement, exactement ces rôles pour le modèle self-hosted de
  ce produit (voir les deux entrées ACCEPTÉE ci-dessus sur le modèle de
  déploiement) -- ajouter des scripts au nom différent qui appellent
  juste les mêmes serait une duplication sans valeur réelle, pas une
  vraie correction.
- **[CORRIGÉE, Phase 5 Étape 7] Piège de nommage réel documenté** : le
  `Dockerfile`/`docker-compose.yml` racine construisent l'ANCIEN
  prototype Streamlit ("nova", `dashboard/app.py`), pas ce produit --
  un vrai risque de confusion pour quiconque suit le spec section 3.1's
  own literal file-naming convention ("`docker-compose.yml` = dev").
  Un bandeau explicite a été ajouté en tête de `Dockerfile` pointant
  vers les vrais `Dockerfile.api`/`frontend/Dockerfile`/
  `docker-compose.selfhosted.yml` -- gardé sous ce nom exact
  uniquement parce que `render.yaml`'s own Blueprint le référence déjà
  (renommer casserait ce déploiement existant).
- **[ACCEPTÉE] Migrations non auto-exécutées dans le CMD du conteneur
  (`Dockerfile.api`/`docker-compose.selfhosted.yml`), contrairement au
  spec section 5.2's own literal `entrypoint.sh` pattern.** Vérifié :
  `docker-entrypoint.sh` existe déjà mais sert un tout autre rôle
  documenté (co-localiser Celery sur Render free-tier, abandonné pour
  cause d'OOM réel -- voir l'entrée Celery ci-dessus) -- le
  réutiliser pour les migrations aurait mélangé deux préoccupations
  sans rapport. **Vraie raison de ne pas ajouter un `alembic upgrade
  head` au démarrage du conteneur** : `docs/install/SCALING.md`
  documente déjà `api` comme un service scalable horizontalement
  (plusieurs replicas) -- migrer à chaque démarrage de conteneur
  créerait une vraie race condition si plusieurs replicas démarrent en
  même temps (`CREATE TABLE`/`ALTER TABLE` concurrents contre la même
  DB). Le mécanisme réel et déjà fonctionnel reste `install.sh`/
  `update.sh` (exécution unique, côté host, avant tout scaling).
- **[ACCEPTÉE] Secrets management reste `.env` seul, pas de Vault/AWS
  Secrets Manager/Doppler.** Confirmé par audit : `.env.example` (133
  variables réelles), aucune intégration Vault dans le code, seulement
  une recommandation en prose (`docs/DEPLOYMENT_GUIDE.md`). **Accepté
  car** : c'est exactement la recommandation du spec lui-même (section
  3.11 : "`.env` + Docker secrets pour commencer, Vault plus tard"),
  et pour un produit self-hosted où chaque client gère son propre
  `.env` sur sa propre machine (pas un secret partagé entre tenants
  d'un SaaS centralisé), la complexité opérationnelle de Vault n'a pas
  de bénéfice de sécurité proportionné aujourd'hui. Deviendrait un
  vrai gap si ce produit opère un jour une offre SaaS centralisée avec
  des secrets partagés entre plusieurs clients (voir `docs/install/SAAS.md`).
- **[CORRIGÉE, Phase 5 Étape 7] `frontend/package.json` épinglait
  `@types/node: "^20"`, réellement incompatible avec `vitest@^5.0.0`**
  (peer dependency exigeant `^22.0.0 || >=24.0.0` -- 20.x ne satisfait
  aucune des deux plages). Trouvé en re-tentant réellement le build
  Docker frontend (2e essai, ci-dessous) : `npm ci` échouait sur un
  vrai conflit `ERESOLVE`, pas un problème réseau cette fois (le 1er
  essai avait échoué plus tôt, sur un timeout d'auth Docker Hub, avant
  même d'atteindre `npm ci`). Corrigé en `^22`, aligné sur le
  `node:22-slim` déjà utilisé par `frontend/Dockerfile`. C'était un
  vrai bug latent, jamais déclenché avant cette étape car rien
  n'avait exécuté `npm ci` en environnement propre (sans
  `node_modules` déjà résolu localement) depuis que `vitest` a été mis
  à jour vers sa v5.
- **[TRACÉE, P1] Build Docker complet (backend + frontend) non
  vérifié de bout en bout — bloqué par le réseau local. À vérifier en
  environnement de déploiement.**
  **Description précise** : deux essais réels ont été faits pour
  chaque image (règle de zéro limite point 19 : réessayer au moins une
  fois avant de tracer), avec l'erreur exacte et le moment de chacun :
  - *Backend, essai 1* (`docker build -f Dockerfile.api`) : échec sur
    `pip install`, `ERROR: No matching distribution found for
    bcrypt==5.0.0`, précédé de 2 reprises de téléchargement
    interrompu (`WARNING: Connection interrupted while downloading`).
  - *Backend, essai 2* : `bcrypt` s'est résolu sans erreur cette fois
    (confirmant que l'essai 1 était bien un faux positif réseau), mais
    échec plus loin sur `ERROR: No matching distribution found for
    torch==2.13.0+cpu`, précédé de 4 reprises de téléchargement
    interrompu sur `pandas-3.0.5`.
  - *Cause identifiée* : ni `bcrypt==5.0.0` ni `torch==2.13.0+cpu` ne
    sont de vraies versions manquantes -- vérifié indépendamment avec
    `pip index versions bcrypt` et `pip index versions torch
    --index-url https://download.pytorch.org/whl/cpu` : les deux
    existent réellement et sont déjà installées avec succès dans cet
    environnement local. La cause réelle est une instabilité réseau de
    cet environnement (timeouts TLS confirmés aussi vers
    `api.github.com`/`auth.docker.io` pendant cette même étape), qui
    fait échouer `pip` après épuisement de ses propres reprises
    automatiques sur un paquet différent à chaque essai.
  - *Frontend, essai 1* : échec avant même `npm ci`, timeout
    d'authentification Docker Hub (`failed to fetch oauth token: ...
    TLS handshake timeout`) en tirant `node:22-slim`.
  - *Frontend, essai 2* : l'image s'est tirée sans problème cette
    fois, mais `npm ci` a échoué sur le vrai bug `@types/node`
    ci-dessus (corrigé). Une 3e tentative complète (image + `npm ci`
    + `npm run build`) n'a pas pu être menée à bout dans cette passe :
    le `npm install` local lancé pour régénérer le lockfile après le
    correctif est resté bloqué plus de 6h (horloge de cet
    environnement) sans la moindre progression (`node_modules` figé à
    387 paquets, `package-lock.json` non modifié) -- même signature
    d'instabilité réseau que les essais précédents, pas un nouveau bug
    de code. Arrêté explicitement (`TaskStop`) plutôt que laissé tourner
    indéfiniment, conformément à la règle de gestion des tokens.
  - **Impact réel** : ni l'image backend ni l'image frontend n'ont été
    prouvées buildables de bout en bout dans CET environnement --
    seule la syntaxe (`docker compose config`, `nginx -t`) et les
    dépendances Python/npm prises individuellement ont été vérifiées
    réelles. Un déploiement réel pourrait rencontrer un problème non
    encore vu si le réseau de CET environnement en masquait un.
  - **Priorité : P1** (un build non prouvé est un vrai risque de
    déploiement, pas une simple limite cosmétique).
  - **Complexité/plan concret** : aucun changement de code nécessaire a
    priori (le seul vrai bug trouvé, `@types/node`, est déjà corrigé
    ci-dessus) -- relancer les deux builds sur un réseau stable :
    `docker build -f Dockerfile.api -t rag-saas-api .` puis
    `docker build -f frontend/Dockerfile -t rag-saas-frontend
    ./frontend`. Si un nouvel échec réel (non réseau) apparaît, il
    sera cette fois sur un paquet différent des deux déjà vérifiés
    innocents -- traiter au cas par cas comme le `@types/node` ci-dessus.

- **[CORRIGÉE, Phase 5 Étape 6] Real function calling (LLM tool use)
  never actually ran** -- `api.services.tools`' `ToolSpec`/`register_tool`/
  `_REGISTRY` existed since Partie 5.1.2, and `tool_selection.py`/
  `tool_validation.py`/`tool_timeout.py`/`parallel_tools.py` were all
  real and independently tested, but **zero real call site ever passed
  `tools=` into an actual LLM completion** -- `chat_completion_with_usage`
  didn't even parse `message.tool_calls` back out of the provider
  response before this étape. `AgentOrchestrator.run_agent`'s `_execute`
  now runs a real, provider-native function-calling loop (tool schemas
  sent via `tools=[...]`, `message.tool_calls` parsed, real handlers
  awaited, `role:"tool"` results fed back, looped up to
  `settings.AGENT_MAX_TOOL_ITERATIONS` with an honest `LLMError` if that
  cap is hit) -- the same MAX_STEPS-honesty pattern already established
  by `workflow_engine.py`'s graph executor. Multiple simultaneous tool
  calls in one turn run concurrently (`asyncio.gather`), each under its
  own `execute_tool_with_timeout` (`settings.AGENT_TOOL_CALL_TIMEOUT`),
  each producing its own `AgentTrace` row (`step_type="tool_call"`) with
  secrets redacted (`_redact_secrets`, keys matching `api_key`/
  `password`/`token`/`secret`/`authorization` etc.). Proven by 9 new
  tests in `tests/test_agent_orchestrator.py` (single tool call,
  parallel tool calls, tool error surfaced as a `role:"tool"` error
  message rather than crashing the run, iteration cap honestly
  enforced, secrets redacted in traces) plus a real litellm-shaped
  fake response builder (`_tool_call_response`), not hand-rolled dicts.
- **[CORRIGÉE, Phase 5 Étape 6] 6 of the 12 real `AGENT_TOOL_CATALOG`
  tools were real, callable Python functions that were never wrapped
  into the shared `ToolSpec` registry** -- meaning even with the loop
  above built, an agent configured to use `github_get_repo`/
  `github_list_issues`/`execute_sql_query`/`calendar_list_events`/
  `calendar_create_event`/`email_read` could never actually reach any
  of them. `api/services/tool_wiring.py` (new) wraps 5 of the 6 as
  static, registered `ToolSpec`s; `execute_sql_query` is deliberately
  built per-run instead (`build_sql_query_tool`), binding `db`/
  `organization_id` by closure so an LLM's own tool-call arguments can
  never supply a different `organization_id` (a real cross-tenant leak
  otherwise). Also adds `http_request`, one of the étape's own spec's
  named builtin tools with no prior implementation, real and
  SSRF-protected via this codebase's own canonical `ssrf_safe_client()`
  -- never a second, parallel HTTP path. A real, previously-latent
  catalog/registry name mismatch (`"calculate"` in the agent-facing
  catalog vs. `"calculator"` in the registry) was also found and fixed
  via an explicit alias (`_CATALOG_TO_REGISTRY_NAME`) during this work
  -- `resolve_agent_tools` would otherwise have silently resolved zero
  tools for any agent configured with the catalog's own literal name.
  **Real, total builtin tool count after this étape: 8 statically
  registered (`calculator`, `word_count` pre-existing +
  `github_get_repo`, `github_list_issues`, `calendar_list_events`,
  `calendar_create_event`, `email_read`, `http_request` new) + 1 built
  fresh per run (`execute_sql_query`, org-bound by closure) = 9.**
  Custom, org-defined webhook tools (`api/models/custom_tool.py`) are
  separate and dynamic, not counted here.
- **[CORRIGÉE, Phase 5 Étape 6] No cross-run agent memory existed at
  all** -- `AgentSession`/`AgentMemoryItem` (Partie 5.1.11) are real but
  genuinely short-term only, scoped to one `AgentSession` that itself
  expires (`AGENT_MEMORY_TTL`), never retrievable from a later session.
  New `AgentLongTermMemoryItem` (migration `0118`, applied and
  round-trip-verified against real Postgres: `upgrade head` →
  `downgrade -1` → `upgrade head`, schema inspected column-by-column
  including both real FKs `ON DELETE CASCADE` and the real
  `(agent_id, user_id, key)` unique constraint) gives a real,
  cross-run, optionally-per-user, optionally-expiring fact store.
  `user_id IS NULL` means a real, org-wide fact; a real, non-null,
  per-user fact overrides it on a key collision. `run_agent` now reads
  it at the start of every run (alongside existing short-term memory).
  Real CRUD endpoints: `GET/PUT/DELETE /agents/{agent_id}/memory[/{key}]`,
  read gated by `require_agent_member`, write/delete by
  `require_agent_manager` (same tier convention as every other agent
  sub-resource in this router). Proven by 14 new tests
  (`tests/test_agent_long_term_memory.py`): service-layer CRUD,
  org-wide vs. per-user precedence, real lazy expiration, cross-agent
  isolation, and endpoint-level permission enforcement (manager can
  write/delete, member can only read, both real 403s proven).
- **[TRACÉE, P2] Long-term memory has no automatic "decide what's worth
  remembering" summarization step.** A tool (or an explicit API caller)
  can WRITE a long-term fact, and every run READS what's already there,
  but nothing watches a run's own output and decides on its own that a
  new fact is worth persisting past that run. **Estimated complexity:
  substantial** (a real, separate LLM call with its own prompt and
  failure modes, not a quick addition) -- deliberately out of this
  étape's own scope; the core "persist, retrieve, expire" capability
  is real and complete without it.
- **[TRACÉE, P2] The real function-calling loop is `run_agent`-only --
  `stream_response` (the SSE/streaming sibling) still only does tool
  SELECTION for prompt injection, never real tool EXECUTION mid-stream**
  (confirmed by reading `stream_response`'s own body: `selected_tools`
  is computed and summarized into the system prompt, but `tools=` is
  never passed to `chat_completion_stream`, and no `role:"tool"` loop
  exists there). **Impact**: a streaming agent conversation cannot
  actually call a tool today -- it can only be told the tool exists in
  its own prompt. **Real, architectural reason this wasn't done in the
  same pass**: real, live token streaming and a real, multi-turn
  tool-call loop interact non-trivially (when does the client see a
  "the agent is now calling a tool" event vs. raw tokens; the loop can
  restart the LLM call mid-stream) -- a genuine, separate feature, not
  a quick copy-paste of the `run_agent` loop. **Priority: P2** (the
  primary, most-used non-streaming path is now real and complete;
  streaming was already the more narrowly-scoped sibling before this
  étape per its own docstring).
- **[ACCEPTÉE] Tool execution security uses `ToolPermission`/
  `check_tool_permission` (api/security/tool_permissions.py, real,
  per-agent-per-tool allow/deny, already wired into both `run_agent` and
  `stream_response`), not a `tool:*`/`tools` key in the granular
  52-permission catalog** (no such resource exists in
  `api/security/permission_catalog.py`). **Accepted, not newly tracked,
  because**: this is the exact same pre-existing, already-tracked gap
  (see "Granular Permission Enforcement" below) applied to one more
  surface -- tool execution already has its own real, dedicated,
  enforced permission model, unrelated to and not weakened by the
  broader RBAC gap.
- **[Phase 5, Étape 6 -- deferred corrections, verified] Items 1-3, 5-6
  from Étape 5's own deferral list are sans rapport with this,
  backend-only étape**: (1) the Celery worker gap is specifically about
  the *Workflow Engine's* dispatch (`api.tasks.workflows.run_workflow_task`)
  -- confirmed unrelated by reading `AgentOrchestrator.run_agent`'s own
  dispatch, which uses `asyncio.create_task(_execute())` in-process, not
  Celery, by design (same fire-and-forget pattern as its own SSE run
  creation) -- there is no agent-side Celery gap to test. (2)/(3) canvas
  undo/redo and the human block's rich options editor are Workflow
  Builder frontend concerns this étape never touches. (5) notification
  templates (DB-backed CRUD) -- agents raise no new notification type
  and need no custom template. (6) notification real-time replay -- the
  gap is specific to `notifications:{user_id}` pub/sub, unrelated to
  agent execution. Item (4), `billing_quota_warning`/
  `billing_quota_exceeded`, remains genuinely unwired, P1, unchanged --
  this étape doesn't touch billing usage thresholds either way. Item
  (7), Granular Permissions, addressed above (one more accepted
  instance of the same pre-existing gap). Item (8), ROADMAP coherence,
  is this very pass.
- **[CORRIGÉE, Phase 5 Étape 5] `FRONTEND_URL` in `.env` had drifted
  from the real dev port.** Set to `http://localhost:3011`, but
  `.claude/launch.json`'s own real "frontend" config runs Next.js on
  its default port 3000 -- `CORSMiddleware(allow_origins=[FRONTEND_URL])`
  silently rejected every real browser request (a raw network-level
  failure, never a JSON error body) until this étape's own real,
  end-to-end browser verification surfaced it. Fixed in `.env`; kept
  in sync with `.claude/launch.json`'s own port going forward.
- **[CORRIGÉE, Phase 5 Étape 5] Migration 0117
  (`workflows.variables`) existed in code but had never actually been
  applied to the real dev Postgres**, caught by this étape's own real
  (not simulated) end-to-end browser test: creating a workflow failed
  with a real `UndefinedColumnError`. Applied via `alembic upgrade
  head`, round-tripped (`downgrade -1` → `upgrade head`), and verified
  against the real running app afterward (workflow creation, save, and
  run all succeeded for real in the browser).
- **[CORRIGÉE, Phase 5 Étape 5] Two real backend gaps found during
  this étape's own audit, closed because the Workflow Builder UI is
  genuinely unusable without them**: (1) `GET /workflows/{id}/runs`,
  `GET /workflows/runs/{run_id}`, and a real SSE
  `GET /workflows/runs/{run_id}/stream` (execution history + live
  debug) didn't exist -- `POST .../run` could trigger a run but
  nothing could ever list past runs, fetch one's detail, or watch one
  live. (2) `api/security/workflows.import_workflow` and
  `api/services/workflows.export_workflow` were real, complete,
  tested-in-isolation functions with ZERO router endpoint -- the same
  "built, never wired" pattern this session already found and closed
  in `billing_stripe_sync.py` (Phase 5, Étape 3). All five wired,
  tested (backend: 44/44 passing across `test_workflows.py` +
  `test_workflow_engine.py`; frontend: 9/9 passing in
  `components/workflows/components.test.tsx`), and proven for real in
  the browser (see this étape's own End-to-End section).
- **[CORRIGÉE, Phase 5 Étape 5] `workflow_approval_needed` (P1,
  reclassified in Phase 5 Étape 4) wired for real** at
  `api/services/workflow_engine.py`'s own `_execute_node`, right where
  a run pauses on a real `human` block -- the workflow's own creator
  gets a real, persisted, urgent in-app notification the moment their
  approval is needed, not just a theoretical API they'd have to poll.
  Proven by `test_human_block_notifies_the_workflows_creator`.
- **[TRACÉE, P2] The Workflow Builder canvas has no undo/redo or
  copy/paste** (this étape's own spec section 4.1). React Flow's own
  built-in multi-select (shift-click, drag-select) works out of the
  box and is real, but keyboard-driven undo/redo and node
  copy/paste are not wired.
  **Impact**: real UX friction for iterative graph editing (a
  mis-click has no quick undo) -- not a data-loss risk (nothing
  persists until the real, explicit "Enregistrer" button is clicked).
  **Estimated complexity: moderate** (undo/redo needs a real history
  stack of `{nodes, edges}` snapshots; copy/paste needs a clipboard
  representation and id-remapping on paste to avoid real id
  collisions) -- a genuine, separate follow-up, not a quick addition.
- **[TRACÉE, P3] The `human` block's node editor only exposes
  `input_type` (text/confirm/choice), not a rich custom-options list
  builder** for the `choice` type's own real `options` array
  (`api/models/workflow_human_input.py`'s own `options: JSON`
  column, already real and functional backend-side). An operator who
  wants a `choice` block with specific options must still set
  `options` via a direct API call or a future dedicated editor, not
  through `NodeEditor.tsx`'s own UI yet.
  **Impact**: small -- `confirm` (yes/no) already covers the
  spec's own literal "approve/reject" ask end-to-end (proven by this
  étape's own `approval-workflow` template); only the more general
  multi-choice case needs the richer editor.
  **Estimated complexity: small** (an "add option" list UI, same
  shape as `VariablePanel.tsx`'s own real add/remove row pattern).
- **[ACCEPTÉE] Workflow templates are code-defined
  (`components/workflows/templates.ts`), not a DB-backed
  `NotificationTemplate`-style CRUD.** Same reasoning already applied
  to notification templates (Phase 5, Étape 4) and billing Plans
  (Phase 5, Étape 2): `Workflow` is already a real, working, DB-backed
  CRUD entity -- "use a template" is just "create a workflow
  pre-filled with these nodes/edges," not a reason to add a second,
  competing source of truth. **Accepted, not tracked**, for the exact
  same reason those two prior decisions were.
- **[ACCEPTÉE] Workflow endpoints use the fixed `OrganizationRole`
  hierarchy (`require_org_manager`/`require_workflow_member`), not the
  granular 52-permission system** (`workflow:read`/`workflow:write`/
  `workflow:run`/`workflow:approve`/`workflow:admin` from this étape's
  own spec section 6.2 were never wired) -- reconfirmed during this
  étape's own audit (`grep -rn "require_permission" api/routers/workflows.py`:
  zero results). **Accepted, not newly tracked, because**: this is the
  exact same pre-existing, already-tracked gap (see "Granular
  Permission Enforcement" above), which doesn't need a second,
  duplicate ROADMAP entry for one more router it also applies to.
- **[TRACÉE, P1] Exécution complète du Workflow Engine avec un worker
  Celery actif — à tester en environnement de déploiement (dev local
  sans worker).** Cette étape a prouvé pour de vrai, dans un vrai
  navigateur contre un vrai backend : le dispatch réel
  (`POST /workflows/{id}/run` → 200, une vraie ligne `WorkflowRun`
  `pending` persistée), la connexion SSE réelle et authentifiée
  (`GET /workflows/runs/{id}/stream`, frame `snapshot` reçue), et la
  mise à jour réelle de l'historique d'exécution. **Ce qui n'a PAS été
  prouvé** : qu'un worker Celery consommant réellement la tâche
  `api.tasks.workflows.run_workflow_task` fait bien progresser le run
  de `pending` à `completed`/`failed` en exécutant réellement les
  nœuds (LLM, RAG, etc.) — aucun worker n'a été démarré dans cet
  environnement de développement (`.claude/launch.json` ne définit que
  "frontend" et "backend", pas de config "celery worker").
  **Impact réel** : bloquant pour la production — si le déploiement
  réel n'a pas de worker Celery actif et correctement configuré
  (broker, tâches enregistrées), un run reste `pending` indéfiniment
  et l'utilisateur ne le saura jamais (le frontend affiche "En
  cours..." sans erreur). C'est exactement le genre de gap qu'un test
  E2E partiel peut masquer si on ne le trace pas explicitement.
  **Priorité : P1** (bloquant pour la production, pas pour le
  développement — le code du worker lui-même est déjà testé
  unitairement dans `tests/test_workflow_engine.py`, 44/44 passants).
  **Complexité estimée : faible** — démarrer un vrai worker
  (`celery -A api.tasks.celery_app worker`) contre le même Redis/
  Postgres que ce test E2E, relancer le même scénario (créer →
  connecter → lancer), et vérifier que le run passe réellement à
  `completed` avec un `output` réel. Une tâche de vérification, pas de
  développement — le code est déjà là et déjà testé unitairement.

- **[CORRIGÉE, Phase 5 Étape 4 correctif] `security_password_changed`
  and `security_2fa_enabled` -- reclassified P1 and wired.** Originally
  traced as P2 alongside 7 other unwired types; corrected because both
  are real, high-value security signals (an attacker who changes a
  victim's password or enables 2FA on a hijacked account should not go
  unnoticed). Wired at `api/routers/account.py`'s `POST
  /account/change-password` and `api/routers/two_factor.py`'s `POST
  /2fa/verify-setup`, both in-app-only by design (each already sends a
  real, dedicated, purpose-formatted email --
  `send_password_changed_email`/`send_two_factor_enabled_email` --
  immediately before calling `create_notification`; letting
  `create_notification` ALSO email would double-send, same reasoning
  as `security_login_new_device`). Proven by
  `test_trigger_security_password_changed_fires_in_app_only`,
  `test_trigger_security_2fa_enabled_fires_in_app_only`,
  `test_password_change_endpoint_creates_in_app_notification`
  (`tests/test_notifications.py`, 23/23 passing).
- **[TRACÉE, P1 -- reclassified from P2] `billing_quota_warning`,
  `billing_quota_exceeded`, `workflow_approval_needed` are not wired.**
  Reclassified from P2 after review: a quota warning/exceeded event
  and a human-in-the-loop approval request are time-sensitive --
  missing one has a real, immediate operational cost (an org exceeds
  its plan silently instead of being warned; a workflow sits blocked
  on a human step nobody was told about), unlike the remaining P2
  types below, which are informational.
  **Impact**: real -- `api/services/billing_usage.py`'s own
  `UsageAlert` mechanism (Phase 5, Étape 2's own real, tested alerting)
  already computes WHEN a threshold is crossed but has no
  `create_notification` call wired to actually tell the org; a
  `workflow_engine.py` run that reaches a real `human` block
  (`execute_human_block`) has no notification either, so a human
  approver only ever discovers it by manually checking.
  **Estimated complexity: small per type** (`billing_quota_warning`/
  `billing_quota_exceeded`: one `create_notification` call inside
  `api/services/billing_usage.py`'s own existing threshold-crossing
  check; `workflow_approval_needed`: one call inside
  `execute_human_block`, api/services/workflow_engine.py) -- not done
  in this étape's own correctif pass; genuinely next in line.
- **[TRACÉE, P2] `billing_payment_succeeded`, `billing_subscription_cancelled`,
  `member_joined`, `member_left` remain unwired, P2 (unchanged).**
  Each is informational, not time-sensitive/security-relevant the way
  the P1 group above is -- missing one is a real UX gap, not an
  operational risk. Each is perfectly usable today via the generic
  `create_notification()` API (no code needs to change in
  `notifications.py` itself to add one) -- what's missing is only the
  one real call site per type.
  **Estimated complexity: small per type**, same pattern as every
  already-wired trigger -- realistically a half-day for all 4.
- **[TRACÉE, P2] `NotificationTemplate`/`NotificationDelivery` are not
  separate DB tables**, unlike the étape's own literal 4-table spec.
  Templates are Jinja2 strings defined in code
  (`api/services/notification_templates.py`) -- real, working, tested
  for all 7 wired types, autoescaped against untrusted context values.
  Delivery tracking is folded into `Notification`'s own
  `email_status`/`email_error`/`email_sent_at`/`email_retry_count`
  columns instead of a separate table (see
  `api/models/notification.py`'s own docstring for the full reasoning).
  **What this genuinely does NOT give**: `POST /notifications/test`
  and `GET`/`PATCH /notifications/templates` (admin-editable custom
  template CRUD + preview) from the étape's own spec's endpoint list --
  there's no DB row to CRUD. An operator who wants to change a
  notification's wording today edits
  `api/services/notification_templates.py`'s `TEMPLATES` dict and
  redeploys, not a live admin UI.
  **Priority: P2** (a real, missing convenience, not a defect -- every
  wired notification renders correctly today, just not
  operator-customizable without a code change).
  **Estimated complexity: moderate** (a real `NotificationTemplate`
  table, an admin CRUD router with Jinja2 syntax validation at save
  time, and a preview endpoint that renders against sample context --
  a genuine, separate feature, roughly 1-2 days).
  **Re-examined per explicit request: does White Label (Phase 5, Étape
  3) require this?** Checked against `OrganizationBranding`'s own real
  field list (`api/models/organization_branding.py`): `logo_url`,
  `favicon_url`, `primary_color`/`secondary_color`/`accent_color`,
  `font_family`, `brand_name`, `custom_css`, `hide_platform_branding`,
  `company_email`/`support_email`, `email_sender_name`/
  `email_sender_email`, `custom_js`, `is_active` -- every one of these
  is VISUAL/SENDER identity, none is "override this notification's own
  wording." White Label's own real, shipped spec never asked for
  per-org message-content customization, only for branding INJECTED
  into whatever content is sent -- and that injection is already real
  and wired: `api/services/notifications.send_notification_email`
  calls the exact same `get_active_branding`/`compose_branded_from_address`/
  `render_branded_header`/`render_branded_footer` primitives Étape 3
  built, so a notification email already carries an org's real logo,
  sender identity, and contact footer today (proven by
  `tests/test_email_branding.py`, extended to notifications). **This
  deviation (code-defined wording, no DB template CRUD) is accepted as
  sufficient for White Label's own real requirement, not merely
  asserted** -- the P2 gap above is about operator convenience
  (changing copy without a redeploy), a distinct, smaller concern than
  branding, which is already fully satisfied.
- **[TRACÉE, P3] Real-time notification delivery (Redis pub/sub +
  SSE) has no replay for a client that wasn't actively subscribed at
  publish time.** A real, honest limitation of pub/sub, not a bug:
  `_publish_realtime` fires once, to whoever is listening on
  `notifications:{user_id}` at that exact moment (the exact same
  trade-off `api/security/documents.py`'s own pre-existing
  `send_progress_update`/`stream_document_progress` already accepts
  for document progress). The notification ITSELF is never lost --
  it's a real, persisted row, visible immediately via
  `GET /notifications`/`GET /notifications/unread-count` regardless of
  whether any SSE client was connected -- only the LIVE push moment
  can be missed by a client that reconnects a moment late. **Priority:
  P3** (a real UX rough edge -- a disconnected client's badge count
  only updates on its next poll/reconnect, not before -- not a
  correctness or data-loss issue). **Estimated complexity: small** if
  ever prioritized (the SSE route could send a snapshot of unread
  notifications created since connection, similar to how
  `stream_document_progress` sends its own initial snapshot before
  subscribing).
- **[ACCEPTÉE] Notifications have no `custom_css` surface at all** --
  the White Label CSS denylist correction (traced separately above) is
  genuinely not applicable here: no notification field accepts
  user-authored CSS (Jinja2 templates are code-defined, not
  user-editable in this étape's own scope, see the `NotificationTemplate`
  gap above). **Accepted, not tracked, because**: there is nothing to
  secure that doesn't already exist -- this only becomes relevant if
  the `NotificationTemplate` admin-CRUD gap above is ever built AND
  that CRUD lets an operator supply custom HTML/CSS, at which point
  the exact same denylist-vs-sandbox correction from White Label would
  need re-applying here too (noted so that future work doesn't
  silently skip it).
- **[ACCEPTÉE] Notification endpoints use the fixed `OrganizationRole`
  hierarchy (via ownership of the underlying row, not even
  role-gated beyond "this is your own notification"), not the
  granular 52-permission system** (`notification:read`/
  `notification:write`/`notification:admin` from this étape's own spec
  section 6.2 were never wired) -- confirmed, re-verified during this
  étape's own audit (`grep -rn "require_permission" api/routers/
  api/services/` outside `permissions.py`/`rbac_custom.py`: still zero
  results, unchanged since Phase 5, Étape 1's own original finding).
  **Accepted, not newly tracked, because**: this is the exact same
  pre-existing, already-tracked gap (see "Granular Permission
  Enforcement" above) -- notifications don't need their own separate
  ROADMAP entry for a gap that already has one covering the whole
  platform; a user's own notifications are gated by row ownership
  (`WHERE user_id = current_user.id`) regardless, which the granular
  permission system was never going to change (Owner/Admin already
  have full access to everything the fixed hierarchy permits, and a
  notification is never shared across users the way an org resource
  is).

These are real, current limitations — not silently missing, but not
fixed either:

- **No Kubernetes manifests.** Deployment is Docker Compose-based
  (`docker-compose.yml`, `docker-compose.selfhosted.yml`,
  `docker-compose.observability.yml`). A Kubernetes path exists only as
  a manual adaptation guide, not ready-made manifests — see
  [`docs/install/KUBERNETES.md`](docs/install/KUBERNETES.md).
- **Anthropic fine-tuning is not supported**, because Anthropic has no
  public fine-tuning REST API. Jobs targeting Anthropic fail fast with a
  clear error rather than silently hanging — see
  [`docs/fine-tuning/OVERVIEW.md`](docs/fine-tuning/OVERVIEW.md).
- **Autonomous agent collaboration is intentionally bounded** to one
  real LLM call per collaboration, not full nested autonomous sub-runs,
  to avoid unbounded agent-calls-agent recursion — see
  [`docs/autonomous/COLLABORATION.md`](docs/autonomous/COLLABORATION.md).
- **SSL automation for custom domains is DNS-01 only**, verified against
  Let's Encrypt staging; it is not "fully automatic" without a DNS
  provider API integration — see
  [`docs/whitelabel/DOMAIN.md`](docs/whitelabel/DOMAIN.md).
- **No admin UI for the widget's per-organization domain allowlist**
  (Phase 4, Étape 5bis). The API exists and is fully functional
  (`GET`/`PATCH /organizations/{org_id}/widget/domains`,
  `api/routers/widget.py`) and tested
  (`tests/test_widget_domain_allowlist.py`), but an organization admin
  must call it directly (or via a future dashboard screen) rather than
  through a form in the existing settings UI.
- **Enterprise SSO's own OIDC metadata fetch is not SSRF-hardened.**
  `api.security.enterprise_oidc.fetch_oidc_metadata` deliberately uses a
  plain `httpx.AsyncClient`, not this codebase's own canonical
  `ssrf_safe_client()` (Phase 4, Étape 4's own audit) — a real enterprise
  IdP legitimately lives on internal/private network in real deployments
  (VPN-only, same-VPC), unlike a public webhook target, and applying the
  same "must resolve to a public IP" policy broke a real, legitimate
  local-IdP integration test. A compromised/malicious org admin could
  still point a configured `issuer` at internal infrastructure today.
- **Granular Permission Enforcement (52 permissions) — built, tested,
  not wired.** `api/security/permissions.py`'s `require_permission`/
  `require_role`/`require_any_permission`/`require_all_permissions`,
  `api/models/rbac.py`'s `CustomRole`/`Permission`/`RolePermission`/
  `UserCustomRole`, and the full permission catalog
  (`api/security/permission_catalog.py`, 52 `resource:action` keys) are
  all real, complete, and tested in isolation
  (`tests/test_rbac_custom.py`, `tests/test_roles_and_permissions.py`) —
  an org admin can create a `CustomRole`, grant it any subset of the 52
  permissions, and assign it to a member, through real, working API
  endpoints. But **no business-logic router actually imports or applies
  these dependencies** (confirmed by audit, Phase 5, Étape 1: zero real
  usages outside `permissions.py`/`rbac.py` themselves) — only the
  fixed `OrganizationRole` hierarchy (owner/admin/manager/member/viewer)
  is genuinely enforced on real endpoints today. A `CustomRole` assigned
  to a Member or Viewer currently has **zero effect** on what they can
  actually do through the API.
  **Estimated complexity: substantial.** Wiring this correctly means
  auditing and updating every sensitive business endpoint across every
  router (documents, conversations, workflows, knowledge bases,
  integrations, widget config, etc. — dozens of files, on the order of
  the 81 files that already use the fixed-role dependencies), choosing
  the right permission key per endpoint from the existing 52-key
  catalog, and adding regression tests proving each one is genuinely
  enforced (not just declared) — realistically several dedicated work
  sessions, not a quick pass.
  **Priority: medium.** The fixed 5-tier role hierarchy already covers
  every real authorization need this platform currently has; the
  granular layer only matters for organizations that need a narrower
  slice of access than Member/Viewer already gives (e.g., "read billing
  but never touch security settings") — a real, legitimate need, but
  not a security hole in the current, shipped behavior (nothing
  currently promises that a `CustomRole` does anything, so no existing
  deployment is silently under-protected because of this gap).

- **[CORRIGÉE, Phase 5 Étape 3] `tests/test_agent.py` and
  `tests/test_injection_test_set.py` could not be collected —
  `src/agentfixture.py` was never created.** Traced in Phase 5, Étape 2
  (P1); closed in Étape 3. Reconstructed from two sources of truth (not
  guessed): every call site across `tests/test_agent.py`'s 407 lines,
  and `src/agent.py`'s own real `Agent`/`_call_model_with_retry`
  interface (`response.content`/`.stop_reason`/`.usage.input_tokens`/
  `.output_tokens`, block `.type`/`.text`/`.name`/`.input`/`.id`). Also
  covers `src/injection_tests.py`'s `run_suite`/`check_case`,
  reconstructed from `tests/test_injection_test_set.py`'s scripted-agent
  tests and `data/injection_test_set.json`'s real case shape
  (`forbidden_phrases`/`forbidden_tools`/`max_tool_calls`). Found and
  fixed one real bug while building it: `FakeAnthropicClient` initially
  stored the live `messages` list by reference in its call log, but
  `agent.py` keeps mutating that same list object across loop
  iterations — every recorded call silently showed the list's FINAL
  state instead of its state at call time, which is exactly what 4 of
  `test_agent.py`'s own assertions (`client.messages.calls[1][...]`)
  depend on. Fixed with a shallow copy taken at call time
  (`src/agentfixture.py`'s own `_FakeMessages.create` docstring).
  **Both files now collect and pass**: 34/34 (`test_agent.py` + `test_injection_test_set.py`).
- **[CORRIGÉE, Phase 5 Étape 3] `billing_stripe_sync.py` (Phase 5 Étape
  2, part (b) below) was real, complete code with zero callers
  anywhere.** Wired, not deleted: `POST /admin/plans/sync/stripe-products`
  and `POST /admin/plans/sync/stripe-prices`
  (`api/routers/admin_subscriptions.py`), platform-admin only, honestly
  501 without a configured Stripe key
  (`test_stripe_sync_endpoints_honestly_501_without_configured_keys`).
- **[CORRIGÉE, Phase 5 Étape 3] A real bug from Étape 2: admins had no
  actual way to set a Plan's `paystack_plan_code_monthly/yearly`
  through the API.** Étape 2 added those two fields to
  `api.schemas.billing.PlanCreateRequest`/`PlanUpdateRequest` — but the
  REAL admin CRUD endpoint (`POST`/`PATCH /admin/plans`,
  `api/routers/admin_subscriptions.py`) has always used
  `api.schemas.admin_dashboard`'s own, separate Plan schemas, which
  Étape 2 never touched (`api.schemas.billing.PlanCreateRequest`/
  `PlanUpdateRequest` are never imported by any router — confirmed by
  audit, dead classes). Found during Étape 3's own audit (checking
  which schema the real endpoint uses before wiring anything else to
  it), fixed by adding the two fields to `admin_dashboard.py`'s
  `PlanResponse`/`PlanCreateRequest`/`PlanUpdateRequest` instead, proven
  by `test_admin_can_set_paystack_plan_codes_through_the_real_endpoint`.
- **[TRACÉE, P2] Paystack has still never been exercised against the
  real Paystack API** (no `PAYSTACK_SECRET_KEY` in any environment this
  session has access to — unchanged since Étape 2). **What Étape 3
  adds**: the 4 tests Étape 2 only promised in prose now exist as real,
  collectible, ready-to-run code —
  `tests/test_billing_paystack_live.py`, marked
  `@pytest.mark.paystack_live` (registered in `pyproject.toml`) and
  individually `skipif`'d on a real key + a real `PAYSTACK_TEST_PLAN_CODE`
  env var, so they show as **SKIPPED** (not silently absent) in every
  test run until both exist. That file's own module docstring is the
  exact runbook: create a sandbox account, create a real Plan, set 2
  env vars, run `pytest -m paystack_live -v`.
  **Priority: P2** (unchanged — blocks a real Paystack go-live, not
  current behavior). **Estimated complexity: small** once a sandbox key
  exists — the tests are already written; what's left is filling in one
  real captured webhook payload for `test_live_webhook_signature_verifies_against_a_real_captured_payload`.
- **[ACCEPTÉE, non re-tracée] Pas de `plans.yaml`.** Reconfirmed
  coherent in Étape 3: `Plan` (`api/services/admin_subscriptions.py`,
  `PATCH/POST /admin/plans`, now also exposing the Paystack plan-code
  fields per the fix above) fully covers every real configuration need
  a YAML file would — including the one new field White Label added
  nothing to this surface. No future need identified that DB-backed
  CRUD doesn't already serve. **Accepted because**: a parallel YAML
  file would be a second, competing source of truth for the exact same
  data, which this codebase's own established discipline (Partie 10/11's
  "fix the incoherence, don't duplicate it" rule) explicitly avoids —
  not an oversight, a standing decision.

- **[CORRIGÉE, Phase 5 Étape 3] `docs/api/openapi.json` was stale**
  (this étape's own full-suite regression run caught it —
  `test_committed_openapi_export_matches_live_app` failed on every new
  billing/branding endpoint, plus pre-existing drift from Phase 4's
  widget-domains endpoints that had never been regenerated either).
  Fixed by regenerating from `api.main.app.openapi()` per the file's
  own documented process (`docs/developer/API.md`).
- **[CORRIGÉE, Phase 5 Étape 3] `tests/test_github_integration.py` and
  `tests/test_github_extraction_integration.py` (21 tests total) hit
  the real, unauthenticated GitHub REST API and were never marked
  `network_flaky`**, unlike the 2 similar tests Phase 4 Étape 5ter
  already marked in `test_documents_integration.py`. Surfaced by this
  étape's own full-suite regression run (`httpx.ReadTimeout`, then a
  real `rate limit exceeded` on a single retry — confirmed transient,
  not a code defect, by re-running once). Both files now carry a
  module-level `pytestmark = pytest.mark.network_flaky`.
- **[CORRIGÉE, Phase 5 Étape 3] Broken relative links in
  `docs/COMPETITIVE_AUDIT_KNOWFLOW.md`** (a pre-existing, untracked
  file) pointing to `../reports/Onyx%20feature%20inventory%202026.md`
  and `../reports/AnythingLLM%20feature%20inventory.md` — the real
  files exist (`reports/Onyx feature inventory 2026.md`,
  `reports/AnythingLLM feature inventory.md`, literal spaces), but the
  links used percent-encoded spaces, which
  `tests/docs/test_links.py`'s own file-existence check resolves
  literally rather than URL-decoding. Initially misclassified as
  "accepted, out of scope" in Étape 3's first report — a real dead
  link is never a valid "accepted" outcome regardless of whether the
  containing file is tracked by git; fixed by correcting both links to
  use literal spaces (matching the real filenames), confirmed by a
  targeted `pytest tests/docs/test_links.py` run.
- **[CORRIGÉE, Phase 5 Étape 3] A real custom-domain gap found during
  the White Label audit: only an EXACT match against
  `CUSTOM_DOMAIN_CNAME_TARGET` was rejected — a real subdomain of the
  platform's own root domain (e.g. `evil.rag-saas-platform.com`, or
  even `sub.app.rag-saas-platform.com`) passed unrejected.** Fixed with
  `_is_reserved_platform_domain()` (`api/security/custom_domains.py`),
  rejecting the exact CNAME target, the bare root domain, and any of
  its subdomains — proven by
  `test_cannot_register_a_subdomain_of_the_platforms_own_root_domain`.
- **[TRACÉE, P2] Email branding is real infrastructure but wired into
  only ONE of ~30 email-sending functions.** Found during the White
  Label audit: `OrganizationBranding.email_sender_name`/
  `email_sender_email`/`logo_url` were stored, configurable via
  `POST /organizations/{org_id}/whitelabel/email`, and completely
  unread by `api/services/email.py` — a real "configure it, nothing
  happens" gap. Closed for the one function this étape actually
  changed: `api/services/email_branding.py`'s
  `send_branded_organization_invitation_email` (wired into
  `api/routers/invitations.py`, proven by `tests/test_email_branding.py`,
  9 tests) genuinely composes the sender identity, a logo header, and
  an org-contact footer from real, active branding, falling back to
  exactly the pre-existing platform defaults when none is configured.
  **The other ~29 functions in `api/services/email.py`
  (`send_organization_member_added_email`, `send_invoice_email`,
  `send_usage_limit_warning_email`, etc.) are unchanged and still don't
  read branding.** **Tracked, not fixed here, because**: migrating all
  of them is a substantially larger refactor (several call sites
  currently pass plain strings with no `db`/`org_id` in scope at all,
  e.g. platform-level auth emails sent before any organization
  context exists) that overlaps with this platform's explicitly
  separate, not-yet-scheduled "Notifications" étape (this étape's own
  spec, section 8, lists Notifications as out of scope) — rewiring
  email composition wholesale is that étape's job, not White Label's.
  **Priority: P2** (a real, user-facing inconsistency for orgs that
  configure branded email — "why does only the invitation email look
  branded?" — but not a security or correctness defect).
  **Estimated complexity: moderate** (auditing all ~30 call sites for
  which ones are genuinely org-scoped vs. platform-level, then
  migrating each org-scoped one the same way this étape migrated
  invitations — roughly a one-to-two-day task).
- **[ACCEPTÉE] The widget's own branding (`WidgetConfig.logo_url`/
  `primary_color`/`secondary_color`, `api/models/widget.py`) does not
  inherit from `OrganizationBranding`; they are two separate, unlinked
  branding surfaces.** Found during the White Label audit. **Accepted
  because**: `WidgetConfig` colors always carry their own real, typed
  defaults (never `NULL`) — there is no "unset" state on the widget
  side to fall back FROM, so linking them would mean either overriding
  a widget's own explicitly-set color whenever it happens to match a
  stale default (wrong), or adding a new explicit
  "inherit_from_org_branding" flag and a real precedence resolver
  (a genuine feature, not a bug fix). A support widget embedded on a
  third-party marketing site legitimately may want different colors
  than the org's own internal-portal branding — this is a real,
  intentional design choice already, not an oversight this étape
  silently found and left broken.
- **[TRACÉE, P2 — reclassifiée depuis "ACCEPTÉE" en Phase 5, Étape 3
  correctif] Custom CSS validation (`api/security/organization_branding.py`'s
  `validate_custom_css`) is a denylist of known-dangerous substrings
  (`javascript:`, `expression(`, `@import`, etc.), not a real CSS
  parser or sandbox — a denylist is never exhaustive by construction,
  and an arbitrary external `url(...)` (e.g. a tracking-pixel-style
  background image, or a same-site-cookie-adjacent probe pointing at an
  attacker-controlled server) is concretely not blocked today.**
  Correction initially misclassified as "accepted" in Étape 3's own
  first report — a real, exploitable gap is never a valid "accepted"
  outcome regardless of how narrow its blast radius is; reclassified
  here to a real, tracked P2 with an actual plan, not just a
  description.
  **Impact réel**: un Owner d'org compromis (ou malveillant) peut
  injecter un `url(...)` externe dans `custom_css`, exfiltrant des
  métadonnées de requête (IP, user-agent, timing) vers un serveur
  qu'il contrôle, pour chaque visiteur qui charge le branding de cette
  organisation — un vecteur de tracking/reconnaissance réel, même si
  borné à l'organisation du compromis (pas d'escalade cross-org).
  **Plan de correction concret** (backend, réalisable sans refonte
  frontend) : étendre `validate_custom_css` pour parser chaque
  occurrence de `url(...)` (regex `url\(\s*['"]?([^'")]+)`) et rejeter
  toute cible qui n'est ni un chemin relatif ni un host explicitement
  autorisé (le bucket de stockage réel de cette organisation,
  `api/services/storage.py`'s own S3/R2 endpoint) — ferme précisément
  le vecteur nommé ici sans nécessiter d'iframe/Shadow DOM côté
  frontend. Une défense en profondeur complémentaire (rendu dans une
  iframe sandboxée avec CSP stricte, ou un Shadow DOM avec une politique
  de style restreinte) reste une amélioration frontend valable pour une
  étape future dédiée au rendu, mais n'est pas nécessaire pour fermer
  ce vecteur précis.
  **Priorité : P2** (exploitable mais borné à l'organisation du
  compromis — pas d'escalade de privilège cross-tenant).
  **Complexité estimée : petite** (une fonction de parsing + une
  allowlist de hosts, plus des tests prouvant qu'un `url()` externe est
  maintenant rejeté et qu'un `url()` relatif/vers le storage autorisé
  passe toujours) — non fait dans cette étape faute de temps, tracé
  pour la prochaine passe sécurité/branding.

## Under consideration (not committed)

- A Kubernetes/Helm deployment path, if self-hosted demand justifies the
  maintenance cost of a second deployment target.
- DNS-provider API integrations (e.g. Cloudflare, Route53) to make
  custom-domain SSL fully automatic instead of manual DNS-01.
- Additional fine-tuning providers as they publish public REST APIs.
- A dedicated dashboard screen for the widget's own domain allowlist
  (Phase 4, Étape 5bis), instead of calling the existing API directly.
- An admin-scoped, internal-network allowlist specifically for
  Enterprise SSO's own OIDC issuer discovery, so that feature could be
  routed through the canonical `ssrf_safe_client()` without breaking
  legitimate internal-network IdP deployments (see the linked gap
  above).

Nothing in this section is scheduled. If you're evaluating the platform
for a specific gap, check the linked docs above first — the honest
answer for most "is X supported" questions is already written down
rather than left implicit.
