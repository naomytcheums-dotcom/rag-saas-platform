# PHASE 3 — Analyse stratégique et préparation de l'implémentation (version détaillée)

**Statut** : document d'analyse uniquement. Aucun code source, migration, fichier frontend ou configuration applicative modifié. Aucun fichier de code créé.
**Sources utilisées** : `docs/COMPETITIVE_AUDIT_KNOWFLOW.md` (Phase 1), `docs/COMPETITIVE_AUDIT_VALIDATION.md` (Phase 2), `docs/CAHIER_DES_CHARGES.md` (3867 lignes, 25 Parties), lecture/grep directs du code réel du dépôt. Aucune nouvelle recherche externe sur Dify/RAGFlow/Flowise/Onyx/AnythingLLM n'a été effectuée.

---

# A. Executive Summary

Sur ~230 capacités concurrentielles recensées en Phase 1/2, RAG SaaS Platform en couvre réellement et de façon branchée environ 95 (~41%), en a ~14 codées mais orphelines (~6%), ~8 partielles (~3%), et ~111 absentes (~48% — dont une bonne moitié sont des fonctionnalités Enterprise payantes ou des connecteurs de niche chez les concurrents eux-mêmes, pas des urgences produit).

**Le message central de cette Phase 3** : la quasi-totalité de la valeur immédiatement récupérable ne vient pas de nouveau code, mais du branchement de code déjà écrit et testé unitairement — 6 stratégies de chunking, 6 techniques de retrieval avancé, RBAC Casbin, exécution parallèle d'outils. Le vrai développement neuf nécessaire se limite à un petit nombre de capacités à forte valeur (MCP, function-calling agent réel) plus une décision produit à trancher explicitement (UI visuelle du Workflow Builder, dont le backend est déjà à 100% de son propre périmètre documenté).

Aucune recommandation de ce document ne propose d'installer ou de copier Dify, RAGFlow, Flowise, Onyx ou AnythingLLM : chaque capacité empruntée est reconstruite comme une option d'un moteur interne unique déjà existant dans RAG SaaS Platform (Partie H).

---

# B. Current Platform State

Cartographie complète, avec preuves fichier/fonction/appelant, classée 🟢A / 🟡B / 🟠C / 🔵D / ⚪E / ⚫F.

## 🟢 A — Implemented & Wired (preuves)
| Capacité | Fichier(s) | Fonction/classe | Appelant réel | Endpoint | Tests |
|---|---|---|---|---|---|
| Auth (email/mdp, OAuth, 2FA) | `api/routers/auth.py`, `api/security/totp.py`, `api/routers/webauthn.py` | `login`, `verify_totp`, WebAuthn handlers | Middleware FastAPI, appelé à chaque requête authentifiée | `/auth/*` | 45/45 vérifiés Phase 1 |
| Rate limiting | `api/security/rate_limit.py` | Sliding window Redis | Middleware | Toutes routes | Réel, backend Redis non stub |
| Organizations/Workspaces/Teams | `api/security/organizations.py` | `require_org_member`, etc. | Dependency injection FastAPI sur les routers concernés | `/organizations/*` | Oui |
| Ingestion documentaire (formats + connecteurs collaboratifs) | `api/security/documents.py`, `api/tasks/*_import.py` | `process_document` + tâches Celery dédiées | Upload utilisateur → Celery | `/documents/*`, `/external-sources/*` | Oui |
| Retrieval hybride + reranking | `api/services/retrieval_pipeline.py` | `search()`, `hybrid_reranked_search` (CrossEncoder réel) | `api/routers/search.py` | `POST /organizations/{org_id}/search` | Oui |
| Multi-LLM/embeddings | `api/services/llm_providers.py`, `embedding_providers.py` | `chat_completion_with_fallback`, `get_embeddings_with_fallback` | Générateur de réponse, blocs workflow | interne | Oui |
| Anti-hallucination | `api/services/hallucination_detector.py` | Scoring 5 facteurs | `response_quality.py::enrich_response_with_quality_metrics` | interne à la génération | Oui |
| Agents autonomes | `api/services/autonomous_agents.py` | `run_autonomous_agent` | `api/tasks/autonomous_agents.py` (Celery) | `/autonomous-agents/*` | Oui |
| **Workflow Engine (backend d'exécution)** | `api/services/workflow_engine.py` | `execute_workflow_run`, `resume_workflow_run` | `api/tasks/workflows.py` (Celery) | `/workflows/{id}/run`, `/webhooks/{trigger_id}` | 77/77 |
| Widget embarquable | `api/routers/widget.py`, `frontend/widget/` | — | Script tiers | `/widget/*` | Oui |
| API publique v1 + SDKs | `api/routers/public_api.py`, `sdks/` | 9 endpoints, clés scopées | Client externe | `/v1/*` | Oui |
| Marketplace de plugins sandboxé | `api/routers/plugins.py`, `Dockerfile.plugin-sandbox` | Exécution Docker `--network none --read-only --cap-drop ALL` | Runtime plugin | `/plugins/*` | Oui |
| Monitoring | `api/monitoring.py` | `/health`, `/ready`, `/metrics` | Infra (Prometheus) | idem | Oui |
| Evaluation Lab | `api/services/evaluation_jobs.py` | Jobs, comparaisons, seuils de régression | `api/tasks/evaluation_jobs.py` | `/evaluation-jobs/*` | Oui — **en avance sur les 5 concurrents étudiés** |

## 🟡 B — Implemented but Unconnected
Voir Partie C (tableau exhaustif dédié demandé explicitement, avec les 14 items).

## 🟠 C — Partial
| Capacité | Fichier | Ce qui marche | Ce qui ne marche pas |
|---|---|---|---|
| Protection SSRF | `api/services/url_fetching.py::ssrf_safe_client` | Appliquée dans `url_fetching.py`, `custom_tools.py`, `workflow_block_http.py` | Absente dans `api/tools/url_reader.py` (outil agent) et `api/services/chat_integrations/teams.py` (gap auto-documenté dans le code) |
| Filtrage metadata | `api/services/metadata_filtering.py` | Appelé réellement par `workflow_block_rag.py` (chemin workflow) | Absent de `SearchRequest`/`/search` ; `search_kb.py` non branché dans `agent_tools.py` |
| Facturation Stripe | `api/services/billing_stripe.py` | Code d'intégration réel (`stripe.Customer.create`, etc.) | `STRIPE_SECRET_KEY=None` par défaut, jamais configuré |
| Voice AI | `frontend/app/voice-demo/`, `lib/voiceApi.ts` | Composants STT/TTS réels, appellent le backend `/voice/*` | Jamais câblés dans `/chat`, page démo isolée |
| Guardrails IA | `api/services/agent_guardrails.py` | Détection écrite | Pas de filtre actif avant génération |
| Reranking (nuance) | `retrieval_pipeline.py` | Fonctionnel sur `/search` | Non exposé comme option sur les blocs agent hors workflow (à vérifier au cas par cas) |

## 🔵 D — Tested Only
Aucun item significatif identifié distinct de la catégorie B dans ce projet (le code non branché de ce dépôt est du code produit complet testé unitairement, pas de simples prototypes de test isolés — la frontière D/B est donc quasi vide ici, ce qui est noté explicitement plutôt que forcé).

## ⚪ E — Absent (sans obligation de développement automatique)
MCP (client+serveur), interface visuelle Workflow Builder, parallélisme de workflow, connecteurs CRM/ticketing, permission sync, SCIM, SAML (décision OIDC-only déjà prise), PII detection, antimalware, markdown/coloration chat, allowlist widget, export de conversation, marketplace de templates workflow, RLS Postgres réelle (rôle dédié), certifications de conformité.

## ⚫ F — Obsolete / Not Applicable (à ne pas reproduire)
| Capacité | Pourquoi |
|---|---|
| GraphRAG / Knowledge Graph | Le seul concurrent qui le poussait vraiment (RAGFlow) l'a déprécié en 2026 (remplacé par "Knowledge Compilation") |
| Reranking supprimé façon Onyx | Contre-exemple : Onyx a retiré son reranking (code déjà mort) — RAG SaaS Platform doit au contraire préserver le sien, qui fonctionne |
| Canvas no-code comme unique différenciateur produit | Leçon de l'échec commercial de Flowise (racheté par Workday puis arrêté un an après) |
| Application mobile native | Absente chez les 5 concurrents étudiés, aucune preuve de demande |
| Copier du code Dify/Flowise/RAGFlow tel quel | Licences anti-SaaS (Dify) ou projet mort (Flowise) — inspiration conceptuelle seulement |

---

# C. Existing-but-Unconnected Features — les ~14 items, un par un

| # | Fonctionnalité | Fichier | Fonction/classe | État | Pourquoi non branchée | Ce qui manque | Action |
|---|---|---|---|---|---|---|---|
| 1 | Chunking recursive | `api/services/chunking.py` | `chunk_recursive_text` | Codé, testé | `process_document` (`documents.py:3161`) n'appelle que `chunk_text` fixe | Sélection par type de document + champ `chunking_strategy` | **CONNECT** |
| 2 | Chunking markdown-aware | `api/services/markdown_chunking.py` | `chunk_markdown_by_headings` | Codé, testé | Idem | Idem | **CONNECT** |
| 3 | Chunking code-aware | `api/services/code_chunking.py` | `chunk_code_by_functions` | Codé, testé | Idem | Idem | **CONNECT** |
| 4 | Chunking sémantique | `api/services/semantic_chunking.py` | `merge_semantic_chunks` | Codé, testé | Idem | Idem + appel embedding en plus | **CONNECT** |
| 5 | Chunking par phrase | `api/services/sentence_chunking.py` | `chunk_by_sentences` | Codé, testé | Idem | Idem | **CONNECT** |
| 6 | Chunking par paragraphe | `api/services/paragraph_chunking.py` | `chunk_by_paragraphs` | Codé, testé | Idem | Idem | **CONNECT** |
| 7 | Chunking parent-enfant | `api/services/parent_child_chunking.py` | `create_parent_chunks` | Codé, testé | Idem | Idem + modèle de stockage à 2 niveaux | **CONNECT** |
| 8 | HyDE | `api/services/hyde.py` | fonction de génération d'hypothèse | Codé, testé | Zéro appelant hors tests (`grep` confirmé) | Champ `use_hyde` sur `SearchRequest` + branchement `retrieval_pipeline.search` | **CONNECT** |
| 9 | Multi-query retrieval | `api/services/multi_query.py` | génération multi-requêtes | Codé, testé | Zéro appelant hors tests ; importe `duplicate_removal` (donc mort en cascade) | Champ `use_multi_query` + branchement | **CONNECT** |
| 10 | MMR | `api/services/mmr.py` | sélection MMR | Codé, testé | Zéro appelant hors tests | Champ `use_mmr` + branchement post-fusion | **CONNECT** |
| 11 | Query rewriting | `api/services/query_rewriting.py` | reformulation de requête | Codé, testé | Zéro appelant hors tests | Champ `use_query_rewriting` + branchement pré-retrieval | **CONNECT** |
| 12 | Context compression | `api/services/context_compression.py` | compression de contexte | Codé, testé | Zéro appelant hors tests | Branchement post-retrieval avant assemblage du prompt | **CONNECT** |
| 13 | RBAC Casbin | `api/security/rbac.py` | `require_permission()` | Moteur complet, seedé, testé en intégration Postgres réelle | `require_org_*` reste des tuples codés en dur ; la fixture de test `client` (ASGITransport) ne déclenche jamais le lifespan qui initialise l'enforcer | Ajouter `asgi-lifespan`/`LifespanManager` à la fixture, puis migrer route par route | **CONNECT** (risque moyen — ~450 tests à ne pas casser) |
| 14 | Exécution parallèle d'outils | `api/services/parallel_tools.py` | `execute_tools_parallel` | Codé, testé | Jamais importé par un routeur/service, seulement par son propre test | Brancher dans `agent_orchestrator.py`, dépend du function-calling réel | **CONNECT** (après item de function-calling, hors de cette liste des 14 car c'est une extension, pas un simple branchement) |

