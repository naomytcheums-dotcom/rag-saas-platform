# HANDOVER — état observé du projet

### 1. IDENTITÉ DU PROJET

- **Nom :** RAG SaaS Platform, nom affiché dans le titre du [README.md](../README.md#L1).
- **Objectif déclaré :** plateforme multi-tenant pour construire, évaluer et exploiter des assistants RAG sur des documents d'organisation, avec citations, contrôle des coûts et boucle de mesure qualité. C'est la description du dépôt, pas une validation indépendante de tous les parcours ([README.md](../README.md#L3)).
- **Type de produit :** hybride selon la documentation : déploiement self-hosted Docker ou exploitation comme SaaS ([README.md](../README.md#L19)).
- **Public cible :** équipes et organisations qui veulent déployer des assistants RAG sur leur documentation; audience commerciale précise : UNKNOWN ([README.md](../README.md#L3)).
- **Licence :** MIT, déclarée dans [README.md](../README.md#L155). La cohérence avec un fichier de licence distribué n'a pas été contrôlée ici : UNKNOWN.
- **Visibilité Git :** UNKNOWN. Un URL de clonage est documenté, mais l'accès, la visibilité actuelle et le dépôt distant n'ont pas été interrogés.
- **Méthode de ce handover :** faits locaux cités par fichier/ligne; les documents d'audit antérieurs sont signalés comme rapports, pas comme preuve d'état de production.
- Les fichiers `.env` production n'ont pas été lus. Seul le template `.env.staging` sans credential réel a été sélectionné pour les tests isolés; valeurs déployées, clés et DSN restent exclus ([STAGING_TEST_REPORT.md](./audit/STAGING_TEST_REPORT.md#L1)).
- Git était absent du PATH lors du premier handover, mais a été retrouvé à son chemin Windows explicite pendant la mission staging; branche/HEAD vérifiés, voir section 10 et [CHANGE_LEDGER.md](./audit/CHANGE_LEDGER.md#L420).
- La documentation de projet contient des affirmations de complétion qui ne signifient pas que les fonctions ont été validées en production. Le [ROADMAP.md](../ROADMAP.md#L10) annonce 25 parties complétées; les audits statiques documentent simultanément des limites, écarts et blocages.

### 2. STACK TECHNIQUE

- **Backend — langage :** Python. Version annoncée dans les instructions du dépôt : 3.11 ([agents.md](../agents.md#L23)).
- **Backend — framework :** FastAPI; version épinglée `0.141.1` ([requirements-api.txt](../requirements-api.txt#L16)).
- **Backend — runtime réellement observé :** `.venv` local utilisant Python `3.13.12`; cela ne prouve pas la version du serveur hébergé ([TESTS.md](./audit/TESTS.md#L5)).
- **Écart de version Python :** README/contrat annoncent 3.11 tandis que l'environnement de test analysé est 3.13.12; compatibilité des déploiements réels : UNKNOWN ([agents.md](../agents.md#L23), [TESTS.md](./audit/TESTS.md#L5)).
- **Frontend — langage :** TypeScript/JavaScript selon scripts et manifest; version du compilateur déclarée par le manifest, runtime de déploiement : UNKNOWN ([frontend/package.json](../frontend/package.json#L1)).
- **Frontend — framework :** Next.js `16.3.4`; React `19.2.8` dans le manifest local ([frontend/package.json](../frontend/package.json#L1)).
- **Frontend — CSS :** Tailwind CSS, version et paquet à vérifier dans le manifest pour le déploiement; le dépôt utilise Tailwind selon les documents d'architecture ([README.md](../README.md#L58)).
- **Base déclarée :** PostgreSQL avec pgvector; Supabase est indiqué par le README ([README.md](../README.md#L63)).
- **Base self-hosted documentée :** PostgreSQL 16 dans le déploiement Docker. La version du serveur actuellement ciblé par l'application n'a pas été observée ([DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L6)).
- **Base live / hébergeur live :** UNKNOWN. La cible staging Supabase fournie par l'utilisateur est `db.<STAGING_PROJECT_REF>.supabase.co`; aucune authentification ou SQL effectuée. Réseau IPv6 inaccessible après résolution alternative ([STAGING_TEST_REPORT.md](./audit/STAGING_TEST_REPORT.md#L1)).
- **Extension vectorielle :** pgvector; version Python `pgvector==0.3.6`; version installée côté serveur : UNKNOWN ([requirements-api.txt](../requirements-api.txt#L379)).
- **Cache :** Redis; code de cache explicite dans [cache_service.py](../api/services/cache_service.py#L47), et des usages séparés de Redis sont documentés pour rate limiting et Celery. État du Redis connecté : UNKNOWN.
- **Sélection dotenv :** `RAG_ENV_FILE` opt-in dans l'API et le loader historique, défaut `.env` conservé. Le runner staging sélectionne `.env.staging`, sans fallback production, et interdit l'auto-chargement dotenv tiers ([config.py](../api/config.py#L27), [generation.py](../src/generation.py#L73)).
- **Queue :** Celery `5.6.3`, broker/result backend configurés par variables d'environnement Redis; worker et Beat présents dans la documentation du déploiement ([requirements-api.txt](../requirements-api.txt#L86), [README.md](../README.md#L73)).
- **LLM providers configurés dans les choix d'application :** Anthropic, OpenAI, Google/Gemini, Mistral, Ollama, watsonx et fournisseurs compatibles OpenAI; source de configuration et liste exhaustive déclarée dans [README.md](../README.md#L33) et [api/config.py](../api/config.py#L1).
- **LiteLLM :** version épinglée `1.99.0`; sa compatibilité générale avec d'autres providers ne prouve pas qu'ils sont exposés/configurés dans l'application ([requirements-api.txt](../requirements-api.txt#L444)).
- **Providers configurés en environnement réel :** UNKNOWN; aucune configuration `.env` n'a été lue et aucune requête provider n'a été faite.
- **Dépendances critiques — versions de manifeste :**
  - FastAPI `0.141.1` ([requirements-api.txt](../requirements-api.txt#L16)).
  - Uvicorn `0.52.4` ([requirements-api.txt](../requirements-api.txt#L17)).
  - SQLAlchemy asyncio `2.0.40` ([requirements-api.txt](../requirements-api.txt#L39)).
  - asyncpg `0.31.0` ([requirements-api.txt](../requirements-api.txt#L40)).
  - psycopg2-binary `2.9.12` ([requirements-api.txt](../requirements-api.txt#L41)).
  - Alembic `1.19.1` ([requirements-api.txt](../requirements-api.txt#L42)).
  - Pydantic Settings `2.15.0` ([requirements-api.txt](../requirements-api.txt#L45)).
  - HTTPX `0.28.1` ([requirements-api.txt](../requirements-api.txt#L29)).
  - Celery `5.6.3` ([requirements-api.txt](../requirements-api.txt#L86)).
  - Redis Python client `8.1.0` ([requirements-api.txt](../requirements-api.txt#L87)).
  - boto3 `1.43.83` ([requirements-api.txt](../requirements-api.txt#L83)).
  - LiteLLM `1.99.0` ([requirements-api.txt](../requirements-api.txt#L444)).
  - Stripe `11.4.1` ([requirements-api.txt](../requirements-api.txt#L242)).
  - pgvector Python package `0.3.6` ([requirements-api.txt](../requirements-api.txt#L379)).
  - PyMuPDF `1.28.2` ([requirements-api.txt](../requirements-api.txt#L136)).
  - PyTorch `2.13.0+cpu` ([requirements-api.txt](../requirements-api.txt#L171)).
  - sentence-transformers `5.7.0` ([requirements-api.txt](../requirements-api.txt#L172)).
  - Transformers `5.16.1` ([requirements-api.txt](../requirements-api.txt#L183)).
  - DeepEval `4.2.6` ([requirements-api.txt](../requirements-api.txt#L519)).
  - mem0ai `2.2.1` ([requirements-api.txt](../requirements-api.txt#L531)).
- **Dépendance OpenLineage :** `openlineage-python==1.53.0` ([requirements-api.txt](../requirements-api.txt#L539)).
- **Dépendance A2A :** `a2a-sdk==1.2.0` ([requirements-api.txt](../requirements-api.txt#L552)).
- **Dépendance BeeAI :** `beeai-framework==0.1.85` ([requirements-api.txt](../requirements-api.txt#L158)).
- **Services externes visibles dans les interfaces/code :** Supabase/PostgreSQL, Redis, services LLM ci-dessus, Stripe, Paystack, S3/R2 compatibles, GitHub, Google Docs, SMTP/email, Slack, CRM/connecteurs, providers OAuth/SSO, Langfuse/OTLP, Sentry et API externes utilisées par des workflows. L'activation réelle de chacun est UNKNOWN ([README.md](../README.md#L33), [BACKUP_AUDIT.md](./audit/BACKUP_AUDIT.md#L17)).
- **Stack réellement déployée :** UNKNOWN; les versions ci-dessus sont des déclarations/manifests locaux, pas une collecte du runtime distant.

### 3. ARCHITECTURE

- **Diagramme textuel des composants :**
  - Utilisateur / SDK / widget / intégration externe.
  - Frontend Next.js et API publique.
  - API FastAPI (`api/main.py`) et routers REST, MCP et A2A.
  - Services métier : documents, retrieval, génération, workflows, évaluations, billing.
  - PostgreSQL/pgvector pour données, Redis pour cache/queue/rate limit, stockage objet S3-compatible optionnel.
  - Celery worker/Beat pour tâches de fond.
  - Providers LLM, paiement, monitoring et intégrations externes.
  - Ce diagramme résume les composants trouvés dans le dépôt; il ne démontre pas le déploiement actif ([api/main.py](../api/main.py#L1), [README.md](../README.md#L58)).
- **Flux ingestion — source locale :**
  1. L'API expose l'upload et les imports de documents dans [documents.py](../api/routers/documents.py#L225).
  2. Les documents et chunks disposent de modèles locaux ([document.py](../api/models/document.py#L72), [document.py](../api/models/document.py#L224)).
  3. L'extraction, le découpage, les embeddings et l'indexation utilisent services et tâches de fond documentés; ordre et succès en environnement de production : UNKNOWN ([README.md](../README.md#L25)).
  4. Les imports GitHub et Google Docs ont des routes dédiées ([documents.py](../api/routers/documents.py#L344), [documents.py](../api/routers/documents.py#L418)).
  5. Les dépendances storage/LLM/DB réelles n'ont pas été validées.
- **Flux requête RAG — source locale :**
  1. Route d'agent ou API publique reçoit une requête ([agents.py](../api/routers/agents.py#L61), [public_api.py](../api/routers/public_api.py#L280)).
  2. Le pipeline de retrieval fournit une API de recherche et une API avec contexte ([retrieval_pipeline.py](../api/services/retrieval_pipeline.py#L713), [retrieval_pipeline.py](../api/services/retrieval_pipeline.py#L1009)).
  3. Le service de génération appelle une intégration LLM ([generation.py](../api/services/generation.py#L53)).
  4. Les citations et l'usage peuvent être enregistrés; intégrité du flux et mesure live : non validées dans cette phase.
- **Flux agent :**
  - Les agents sont créés et configurés par le routeur des agents; les agents autonomes ont un routeur distinct ([agents.py](../api/routers/agents.py#L61), [autonomous_agents.py](../api/routers/autonomous_agents.py#L1)).
  - Un orchestrateur BeeAI est présent pour exécuter des exigences et équipes multi-agents ([beeai_orchestrator.py](../api/services/beeai_orchestrator.py#L83)).
  - La résolution du provider/modèle et les exécutions live ne sont pas testées ici.
- **Flux workflow :**
  - CRUD et triggers exposés par [workflows.py](../api/routers/workflows.py#L56).
  - Le moteur exécute un run via [workflow_engine.py](../api/services/workflow_engine.py#L275).
  - Celery, webhooks et effets externes supposent un environnement valide; aucune exécution de production n'a été vérifiée.
- **Flux A2A :**
  - Le routeur JSON-RPC est dans [a2a.py](../api/routers/a2a.py#L117).
  - Une correction locale de fermeture/drainage des handlers a été testée; 15 tests A2A ciblés ont passé, sans warning signalé ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).
  - Le README documente A2A comme non-streaming et sans push notifications; les crédits sont une estimation forfaitaire ([README.md](../README.md#L132)).
- **Flux MCP :**
  - Serveur MCP et gestion des serveurs MCP externes ont des routers dédiés ([mcp_server.py](../api/routers/mcp_server.py#L1), [mcp_servers.py](../api/routers/mcp_servers.py#L1)).
  - La documentation agents décrit des routes serveur authentifiées par API key; cette description ne prouve pas que tous les tools sont exposés ou actifs ([agents.md](../agents.md#L85)).
- **Points de défaillance connus :**
  - DB de production, révision de schéma et accès réel inconnus ([DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L46)).
  - Migration locale 0132 dépend de 0131 qui était rapportée non suivie dans les audits; provenance Git actuelle inconnue ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L155)).
  - La migration 0131 active RLS sur des tables sans créer de policies; comportement réel selon rôle DB non vérifié ([MIGRATION_0131_ANALYSIS.md](./audit/MIGRATION_0131_ANALYSIS.md#L1)).
  - L'audit SQL statique a une différence non résolue de quatre candidats entre deux méthodes d'inventaire ([SQL_QUERY_AUDIT.md](./security/SQL_QUERY_AUDIT.md#L1)).
  - Le workflow CI Celery neutralise certains codes de sortie selon l'audit de sécurité; workflow non exécuté dans cette phase ([SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L59)).
  - La conservation distante des backups peut cibler un préfixe plus large que les seuls backups si celui-ci est partagé; aucun backup/restore n'a été exécuté ([BACKUP_AUDIT.md](./audit/BACKUP_AUDIT.md#L63)).
  - Certains tests ont besoin de services/identifiants externes et n'ont pas été exécutés.

### 4. MODÈLE DE DONNÉES

- **Nombre total de tables ORM : 177**, comptage de metadata statique locale, pas de tables live ([DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L24), [TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L3)).
- **Tables avec `organization_id` direct : 79**, classification statique ([TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L9)).
- **Tables avec chemin tenant indirect candidat : 63**, classification par Foreign Key; l'existence du chemin ne prouve pas chaque vérification runtime ([RLS_POLICY_DESIGN.md](./security/RLS_POLICY_DESIGN.md#L8)).
- **Tables user-scoped : 24**, catégorie de la matrice; association à un utilisateur ne démontre pas à elle seule l'isolation organisationnelle ([TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L1)).
- **Tables globales candidates : 3** selon inventaire statique ([TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L1)).
- **Tables système candidates : 6** selon inventaire statique ([TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L1)).
- **Tables UNKNOWN : 2** selon l'inventaire; la classification est heuristique ([TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L1)).
- **Important :** les chiffres sont une analyse de modèles chargés; les rapports avertissent explicitement qu'ils ne décrivent pas un schéma DB live ([TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L3)).
- **Dix tables critiques — justification fonctionnelle locale :**
  1. `organizations` — racine de tenant et de facturation ([organization.py](../api/models/organization.py#L38)).
  2. `organization_members` — appartenance et rôles d'organisation ([organization.py](../api/models/organization.py#L84)).
  3. `workspaces` — conteneur d'organisation et description ajoutée dans 0132 ([workspace.py](../api/models/workspace.py#L1)).
  4. `documents` — métadonnées et cycle de vie des documents ([document.py](../api/models/document.py#L72)).
  5. `document_chunks` — unités utilisées pour l'indexation et la recherche ([document.py](../api/models/document.py#L224)).
  6. `agents` — configuration des agents ([agent.py](../api/models/agent.py#L45)).
  7. `conversations` — association utilisateur/agent et historique ([conversation.py](../api/models/conversation.py#L29)).
  8. `conversation_messages` — messages et historique associé; une lecture IDOR a été corrigée ([conversation.py](../api/models/conversation.py#L61), [PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).
  9. `workflows` — définitions des automatisations ([workflow.py](../api/models/workflow.py#L42)).
  10. `credits` / `credit_transactions` — solde et audit d'usage financier ([billing.py](../api/models/billing.py#L52), [billing.py](../api/models/billing.py#L62)).
- La liste est un classement de criticité métier, pas un classement de volumétrie mesurée.
- **Schema live complet : UNKNOWN.** Aucun inventaire DB n'a été lancé.

### 5. MULTI-TENANCY

- **Modèle actuel visible dans le code :** principalement applicatif, par scope organisation, membership, permissions et relations ORM; les tests d'isolation incluent des balayages cross-tenant ([organizations.py](../api/security/organizations.py#L106), [test_cross_tenant_sweep.py](../tests/test_cross_tenant_sweep.py#L1)).
- **Modèle RLS :** non vérifié en runtime. Les sources locales montrent une activation RLS sans policy associée dans la révision 0131; la configuration de rôle applicatif est un risque à lever ([MIGRATION_0131_ANALYSIS.md](./audit/MIGRATION_0131_ANALYSIS.md#L1), [SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L45)).
- **Tables taguées « RLS YES » par la matrice statique : 174 sur 177 lignes de tables.** Ce marqueur est déduit des sources, pas d'une DB; la matrice est expressément un outil de découverte statique ([TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L3)).
- **Migration locale 0131 :** active RLS sur 11 tables selon l'analyse; aucune policy n'y est créée ([MIGRATION_0131_ANALYSIS.md](./audit/MIGRATION_0131_ANALYSIS.md#L1)).
- **Policy RLS dans le code source des migrations locales :** audit statique trouvé zéro instruction `CREATE POLICY`; l'état de la DB connectée est UNKNOWN ([RLS_POLICY_DESIGN.md](./security/RLS_POLICY_DESIGN.md#L4)).
- **Tables réellement avec RLS activé en DB : UNKNOWN.**
- **Tables réellement protégées par une policy en DB : UNKNOWN.**
- **Architecture cible documentée :** policies `USING` et `WITH CHECK` tenant pour les tables directes, policies par chemin FK pour tables indirectes, exceptions explicitement examinées; document de conception non exécuté ([RLS_POLICY_DESIGN.md](./security/RLS_POLICY_DESIGN.md#L45)).
- **Risque :** si le rôle applicatif contourne RLS ou si les contrôles applicatifs omettent une relation, la DB n'apporte pas de barrière indépendante démontrée ([SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L47)).
- **Risques additionnels :** objets user-scoped, tables globales candidates, chemins FK ambigus, workers hors requête HTTP et requêtes SQL historiques doivent être vérifiés par cas ([TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L3)).
- **État d'isolement client A/B en DB réelle :** non testé. Les tests IDOR rejoués l'ont été sur SQLite/mocks, pas PostgreSQL live ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).

### 6. AUTHENTIFICATION ET AUTORISATION

- **Authentification présente dans le dépôt :** credentials/session/JWT selon les modules; OAuth, SSO et API keys ont des modèles/routers dédiés. Liste d'activation par environnement : UNKNOWN ([auth.py](../api/routers/auth.py#L1), [oauth.py](../api/routers/oauth.py#L1), [organization_api_key.py](../api/models/organization_api_key.py#L1)).
- **Autres mécanismes documentés :** MFA/WebAuthn, clés d'organisation et API publique à scopes; disponibilité live non vérifiée ([README.md](../README.md#L46), [public_api.py](../api/routers/public_api.py#L280)).
- **Autorisation :** RBAC fixe d'organisation et catalogue de permissions existent dans le code ([organization.py](../api/models/organization.py#L25), [permission_catalog.py](../api/security/permission_catalog.py#L16)).
- **Statut RBAC granulaire :** PARTIAL / non démontré partout. Le catalogue définit les permissions, mais l'audit n'a pas prouvé le câblage de toutes les routes; README mentionne également des custom roles, sans valider ici tous leurs parcours ([permission_catalog.py](../api/security/permission_catalog.py#L40), [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1), [README.md](../README.md#L47)).
- **Permissions déclarées : 52**, calcul documenté comme 13 ressources × 4 actions ([permission_catalog.py](../api/security/permission_catalog.py#L10)).
- **Rôles fixes :** `owner`, `admin`, `manager`, `member`, `viewer` d'après l'énumération locale. Le README mentionne en plus des custom roles ([organization.py](../api/models/organization.py#L25), [README.md](../README.md#L47)).
- **Endpoints avec sécurité OpenAPI déclarée :** 840 opérations dans le snapshot statique rapporté; ceci compte une déclaration OpenAPI et ne prouve pas le contrôle effectif à l'exécution ([WORKSPACE_FORENSICS.md](./audit/WORKSPACE_FORENSICS.md#L1)).
- **Opérations sans sécurité OpenAPI explicite :** 96 selon le snapshot; ce chiffre ne permet pas de conclure qu'elles sont publiques, car des contrôles peuvent être appliqués ailleurs. Chaque route doit être inspectée ([WORKSPACE_FORENSICS.md](./audit/WORKSPACE_FORENSICS.md#L1)).
- **Routes réellement protégées : UNKNOWN.** Il n'existe pas de décompte runtime validé dans ce handover.
- **Tests IDOR présents :** agents, documents, conversations, billing, MCP, workflows, datasets/évaluations, médias et A2A; les fichiers spécifiques sont listés à la section 8 et section 16.
- **Écart de contrat :** cinq des neuf scénarios de replay IDOR restent INCOMPLETE car les routes/alias testés ne correspondent pas aux contrats présents; voir le rapport de Phase 2 ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).

### 7. MIGRATIONS

- **Nombre de fichiers de migration Python relevé :** 132 en local après ajout de 0132, comptage du rapport de Phase 2 ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L123)).
- **Head local enregistré :** `0132`; le dernier audit indique que `alembic heads` local après ajout a retourné 0132 ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L123)).
- **Head DB réel : UNKNOWN.** Pas de connexion DB ni requête `alembic_version` ([DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L46)).
- **Nombre historique avant ajout :** le rapport de forensics dénombrait 131 révisions et head 0131 au moment de sa capture ([DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L40)).
- **Révision 0132 :** ajoute une colonne nullable `workspaces.description`; le fichier se trouve sous le dossier Alembic local et avait aussi été préparé sous `scripts/pending` ([0132_workspace_description.py](../api/alembic/versions/0132_workspace_description.py#L1), [DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L57)).
- **Révisions signalées non suivies par Git lors des audits antérieurs :** 0125 à 0131; état de suivi Git actuel UNKNOWN ([DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L54)).
- **0132 suivie par Git : UNKNOWN**, Git CLI étant indisponible dans le contexte de finalisation.
- **Migrations potentiellement pending :** 0132 existe dans le graphe local; migrations pending en base : UNKNOWN ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L123)).
- **Migrations appliquées à une DB : UNKNOWN.** Aucun accès DB dans cette tâche.
- **Différences schema/code :** impossible à établir sans introspection live; la différence est un blocage production documenté ([PRODUCTION_BLOCKERS.md](./audit/PRODUCTION_BLOCKERS.md#L27)).
- **Migrations existantes non modifiées pendant la phase de handover.** Les analyses ont été documentaires/statique; aucune commande de migration n'a été exécutée.
- **Attention au downgrade 0132 :** la colonne de description serait supprimée et les données correspondantes perdues selon l'analyse; ne pas exécuter sans plan de sauvegarde ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L42)).
- **Attention à 0131 :** downgrade désactive RLS sur les tables visées; effets de sécurité à valider avant usage ([MIGRATION_0131_ANALYSIS.md](./audit/MIGRATION_0131_ANALYSIS.md#L1)).

### 8. FONCTIONNALITÉS — LISTE EXHAUSTIVE

- Les statuts ci-dessous distinguent code/documentation locale d'une validation de bout en bout.
- **SHIPPED** signifie que les composants correspondants sont présents; ne signifie pas déploiement ou acceptation production.
- **PARTIAL** signifie que des limites connues ou tests manquants sont documentés.
- **TRACED** signifie qu'un besoin est mentionné/partiellement représenté sans parcours complet prouvé.
- **BLOCKED** signifie que les preuves requises ne sont pas disponibles ou que le parcours dépend d'un prérequis externe.
- Le [Feature Matrix](./audit/FEATURE_MATRIX.md#L1) et le [ROADMAP.md](../ROADMAP.md#L19) documentent des limitations qui contredisent une lecture trop littérale du statut général « toutes les parties achevées ».

- **Organizations — SHIPPED (code local); runtime UNKNOWN.**
  - Sources : [organization.py](../api/models/organization.py#L38), [organizations.py](../api/security/organizations.py#L51).
  - Tests : tests d'organisations et de rôles dans `tests/`; suite exhaustive pas exécutée dans cette tâche.
  - Limites : isolement DB/RLS et déploiement non vérifiés.
  - ROADMAP : sections d'organisation; statut général documentaire ([ROADMAP.md](../ROADMAP.md#L8)).
- **Workspaces — PARTIAL.**
  - Sources : [workspace.py](../api/models/workspace.py#L1), [workspaces.py](../api/routers/workspaces.py#L1), migration locale 0132.
  - Test : [test_workspaces.py](../tests/test_workspaces.py#L1).
  - Limites : migration locale dépend d'une révision non suivie rapportée; état DB inconnu; description pas validée sur une base.
  - ROADMAP : workspace décrit parmi les composants; voir [PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L51).
- **Documents — SHIPPED (routes et modèles présents).**
  - Sources : [documents.py](../api/routers/documents.py#L225), [document.py](../api/models/document.py#L72).
  - Tests : `test_documents*.py`, `test_document_idor.py`; une base live n'a pas été utilisée.
  - Limites : stockage objet et providers externes non validés; tests de charge incomplets selon README ([README.md](../README.md#L130)).
  - ROADMAP : traitement des documents et ingestion.
- **Chunks — SHIPPED (modèle/pipeline présents).**
  - Sources : [document.py](../api/models/document.py#L224), [retrieval_pipeline.py](../api/services/retrieval_pipeline.py#L713).
  - Tests : [test_retrieval_pipeline.py](../tests/test_retrieval_pipeline.py#L1).
  - Limites : index pgvector live et tailles de production inconnus.
  - ROADMAP : retrieval.
- **Agents — SHIPPED (routes et modèles présents).**
  - Sources : [agents.py](../api/routers/agents.py#L61), [agent.py](../api/models/agent.py#L45).
  - Tests : [test_agents.py](../tests/test_agents.py#L1), [test_agent_idor.py](../tests/test_agent_idor.py#L1).
  - Limites : provider réellement configuré et déploiement inconnus.
  - ROADMAP : agents.
- **Autonomous agents — PARTIAL.**
  - Sources : [autonomous_agents.py](../api/routers/autonomous_agents.py#L1), [beeai_orchestrator.py](../api/services/beeai_orchestrator.py#L83).
  - Tests : répertoire de tests agents; couverture de tout le parcours externe inconnue.
  - Limites : BeeAI provider/model en live non testés.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **Workflows — PARTIAL.**
  - Sources : [workflows.py](../api/routers/workflows.py#L56), [workflow_engine.py](../api/services/workflow_engine.py#L275).
  - Tests : fichiers `test_workflow*.py`; les workflows externes live ne sont pas validés.
  - Limites : un workflow CI Celery est signalé comme masquant des erreurs de worker ([SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L59)).
  - ROADMAP : décrit les composants, mais runtime dépend de Celery/providers.
- **Evaluations — SHIPPED (API et services présents).**
  - Sources : [evaluation_datasets.py](../api/routers/evaluation_datasets.py#L33), [evaluation_jobs.py](../api/routers/evaluation_jobs.py#L30).
  - Tests : [test_evaluation_datasets_endpoints.py](../tests/test_evaluation_datasets_endpoints.py#L1), [test_evaluation_jobs_endpoints.py](../tests/test_evaluation_jobs_endpoints.py#L1).
  - Limites : benchmark live/provider et base non exécutés ici.
  - ROADMAP : boucle qualité ([README.md](../README.md#L39)).
- **MCP — PARTIAL / code présent.**
  - Sources : [mcp_server.py](../api/routers/mcp_server.py#L1), [mcp_servers.py](../api/routers/mcp_servers.py#L1).
  - Tests : [test_mcp_idor.py](../tests/test_mcp_idor.py#L1) et tests MCP associés.
  - Limites : interopérabilité de serveurs externes non testée en live; routes documentées ne prouvent pas l'ensemble de la compatibilité.
  - ROADMAP : [agents.md](../agents.md#L85).
- **A2A — PARTIAL, correction de lifecycle locale validée.**
  - Source : [a2a.py](../api/routers/a2a.py#L117).
  - Tests : [test_a2a_router.py](../tests/test_a2a_router.py#L1), [test_a2a_integration.py](../tests/test_a2a_integration.py#L1), [test_a2a_idor.py](../tests/test_a2a_idor.py#L1).
  - Limites : streaming/push notifications absents selon le README; crédit estimé forfaitaire ([README.md](../README.md#L132)).
  - ROADMAP : correction enregistrée dans [ROADMAP.md](../ROADMAP.md#L3924).
- **Billing — PARTIAL.**
  - Sources : [billing.py](../api/models/billing.py#L52), [public_api.py](../api/routers/public_api.py#L92).
  - Tests : [test_billing_idor.py](../tests/test_billing_idor.py#L1).
  - Limites : statut de provider live inconnu; audit antérieur signale un risque de recharge gratuite si configuration incorrecte, corrigé localement mais non vérifié en production ([PRODUCTION_BLOCKERS.md](./audit/PRODUCTION_BLOCKERS.md#L9)).
  - ROADMAP : business/billing ([README.md](../README.md#L52)).
- **Credits — PARTIAL.**
  - Sources : [billing.py](../api/models/billing.py#L52), route A2A [a2a.py](../api/routers/a2a.py#L1).
  - Tests : tests billing et A2A.
  - Limites : audit relève un risque de débit post-exécution A2A; comportement PostgreSQL live à confirmer ([SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L28)).
  - ROADMAP : business.
- **Guardian / alertes de qualité — PARTIAL.**
  - Sources : [quality_alerts.py](../api/routers/quality_alerts.py#L112), métriques de retrieval.
  - Tests : fichiers d'évaluation et d'alerting présents; suite complète non rejouée.
  - Limites : livraison effective des alertes et configuration de canaux inconnues.
  - ROADMAP : descriptif de qualité dans [README.md](../README.md#L42).
- **Autopsy — TRACED / couverture fonctionnelle non prouvée.**
  - Sources : API d'échecs d'évaluation dans [evaluation_jobs.py](../api/routers/evaluation_jobs.py#L90).
  - Tests : tests d'évaluation des échecs présents; appel MCP `get_failure_report` live non vérifié.
  - Limites : la commande du contrat agents.md n'a pas été exécutée.
  - ROADMAP : référence d'alerte/échec à confirmer ([agents.md](../agents.md#L109)).
- **ChangeLab — TRACED.**
  - Sources : benchmarks et configuration retrieval présents dans les services d'évaluation.
  - Tests : tests d'évaluation; aucun autotuning automatique de bout en bout exécuté.
  - Limites : rollback automatique, benchmark comparatif live et commit automatique non démontrés.
  - ROADMAP : le workflow décrit dans [agents.md](../agents.md#L69)) est un contrat, pas une preuve d'exécution.
- **Multimodal — PARTIAL.**
  - Sources : modèles média et dépendances de traitement; modules dans `api/models/media.py` et `api/models/document_image.py`.
  - Tests : tests media présents; intégrations de fournisseurs externes non testées.
  - Limites : types, formats et limites de production à confirmer.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **Voice — PARTIAL.**
  - Source : [voice.py](../api/models/voice.py#L1).
  - Tests : tests voice du dépôt, mais pas de provider live exécuté.
  - Limites : credentials et comportement audio distant inconnus.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **SDK — PARTIAL.**
  - Sources : répertoires `sdks/` et packages déclarés; état de publication inconnu.
  - Tests : tests dans chaque SDK éventuels, nombre et dernier résultat global UNKNOWN.
  - Limites : versions publiées et compatibilité serveur non vérifiées.
  - ROADMAP : [README.md](../README.md#L33).
- **White-label — PARTIAL.**
  - Sources : [organization_branding.py](../api/models/organization_branding.py#L1), modèle de domaines personnalisés.
  - Tests : tests du branding présents ou à recenser; validation DNS/certificats live absente.
  - Limites : domaine de production, TLS et branding réellement activés inconnus.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **Plugins — PARTIAL.**
  - Source : [plugins.py](../api/models/plugins.py#L1).
  - Tests : état exact des tests par plugin UNKNOWN.
  - Limites : compatibilité des plugins tiers et surface runtime non vérifiées.
  - ROADMAP : [README.md](../README.md#L33).
- **RBAC — PARTIAL.**
  - Sources : [organization.py](../api/models/organization.py#L25), [permission_catalog.py](../api/security/permission_catalog.py#L16).
  - Tests : [test_audit_phase4_role_idor.py](../tests/test_audit_phase4_role_idor.py#L1), autres tests de permissions.
  - Limites : 52 permissions générées, mais câblage de chaque endpoint non établi.
  - ROADMAP : audit de sécurité et Feature Matrix.
- **Audit logs — PARTIAL.**
  - Source : [audit_log.py](../api/models/audit_log.py#L1); présence de journaux ne prouve pas que toutes les actions sensibles les écrivent.
  - Tests : tests d'audit disponibles; exhaustive coverage UNKNOWN.
  - Limites : rétention et destination de production inconnues.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **Notifications — PARTIAL.**
  - Sources : [notification.py](../api/models/notification.py#L1), alertes qualité.
  - Tests : tests notification; canal de production non vérifié.
  - Limites : livraison externe et reprises d'erreur inconnues.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **Analytics — PARTIAL.**
  - Source : [analytics.py](../api/models/analytics.py#L1).
  - Tests : métriques applicatives/évaluations locales; analytics de production non inspectées.
  - Limites : exactitude, agrégation tenant et instrumentation non vérifiées.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **Fine-tuning — TRACED / disponibilité externe inconnue.**
  - Source : [fine_tuning.py](../api/models/fine_tuning.py#L1).
  - Tests : aucune tâche de fine-tuning externe lancée dans cette phase.
  - Limites : fournisseurs, coût, politique de données et déploiement de modèles UNKNOWN.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **A/B testing — PARTIAL.**
  - Source : modèle `rag_experiment.py` et paramètres de configuration; runtime décisionnel non éprouvé.
  - Tests : tests associés à rechercher avant activation; résultats live UNKNOWN.
  - Limites : allocation, métriques et arrêt automatique non validés.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **CRM connectors — PARTIAL.**
  - Sources : `api/routers/crm.py` et modules d'intégration; les documents annoncent plusieurs connecteurs.
  - Tests : suites spécifiques providers non exécutées dans cette tâche.
  - Limites : la présence d'un connecteur ne prouve ni credentials ni compatibilité externe.
  - ROADMAP : [README.md](../README.md#L33).
- **Webhooks — PARTIAL.**
  - Sources : [webhook.py](../api/models/webhook.py#L1), triggers workflow ([workflows.py](../api/routers/workflows.py#L170)).
  - Tests : tests webhook/workflow dans le dépôt.
  - Limites : signatures, retries et endpoints réels non validés.
  - ROADMAP : [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
- **Cache — PARTIAL.**
  - Source : [cache_service.py](../api/services/cache_service.py#L47).
  - Tests : tests cache unitaires; Redis réel non pingé.
  - Limites : disponibilité, invalidation distribuée et namespaces tenant live inconnus.
  - ROADMAP : stack Redis dans [README.md](../README.md#L63).
- **Rate limiting — PARTIAL.**
  - Sources : code public API et Redis; la configuration effective est UNKNOWN.
  - Tests : tests de limites présents; charge multi-tenant non mesurée.
  - Limites : aucune vérification du backend Redis en production.
  - ROADMAP : [README.md](../README.md#L46).
- **Sentry — PARTIAL.**
  - Source : [error_tracking.py](../api/security/error_tracking.py#L25); configuration DSN facultative dans [config.py](../api/config.py#L2286).
  - Tests : tests locaux/mock documentés dans ROADMAP.
  - Limites : DSN, projet et erreurs réellement reçues UNKNOWN; `@sentry/nextjs` est maintenant présent dans le manifest. Le passage historique « frontend absent » ne décrit pas ce manifest courant ([package.json](../frontend/package.json#L14), [ROADMAP.md](../ROADMAP.md#L1691)).
  - ROADMAP : [ROADMAP.md](../ROADMAP.md#L608).
- **OpenTelemetry — PARTIAL.**
  - Source : [tracing.py](../api/security/tracing.py#L29), désactivé par défaut dans la config locale ([config.py](../api/config.py#L2261)).
  - Tests : tests d'instrumentation locaux; exporter live UNKNOWN.
  - Limites : `OTEL_ENABLED=False` par défaut; destination effective inconnue.
  - ROADMAP : instrumentation décrite ([ROADMAP.md](../ROADMAP.md#L613)).
- **Langfuse — PARTIAL.**
  - Sources : configuration Langfuse optionnelle ([config.py](../api/config.py#L2369)) et intégration documentée.
  - Tests : aucun service Langfuse réel contacté.
  - Limites : host, clés, version et traces reçues UNKNOWN.
  - ROADMAP : [ROADMAP.md](../ROADMAP.md#L1994).
- **GraphRAG — PARTIAL.**
  - Source : [graph_rag.py](../api/services/graph_rag.py#L1).
  - Tests : tests unitaires locaux à vérifier; aucune base/provider live.
  - Limites : usage effectif dans la chaîne principale et qualité de graphe non mesurés.
  - ROADMAP : intégration annoncée avec limite d'usage dans [ROADMAP.md](../ROADMAP.md#L1914).
- **PII detection — PARTIAL.**
  - Source : [pii_detection.py](../api/services/pii_detection.py#L64).
  - Tests : tests unitaires de détection/anonymisation.
  - Limites : paquet/modeles de langue réellement disponibles et comportement sur données réelles non vérifiés.
  - ROADMAP : dépendance Presidio et limites dans [ROADMAP.md](../ROADMAP.md#L1833).
- **DeepEval — PARTIAL.**
  - Source : [deepeval_validation.py](../api/services/deepeval_validation.py#L84).
  - Tests : [test_deepeval_validation.py](../tests/test_deepeval_validation.py#L1).
  - Limites : évaluation distante/provider non exécutée.
  - ROADMAP : Feature Matrix.
- **DSPy — PARTIAL.**
  - Source : [prompt_optimization.py](../api/services/prompt_optimization.py#L78).
  - Tests : tests d'optimisation locaux; dataset réel/provider non évalué.
  - Limites : aucun benchmark comparatif live.
  - ROADMAP : Feature Matrix.
- **mem0 — PARTIAL.**
  - Source : [mem0_service.py](../api/services/mem0_service.py#L59).
  - Tests : tests de mémoire locaux.
  - Limites : fournisseur de mémoire externe et isolation en production UNKNOWN.
  - ROADMAP : Feature Matrix.
- **OpenLineage — PARTIAL.**
  - Source : [lineage_tracking.py](../api/services/lineage_tracking.py#L78).
  - Tests : unit tests possibles; endpoint/collector externe non vérifié.
  - Limites : émission effective dépend d'options et service externe non inspectés.
  - ROADMAP : Feature Matrix.
- **OPA — PARTIAL.**
  - Source : module de policy et retrieval policy-aware dans `api/services/`.
  - Tests : tests de politique présents; OPA distant non appelé.
  - Limites : politiques réellement chargées et moteur actif UNKNOWN.
  - ROADMAP : Feature Matrix.
- **BeeAI — PARTIAL.**
  - Source : [beeai_orchestrator.py](../api/services/beeai_orchestrator.py#L83).
  - Tests : tests d'orchestration locaux éventuels; modèle/provider live non testé.
  - Limites : erreurs externes et qualité d'équipe multi-agent UNKNOWN.
  - ROADMAP : Feature Matrix.
- **Sandbox — TRACED / produit non complet.**
  - Source : modèle sandbox et documentation roadmap.
  - Tests : exécution sécurisée de code non prouvée dans cette phase.
  - Limites : ROADMAP nomme explicitement le manque d'un environnement sandbox isolé ([ROADMAP.md](../ROADMAP.md#L32)).
  - ROADMAP : statut tracé P2, pas de sandbox forte prouvée.
- **Eval Lab UI — PARTIAL.**
  - Sources : APIs datasets/jobs et frontend d'évaluation; pages frontend exactes à inventorier.
  - Tests : endpoints d'évaluation couverts localement; parcours navigateur complet non vérifié.
  - Limites : UI et benchmark sur DB/provider réel non validés.
  - ROADMAP : Eval Lab décrit ([README.md](../README.md#L39)).
- **Workspace description — PARTIAL / migration locale présente.**
  - Sources : modèle workspace et migration 0132 ([workspace.py](../api/models/workspace.py#L1), [0132_workspace_description.py](../api/alembic/versions/0132_workspace_description.py#L1)).
  - Tests : [test_workspaces.py](../tests/test_workspaces.py#L1); DB migration non exécutée.
  - Limites : HEAD DB et présence de la colonne en production UNKNOWN.
  - ROADMAP : Phase 2 rapporte la modification locale ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L51)).
- **Ingestion GitHub/Google Docs — PARTIAL.**
  - Sources : routes d'import dédiées dans [documents.py](../api/routers/documents.py#L344) et [documents.py](../api/routers/documents.py#L418).
  - Tests : route tests et mocks présents; tokens/API live non testés.
  - Limites : permissions et disponibilité de providers externes UNKNOWN.
  - ROADMAP : intégrations README.
- **Recherche BM25 / pgvector — PARTIAL.**
  - Source : [retrieval_pipeline.py](../api/services/retrieval_pipeline.py#L713).
  - Tests : tests unitaires et benchmark portable.
  - Limites : README précise que BM25 est calculé sur les chunks d'une organisation et que les tests de charge ne couvrent pas pgvector à 10 000 documents ([README.md](../README.md#L130)).
  - ROADMAP : retrieval.
- **API publique / clés — PARTIAL.**
  - Source : [public_api.py](../api/routers/public_api.py#L280).
  - Tests : tests de clés et IDOR.
  - Limites : opération de production et limites de débit live non vérifiées.
  - ROADMAP : SDK/API publique.
- **Intégrations stockage S3/R2 — PARTIAL.**
  - Sources : `boto3`, scripts backup et documentation d'installation.
  - Tests : aucune sauvegarde ou restauration exécutée.
  - Limites : backup ne comprend pas le stockage objet; rétention distante peut viser un préfixe partagé ([BACKUP_AUDIT.md](./audit/BACKUP_AUDIT.md#L63)).
  - ROADMAP : documentation backup/restore.

### 9. TESTS

- **Fichiers de tests Python : 399** après les ajouts staging/loader/guard; les tests frontend et autres types de tests ne sont pas inclus ([AUTONOMOUS_AUDIT_01_DISCOVERY.md](./AUTONOMOUS_AUDIT_01_DISCOVERY.md#L1)).
- **Fonctions définies avec nom de test : 4 881** selon comptage AST statique après ces ajouts; différent du nombre de cas paramétrés collectés.
- **Collection pytest actuelle : 5 335 node IDs sélectionnés** après restauration des paquets déclarés manquants; ce n'est pas un résultat de tests exécutés ([AUTONOMOUS_AUDIT_05_FIXES.md](./AUTONOMOUS_AUDIT_05_FIXES.md#L1)).
- **Frontend actuel : 13 fichiers / 112 tests passés**, lint 0 erreur / 32 warnings et type-check vert, après corrections de deux surfaces JSX/React ([AUTONOMOUS_AUDIT_05_FIXES.md](./AUTONOMOUS_AUDIT_05_FIXES.md#L1)).
- **Guard/config/loader ciblés : 22 passés** après ajout des deux tests entrypoints du runner; tests staging : 11 skippés, aucun PASS PostgreSQL ne peut être déduit de ces skips ([AUTONOMOUS_AUDIT_06_TESTS.md](./AUTONOMOUS_AUDIT_06_TESTS.md#L1)).
- **Dernier run complet actuel :** 4 993 passed, 125 failed, 208 skipped, 23 deselected, exit 1; 49 min 30 s. 104 échecs ont un rejeu ciblé passant, pas un nouveau résultat complet ([AUTONOMOUS_AUDIT_06_TESTS.md](./AUTONOMOUS_AUDIT_06_TESTS.md#L1)).
- **Historique distinct :** rapport du 16 septembre 2026, 4 340 passed/11 skipped; ne remplace pas le run actuel ([TESTS.md](./audit/TESTS.md#L18)).
- **Tests passants récents ciblés :**
  - Replays IDOR : 9 tests passés séquentiellement; le rapport indique 5 scénarios incomplets au regard des routes/contracts attendus ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).
  - A2A : 15 tests ciblés passés après correction du lifecycle du handler, sans warning rapporté ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).
  - Les stdout initiaux des preuves P2C-1 à P2C-9 ont été perdus pendant une opération de renommage sensible à la casse; les tests ont été rejoués et les preuves canoniques recréées. Les nouveaux fichiers signalent la perte de la sortie initiale ([CHANGE_LEDGER.md](./audit/CHANGE_LEDGER.md#L391)).
- **Évolution du 2026-10-04 :** SDK/extraction/guard 63/63, sitemap réel 4/4, PII réelle 4/4; 117 des 125 échecs initiaux ont un rejeu passant. Huit restent sans réussite démontrée. Pas huit vulnérabilités confirmées ([FINAL_STATUS.md](./FINAL_STATUS.md#L1)).
- **Tests skippés actuels :** 208 dans le run complet; 11 tests staging skippés dans le groupe ciblé. Journaux/JUnit conservés hors projet ([AUTONOMOUS_AUDIT_06_TESTS.md](./AUTONOMOUS_AUDIT_06_TESTS.md#L1)).
- **Tests flaky :** UNKNOWN; aucun inventaire flaky exhaustif n'a été exécuté.
- **Warnings connus :**
  - A2A `PytestUnraisableExceptionWarning` reproduit, cause identifiée comme handlers/tâches non fermés; fix local testé dans le sous-ensemble A2A ([PYTEST_WARNINGS_ANALYSIS.md](./audit/PYTEST_WARNINGS_ANALYSIS.md#L1)).
  - Avertissement de réécriture pytest associé à `anyio` rapporté historiquement et non filtré ([CHANGE_LEDGER.md](./audit/CHANGE_LEDGER.md#L286)).
  - Ruff `B008` dans `api/routers/a2a.py` préexistant pour les valeurs `Depends`; pas modifié dans cette phase.
- **Couverture :** un seuil `--cov-fail-under=75` est configuré/documenté; pourcentage exact mesuré actuellement : UNKNOWN ([TESTS.md](./audit/TESTS.md#L89)).
- **Environnement :** `.venv` existant; SDK déclarés restaurés et pin DSPy ajouté au manifest. Résolution conjointe compatible avec les pins embeddings/Torch CPU; pip check vert. Modèle PII officiel installé et tests réels passants ([AUTONOMOUS_AUDIT_06_TESTS.md](./AUTONOMOUS_AUDIT_06_TESTS.md#L1)).
- **PostgreSQL integration tests :** aucun test DB live exécuté; ne pas confondre avec tests SQLite/mocks ([POSTGRES_TEST_PLAN.md](./audit/POSTGRES_TEST_PLAN.md#L1)).
- **Test complet recommandé :** seulement après identification d'une base isolée et vérification des effets des tests; le plan PostgreSQL est read-only pour l'audit catalogué, pas un substitut aux tests d'intégration.

### 10. ÉTAT GIT

- **Branche vérifiée pendant la mission staging :** `bob/auto-fix-20261003-191324` ([CHANGE_LEDGER.md](./audit/CHANGE_LEDGER.md#L420)).
- **HEAD vérifié :** `2e7bfaa3c3fbca3b1a66ad26f9c9ce5ad19d15a2`; aucune nouvelle révision Git créée par cette mission.
- Git retrouvé : `C:\Program Files\Git\cmd\git.exe`; commandes `branch --show-current`, `rev-parse HEAD`, `status --porcelain` exécutées sans reset ni rebase.
- **Snapshot de clôture documentaire :** 137 entrées tracked modifiées et 166 entrées non suivies. Les entrées porcelain de dossiers peuvent regrouper plusieurs fichiers; ce n'est pas une attribution à cette mission.
- **Nombre de fichiers modifiés/non suivis après dernières écritures :** voir le rapport final; compte instantané UNKNOWN tant que les rapports sont en cours de rédaction.
- **Staged / supprimés :** non relevés dans ce snapshot intermédiaire; UNKNOWN.
- **10 commits récents observés** (`git log -10 --format='%h %s'`) :
  1. `2e7bfaa` — global GUARDIAN metrics on Bob's real documents.
  2. `ba51e04` — SUBMISSION.md, Bob as hero and final results.
  3. `465348f` — final GUARDIAN benchmark on Bob's real documents.
  4. `d7ddd0e` — Post-Bob Local Validation report.
  5. `c3506a9` — IBM Bob 2.0 evidence artifacts and lab results.
  6. `d57e6ba` — evaluation timeout 30s to 180s.
  7. `3827910` — wrap port access so startup never crashes.
  8. `6257c8f` — pool overrides and RUNTIME_DB_CONFIG log.
  9. `0b964a1` — pool_size 5 / max_overflow 10.
  10. `d9a6a12` — diagnostic evaluation TRACE prints.
- **Branches locales observées :** `main`, `bob/auto-fix-20261003-1518`, `bob/auto-fix-20261003-191324`, cinq `worktree-agent-*` (`a0701ae782b6e6258`, `a2a11bdc3c13b2abc`, `a57265392c1e48c50`, `aa5d4b012de7274a7`, `aaea7cf1c3b134b1e`).
- **Références distantes observées :** `origin` (symbolique), `origin/main`, `origin/flyio-new-files`; cette observation est locale, aucun fetch effectué.
- **Remote et visibilité du dépôt : UNKNOWN.**
- Aucun commit, push ou rebase dans cette mission. Une nouvelle branche de travail a été créée pendant la mission staging, sans perdre le worktree préexistant.
- Avant partage ou déploiement, établir la provenance des fichiers 0125–0132 et faire un inventaire non destructif du worktree ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L155)).

### 11. ENVIRONNEMENTS

- **DEV identifié ?** UNKNOWN. Des sources locales décrivent une configuration non locale, mais l'environnement connecté et son nom n'ont pas été prouvés ([DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L6)).
- **TEST identifié ?** UNKNOWN comme environnement déployé; des tests locaux SQLite/mocks existent.
- **STAGING identifié ?** oui par cible fournie et allowlist exacte, pas par identité SQL vérifiée : `db.<STAGING_PROJECT_REF>.supabase.co` ([STAGING_TEST_REPORT.md](./audit/STAGING_TEST_REPORT.md#L1)).
- **PRODUCTION identifié ?** UNKNOWN; aucun déploiement ou endpoint de production n'a été sondé.
- **Base cible déclarée :** PostgreSQL/Supabase ([README.md](../README.md#L63)).
- **Host staging sans credentials :** `db.<STAGING_PROJECT_REF>.supabase.co`, port 5432, DB/user postgres; aucun host production utilisé. Le nom UI « -STAGING » n'est pas un suffixe de hostname vérifiable.
- **Base testée :** non pendant cette phase; tests de base réels explicitement bloqués.
- **Base mutée :** non pendant cette phase; aucune connexion ni migration n'a eu lieu.
- **Transport staging :** DNS OS en échec 11001, résolution AAAA alternative obtenue, TCP IPv6 en échec 10051; aucune authentification DB ([STAGING_TEST_REPORT.md](./audit/STAGING_TEST_REPORT.md#L1)).
- **État général DB antérieur :** HEAD appliqué inconnu ([DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L46)).
- **Fichiers locaux de configuration :** leur existence est signalée par forensics; leurs valeurs n'ont pas été consultées ([WORKSPACE_FORENSICS.md](./audit/WORKSPACE_FORENSICS.md#L27)).
- **Docker self-hosted :** PostgreSQL 16, Redis 7, API, worker Celery/Beat et frontend sont documentés; le lancement effectif n'a pas été testé.
- **Aucune inférence environnementale** n'est faite à partir de noms de variables, d'URL de README ou de présence de fichiers.

### 12. SÉCURITÉ

- **Failles corrigées dans cette phase :**
  - IDOR historique de message : le message demandé est désormais lié à la conversation autorisée; test SQLite ciblé passé ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16), [conversation.py](../api/models/conversation.py#L61)).
  - IDOR de détachement Stripe : le PaymentMethod est vérifié contre le customer Stripe de l'organisation avant détachement; test mocké passé, aucun appel Stripe réel ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).
  - Lifecycle A2A : fermeture/drainage du handler corrigée et tests ciblés passés ([ROADMAP.md](../ROADMAP.md#L3931)).
- **Failles/risques connus — sévérité telle que l'audit local la classe :**
  - **P0 conditionnel / moyenne statique :** risque de recharge gratuite si une configuration/provider de paiement incorrecte est déployée; défaut local corrigé, configuration réelle non vérifiée ([SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L9), [PRODUCTION_BLOCKERS.md](./audit/PRODUCTION_BLOCKERS.md#L9)).
  - **P1 :** facturation A2A après exécution, risque d'appel exécuté sans débit; comportement PostgreSQL réel non vérifié ([SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L28)).
  - **P1 structurel :** RLS activé sans policies applicatives; fuite cross-tenant non démontrée, mais barrière DB non prouvée ([SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L45)).
  - **P2 :** workflow CI Celery neutralise des codes d'erreur, possibilité de faux succès CI ([SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L59)).
  - **P2 / opérationnel :** le préfixe de rétention backup peut supprimer des objets non-backup si partagé ([BACKUP_AUDIT.md](./audit/BACKUP_AUDIT.md#L63)).
- **Architecture RLS cible :** voir [RLS_POLICY_DESIGN.md](./security/RLS_POLICY_DESIGN.md#L1); conception non appliquée et non vérifiée.
- **Design de policies RLS :** `USING` + `WITH CHECK` pour tenant direct et stratégie spécifique aux chemins indirects; pas de policies exécutables créées par le document ([RLS_POLICY_DESIGN.md](./security/RLS_POLICY_DESIGN.md#L45)).
- **Matrice tenant :** [TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L1), classification statique seulement.
- **Tests IDOR existants :**
  - [test_agent_idor.py](../tests/test_agent_idor.py#L1).
  - [test_document_idor.py](../tests/test_document_idor.py#L1).
  - [test_conversation_idor.py](../tests/test_conversation_idor.py#L1).
  - [test_billing_idor.py](../tests/test_billing_idor.py#L1).
  - [test_mcp_idor.py](../tests/test_mcp_idor.py#L1).
  - [test_workflow_idor.py](../tests/test_workflow_idor.py#L1).
  - [test_evaluation_idor.py](../tests/test_evaluation_idor.py#L1).
  - [test_media_idor.py](../tests/test_media_idor.py#L1).
  - [test_a2a_idor.py](../tests/test_a2a_idor.py#L1).
  - [test_cross_tenant_sweep.py](../tests/test_cross_tenant_sweep.py#L1).
- **Tests IDOR manquants / incomplets :** cinq contrats de route sur neuf replays restent incomplets parce que les routes/alias attendus n'existent pas ou ne correspondent pas; ils doivent être classés comme incomplets, pas comme pass ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).
- **Audit SQL :** 815 fichiers Python inspectés, 234 avec motifs, 1 195 call sites recensés; registre de 660 candidats contre 656 dans un replay AST indépendant, écart de quatre non résolu ([SQL_QUERY_AUDIT.md](./security/SQL_QUERY_AUDIT.md#L1)).
- **Tests IDOR PostgreSQL :** aucun run A→B/B→A sur la DB réelle; risque de rôle DB et migrations reste ouvert.
- Aucun secret ou valeur de `.env` n'est inclus dans ce rapport.

### 13. DETTE TECHNIQUE

- **P0 — Identifier l'environnement DB et vérifier migrations avant toute release.**
  - Description : HEAD réel, rôle, schéma et cible DB sont inconnus.
  - Impact : incompatibilité schéma/code ou action sur mauvaise base.
  - Complexité : moyenne, dépend de l'accès autorisé à une base de staging.
  - Plan : audit catalogué read-only, vérifier `alembic_version`, confirmer une cible non-production, puis comparer schema/code.
  - Sources : [PRODUCTION_BLOCKERS.md](./audit/PRODUCTION_BLOCKERS.md#L27), [POSTGRES_TEST_PLAN.md](./audit/POSTGRES_TEST_PLAN.md#L1).
- **P0 — Clarifier l'état et la provenance Git.**
  - Description : current branch/HEAD/statut de fichiers non vérifiables; migrations précédentes rapportées non suivies.
  - Impact : risque de partager un worktree différent du commit supposé.
  - Complexité : faible à moyenne.
  - Plan : rétablir Git CLI dans l'environnement autorisé, inventorier sans reset/checkout, sauvegarder les changements et réconcilier les migrations.
  - Source : [PRODUCTION_BLOCKERS.md](./audit/PRODUCTION_BLOCKERS.md#L62).
- **P0 — Vérifier la recharge billing en configuration réelle.**
  - Description : l'audit a identifié un risque conditionnel lié à provider/configuration; fix local ne vaut pas validation du déploiement.
  - Impact : création de crédits sans paiement ou perte financière.
  - Complexité : moyenne.
  - Plan : vérifier la configuration effective sans afficher secrets et exécuter des tests mockés/sandbox; aucun vrai top-up.
  - Sources : [PRODUCTION_BLOCKERS.md](./audit/PRODUCTION_BLOCKERS.md#L9), [SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L9).
- **P0 — Revoir les permissions DB/RLS.**
  - Description : la migration active RLS sans policies, rôle de connexion et statut live UNKNOWN.
  - Impact : pas de défense DB indépendante contre les omissions applicatives ou erreur de rôle.
  - Complexité : élevée; nécessite conception et test en staging.
  - Plan : décider entre RLS permissif explicite, rôle BYPASSRLS, ou modèle hybride; ne pas improviser sur la production.
  - Source : [SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L45).
- **P1 — Rendre le débit A2A transactionnel/prévisible.**
  - Description : débit après exécution et échec de débit avalé rapportés.
  - Impact : appels LLM sans débit correspondant.
  - Complexité : moyenne à élevée.
  - Plan : préautorisation/réservation atomique et tests PostgreSQL de concurrence/rollback.
  - Source : [SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L28).
- **P1 — Compléter les cinq scénarios IDOR qui ne testent pas les routes présentes.**
  - Description : les alias/contrats du test sont divergents/absents.
  - Impact : couverture d'autorisation surestimée si un 404 inattendu est considéré comme fix.
  - Complexité : moyenne.
  - Plan : aligner test sur API documentée ou implémenter explicitement le contrat; vérifier qu'un utilisateur d'un autre tenant ne peut lire/modifier.
  - Test attendu : statut d'accès refusé attendu pour chaque objet cross-tenant, sur DB de test isolée.
  - Source : [PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16).
- **P1 — Réconcilier l'inventaire SQL.**
  - Description : 660 vs 656 candidats AST, différence de quatre non expliquée.
  - Impact : audit tenant incomplet ou doublons.
  - Complexité : faible à moyenne.
  - Plan : comparer les quatre entrées et classer leur contexte, sans supposer qu'elles sont vulnérables.
  - Source : [SQL_QUERY_AUDIT.md](./security/SQL_QUERY_AUDIT.md#L1).
- **P1 — Prouver backup et restore sur cible isolée.**
  - Description : scripts analysés mais aucun dump/restore exécuté.
  - Impact : impossibilité de démontrer la récupération.
  - Complexité : moyenne.
  - Plan : bucket/préfixe dédié, DB jetable, restauration et vérification de comptages/checksums.
  - Source : [BACKUP_AUDIT.md](./audit/BACKUP_AUDIT.md#L83).
- **P1 — Distinguer CI succès du worker Celery.**
  - Description : workflow neutralise certains codes de sortie.
  - Impact : échec de tâches masqué dans CI.
  - Complexité : faible.
  - Plan : faire échouer le job sur erreurs réelles et tester codes attendus.
  - Source : [SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md#L59).
- **P2 — Faire un run complet reproductible sur environnement isolé.**
  - Description : dernier rapport complet est historique et non nécessairement sur le worktree actuel.
  - Impact : régressions non détectées.
  - Complexité : moyenne; nécessite services test correctement provisionnés.
  - Plan : installer les dépendances uniquement selon le lock/manifest et exécuter les suites ciblées puis complètes sans toucher la production.
  - Test attendu : pytest, frontend lint/type-check/tests, résultats archivés.
- **P2 — Revoir documentation et chiffres README.**
  - Description : le README annonce 98 routers, ~900 routes, 130 migrations, 376 fichiers de tests, 48 pages; inventaire ultérieur donne 132 migrations, 395 tests et snapshot OpenAPI différent.
  - Impact : les utilisateurs se fient à des métriques obsolètes.
  - Complexité : faible.
  - Plan : mettre à jour les chiffres à partir de scripts reproductibles et dater la mesure ([README.md](../README.md#L69)).
- **P2 — Mesurer retrieval sur PostgreSQL et charge HTTP.**
  - Description : README documente couverture de charge partielle.
  - Impact : performances importantes inconnues à l'échelle.
  - Complexité : élevée.
  - Plan : dataset synthétique, staging, tests pgvector/HNSW et concurrence.
  - Source : [README.md](../README.md#L130).
- **P2 — Documenter statut déployé des fournisseurs/observabilité.**
  - Description : présence de code ne prouve pas activation Sentry, OTEL, Langfuse ou OPA.
  - Impact : angles morts de monitoring/policy.
  - Complexité : moyenne.
  - Plan : inventaire de configuration sans exposer les valeurs secrètes, test de réception synthétique.
- **P3 — Stabiliser statut des fonctions tracées.**
  - Description : sandbox, fine-tuning, intégrations avancées et autres surfaces ont une preuve variable.
  - Impact : écarts d'attentes produit.
  - Complexité : variable.
  - Plan : maintenir Feature Matrix avec critère d'acceptation et lien vers test pour chaque capacité.

### 14. BLOCKED_EXTERNAL

- **Audit PostgreSQL live**
  - Raison : aucune cible explicitement identifiée et aucune connexion autorisée/exécutée.
  - Prérequis : DB DEV/TEST/STAGING clairement nommée, credentials fournis hors rapport et approbation du script read-only.
  - Impact : RLS, policies, migrations appliquées et rôle effectif demeurent UNKNOWN.
  - Référence : [POSTGRES_TEST_PLAN.md](./audit/POSTGRES_TEST_PLAN.md#L1).
- **Tests PostgreSQL d'intégration**
  - Raison : les tests pourraient se connecter et muter leur DB cible; target non confirmée.
  - Prérequis : base jetable isolée, fixtures et validation préalable de l'URL sans exposition de secrets.
  - Impact : aucun résultat live sur transactions, locks et RLS.
  - Référence : [test_postgres_integration.py](../tests/test_postgres_integration.py#L1).
- **Vérification Stripe réelle**
  - Raison : test d'IDOR effectué avec mock; pas d'appel Stripe.
  - Prérequis : sandbox Stripe non-production et PaymentMethod/customer de test.
  - Impact : comportement provider distant non validé.
  - Référence : [PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16).
- **Providers LLM et integrations externes**
  - Raison : aucun appel réel; clés et environnements non inspectés.
  - Prérequis : sandbox ou credentials de test explicites, quotas et budget validés.
  - Impact : génération, ingestion distante et coûts réels restent UNKNOWN.
  - Référence : [README.md](../README.md#L33).
- **Backup/restore distant**
  - Raison : scripts analysés statiquement; aucune exécution de sauvegarde/restauration.
  - Prérequis : bucket/préfixe isolé, DB jetable, politique de rétention test.
  - Impact : récupérabilité non démontrée; risque de suppression si le préfixe est partagé.
  - Référence : [BACKUP_AUDIT.md](./audit/BACKUP_AUDIT.md#L63).
- **Déploiement production**
  - Raison : aucun accès ni état de production vérifié.
  - Prérequis : validation humaine de staging, migration, sécurité et monitoring.
  - Impact : aucune garantie de fonctionnement ou sécurité production ne peut être émise.
  - Référence : [PRODUCTION_BLOCKERS.md](./audit/PRODUCTION_BLOCKERS.md#L93).
- **Collecte Git complète**
  - Raison : Git CLI indisponible et dépôt non reconnu par l'environnement actuel.
  - Prérequis : environnement qui permet inspection Git en lecture seule.
  - Impact : provenance, branches, statut et commits actuels restent UNKNOWN.
  - Référence : [WORKSPACE_FORENSICS.md](./audit/WORKSPACE_FORENSICS.md#L6).

### 15. ROADMAP

- **Phases déclarées complétées :** le début de la roadmap déclare les 25 parties de développement achevées ([ROADMAP.md](../ROADMAP.md#L6)).
- Cette déclaration décrit le statut de la roadmap, pas un résultat d'acceptation production.
- **Limites explicitement documentées :** sections « Known, honestly-documented gaps », notamment sandbox isolée et Sentry frontend ([ROADMAP.md](../ROADMAP.md#L19)).
- **Phase récente documentée :** Phase 2 corrective, audits et corrections locales IDOR/A2A ([ROADMAP.md](../ROADMAP.md#L3924)).
- **Phase actuelle selon ce dossier :** handover/documentation factuelle; aucun numéro de phase produit actuellement confirmé.
- **Éléments réalisés dans la phase corrective :** replays IDOR ciblés, correction du lifecycle A2A, inventaire statique multi-tenant/SQL/migrations, analyses backup, et plan DB read-only ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).
- **Éléments bloqués :** PostgreSQL live, vérification RLS/policies, migrations appliquées, backup/restore réel, provider/paiement sandbox ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L151)).
- **Critères de fin réalistes de la phase corrective :**
  - Provenance Git et migrations locales réconciliées.
  - Cible staging/test explicitement identifiée.
  - Audit PostgreSQL read-only terminé.
  - Tests PostgreSQL IDOR/RLS sur DB jetable.
  - Restore vérifié sans risque de toucher aux données de production.
  - Candidats SQL 660/656 réconciliés.
  - Toute route IDOR contractuelle classée PASS ou INCOMPLETE avec preuve.
- Ces critères sont les suites recommandées des blocages, pas des critères de livraison déjà atteints.
- **Prochaine phase recommandée :** validation contrôlée en staging, une fois l'environnement explicitement identifié.
- **Aucun lancement de migration ou déploiement** n'a eu lieu pendant la préparation de ce fichier.

### 16. FICHIERS CRITIQUES

- Les lignes indiquent le nombre de lignes observé dans le snapshot local de préparation; les numéros peuvent changer avec de nouvelles modifications.
- Les dépendances listées sont les dépendances fonctionnelles principales repérées, pas un graphe exhaustif d'import.

1. **[README.md](../README.md)** — 161 lignes — Présentation, stack, installation, limites, licence — dépend des manifests et de la roadmap.
2. **[ROADMAP.md](../ROADMAP.md)** — 3 992 lignes — Historique des phases, décisions et limites produit — dépend des rapports d'audit et du code.
3. **[agents.md](../agents.md)** — 397 lignes — Contrat d'architecture et opération — dépend des endpoints et commandes du dépôt.
4. **[requirements-api.txt](../requirements-api.txt)** — 552 lignes — Dépendances backend épinglées — fournit libraries à l'API, tâches et services.
5. **[pyproject.toml](../pyproject.toml)** — 57 lignes — Configuration Python/tests/coverage — dépend des outils Python installés.
6. **[package.json](../frontend/package.json)** — 45 lignes — Scripts et dépendances frontend — utilisé par Next.js, React et tooling.
7. **[main.py](../api/main.py)** — 481 lignes — Création/configuration API et inclusion de routers — dépend de `api/routers`, config et middleware.
8. **[config.py](../api/config.py)** — 2 439 lignes — Configuration backend et providers — dépend de variables d'environnement et Pydantic.
9. **[database.py](../api/database.py)** — 84 lignes — Moteur/session SQLAlchemy — dépend de SQLAlchemy, asyncpg et config DB.
10. **[__init__.py](../api/models/__init__.py)** — 150 lignes — Chargement des modèles et metadata ORM — dépend de l'ensemble des modèles.
11. **[organization.py](../api/models/organization.py)** — 127 lignes — Tenant et membership/roles — dépend de SQLAlchemy et modèles user.
12. **[workspace.py](../api/models/workspace.py)** — 37 lignes — Modèle workspace — dépend de l'organisation et migration 0132.
13. **[document.py](../api/models/document.py)** — 471 lignes — Documents, chunks, tags et versions — dépend de SQLAlchemy/pgvector et organisation.
14. **[agent.py](../api/models/agent.py)** — 118 lignes — Configuration/persistance agent — dépend de l'organisation et documents.
15. **[conversation.py](../api/models/conversation.py)** — 82 lignes — Conversations/messages — dépend d'utilisateur, agent et tenant.
16. **[workflow.py](../api/models/workflow.py)** — 73 lignes — Définition du workflow — dépend d'organisation et workflow runs.
17. **[evaluation.py](../api/models/evaluation.py)** — 550 lignes — Datasets/jobs/résultats d'évaluation — dépend d'agent et organisation.
18. **[billing.py](../api/models/billing.py)** — 175 lignes — Crédit, transaction, facture et customer — dépend de Stripe/Paystack et org.
19. **[organizations.py](../api/security/organizations.py)** — 244 lignes — Vérifications membership/roles — dépend de modèles org et FastAPI.
20. **[permission_catalog.py](../api/security/permission_catalog.py)** — 58 lignes — Catalogue de permissions — dépend des actions/ressources de l'API.
21. **[auth.py](../api/routers/auth.py)** — 409 lignes — Router d'authentification — dépend de JWT/session/user.
22. **[documents.py](../api/routers/documents.py)** — 1 137 lignes — API ingestion/document — dépend de stockage, tâches et DB.
23. **[agents.py](../api/routers/agents.py)** — 516 lignes — API création/configuration agents — dépend des services RAG/permissions.
24. **[autonomous_agents.py](../api/routers/autonomous_agents.py)** — 202 lignes — API agents autonomes — dépend de BeeAI/services.
25. **[workflows.py](../api/routers/workflows.py)** — 357 lignes — API définition, versions, triggers et runs — dépend de Celery/moteur.
26. **[evaluation_datasets.py](../api/routers/evaluation_datasets.py)** — 153 lignes — CRUD datasets/questions — dépend d'évaluation et DB.
27. **[evaluation_jobs.py](../api/routers/evaluation_jobs.py)** — 129 lignes — Lancement/suivi jobs et failures — dépend de services eval/Celery.
28. **[evaluation_results.py](../api/routers/evaluation_results.py)** — 73 lignes — API des résultats d'évaluation — dépend de modèles/service eval.
29. **[mcp_server.py](../api/routers/mcp_server.py)** — 190 lignes — Exposition MCP locale — dépend de tools/API key.
30. **[mcp_servers.py](../api/routers/mcp_servers.py)** — 169 lignes — Gestion des serveurs externes — dépend de transport et SSRF-safe clients.
31. **[a2a.py](../api/routers/a2a.py)** — 168 lignes — Endpoint A2A JSON-RPC et lifecycle corrigé — dépend de `a2a-sdk`, agent et billing.
32. **[rag_control_plane.py](../api/routers/rag_control_plane.py)** — 205 lignes — Routes d'exploitation/contrôle RAG — dépend de retrieval et permission.
33. **[public_api.py](../api/routers/public_api.py)** — 433 lignes — API publique/scopes/quota — dépend de clés, rate limit et billing.
34. **[retrieval_pipeline.py](../api/services/retrieval_pipeline.py)** — 1 129 lignes — Retrieval et contexte — dépend de PostgreSQL/pgvector, embeddings et rerankers.
35. **[generation.py](../api/services/generation.py)** — 238 lignes — Génération de réponse — dépend de LiteLLM/providers et contexte.
36. **[workflow_engine.py](../api/services/workflow_engine.py)** — 369 lignes — Exécution workflows — dépend de modèles et services de blocs.
37. **[beeai_orchestrator.py](../api/services/beeai_orchestrator.py)** — 203 lignes — Orchestration multi-agent — dépend de BeeAI et LLM.
38. **[graph_rag.py](../api/services/graph_rag.py)** — 202 lignes — Service GraphRAG — dépend de LightRAG et embeddings.
39. **[deepeval_validation.py](../api/services/deepeval_validation.py)** — 124 lignes — Validation DeepEval — dépend de DeepEval et LLM.
40. **[prompt_optimization.py](../api/services/prompt_optimization.py)** — 167 lignes — Optimisation DSPy — dépend de dataset d'évaluation et provider LLM.
41. **[mem0_service.py](../api/services/mem0_service.py)** — 197 lignes — Mémoire long terme — dépend de mem0, embeddings et org/agent.
42. **[pii_detection.py](../api/services/pii_detection.py)** — 106 lignes — Détection/anonymisation PII — dépend de Presidio et modèles de langue.
43. **[lineage_tracking.py](../api/services/lineage_tracking.py)** — 126 lignes — Émission d'événements OpenLineage — dépend de configuration et collector.
44. **[cache_service.py](../api/services/cache_service.py)** — 106 lignes — Cache Redis — dépend de Redis et clés/namespaces.
45. **[tracing.py](../api/security/tracing.py)** — 131 lignes — Instrumentation OpenTelemetry — dépend de config OTEL/exporter.
46. **[error_tracking.py](../api/security/error_tracking.py)** — 54 lignes — Initialisation/statut Sentry — dépend de DSN/config.
47. **[test_cross_tenant_sweep.py](../tests/test_cross_tenant_sweep.py)** — 115 lignes — Balayage cross-tenant — dépend des routes et fixtures de test.
48. **[test_postgres_integration.py](../tests/test_postgres_integration.py)** — 874 lignes — Tests PostgreSQL/RLS — dépend d'une DB, non lancée ici.
49. **[test_conversation_idor.py](../tests/test_conversation_idor.py)** — 79 lignes — Tests IDOR conversation/message — dépend de fixtures user/tenant.
50. **[test_billing_idor.py](../tests/test_billing_idor.py)** — 118 lignes — Tests IDOR billing/Stripe mock — dépend de modèle billing et client mocké.

- Les nombres de lignes sont calculés sur le snapshot local lors de la rédaction; les fichiers peuvent changer ensuite.
- Les références de code principales des fonctionnalités sont également indiquées à la section 8.

### 17. COMMANDES UTILES

- **Créer l'environnement Python :** `python -m venv .venv` puis activation adaptée à Windows; le README décrit également l'installation de `requirements-api.txt` ([README.md](../README.md#L73)).
- **Démarrer l'API localement :** `uvicorn api.main:app --reload`; présence du point d'entrée vérifiée, commande exacte de déploiement local à confirmer dans README ([api/main.py](../api/main.py#L1)).
- **Démarrer le frontend :** `cd frontend` puis `npm run dev`; scripts dans [package.json](../frontend/package.json#L1).
- **Démarrer worker/Beat :** commandes Celery de l'environnement décrit par Docker/deployment docs; nom exact de l'application Celery à confirmer avant usage, ne pas lancer en production sans cible connue.
- **Lancer tests ciblés backend :** `python -m pytest tests/test_a2a_router.py tests/test_a2a_integration.py tests/test_a2a_idor.py -q`; ce groupe a donné 15 pass dans la phase corrective ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L16)).
- **Lancer tests du dépôt :** `python -m pytest tests/ -x`; cela peut dépendre de services, mocks et variables d'environnement. Vérifier la cible DB avant tout run ([agents.md](../agents.md#L130)).
- **Lancer tests Eval :** répertoire `tests/eval/` observé avec `dataset_demo.json`, sans module Python `test_*.py`; `python -m pytest tests/eval/ -x` peut ne collecter aucun test et n'est pas une validation établie.
- **Lint backend :** `ruff check api/`; cible déclarée dans [agents.md](../agents.md#L135).
- **Format backend :** `ruff format api/`; cette commande modifie les fichiers, à exécuter uniquement lors d'une tâche de formatage autorisée.
- **Lint frontend :** `cd frontend` puis `npm run lint`; script manifest présent ([package.json](../frontend/package.json#L1)).
- **Type-check frontend :** `cd frontend` puis `npm run type-check`; script manifest présent ([package.json](../frontend/package.json#L1)).
- **Tests frontend :** `cd frontend` puis `npm test`; script manifest présent ([package.json](../frontend/package.json#L1)).
- **Générer / vérifier OpenAPI :** snapshot statique local sous `docs/api/openapi.json`; commande de génération/reproductibilité : UNKNOWN. 781 paths, 936 opérations, dont 840 avec sécurité déclarée dans le snapshot observé ([WORKSPACE_FORENSICS.md](./audit/WORKSPACE_FORENSICS.md#L1)).
- **Exporter matrice tenant :** [TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md#L1) est l'artefact courant; commande reproductible exacte : UNKNOWN.
- **Analyser DB en lecture seule :** `python scripts/postgres_readonly_audit.py --dry-run`; seul dry-run exécuté. Le mode d'exécution exige approbation/environment et n'a pas été utilisé sur une DB ([POSTGRES_TEST_PLAN.md](./audit/POSTGRES_TEST_PLAN.md#L1)).
- **Vérifier environnement DB :** suivre [POSTGRES_TEST_PLAN.md](./audit/POSTGRES_TEST_PLAN.md#L1); ne pas afficher d'URL ni de secret. Aucun test DB n'a été fait dans cette session.
- **Afficher les heads Alembic locaux sans connexion :** commande `alembic heads` précédemment utilisée, résultat enregistré `0132`; ce n'est pas le head DB ([PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L123)).
- **Exécuter migrations :** `alembic upgrade head` est une commande mutante et n'a pas été lancée; exiger une approbation et staging identifié ([agents.md](../agents.md#L139)).
- **Backup/restore :** scripts `scripts/backup.sh` et `scripts/restore.sh`; ne pas exécuter sur stockage ou DB partagés sans environnement jetable ([BACKUP_AUDIT.md](./audit/BACKUP_AUDIT.md#L17)).
- Les commandes documentées sont des points de départ; dépendances, variables et services locaux peuvent empêcher leur exécution.

### 18. CONTACTS ET RESSOURCES

- **Documentation principale :** [README.md](../README.md).
- **Roadmap :** [ROADMAP.md](../ROADMAP.md).
- **Contrat agents :** [agents.md](../agents.md).
- **Cahier des charges :** `docs/CAHIER_DES_CHARGES.md`; présence/actualité à revérifier avant diffusion.
- **Change ledger :** [CHANGE_LEDGER.md](./audit/CHANGE_LEDGER.md).
- **Rapport Phase 2 :** [PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md).
- **Feature matrix :** [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md).
- **Forensics database :** [DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md).
- **Forensics workspace :** [WORKSPACE_FORENSICS.md](./audit/WORKSPACE_FORENSICS.md).
- **Audit SQL :** [SQL_QUERY_AUDIT.md](./security/SQL_QUERY_AUDIT.md).
- **Matrice tenant :** [TENANT_ISOLATION_MATRIX.md](./security/TENANT_ISOLATION_MATRIX.md).
- **Design RLS :** [RLS_POLICY_DESIGN.md](./security/RLS_POLICY_DESIGN.md).
- **Audit sécurité :** [SECURITY_AUDIT.md](./audit/SECURITY_AUDIT.md).
- **Blockers production :** [PRODUCTION_BLOCKERS.md](./audit/PRODUCTION_BLOCKERS.md).
- **Plan PostgreSQL :** [POSTGRES_TEST_PLAN.md](./audit/POSTGRES_TEST_PLAN.md).
- **Audit backups :** [BACKUP_AUDIT.md](./audit/BACKUP_AUDIT.md).
- **Warnings pytest :** [PYTEST_WARNINGS_ANALYSIS.md](./audit/PYTEST_WARNINGS_ANALYSIS.md).
- **Rapport de tests historique :** [TESTS.md](./audit/TESTS.md).
- **Analyses migrations :** [MIGRATION_0128_ANALYSIS.md](./audit/MIGRATION_0128_ANALYSIS.md) et [MIGRATION_0131_ANALYSIS.md](./audit/MIGRATION_0131_ANALYSIS.md).
- **Preuves Phase 2 :** dossier [PHASE_2_EVIDENCE](./audit/PHASE_2_EVIDENCE).
- **Contact indiqué dans le contrat projet :** Naomy Tcheums ([agents.md](../agents.md#L1)).
- L'identité du contact, sa disponibilité et l'adresse de contact ne sont pas vérifiées ici.

### 19. HISTORIQUE DES PHASES

- **Phase antérieure — date du rapport : 2026-09-16.**
  - Objectif : résultats de tests complets archivés.
  - Statut : historique, pas un test actuel.
  - Rapport : [TESTS.md](./audit/TESTS.md#L18).
  - Artefact : résultat résumé 4 340 pass, 11 skipped, 0 fail.
- **Phase d'audit initial — date consignée : 2026-10-03.**
  - Objectif : cartographier workspace, DB, features, SQL, isolation et blockers.
  - Statut : analyses statiques achevées, runtime externe non vérifié.
  - Rapports : [DATABASE_FORENSICS.md](./audit/DATABASE_FORENSICS.md#L1), [WORKSPACE_FORENSICS.md](./audit/WORKSPACE_FORENSICS.md#L1), [FEATURE_MATRIX.md](./audit/FEATURE_MATRIX.md#L1).
  - Artefacts : matrice tenant, audit SQL, security audit, backups et production blockers.
- **Phase 2 corrective — date consignée : 2026-10-03.**
  - Objectif : traiter 16 tâches d'audit, rejouer scénarios IDOR, réparer warning A2A et documenter limites.
  - Statut : corrections locales et tests ciblés terminés; vérifications DB/externes bloquées.
  - Rapport : [PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L1).
  - Ledger : [CHANGE_LEDGER.md](./audit/CHANGE_LEDGER.md#L1).
  - Artefacts : seize fichiers de preuves dans [PHASE_2_EVIDENCE](./audit/PHASE_2_EVIDENCE).
  - Perte de données de sortie à signaler : sorties brutes initiales P2C 1–9 supprimées accidentellement au renommage; replays refaits, preuves recréées et limite documentée ([CHANGE_LEDGER.md](./audit/CHANGE_LEDGER.md#L391)).
- **Phase migrations/workspace — même période de rapport.**
  - Objectif : ajout de `workspaces.description` via migration 0132.
  - Statut : artefact local uniquement; aucune DB migrée.
  - Source : [PHASE_2_REPORT.md](./audit/PHASE_2_REPORT.md#L51).
  - Artefact : [0132_workspace_description.py](../api/alembic/versions/0132_workspace_description.py#L1).
- **Phase A2A lifecycle — même période de rapport.**
  - Objectif : fermer les handlers qui laissaient des tâches actives au teardown.
  - Statut : fix local et suite ciblée verte.
  - Source : [ROADMAP.md](../ROADMAP.md#L3931).
  - Artefact : [a2a.py](../api/routers/a2a.py#L117).
- **Phase handover — date de rédaction : 2026-10-03, date d'après journal local.**
  - Objectif : synthèse de l'état réel citée par fichier/ligne.
  - Statut : document créé; pas de modification d'autre fichier dans cette étape.
  - Rapport : ce fichier.
  - Artefact : [HANDOVER.md](./HANDOVER.md).
- Les phases avec numéros supplémentaires/dates intermédiaires n'ont pas toutes été réconciliées à partir d'un historique Git complet; elles sont UNKNOWN.

### 20. PROCHAINES ACTIONS

- **P0 — Confirmer l'identité d'une cible staging/test sans exposer d'identifiants.**
  - Fichier cible : documentation d'environnement/plan [POSTGRES_TEST_PLAN.md](./audit/POSTGRES_TEST_PLAN.md).
  - Test attendu : audit catalogué read-only, vérifier rôle, `alembic_version`, RLS/policies.
  - Risque : connexion accidentelle à la production si la cible est ambiguë.
- **P0 — Réconcilier le dépôt et les migrations non suivies.**
  - Fichier cible : révisions 0125–0132, notamment [0132_workspace_description.py](../api/alembic/versions/0132_workspace_description.py#L1).
  - Test attendu : `git status`, `git log`, `alembic heads` exécutés dans un contexte fiable; aucune commande destructive.
  - Risque : perdre ou publier par erreur des changements non attribués.
- **P0 — Décider le modèle DB/RLS avant release.**
  - Fichier cible : [RLS_POLICY_DESIGN.md](./security/RLS_POLICY_DESIGN.md).
  - Test attendu : tests A→B et B→A sur PostgreSQL de test avec le rôle exact de l'application.
  - Risque : isolement uniquement applicatif ou policy inopérante.
- **P0 — Vérifier le défaut billing dans une configuration sandbox.**
  - Fichier cible : `api/config.py`, tests config/billing.
  - Test attendu : top-up impossible sans provider payé, et PaymentMethod étranger refusé.
  - Risque : crédits non payés ou perte financière.
- **P1 — Terminer les cinq scénarios IDOR incomplets et documenter les contrats.**
  - Fichier cible : tests IDOR concernés et routers correspondants.
  - Test attendu : assertions explicites de refus pour toutes les routes réellement exposées.
  - Risque : faux sentiment de sécurité basé sur 404 d'une route inexistante.
- **P1 — Réconcilier les quatre candidats du scan SQL.**
  - Fichier cible : [SQL_QUERY_AUDIT.md](./security/SQL_QUERY_AUDIT.md).
  - Test attendu : table de correspondance entre inventaire statique (660) et replay AST (656).
  - Risque : omission de requêtes tenant ou duplication de findings.
- **P1 — Tester débit A2A atomique sur PostgreSQL isolé.**
  - Fichier cible : [a2a.py](../api/routers/a2a.py) et tests billing/A2A.
  - Test attendu : solde insuffisant ne lance pas l'agent; erreur de débit n'est pas avalée; concurrence sans double dépense.
  - Risque : appel LLM non facturé ou débit incohérent.
- **P1 — Valider backup/restore et rétention dans un bucket jetable.**
  - Fichier cible : [backup.sh](../scripts/backup.sh), [restore.sh](../scripts/restore.sh).
  - Test attendu : restaurer dans DB jetable et vérifier données/indexes/fichiers.
  - Risque : suppression ou altération de données partagées.
- **P1 — Corriger et tester le résultat du workflow Celery CI.**
  - Fichier cible : `.github/workflows/celery-worker.yml`.
  - Test attendu : code d'échec worker/timeout fait échouer le job.
  - Risque : CI verte malgré un worker défaillant.
- **P2 — Relancer suites backend et frontend dans environnement isolé.**
  - Fichier cible : aucun changement initial; collecter résultats.
  - Test attendu : pytest complet, `npm run lint`, `npm run type-check`, `npm test`.
  - Risque : les tests peuvent dépendre d'une DB ou services dont la cible doit être vérifiée.
- **P2 — Mettre à jour les métriques du README depuis une commande reproductible.**
  - Fichier cible : [README.md](../README.md#L69).
  - Test attendu : les nombres de routers, migrations, fichiers de tests et pages correspondent au snapshot calculé.
  - Risque : les chiffres documentaires induisent en erreur.
- **P2 — Mesurer retrieval pgvector et charge HTTP à l'échelle.**
  - Fichier cible : `scripts/retrieval_benchmark.py`, documentation résultats.
  - Test attendu : benchmark staging pour tailles corpus, latence p95 et concurrence.
  - Risque : performance réelle inconnue.
- **P2 — Vérifier instrumentation Sentry/OTEL/Langfuse sans divulguer les secrets.**
  - Fichier cible : configuration et services d'observabilité.
  - Test attendu : événement synthétique reçu dans un environnement de test.
  - Risque : erreurs silencieuses et absence de traces.
- **Action de publication du handover :** confirmer par review que les chemins, versions et dates issus des rapports historiques n'ont pas changé; aucun secret inclus.
- **Critère global avant affirmation « entièrement fonctionnel » :** preuves d'intégration des parcours principaux sur staging, migrations vérifiées, isolation cross-tenant, paiements sandbox, workers, backups/restores et observabilité. Ces critères ne sont pas atteints par la seule présence du code ou les tests ciblés rapportés ici.