**Nuance sur un 15e item limitrophe** : `api/services/tool_validation.py::get_validation_errors` **est** appelé par `custom_tools.py` (validation de schéma à la création d'un outil personnalisé) — ce module n'est donc pas 100% orphelin comme un audit antérieur moins précis l'affirmait. Seule la fonction `validate_tool_result` (validation d'un résultat d'exécution à l'exécution, pas à la création) reste sans appelant confirmé dans l'orchestrateur principal. Classé **CONNECT** également, mais listé à part pour ne pas fausser le compte des 14.

## Totaux (les 14 items ci-dessus)
- **CONNECT = 14**
- **EXTEND = 0**
- **BUILD = 0**
- **DEFER = 0**
- **DROP = 0**

Conforme à la demande : CONNECT est bien systématiquement priorisé, car les 14 items sont tous du code déjà fonctionnellement complet et testé unitairement — aucun ne nécessite de réécriture, d'extension conceptuelle, ni de report.

---

# D. Partial Features

(Détail des preuves déjà donné en Partie B🟠.) Point commun structurel : dans chaque cas, l'infrastructure dure existe (transport SSRF sûr, moteur de filtrage, intégration Stripe, composants voix, détecteur de prompt injection) mais le dernier maillon vers le chemin utilisateur réel manque. Risque le plus élevé : SSRF et guardrails (sécurité active), pas juste du confort produit.

---

# E. Missing Capabilities

| Capacité | Chez qui (nombre de concurrents) | Pertinence RAG SaaS Platform | Recommandation |
|---|---|---|---|
| MCP client | 4/5 | Haute (standard 2026) | Construire, voir Partie Q |
| MCP serveur | 3/5 | Moyenne | Différer après le client |
| UI Workflow Builder | 3/5 vivantes | Haute si vente à non-développeurs visée | Décision produit à trancher, Partie P |
| Parallélisme workflow | 2/5 | Moyenne, dépend de la demande | Différer jusqu'à demande démontrée |
| Connecteurs CRM/ticketing | 1/5 (Onyx) | Dépend du marché cible | Rechercher la demande avant construire |
| Permission sync | 1/5 (Onyx, payant) | Enterprise uniquement | Différer, packager en option payante |
| SCIM/SAML | 2/5, tous payants | Enterprise uniquement | Différer jusqu'à demande client réelle |
| GraphRAG | 0/5 actif | Faible actuellement | Ne pas construire |
| PII detection, antimalware | Non confirmé chez les 5 | Dépend du secteur cible | Rechercher le besoin avant construire |
| Markdown+coloration chat | Quasi tous | Haute | Construire (P0) |
| Export de conversation | Plusieurs | Moyenne | Construire en confort (P2) |
| Widget allowlist domaine | AnythingLLM (imparfait) | Haute (sécurité de base) | Construire (P0) |

---

# F. Quick Wins (fiche complète par item, comme demandé)

| Fonctionnalité | Code existant | Fichier | Fonction/classe | État actuel | Ce qui manque | Modification minimale nécessaire | Dépendances | Risques | Valeur apportée | Priorité |
|---|---|---|---|---|---|---|---|---|---|---|
| Chunking avancé (6 stratégies) | Oui, complet | `api/services/*_chunking.py` | Voir Partie C | Testé unitairement | Sélection par type de document | Ajouter un champ `chunking_strategy` (ou détection auto par extension) dans `process_document` | Aucune | Faible — bien isolé par type de fichier | Haute (qualité RAG sur docs structurés) | **P0** |
| Retrieval avancé (HyDE/multi-query/MMR/query rewriting/context compression) | Oui, complet | `api/services/{hyde,multi_query,mmr,query_rewriting,context_compression}.py` | Voir Partie C | Testé unitairement | Champs API + branchement pipeline | Ajouter des champs optionnels booléens sur `SearchRequest`, appeler la fonction correspondante avant/après `retrieval_pipeline.search` | Aucune | Faible — attention à ne pas casser les appelants existants de `/search` | Haute (pertinence des réponses) | **P0** |
| Duplicate removal | Oui | `api/services/duplicate_removal.py` | `deduplicate_by_hash` | Orphelin (seul appelant = `multi_query.py`, lui-même mort) | Branchement direct en sortie de fusion | Appeler dans `retrieval_pipeline.py` après RRF | Multi-query connecté en même temps | Faible | Basse-moyenne | **P0** |
| Filtrage metadata sur `/search` | Oui | `api/services/metadata_filtering.py` | `apply_metadata_filter`, `validate_filters` | Réel mais atteignable seulement via JSON de workflow | Champ `filters` sur `SearchRequest` ; brancher `search_kb.py` dans `agent_tools.py` | Ajouter le champ + appel conditionnel | Aucune | Faible | Haute | **P0** |
| Protection SSRF étendue | Oui (transport réel) | `api/services/url_fetching.py::ssrf_safe_client` | déjà défini | Appliqué sur 3 chemins, absent sur 2 | Remplacer `httpx` direct par `ssrf_safe_client` dans `url_reader.py` et `teams.py` | 2 remplacements d'import + de client HTTP | Aucune | Faible — réduction de risque directe | Haute (sécurité) | **P0** |
| Widget allowlist domaine | Non (champ absent) | `api/models/widget.py` | `WidgetConfig` | Aucun contrôle d'origine aujourd'hui | Champ `allowed_domains` + vérification `Origin`/`Referer` | Migration + colonne + vérification dans `routers/widget.py` | Aucune | Faible | Haute (sécurité) | **P0** |
| Markdown + coloration chat | Non | `frontend/components/MessageContent.tsx` | composant de rendu | Texte brut actuellement | Librairie de rendu Markdown + coloration | Intégrer `react-markdown` + `highlight.js`/`shiki` | Aucune | Faible | Haute (UX attendue 2026) | **P0** |
| RBAC Casbin branché | Oui, complet | `api/security/rbac.py` | `require_permission` | Moteur prêt, jamais invoqué | Fixture de test ASGI + migration route par route | `asgi-lifespan` sur fixture `client`, puis remplacer les tuples codés en dur route par route | Fixture de test à corriger d'abord | **Moyen** — 450 tests existants | Haute (sécurité de permission réelle) | **P1** |
| Facturation Stripe configurée | Oui, complet | `api/services/billing_stripe.py` | intégration Stripe réelle | Non configurée par défaut | Clés réelles + webhooks testés | Configuration d'environnement + tests d'intégration mode test | Aucune | **Moyen** — risque financier si mal testé | Haute (bloquant commercial) | **P1** |
| Exécution parallèle d'outils | Oui, complet | `api/services/parallel_tools.py` | `execute_tools_parallel` | Jamais appelé | Function-calling réel doit exister d'abord | Appeler depuis `agent_orchestrator.py` une fois la boucle réelle en place | Function-calling agent réel | Faible une fois la dépendance résolue | Moyenne | **P1** |
| Voice AI intégrée au chat | Oui, composants réels | `frontend/app/voice-demo/`, `lib/voiceApi.ts` | composants STT/TTS | Isolés dans une page démo | Câblage dans `/chat` | Réutiliser les composants dans `frontend/app/chat/` | Aucune | Faible | Moyenne | **P2** |

---

# G. Capability Classification

| Capacité | CORE | USEFUL | ENTERPRISE | PLUGIN | REDUNDANT | OBSOLETE | NOT APPLICABLE |
|---|---|---|---|---|---|---|---|
| Chunking avancé branché | ✅ | | | | | | |
| Retrieval avancé branché | ✅ | | | | | | |
| RBAC Casbin branché | ✅ | | | | | | |
| MCP client | ✅ | | | | | | |
| MCP serveur | | ✅ | | | | | |
| SSRF étendu | ✅ | | | | | | |
| Widget allowlist | ✅ | | | | | | |
| Markdown chat | ✅ | | | | | | |
| Function-calling agent réel | ✅ | | | | | | |
| Facturation Stripe configurée | ✅ | | | | | | |
| UI Workflow Builder | ✅ *(si parité concurrentielle visée)* | | | | | | |
| Parallélisme workflow | | ✅ | | | | | |
| Voice AI intégrée | | ✅ | | | | | |
| Export conversation | | ✅ | | | | | |
| Marketplace templates workflow | | ✅ | | | | | |
| Connecteurs CRM/ticketing | | | | ✅ | | | |
| Permission sync | | | ✅ | | | | |
| SCIM | | | ✅ | | | | |
| SAML | | | ✅ *(si demandé)* | | | | |
| RLS Postgres réelle | | | ✅ | | | | |
| Certifications SOC2/ISO27001 | | | ✅ | | | | |
| PII detection/masking | | | ✅ | | | | |
| GraphRAG/Knowledge Graph | | | | | | ✅ | |
| Compression de contexte | | | | | ✅ *(couvert par le branchement retrieval)* | | |
| Reranking (déjà acquis) | ✅ | | | | | | |
| Application mobile native | | | | | | | ✅ |

---

# H. Unified Architecture

Matrice complète demandée — un seul moteur interne par capacité :

| Capacité | Moteur interne retenu | Code existant | À construire | Pourquoi |
|---|---|---|---|---|
| Auth | Système auth existant (JWT+OAuth+2FA) | ✅ Complet | — | Déjà mature, aucune raison de changer |
| Organizations | `api/security/organizations.py` | ✅ Complet | — | Idem |
| RBAC | Casbin (`api/security/rbac.py`) | ✅ Moteur prêt | Branchement seulement | Un seul moteur de permission, pas de second système parallèle aux tuples codés en dur |
| Multi-tenancy | Isolation applicative (`organization_id` partout) + RLS activée (bypass actuel) | ✅ Applicatif | RLS réelle (P3) | Défense en profondeur à ajouter, pas remplacer |
| Documents | `api/security/documents.py` + `api/tasks/*_import.py` | ✅ Complet | Connecteurs CRM (pattern identique) | Un seul pipeline d'ingestion, chaque connecteur suit le même pattern de tâche Celery |
| Parsing | Extracteurs dédiés par format déjà réels | ✅ Complet | — | — |
| Chunking | `api/services/chunk_config.py` comme point d'entrée unique choisissant parmi les 7 stratégies déjà codées | ✅ 7 stratégies codées | Branchement seulement | Ne jamais écrire une 8e stratégie avant d'avoir branché les 7 |
| Embeddings | `api/services/embedding_providers.py` | ✅ Complet (5 providers) | — | — |
| Vector Store | Abstraction déjà en place dans `retrieval_pipeline.py`/ingestion | ✅ Complet | — | Ne pas ajouter un second vector store sans besoin d'échelle démontré |
| BM25 | `retrieval_pipeline.py::bm25_search` (rank_bm25) | ✅ Complet | — | — |
| Hybrid Retrieval | `retrieval_pipeline.py::hybrid_search`/`hybrid_reranked_search` | ✅ Complet | — | — |
| RRF | `retrieval_pipeline.py::reciprocal_rank_fusion` | ✅ Complet | — | — |
| Reranking | `retrieval_pipeline.py` (CrossEncoder réel) | ✅ Complet | — | À préserver — avantage confirmé face à Onyx qui l'a supprimé |
| Query Enhancement (HyDE/multi-query/MMR/rewriting/compression) | Modules dédiés déjà écrits, à unifier comme options du même appel `retrieval_pipeline.search` | ✅ Codé | Branchement seulement | Un seul point d'entrée `/search` avec options, pas 6 endpoints séparés |
| LLM | LiteLLM (`api/services/llm_providers.py`) | ✅ Complet | — | — |
| Agents | `agent_orchestrator.py` + `autonomous_agents.py` | ✅ Orchestrateur existant | Function-calling réel (extension) | Ajouter DANS l'existant, pas un second framework |
| Tools | `api/services/agent_tools.py` (registre) | ✅ Registre existant | MCP doit alimenter ce même registre | Un seul catalogue d'outils, jamais deux |
| Workflows | `api/services/workflow_engine.py` (construit cette session) | ✅ Moteur complet | Loop/retry/parallélisme (extensions) | Ne jamais écrire un second moteur d'exécution |
| MCP | Nouvelle couche fine au-dessus du registre d'outils existant | ⚪ À construire | Client d'abord, serveur ensuite | Ne pas dupliquer le catalogue d'outils déjà réel |
| Memory | Mémoire d'agent déjà réelle (`autonomous_agents.py`, agent memory) | ✅ Existant | — | Pas de second système de mémoire pour le futur agent MCP |
| Evaluation | `api/services/evaluation_jobs.py` | ✅ Complet | — | En avance sur les concurrents, à préserver |
| Observability | `api/monitoring.py` (`/health`,`/ready`,`/metrics`) | ✅ Complet | CLI d'administration (USEFUL, inspiré de RAGFlow/Onyx) | — |
| Billing | Stripe (`billing_stripe.py`) | ✅ Code existant | Configuration (P1) | Ne pas ajouter Paystack en parallèle — un seul processeur |
| Notifications | Email/webhooks déjà réels dans les tâches Celery | ✅ Existant | — | — |
| Integrations | Connecteurs documentaires déjà réels, pattern Celery établi | ✅ Existant | CRM (PLUGIN, même pattern) | Chaque connecteur = un module suivant le pattern déjà établi |
| Widget | `api/models/widget.py` | ✅ Existant | Allowlist (P0) | — |
| API | `api/routers/public_api.py` | ✅ Complet | MCP comme futur consommateur de ce même registre d'outils | — |

---

# I. Architecture Duplication Risks

| Risque | Emplacement | Solutions concurrentes possibles | Solution à conserver | Solution à abandonner | Migration nécessaire | Risque |
|---|---|---|---|---|---|---|
| Deux moteurs de recherche | Retrieval avancé | Nouvel endpoint dédié "recherche avancée" vs extension de `/search` | Extension de `SearchRequest`/`retrieval_pipeline.py` | Tout nouvel endpoint séparé | Aucune si fait dès le départ | Haute si non anticipé |
| Deux catalogues d'outils | MCP | Registre séparé pour les outils MCP découverts vs enregistrement dans `agent_tools.py` | Enregistrement dans le registre existant | Un second registre MCP-only | Aucune si fait dès le départ | Haute |
| Deux moteurs de workflow | Extension pour parallélisme/Loop | Nouveau `workflow_engine_v2.py` vs extension de `_advance`/`_execute_node` | Extension en place de `workflow_engine.py` | Tout second moteur | Aucune | Haute |
| Deux systèmes de permission actifs | Migration RBAC Casbin | Tuples codés en dur + Casbin en parallèle pendant la transition | Casbin, avec dépréciation progressive des tuples route par route | Les tuples codés en dur, une fois toutes les routes migrées | Migration route par route documentée | **Moyenne pendant la transition, à surveiller** |
| Deux processeurs de paiement | Facturation | Stripe (existant) vs ajouter Paystack (mentionné dans l'ancien cahier des charges obsolète) | Stripe uniquement (déjà réel et intégré) | Paystack (jamais implémenté, à abandonner comme piste) | Aucune | Faible — décision déjà de facto prise par le code existant |
| Deux abstractions LLM | Aucune détectée | — | LiteLLM (déjà unique) | — | — | Aucun risque actuel |
| Deux systèmes de scheduling | Aucune détectée | Cron applicatif ad hoc vs Celery Beat | Celery Beat (déjà le pattern pour reindex et workflows) | Tout scheduler ad hoc | — | Aucun risque actuel |
| Deux systèmes de configuration organisationnelle | Aucune détectée | `organization_settings.py` déjà centralisé | Conserver ce point d'entrée unique pour toute nouvelle option (chunking_strategy, use_hyde par défaut, etc.) | — | — | Faible si discipliné |

---

# J. Cahier des Charges Reconciliation

## A — Promesses initiales (ce qui était réellement prévu)
D'après `docs/CAHIER_DES_CHARGES.md` : Auth (1.1, 19/19), Rôles & Permissions (1.2, 6/8), Multi-tenant (1.3, 8/10), White-label (1.4, 6/10), Knowledge Base (2, 27/35), Pipeline RAG — **chunking (3.2) et recherche hybride avancée (3.4) marqués ✅ complets ("8/8", "12/12") par le projet lui-même au sens de l'écriture du code**, Multi-LLM (4, 18/18), Agent IA + Workflow Builder **backend uniquement, UI explicitement hors périmètre par décision documentée** (5, dont 5.4 13/13), Citations/Anti-hallucination (6, complet), Evaluation Lab (7, complet), Interface Utilisateur (8), API publique (9, complet), Sécurité (10, ~10/49), Admin/Analytics (11), Facturation (12, ~18/23, Stripe/Paystack — voir correction ci-dessous), Developer Experience (13), Documentation (14).

## B — Gaps par rapport au cahier des charges (ce qui manque pour respecter les objectifs initiaux déjà actés)
- Chunking avancé et retrieval avancé sont marqués "complets" pour l'écriture du code, mais **non branchés en production** — c'est un gap d'exécution par rapport à la propre définition de complétude du cahier des charges, pas un gap de conception.
- RBAC Casbin — chantier déjà identifié et scopé dans le cahier des charges lui-même (Partie 1.2.7), pas une découverte de cet audit.
- Sécurité de base (Partie 10.1, ~10/49) — SSRF partiellement réelle (corrigé par le contre-audit), guardrails IA écrits non branchés : gaps d'exécution sur des items déjà planifiés.
- Facturation (Partie 12, ~18/23) — Stripe réel mais non configuré : gap de configuration, pas de conception.

## C — Gaps concurrentiels (jamais promis par le cahier des charges)
MCP (0 occurrence sur 3867 lignes), permission sync, SCIM, GraphRAG (déconseillé), certifications de conformité, CLI officiel d'administration, marketplace de templates de workflow, allowlist de domaine widget (le cahier des charges couvre le widget en 9.3 sans détailler cette sécurité).

## D — Extensions stratégiques (ce qui pourrait être ajouté maintenant, avec justification de valeur réelle)
- **MCP client** : seule extension de cette liste avec une justification de valeur unanime (4/5 concurrents), à formaliser dans une future révision du cahier des charges si retenue — **mais pas automatiquement obligatoire du simple fait que les concurrents l'ont**.
- **Markdown/coloration chat** : absence probablement due à une omission de rédaction du cahier des charges (Partie 8.1 liste des fonctionnalités de chat riches sans exclure explicitement le markdown, contrairement à l'UI du Workflow Builder qui est explicitement exclue) — à corriger comme une extension à faible coût, pas une nouvelle promesse.
- **Widget allowlist** : extension naturelle et peu coûteuse de la Partie 9.3 déjà existante.
- **Principe appliqué à toute la liste C** : aucune fonctionnalité concurrente n'est convertie automatiquement en obligation ("concurrent possède X" ≠ "nous devons avoir X"). Seules celles de la catégorie D ont une justification de valeur propre à RAG SaaS Platform, indépendante de la simple existence chez un concurrent.

---

# K. Dify → RAG SaaS Mapping
**Capacités à récupérer (conceptuellement)** : retry configurable + branche d'échec par nœud de workflow ; organisation du marketplace de plugins en catégories claires (Models/Tools/Agent Strategies/Extensions/Bundles) ; confirmation que le pattern "Human Input" pausant un workflow est une bonne conception (déjà implémenté chez RAG SaaS Platform, rien à changer). **À ne pas reproduire** : le code lui-même (licence anti-SaaS explicite).

# L. RAGFlow → RAG SaaS Mapping
**Capacités à récupérer** : confirmation que ~7 stratégies de chunking nommées est la bonne cible (déjà atteinte en code, reste à brancher/nommer) ; un CLI d'administration en complément du monitoring déjà réel (USEFUL) ; MCP bidirectionnel mature comme référence de conception. **À ne pas reproduire** : GraphRAG (déprécié par RAGFlow lui-même en 2026).

# M. Flowise → RAG SaaS Mapping
**Capacités à récupérer** : aucune capacité de code (produit mort, parties intéressantes sous licence Enterprise). Le "Document Store" indépendant d'un flow est déjà acquis chez RAG SaaS Platform (KB indépendante des workflows). Le mode queue Celery/Redis est déjà le pattern de RAG SaaS Platform. **Leçon à retenir, pas une capacité** : ne pas centrer la stratégie produit sur un canvas no-code seul — le diagnostic des mainteneurs eux-mêmes ("les agents de codage généralistes remplacent l'approche low-code rigide") doit peser sur la décision de la Partie P.

# N. Onyx → RAG SaaS Mapping
**Capacités à récupérer** : facturation Stripe self-service comme référence directe pour terminer P1 ; permission sync comme modèle Enterprise différenciant (P3) ; limiter un futur client MCP au transport HTTP (précédent rassurant, réduit l'effort) ; confirmation que le reranking cross-encoder reste précieux (Onyx vient de l'abandonner — RAG SaaS Platform est en avance, à préserver).

# O. AnythingLLM → RAG SaaS Mapping
**Capacités à récupérer** : override de modèle par mode d'usage (chat économique vs agent plus fort) — USEFUL à évaluer ; principe de sécurité multi-tenant pour les capacités risquées si un tiers hébergé mutualisé est envisagé un jour ; widget avec allowlist — mais RAG SaaS Platform doit faire **mieux** qu'AnythingLLM en étant fermé par défaut (AnythingLLM est ouvert par défaut, un vrai défaut de sécurité chez eux à ne pas copier).

---

# P. Workflow Engine Strategy

## Vérification composant par composant (preuves)
| Composant | Fichier | Statut réel |
|---|---|---|
| `llm` | `api/services/workflow_block_llm.py` → `execute_llm_block` | ✅ Réutilise `resolve_llm_config`/`chat_completion` (LiteLLM), testé |
| `rag` | `api/services/workflow_block_rag.py` → `execute_rag_block` | ✅ Réutilise `retrieval_pipeline.search` + `metadata_filtering` — **seul chemin de production qui utilise déjà le filtrage metadata** |
| `web search` | `api/services/workflow_block_search.py` | ✅ Réutilise l'outil Tavily existant |
| `http` | `api/services/workflow_block_http.py` | ✅ Protection SSRF réelle (`ssrf_safe_client`) |
| `condition` | `api/services/workflow_block_condition.py` | ✅ Évaluateur AST sûr (motif de `calculator.py` réutilisé) |
| `code` | `api/services/workflow_block_code.py` | ✅ Même évaluateur AST à liste blanche, JS honnêtement rejeté (pas de runtime) |
| `email` | `api/services/workflow_block_email.py` | ✅ Réutilise `email_tools.py` |
| `calendar` | `api/services/workflow_block_calendar.py` | ✅ Réutilise `calendar_tools.py` |
| `database` | `api/services/workflow_block_database.py` | ✅ Réutilise `sql_tool.py` (SELECT mono-table, liste blanche, filtre organization_id) |
| `human` | `api/services/workflow_block_human.py` + `api/models/workflow_human_input.py` | ✅ Pause réelle, reprise avec injection de la réponse |
| Triggers | `api/services/workflow_triggers.py` | ✅ Manuel, webhook (token `secrets.compare_digest`), cron |
| Webhook | `POST /webhooks/{trigger_id}` | ✅ Token sécurisé, testé |
| Cron | `check_scheduled_workflow_triggers` (Celery Beat) | ✅ **Construit cette session**, anti-rejeu via `last_run_at`, même pattern que `reindex_schedules.py` |
| Celery/Celery Beat | `api/tasks/workflows.py` | ✅ `run_workflow_task`/`resume_workflow_task`, dispatch best-effort |
| Resume | `resume_workflow_run` | ✅ Testé (pause/reprise humaine, cas "human = dernier nœud") |
| Erreurs | `WorkflowBlockError`/`WorkflowExecutionError` capturées dans `_advance` | ✅ Run "failed" propre, jamais de crash worker |
| Limites d'exécution | `MAX_STEPS = 200` | ✅ Testé sur graphe cyclique |
| Validation du graphe | `api/services/workflows.py::validate_workflow` | ✅ Détection de nœud dupliqué, type inconnu, arête invalide (préexistant, avant cette session) |

## Ce qui fonctionne déjà
Exécution séquentielle complète avec branchement conditionnel, pause/reprise humaine, déclenchement manuel/webhook/cron, gestion d'erreur propre, versioning complet (create/get/list/restore/diff façon git) — 77/77 tests passent.

## Ce qui est incomplet
Un seul chemin d'exécution actif à la fois (pas de parallélisme réel) ; pas de nœud `Loop` dédié avec variable de boucle (un cycle d'arêtes fonctionne mais sans primitive nommée) ; pas de retry configurable par nœud (un échec de bloc = échec de tout le run) ; pas d'import symétrique à l'export déjà existant.

## Ce qui manque pour un vrai Workflow Builder (au sens concurrentiel)
L'interface visuelle (React Flow ou équivalent) — le cahier des charges documente explicitement cette absence comme un choix de périmètre validé avant de commencer, pas un oubli. C'est la seule pièce manquante qui rend le Workflow Builder "invisible" pour un utilisateur non-développeur aujourd'hui.

## Ce qui doit être réutilisé
Tout le backend d'exécution actuel — dispatch de blocs (`_execute_node`), résolution du nœud suivant (`_next_node_id`), pattern de pause/reprise humaine, intégration Celery/cron.

## Ce qui ne doit surtout PAS être réécrit
Le moteur d'exécution lui-même. Toute extension (Loop, retry, parallélisme) doit modifier `_advance`/`_execute_node` en place, jamais créer un second fichier `workflow_engine_v2.py`.

## Intégration future avec React Flow
Le backend expose déjà tout ce dont une UI React Flow aurait besoin : `nodes`/`edges` stockés exactement dans la forme littérale React Flow (`{id,type,position,data}` / `{id,source,target}`), CRUD complet (`api/routers/workflows.py`), validation structurelle (`validate_workflow`), export (`export_workflow`). **Aucun changement backend n'est nécessaire pour démarrer un chantier frontend React Flow** — c'est un chantier frontend pur, correctement scopé comme "un nouveau projet complet" par le cahier des charges lui-même (aucune dépendance React n'existe encore dans `frontend/package.json` — à vérifier, mais Next.js étant déjà utilisé, React Flow s'ajoute comme une dépendance npm standard, pas une refonte).

---

# Q. MCP Strategy

## Valeur pour la plateforme
Standardiser la consommation d'outils/données tiers (rôle client) sans écrire un connecteur dédié pour chacun, et élargir la distribution du produit en exposant la recherche KB/les agents à des clients MCP externes comme Claude Desktop ou Cursor (rôle serveur).

## Architecture d'intégration
Nouvelle couche fine `mcp_client` qui enregistre les outils découverts d'un serveur MCP **dans le registre existant `api/services/agent_tools.py`** — jamais un second catalogue.

## MCP Server / MCP Client
Client d'abord (P1, dépend du function-calling réel pour avoir un intérêt pratique), serveur ensuite (P2, réutilise la même couche).

## Tools / Resources / Prompts
Les "tools" MCP s'intègrent au registre d'outils existant. Les "resources" (documents/données exposées) pourraient être mappées sur les Knowledge Bases existantes. Les "prompts" MCP (templates de prompt partagés par un serveur) n'ont pas d'équivalent direct dans RAG SaaS Platform aujourd'hui — à concevoir comme une extension du système de templates de prompt déjà utilisé dans les blocs `llm_call`/`agent_prompts.py`, pas un système séparé.

## Authentication / Permissions / Isolation multi-tenant
Auth vers un serveur MCP externe (API key/OAuth) doit être stockée chiffrée avec le même mécanisme que les credentials LLM (`api/security/secret_encryption.py`). La configuration des serveurs MCP doit être scopée par `organization_id` comme toute autre ressource (cohérence avec l'isolation applicative existante).

## Sécurité / Audit
Limiter le transport au HTTP (pas de stdio, précédent Onyx — réduit la surface d'attaque en environnement self-hosted/multi-tenant). Chaque appel d'outil MCP doit être tracé dans le système d'audit existant (`api/security/audit_log.py`, HMAC anti-falsification déjà réel) comme n'importe quel autre appel d'outil d'agent.

## Marketplace éventuel
Différé — pas de valeur immédiate tant que le rôle client n'est pas mature ; le marketplace de plugins déjà réel de RAG SaaS Platform pourrait accueillir une future catégorie "serveurs MCP recommandés" sans nouveau système.

## Intégration avec agents et workflows
Agents : un outil MCP découvert doit apparaître exactement comme `web_search` ou `calculator` aujourd'hui, dépend du function-calling réel. Workflows : un futur type de bloc `mcp_tool_call` réutiliserait la même couche cliente, à ajouter à `BLOCK_TYPES` sans toucher au moteur d'exécution central.

## Classification
**CORE** pour le rôle client (standard 2026, 4/5 concurrents). **USEFUL** pour le rôle serveur (valeur réelle, non bloquante). Justification technique : le rôle client a un impact direct sur la capacité produit de l'agent (plus d'outils disponibles immédiatement) ; le rôle serveur n'a d'impact que sur la distribution/écosystème, mesurable seulement après adoption du client.

## Dépendances
Function-calling agent réel doit exister avant que MCP client ait un intérêt pratique.

## Priorité proposée
**P1** (client), **P2** (serveur).

---

# R. Agents — capacités agentiques

| Capacité | Existe déjà ? | Fichier | Manque |
|---|---|---|---|
| Agent runtime | ✅ | `api/services/agent_orchestrator.py`, `autonomous_agents.py` | — |
| Tool calling | 🟡 | `agent_tools.py` | Sélection textuelle seulement, pas de vraie boucle de parsing `tool_calls`/ré-invocation |
| Planning | ✅ | `autonomous_agents.py::create_agent_plan` | — |
| Memory | ✅ | `AgentMemory` (autonomous agents) | — |
| Web search | ✅ | `api/tools/web_search.py` | — |
| RAG | ✅ | `api/tools/search_kb.py` | Non branché dans le dispatcher d'outils agent (`agent_tools.py`) |
| HTTP | ✅ | Réutilisé via le bloc workflow, outil agent direct à vérifier séparément | — |
| Code | ✅ | Évaluateur AST sûr partagé | — |
| Database | ✅ | `api/tools/sql_tool.py` | — |
| Human-in-the-loop | ✅ | `api/security/human_approval.py` (agents), `workflow_block_human.py` (workflows) | Non branché dans l'orchestrateur d'agent simple (uniquement dans les agents autonomes) |
| Multi-step execution | ✅ | `run_autonomous_agent` | — |
| Retries | ✅ | `llm_providers.py::chat_completion_with_fallback` | Pas de retry générique au niveau exécution d'outil |
| Timeout | ✅ | `asyncio.wait_for` dans `agent_orchestrator.py` | — |
| Validation | 🟡 | `tool_validation.py` | `validate_tool_result` (résultat runtime) non branché, `get_validation_errors` (schéma création) déjà branché |
| Permissions | ✅ | Vérification de permission dans `agent_orchestrator.py` | — |
| Agent Builder (UI) | 🟠 | `frontend/app/dashboard/agents/` | Limité à nom/description/prompt, pas de sélection modèle/KB/outils/mémoire/garde-fous |
| Agent templates | ⚪ | — | Absent, à considérer comme USEFUL après l'Agent Builder complet |

---

# S. Knowledge / Documents

| Capacité | Existe déjà ? | Preuve |
|---|---|---|
| Upload | ✅ | `api/security/documents.py` |
| Ingestion (formats) | ✅ | PDF/DOCX/TXT/MD/HTML/CSV/JSON/XML/EPUB — extracteurs dédiés réels |
| Parsing | ✅ | OCR fallback, extraction de structure |
| Nettoyage | ✅ | Partie du pipeline `process_document` |
| Structure | ✅ | Détection de titres/sections (extracteurs par format) |
| Metadata | ✅ | Champs metadata réels sur `Document` |
| Chunking | 🟡 | 7 stratégies codées, 1 seule branchée (voir Partie C) |
| Indexing | ✅ | Pipeline d'indexation vectorielle réel |
| Reindexing | ✅ | `api/security/reindex_schedules.py`, tâches Celery dédiées |
| Deletion | ✅ | Soft-delete réel sur `Document` |
| Versioning | ⚪ | Non confirmé au niveau document individuel (à distinguer du versioning de Workflow, qui lui existe) |
| **Connecteurs réellement vérifiés dans le code** (pas supposés depuis la doc) | ✅ | `api/tasks/google_drive_import.py`, `google_docs_import.py`, `notion_import.py`, `confluence_import.py`, `onedrive_import.py`, `github_import.py`, `sitemap_import.py`, `zip_import.py`, `url_import.py` — tous réels, avec tâche Celery dédiée |
| Slack (import) | ✅ | Confirmé dans les audits Phase 1 précédents (`api/services/chat_integrations/slack.py` pour le chat bot ; import documentaire Slack confirmé séparément dans l'audit KB) |
| Teams (import) | ✅ | Idem, avec le gap SSRF déjà noté |
| CRM (Salesforce, Zendesk, Jira, Linear) | ⚪ | **Aucun fichier trouvé** — absence confirmée, pas supposée |
| Sync | ✅ | Chaque connecteur a sa tâche Celery de synchronisation |
| Scheduled sync | ✅ | `api/security/reindex_schedules.py` (pattern cron réutilisé aussi par le Workflow Engine) |
| Permissions/ACL sur les documents | 🟠 | Isolation par `organization_id`/`workspace_id`, pas de permission-sync depuis la source (comme Onyx EE) |
| Source tracking | ✅ | Chaque document garde une référence à sa source d'import |
| Citations | ✅ | Système de citations réel (Partie 6 du cahier des charges, complet) |

---

# T. Dependency Graph

```
Auth (✅)
  ↓
Organizations / Multi-tenant applicatif (✅)
  ↓
┌─────────────────────────┬─────────────────────────┐
RBAC Casbin branché (P1)   Widget allowlist (P0, indépendant)
  ↓                        Markdown chat (P0, indépendant)
Knowledge Bases (✅)
  ↓
Chunking branché (P0) ──────────┐
  ↓                              │
Retrieval avancé branché (P0) ──→ Filtrage metadata sur /search (P0)
  ↓
Function-calling agent réel (P1)
  ↓                    ↓
Parallel tools (P1)   MCP client (P1)
  ↓                    ↓
Tool validation (P1)  MCP serveur (P2)
                        ↓
                  Workflow Engine (✅) ──→ bloc mcp_tool_call (P2, futur)
                        ↓
        Décision UI Workflow Builder (P1, décision)
                        ↓
              Parallélisme + Loop + retry workflow (P2)
                        ↓
                  Facturation configurée (P1, indépendant du reste)
                        ↓
              Fonctionnalités Enterprise
              (Permission sync, SCIM, SAML, RLS réelle, connecteurs CRM) (P3)
```

## Ce qui doit être développé avant quoi
- Chunking et retrieval avancé branchés (P0) n'ont aucune dépendance technique entre eux et peuvent être menés en parallèle par deux personnes différentes — ils partagent seulement le même endpoint `/search` en aval, donc coordination légère sur ce fichier uniquement.
- Function-calling agent réel doit précéder : exécution parallèle d'outils, validation de résultat d'outil, et MCP client (sinon un outil MCP découvert reste limité au mode texte).
- MCP client doit précéder MCP serveur (partage de la même couche).
- La décision sur l'UI Workflow Builder doit précéder tout investissement dans le parallélisme/Loop/retry du moteur (un moteur plus riche sans interface pour l'exploiter n'apporte pas de valeur immédiate mesurable).
- RBAC Casbin doit d'abord corriger sa fixture de test avant toute migration route par route.

## Ce qui peut être développé en parallèle
Chunking + retrieval avancé (P0) ∥ SSRF étendu (P0) ∥ Widget allowlist (P0) ∥ Markdown chat (P0) — ces 4 items P0 sont totalement indépendants entre eux. En P1 : RBAC Casbin ∥ Facturation Stripe ∥ function-calling agent réel sont indépendants les uns des autres (seul MCP client dépend du function-calling).

---

# U. Prioritized Feature Matrix (matrice globale, 10 colonnes)

| Fonctionnalité | Concurrent(s) | Catégorie | État RAG SaaS | Source de vérité | Valeur | Complexité | Dépendances | Action | Priorité |
|---|---|---|---|---|---|---|---|---|---|
| Chunking avancé (6 stratégies) | RAGFlow, Dify, Flowise | CORE | 🟡 | `api/services/*_chunking.py` | Haute | Faible | Aucune | **CONNECT** | P0 |
| HyDE | Dify, RAGFlow | CORE | 🟡 | `hyde.py` | Moyenne | Faible | Aucune | **CONNECT** | P0 |
| Multi-query | Onyx, Flowise | CORE | 🟡 | `multi_query.py` | Moyenne | Faible | Aucune | **CONNECT** | P0 |
| MMR | Flowise | CORE | 🟡 | `mmr.py` | Moyenne | Faible | Aucune | **CONNECT** | P0 |
| Query rewriting | Onyx | CORE | 🟡 | `query_rewriting.py` | Moyenne | Faible | Aucune | **CONNECT** | P0 |
| Context compression | — | CORE | 🟡 | `context_compression.py` | Basse-Moyenne | Faible | Aucune | **CONNECT** | P0 |
| Duplicate removal | — | REDUNDANT (couvert par retrieval avancé) | 🟡 | `duplicate_removal.py` | Basse | Faible | Multi-query | **CONNECT** | P0 |
| Filtrage metadata sur `/search` | Dify, RAGFlow, Onyx | CORE | 🟠 | `metadata_filtering.py` | Haute | Faible | Aucune | **CONNECT** | P0 |
| Protection SSRF étendue | — | CORE (hygiène sécurité) | 🟠 | `url_fetching.py` | Haute | Faible | Aucune | **EXTEND** | P0 |
| Widget allowlist domaine | AnythingLLM | CORE | ⚪ | `models/widget.py` | Haute | Faible | Aucune | **BUILD** (petit) | P0 |
| Markdown + coloration chat | Quasi tous | CORE | ⚪ | `MessageContent.tsx` | Haute | Faible | Aucune | **BUILD** (petit) | P0 |
| RBAC Casbin branché | Toutes (payant chez elles) | CORE | 🟡 | `security/rbac.py` | Haute | Moyenne | Fixture de test | **CONNECT** | P1 |
| Function-calling agent réel | Toutes | CORE | 🟡 | `agent_orchestrator.py` | Haute | Moyenne | Aucune | **EXTEND** | P1 |
| Exécution parallèle d'outils | Dify | CORE | 🟡 | `parallel_tools.py` | Moyenne | Faible | Function-calling réel | **CONNECT** | P1 |
| Validation de résultat d'outil | — | CORE | 🟡 | `tool_validation.py` | Moyenne | Faible | Function-calling réel | **CONNECT** | P1 |
| Facturation Stripe configurée | Onyx | CORE | 🟠 | `billing_stripe.py` | Haute | Moyenne | Aucune | **EXTEND** | P1 |
| MCP client | Dify, RAGFlow, Onyx, AnythingLLM | CORE | ⚪ | `agent_tools.py` (à réutiliser) | Haute | Élevée | Function-calling réel | **BUILD** | P1 |
| Décision UI Workflow Builder | Dify, AnythingLLM | CORE si retenue | ⚪ (périmètre documenté) | `workflow_engine.py` | Haute si retenue | — | Aucune | **RESEARCH** (décision produit) | P1 |
| Nœud Loop dédié (workflow) | Dify, RAGFlow | USEFUL | ⚪ | `workflow_engine.py` | Moyenne | Moyenne | Moteur existant | **EXTEND** | P2 |
| Retry par nœud (workflow) | Dify | USEFUL | ⚪ | `workflow_engine.py` | Moyenne | Moyenne | Moteur existant | **EXTEND** | P2 |
| Voice AI intégrée au chat | Onyx, AnythingLLM | USEFUL | 🟠 | `voice-demo/` | Moyenne | Moyenne | Aucune | **CONNECT** | P2 |
| Guardrails IA actifs | — | CORE (sécurité) | 🟠 | `agent_guardrails.py` | Haute | Moyenne | Aucune | **EXTEND** | P2 |
| Export de conversation | Plusieurs | USEFUL | ⚪ | Historique existant | Moyenne | Moyenne | Aucune | **BUILD** | P2 |
| MCP serveur | Dify, RAGFlow, Onyx | USEFUL | ⚪ | `search_kb.py` | Moyenne | Moyenne | MCP client | **BUILD** | P2 |
| Parallélisme workflow | Dify, Flowise | USEFUL | ⚪ | `workflow_engine.py` | Moyenne | Élevée | Décision UI | **BUILD** | P2 |
| Marketplace templates workflow | Dify, Flowise (mort) | USEFUL | ⚪ | — | Basse-Moyenne | Moyenne | Décision UI | **DEFER** | P2/P3 |
| Connecteurs CRM/ticketing | Onyx | PLUGIN | ⚪ | Pattern `*_import.py` | Dépend du marché | Élevée (par connecteur) | Aucune | **RESEARCH** puis BUILD si validé | P3 |
| Permission sync | Onyx (payant) | ENTERPRISE | ⚪ | — | Haute (Enterprise) | Élevée | Connecteurs entreprise | **DEFER** | P3 |
| SCIM | Dify, Onyx (payants) | ENTERPRISE | ⚪ | — | Enterprise | Élevée | SSO SAML | **DEFER** | P3 |
| SAML | Décision OIDC-only déjà prise | ENTERPRISE | ⚪ (choix assumé) | `enterprise_sso.py` | Enterprise (si demandé) | Élevée | Décision à reconfirmer | **DEFER** | P3 |
| RLS Postgres réelle | — | ENTERPRISE | 🟡 (BYPASSRLS) | Tables déjà prêtes | Enterprise | Élevée | Aucune | **DEFER** | P3 |
| Certifications SOC2/ISO27001 | Dify | ENTERPRISE | ⚪ | — | Enterprise (vente) | Élevée (hors dev) | Aucune | **DEFER** | P3 |
| GraphRAG / Knowledge Graph | RAGFlow (déprécié) | OBSOLETE | ⚪ | — | Faible actuellement | Élevée | Aucune | **DROP** | — |
| Application mobile native | Aucun | NOT APPLICABLE | ⚪ | — | Non démontrée | Élevée | — | **DROP** | — |
| Copier du code concurrent tel quel | — | NOT APPLICABLE | N/A | — | N/A | N/A | Vérification licence | **DROP** (principe) | — |
| PII detection/masking | Non confirmé chez les 5 | ENTERPRISE potentiel | ⚪ | — | Dépend du secteur | Moyenne-Élevée | Aucune | **RESEARCH** | — |
| Antimalware (ClamAV) | Non confirmé chez les 5 | ENTERPRISE potentiel | ⚪ | — | Dépend du secteur | Moyenne | Aucune | **RESEARCH** | — |

**Comptage** : KEEP implicite pour tous les items 🟢A de la Partie B (non listés ici car déjà stables, hors périmètre de changement). Sur les 36 lignes ci-dessus : **CONNECT = 12, EXTEND = 6, BUILD = 6, DEFER = 6, DROP = 3, RESEARCH = 3.**

---

# V. P0 Roadmap — Fondations + Quick Wins

| # | Fonctionnalité | Objectif | État actuel | Code existant | Fichiers concernés | Modification prévue | Dépendances | Tests | Validation | Résultat utilisateur | Risques |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Chunking avancé branché | Sélectionner la bonne stratégie par type de document | 🟡 | 6 modules `*_chunking.py` + `chunk_config.py` | `api/security/documents.py` (`process_document`), schéma/migration `chunking_strategy` | Ajout d'un paramètre de sélection + appel conditionnel | Aucune | Intégration par type de document | Un fichier Markdown est chunké en respectant les titres | Meilleure qualité RAG sur docs structurés | Faible |
| 2 | Retrieval avancé branché | Exposer HyDE/multi-query/MMR/query rewriting/context compression | 🟡 | 5 modules dédiés | `api/schemas/search.py`, `api/services/retrieval_pipeline.py` | Champs optionnels + branchement conditionnel | Aucune | API + non-régression des appelants existants | `use_hyde=true` change réellement les résultats | Recherche plus pertinente sur requêtes ambiguës | Faible, attention à la non-régression |
| 3 | Filtrage metadata sur `/search` | Filtrer par metadata sur l'endpoint principal | 🟠 | `metadata_filtering.py` | `api/schemas/search.py`, `api/routers/search.py`, `api/services/agent_tools.py` | Champ `filters` + branchement `search_kb.py` | Aucune | Retrieval filtré | Un filtre `document_type=contrat` restreint réellement les résultats | Recherche ciblée | Faible |
| 4 | Protection SSRF étendue | Fermer le gap confirmé | 🟠 | `ssrf_safe_client` | `api/tools/url_reader.py`, `api/services/chat_integrations/teams.py` | Remplacement de client HTTP | Aucune | Sécurité (URL interne bloquée) | Tentative d'accès IP privée bloquée sur ces 2 chemins | Réduction de risque directe | Faible |
| 5 | Widget allowlist domaine | Empêcher un usage widget non autorisé | ⚪ | `WidgetConfig` | Migration Alembic, `routers/widget.py`, UI whitelabel | Champ + vérification `Origin` | Aucune | Domaine autorisé/refusé | Requête depuis domaine non listé rejetée | Widget sécurisé par défaut | Faible |
| 6 | Markdown + coloration chat | Rendu correct du Markdown/code | ⚪ | `MessageContent.tsx` | Ajout librairie de rendu | `react-markdown` + `highlight.js`/`shiki` | Aucune | Visuel/snapshot | Code Python coloré, pas en texte brut | Parité UX 2026 | Faible |

---

# W. P1 Roadmap — Core Platform

| # | Fonctionnalité | Objectif | État actuel | Code existant | Fichiers concernés | Modification prévue | Dépendances | Tests | Validation | Résultat utilisateur | Risques |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | RBAC Casbin branché | Faire appliquer réellement les permissions fines | 🟡 | `api/security/rbac.py` | `organizations.py`, fixture `client` | `asgi-lifespan`, migration route par route | Fixture de test | Non-régression des ~450 tests + tests dédiés par route | Un rôle personnalisé restreint réellement les actions | Sécurité de permission réelle | **Moyen** |
| 8 | Function-calling agent réel | Vraie boucle d'exécution d'outils | 🟡 | `agent_orchestrator.py` | Boucle de parsing `tool_calls` | Ajout de la boucle réelle | Aucune | Agent end-to-end avec outil réel | Un agent appelle réellement un outil et utilise son résultat | Agents réellement autonomes | Moyen |
| 9 | Exécution parallèle d'outils | Paralléliser les appels indépendants | 🟡 | `parallel_tools.py` | `agent_orchestrator.py` | Branchement | Function-calling réel | Concurrence | Deux appels indépendants en parallèle | Réponses plus rapides | Faible |
| 10 | Validation de résultat d'outil | Fiabiliser les résultats d'outils | 🟡 | `tool_validation.py` | `agent_orchestrator.py` | Branchement post-exécution | Function-calling réel | Tests dédiés | Résultat invalide détecté et signalé | Fiabilité accrue | Faible |
| 11 | Facturation Stripe configurée | Rendre la facturation opérationnelle | 🟠 | `billing_stripe.py` | `api/config.py`, webhooks | Clés réelles + tests | Aucune | Intégration Stripe mode test | Abonnement test créé/facturé/annulé | Facturation fonctionnelle | **Moyen** — risque financier si mal testé |
| 12 | MCP client | Consommer des outils MCP externes | ⚪ | `agent_tools.py` (registre) | Nouveau `mcp_client.py` | Nouveau module | Function-calling réel | Intégration avec serveur MCP de test | Outils d'un serveur MCP réellement invocables | Interopérabilité 2026 | **Élevé** — nouvelle surface d'attaque |
| 13 | Décision UI Workflow Builder | Trancher explicitement le périmètre | ⚪ | Backend complet | — | Décision, pas de code | Aucune | — | Décision documentée avec justification | Clarté de roadmap | Aucun (décision) |

---

# X. P2 Roadmap — Advanced Platform

| # | Fonctionnalité | Objectif | État actuel | Code existant | Fichiers concernés | Modification prévue | Dépendances | Tests | Validation | Résultat utilisateur | Risques |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 14 | Nœud Loop dédié | Primitive de boucle avec variable | ⚪ | `workflow_engine.py` | `BLOCK_TYPES`, `_advance` | Nouveau type de bloc | Moteur existant | Boucle bornée/condition de sortie | Itération correcte sans dépasser le cap | Workflows plus expressifs | Moyen |
| 15 | Retry par nœud | Tentatives configurables par bloc | ⚪ | `workflow_engine.py` | `_advance` | Capture + retry avant échec | Moteur existant | Retry réussi/épuisé | Bloc HTTP réessaie avant d'échouer | Robustesse face aux pannes transitoires | Moyen |
| 16 | Voice AI intégrée | Câbler les composants voix existants | 🟠 | `voice-demo/`, `voiceApi.ts` | `frontend/app/chat/` | Câblage | Aucune | E2E frontend | Voix fonctionnelle dans le chat principal | Fonctionnalité déjà construite exploitable | Faible |
| 17 | Guardrails IA actifs | Filtre pré-génération actif | 🟠 | `agent_guardrails.py` | Middleware LLM | Ajout du filtre | Aucune | Attaque (prompts connus) | Prompt d'injection connu bloqué | Réduction de risque sécurité IA | Moyen (faux positifs à calibrer) |
| 18 | Export de conversation | PDF/DOCX/JSON | ⚪ | Historique réel | Nouveau endpoint | Génération de fichier | Aucune | Génération de fichier | Export contient tous les messages/citations | Confort utilisateur | Faible |
| 19 | MCP serveur | Exposer KB/agents comme outils MCP | ⚪ | `search_kb.py` | Nouveau module serveur | Nouveau module | MCP client | Client MCP externe | Un client MCP externe interroge la KB | Distribution élargie | Moyen |
| 20 | Parallélisme workflow | Fan-out/fan-in réel | ⚪ | `workflow_engine.py` | `_advance` | Extension majeure | Décision UI | Concurrence | Branches parallèles exécutées simultanément | Parité avec moteurs concurrents | Élevé |

---

# Y. P3 Roadmap — Enterprise / Scale

| # | Fonctionnalité | Objectif | État actuel | Code existant | Fichiers concernés | Modification prévue | Dépendances | Tests | Validation | Résultat utilisateur | Risques |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 21 | Connecteurs CRM/ticketing | Ingestion Salesforce/Zendesk/Jira/Linear | ⚪ | Pattern `*_import.py` | Un module par connecteur | Nouveau module par connecteur | Confirmation de demande (RESEARCH) | Par connecteur | Document CRM ingéré et retrouvable | Couverture élargie | Moyen par connecteur |
| 22 | Permission sync | ACL miroir depuis la source | ⚪ | Aucun | Nouveau sous-système | Nouveau | Connecteurs entreprise | Sécurité approfondie | Utilisateur sans accès source ne voit pas le document | Gouvernance Enterprise | Élevé |
| 23 | SCIM | Provisioning automatique | ⚪ | Aucun | Nouveau | Nouveau | SSO SAML | IdP de test | Utilisateur créé dans l'IdP apparaît automatiquement | Onboarding automatisé | Élevé |
| 24 | SAML | Alternative à OIDC | ⚪ (choix OIDC-only) | `enterprise_sso.py` (référence) | Nouveau + `python3-saml`/`xmlsec1` | Nouveau | Décision à reconfirmer | IdP SAML de test | Uniquement si demande client réelle | Compatibilité IdP legacy | Élevé |
| 25 | RLS Postgres réelle | Isolation base de données réelle | 🟡 (BYPASSRLS) | Tables prêtes | Rôle Postgres dédié, policies | Migration de connexion | Aucune | `test_postgres_integration.py` étendu | Requête directe ne voit pas les autres organisations | Défense en profondeur | **Élevé** — le cahier des charges documente déjà "une seule GRANT manquante casse une fonctionnalité au hasard" |
| 26 | Certifications SOC2/ISO27001 | Éligibilité vente Enterprise | ⚪ | — | — (processus externe) | Aucune | Décision commerciale | Audit externe | Certification obtenue | Déblocage ventes Enterprise | Élevé (hors développement) |

---

# Z. Top 20 Implementation Priorities

| # | Nom | Objectif | État actuel | Travail nécessaire | Dépendances | Priorité | Risque |
|---|---|---|---|---|---|---|---|
| 1 | Brancher le chunking avancé | Qualité d'ingestion | 🟡 | Sélection par type + champ config | Aucune | P0 | Faible |
| 2 | Brancher le retrieval avancé | Qualité de recherche | 🟡 | Champs API + branchement | Aucune | P0 | Faible |
| 3 | Brancher le filtrage metadata | Recherche ciblée | 🟠 | Champ API + branchement agent | Aucune | P0 | Faible |
| 4 | Étendre la protection SSRF | Sécurité | 🟠 | 2 remplacements de client HTTP | Aucune | P0 | Faible |
| 5 | Ajouter l'allowlist widget | Sécurité | ⚪ | Champ + vérification | Aucune | P0 | Faible |
| 6 | Markdown + coloration chat | UX | ⚪ | Librairie frontend | Aucune | P0 | Faible |
| 7 | Brancher RBAC Casbin | Sécurité de permission | 🟡 | Fixture de test + migration | Fixture ASGI | P1 | Moyen |
| 8 | Construire le function-calling agent réel | Autonomie agent | 🟡 | Boucle de parsing/ré-invocation | Aucune | P1 | Moyen |
| 9 | Configurer Stripe de bout en bout | Facturation opérationnelle | 🟠 | Clés + tests webhooks | Aucune | P1 | Moyen |
| 10 | Brancher l'exécution parallèle d'outils | Performance agent | 🟡 | Branchement | Function-calling réel | P1 | Faible |
| 11 | Brancher la validation de résultat d'outil | Fiabilité agent | 🟡 | Branchement | Function-calling réel | P1 | Faible |
| 12 | Construire le client MCP | Interopérabilité 2026 | ⚪ | Nouveau module | Function-calling réel | P1 | Élevé |
| 13 | Trancher la décision UI Workflow Builder | Clarté de roadmap | ⚪ | Décision produit | Aucune | P1 | Aucun |
| 14 | Étendre le moteur de workflow (Loop) | Expressivité workflow | ⚪ | Nouveau type de bloc | Moteur existant | P2 | Moyen |
| 15 | Étendre le moteur de workflow (retry) | Robustesse workflow | ⚪ | Extension `_advance` | Moteur existant | P2 | Moyen |
| 16 | Câbler Voice AI dans le chat | Exploiter l'existant | 🟠 | Câblage frontend | Aucune | P2 | Faible |
| 17 | Brancher les guardrails IA | Sécurité IA | 🟠 | Middleware actif | Aucune | P2 | Moyen |
| 18 | Construire l'export de conversation | Confort utilisateur | ⚪ | Génération de fichier | Aucune | P2 | Faible |
| 19 | Construire le serveur MCP | Distribution écosystème | ⚪ | Nouveau module | MCP client | P2 | Moyen |
| 20 | Rechercher la demande de connecteurs CRM | Éviter de construire sans marché | ⚪ | Étude de marché | Aucune | P3 (recherche) | Aucun |

---

# AA. Technical Risks

| Risque | Emplacement | Problème | Conséquence | Solution recommandée | Priorité |
|---|---|---|---|---|---|
| Régression RBAC pendant la migration | `organizations.py` + suite de tests | Deux systèmes de permission actifs en parallèle | Incohérence de sécurité temporaire | Migration route par route, tests de non-régression systématiques | Haute |
| Surface d'attaque MCP | Futur `mcp_client.py` | Serveur MCP tiers malveillant/mal configuré | Exécution d'actions non désirées | Transport HTTP uniquement, modèle de permissions/budgets déjà existant pour les agents | Haute |
| Fuite cross-tenant | Toute nouvelle table (MCP config, connecteurs) | RLS bypassée, isolation 100% applicative | Requête oubliant `organization_id` = fuite de données | Checklist de revue systématique | Haute |
| Duplication de moteur de recherche | Retrieval avancé | Nouvel endpoint séparé au lieu d'étendre `/search` | API incohérente | Toujours étendre `SearchRequest`/`retrieval_pipeline.py` | Haute |
| Duplication de moteur de workflow | Parallélisme/Loop | `workflow_engine_v2.py` séparé | Deux moteurs à maintenir | Étendre en place | Haute |
| Webhooks Stripe mal testés | `billing_stripe.py` | Passage en production sans test complet | Facturation incorrecte | Tests d'intégration mode test avant clé de production | Haute |
| Sous-estimation de l'effort UI Workflow Builder | Décision Partie P | Le cahier des charges prévient : "un nouveau projet complet" | Retard de planning | Scoper comme chantier frontend dédié | Moyenne |
| Chaîne de migrations Alembic | `api/alembic/versions/` (tête : 0111) | Plusieurs fonctionnalités P0/P1 ajoutent chacune une migration | Conflits de merge | Une seule branche à la fois sur la tête | Moyenne |
| Faux positifs des guardrails IA | `agent_guardrails.py` | Filtre mal calibré | Frustration utilisateur | Jeu de test de faux positifs avant activation | Moyenne |
| RLS réelle précipitée | Migration future | "Une seule GRANT manquante casse une fonctionnalité au hasard" (déjà documenté) | Panne difficile à diagnostiquer | Chantier dédié séparé, jamais combiné à une autre fonctionnalité | Élevée si tentée trop tôt |

---

# AB. Final Implementation Order

```text
ÉTAPE 1 — Brancher chunking + retrieval avancé + filtrage metadata (P0, en parallèle)
  ↓
ÉTAPE 2 — Étendre la protection SSRF + ajouter l'allowlist widget (P0, en parallèle, indépendant de l'étape 1)
  ↓
ÉTAPE 3 — Markdown + coloration syntaxique dans le chat (P0, frontend, indépendant)
  ↓
ÉTAPE 4 — Corriger la fixture de test ASGI, puis brancher RBAC Casbin route par route (P1)
  ↓
ÉTAPE 5 — Construire la vraie boucle de function-calling agent (P1)
  ↓
ÉTAPE 6 — Brancher l'exécution parallèle d'outils + la validation de résultat d'outil (P1, dépend de l'étape 5)
  ↓
ÉTAPE 7 — Configurer Stripe de bout en bout (P1, indépendant, peut être mené en parallèle des étapes 4-6)
  ↓
ÉTAPE 8 — Trancher la décision UI Workflow Builder (P1, décision produit)
  ↓
ÉTAPE 9 — Construire le client MCP (P1, dépend de l'étape 5)
  ↓
ÉTAPE 10 — Étendre le moteur de workflow : Loop + retry par nœud (P2, dépend de l'étape 8 si l'UI est retenue)
  ↓
ÉTAPE 11 — Câbler Voice AI + brancher les guardrails IA + construire l'export de conversation (P2, en parallèle, indépendants)
  ↓
ÉTAPE 12 — Construire le serveur MCP (P2, dépend de l'étape 9)
  ↓
ÉTAPE 13 — Parallélisme réel du workflow (P2, dépend de l'étape 8 et 10)
  ↓
ÉTAPE 14 — Rechercher la demande réelle de connecteurs CRM/ticketing avant tout développement (P3, recherche)
  ↓
ÉTAPE 15 — Fonctionnalités Enterprise sur demande client confirmée : permission sync, SCIM, SAML, RLS réelle, certifications (P3)
```

**Ce document est prêt à servir de base à une demande future du type « implémente l'étape 1 » sans nécessiter de refaire l'audit.**
