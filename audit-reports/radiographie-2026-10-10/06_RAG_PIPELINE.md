# 06 — Pipeline RAG réel

Audit du 2026-10-10, HEAD `59d5ec9`. Vocabulaire : « IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ » = code lu, aucune exécution de bout en bout avec de vrais fournisseurs ni sur la base de production. **Aucune métrique de qualité (Recall@K, MRR, NDCG, taux d'hallucination) n'a été mesurée dans cet audit** ; aucune valeur n'est donc annoncée.

## Synthèse (corrigée par le contrôle de l'auditeur)
| Étape | État | Point clé |
|---|---|---|
| Upload, validation, déduplication, S3, dispatch Celery | IMPLÉMENTATION OBSERVÉE ; tests présents (`test_documents.py` 255 tests, réussis en CI) | plafond 50 Mio par fichier (`MAX_DOCUMENT_UPLOAD_BYTES`), lot 10 fichiers / 100 Mio, ZIP 100 entrées ; écriture S3 en thread séparé depuis `01f90f4` pour l'upload direct ; **nom de fichier assaini dans la clé S3** (TEN-005, `a324fcf`) |
| Antivirus ClamAV | OBSERVÉ, **désactivé par défaut** (`CLAMAV_ENABLED`) ; pas de quarantaine persistante | activation en production : NON VÉRIFIÉE |
| Parsing PDF/DOCX/TXT/MD/HTML/CSV/JSON/XML/EPUB (+ZIP) | OBSERVÉ | pas d'autre format (RTF, PPTX, XLSX…) trouvé |
| OCR | OBSERVÉ (Tesseract, fra, 300 dpi) | le CI installe Tesseract ; la machine de développement ne l'a pas (cahier des charges) |
| Chunking | **CONTRADICTOIRE** | `process_document()` utilise le chunker historique ; la config indique elle-même que plusieurs stratégies (récursif, sémantique, Markdown, code, phrase, paragraphe, parent-enfant) ne sont « pas encore câblées » |
| Embeddings | OBSERVÉ ; défaut `sentence-transformers/all-MiniLM-L6-v2` (384 dim), alternatives OpenAI 1536, Voyage 1024, Cohere 1024 | colonne pgvector fixée à 384 : les autres dimensions restent dans le JSON, sans ANN |
| Recherche lexicale (BM25) | OBSERVÉ (`rank_bm25`, cache de 16 organisations) | charge les chunks de l'organisation en mémoire (risque déduit) |
| Recherche vectorielle | OBSERVÉ : cosinus numpy ; index HNSW créé par migration `0128` | **quel chemin sert la production est NON ÉTABLI** (contradiction de la documentation du module) |
| Fusion hybride, reranking, HyDE, MMR, multi-requêtes, compression | OBSERVÉ (résolveurs + tests dédiés) | activation par défaut dans le flux HTTP : NON DÉTERMINÉ |
| Isolation tenant dans la récupération | requêtes centrales filtrées par `organization_id` | exhaustivité sur les chemins annexes : NON ÉTABLIE |
| Contexte insuffisant | refus avant génération **uniquement si** `citation_required` ou `answer_only_from_context` | sinon le modèle peut répondre sans contexte (RAG-004, test `test_p1_chat_stream_refusal.py`) |
| Citations | OBSERVÉ (`citation_chunks`, modèle de réponses/citations) | exactitude des citations : tests présents, qualité réelle NON MESURÉE |
| Streaming | SSE `/chat/stream` | annulation côté serveur non garantie |
| Garde-fous | OBSERVÉ (guardrails agent, détection d'injection, retrieval conscient des politiques) | efficacité NON MESURÉE |
| Évaluation | **Calculs présents** : `api/services/retrieval_metrics.py` (`calculate_recall_at_1/3/5/10`, `calculate_mrr`, `calculate_ndcg`, `calculate_precision`) + `evaluation_results.py`, `evaluation_jobs.py`, DeepEval en option | le sous-agent avait écrit « NON TROUVÉ » : **corrigé** par recherche textuelle ; les valeurs sur des données réelles : NON MESURÉES |
| Suppression / réindexation | soft delete, invalidation du cache BM25 ; la suppression S3 n'est pas faite au soft delete | suppression physique : NON ÉTABLIE |
| Tâches | `process_document_task` (max_retries 5), batch ; dispatch en « best effort » | une panne de broker peut laisser un document `pending` sans traitement (rattrapage RAG-003 ajouté, voir ROADMAP) |

## Écarts entre documentation et code
- `agents.md` décrit les endpoints Eval Lab `/api/eval/datasets`, `/api/eval/runs/...` : **aucun chemin `/api/eval/*` n'existe** (0 sur 943 opérations). Les routes réelles sont `/organizations/{org_id}/datasets`, `/datasets/{id}/evaluate`, `/jobs/{job_id}/failures`, `/jobs/{job_id}/failures/categories`, `/datasets/{id}/metrics/{metric}`, etc.
- `agents.md` décrit `/mcp/v1/servers…` ; le routeur `mcp_server.py` n'expose que `GET /mcp/v1/tools` et `POST /mcp/v1/tools/{tool_name}/call` ; la gestion de serveurs MCP externes est sous `/organizations/{org_id}/mcp-servers…`.
- Dossier `api/eval/` cité par `agents.md` : **absent**.

## Performance et coût (risques déduits, non mesurés)
Chargement des chunks d'une organisation en mémoire (BM25 et repli numpy), candidats intermédiaires non paginés, premier chargement du modèle d'embeddings (warm-up désactivable par `EMBEDDER_WARMUP_ON_STARTUP`), torch CPU sur un conteneur de 512 Mo. **Aucune capacité (documents, requêtes/s) n'est annoncée : NON MESURÉ.**

---
## Annexe — Exploration automatisée du pipeline (sous-agent, lecture seule)
*(numéros de ligne approximatifs ; une affirmation a été corrigée ci-dessus : métriques de retrieval)*

<!-- ANNEXE_AJOUTEE -->
### Audit RAG — chaîne réelle observée

> Audit statique en lecture seule. Les statuts indiquent du code trouvé, pas une preuve d’exécution en production.

#### 1–6. Upload, sécurité, parsing, OCR, langue, métadonnées

##### 1. Upload + validation — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- `upload_document()` valide les octets avant S3/DB via `validate_document_upload()`, calcule le hash, déduplique par organisation, crée `Document`, puis envoie vers S3 et Celery : `api/security/documents.py:602-678`, fonction `upload_document`.
- Formats reconnus : PDF, DOCX, TXT, Markdown, HTML, CSV, JSON, XML, EPUB, plus ZIP comme import spécial : `api/services/document_storage.py:1-100`, fonctions de validation.
- Capacité générique document : **50 MiB** (`MAX_DOCUMENT_UPLOAD_BYTES`, à confirmer dans les lignes de configuration/storage non lues directement). Batch : 10 fichiers / 100 MiB : `api/config.py:564-567`. ZIP : 100 entrées, 50 MiB par entrée : `api/config.py:548-558`.
- Tests associés : `tests/test_documents.py`, `tests/test_document_extraction.py`, `tests/test_csv_extraction.py`, `tests/test_document_duplicates.py`, `tests/test_document_batch_integration.py`.

##### 2. Antivirus/quarantaine CLAMAV — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Scan exécuté uniquement si `settings.CLAMAV_ENABLED` : `api/security/documents.py:642-644`, `upload_document`.
- Defaults : désactivé, socket/host non configurés, port 3310, timeout 30 s, non obligatoire : `api/config.py:998-1005`.
- Aucune quarantaine persistante observée ; le scan intervient avant création du document.
- Test : `tests/test_clamav.py`.

##### 3. Parsing par format — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Dispatcher unique : `extract_document_content()` : `api/services/document_extraction.py:116-245`.
- PDF : PyMuPDF par défaut ; alternative Docling par configuration organisationnelle `pdf_engine`: `api/services/document_extraction.py:116-143`, `api/security/documents.py:3218-3260`.
- DOCX, TXT, Markdown, HTML, CSV, JSON, XML, EPUB sont dispatchés vers leurs extracteurs spécialisés : `api/services/document_extraction.py:80-115`.
- EPUB est découpé par chapitres ; Markdown par sections/headings ; PDF par pages ; les autres formats produisent généralement une section globale : `api/services/document_extraction.py:1-78`.
- ZIP n’est pas chunké comme un document : ses membres deviennent des documents séparés : `api/security/documents.py:660-668`.
- Formats autres : non trouvé dans ce pipeline.
- Tests : `tests/test_pdf_extraction.py` (si présent), `tests/test_docx_extraction.py`, `tests/test_markdown_extraction.py`, `tests/test_html_extraction.py`, `tests/test_csv_extraction.py`, `tests/test_json_extraction.py`, `tests/test_epub_extraction.py`, `tests/test_xml_extraction.py`, `tests/test_document_extraction.py`.

##### 4. OCR — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Détection de PDF scanné puis OCR avant extraction normale : `api/services/document_extraction.py:116-180`, fonctions `detect_scanned_pdf`, `ocr_pdf_scanned`.
- Defaults : activé, langue `fra`, DPI 300, timeout 30 s : `api/config.py:569-577`.
- Le chemin Docling est séparé ; l’OCR décrit ici reste PyMuPDF/Tesseract : `api/services/document_extraction.py:116-143`.
- Test : `tests/test_ocr.py`.

##### 5. Détection de langue — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Configuration présente : activée, fallback `fr`, minimum 20 caractères : `api/config.py:579-584`.
- La langue apparaît dans les métadonnées EPUB et dans la configuration, mais l’appel effectif de détection pendant `process_document()` n’est pas établi par les extraits inspectés.
- Statut prudent : **NON DÉTERMINÉ** quant à l’exécution sur chaque document.
- Test associé : `tests/test_language_detection.py`.

##### 6. Métadonnées — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Le dispatcher retourne métadonnées globales et par section : pages, headings, liens, encodage, lignes, colonnes, profondeur JSON/XML, TOC EPUB, etc. : `api/services/document_extraction.py:1-78`.
- `process_document()` récupère ensuite les paramètres d’organisation et exploite la sortie du dispatcher : `api/security/documents.py:3218-3260`.
- Tests : `tests/test_metadata_enrichment.py`, `tests/test_metadata_normalization.py`, tests propres à chaque extracteur.

#### 7–9. Chunking, embeddings, indexation

##### 7. Chunking — **CONTRADICTOIRE**

- Le chemin effectivement utilisé par `process_document()` appelle le chunker historique avec tokenizer et paramètres d’organisation : `api/security/documents.py:3218-3260`, `chunk_text()` à `api/security/documents.py:385-409`.
- Les stratégies spécialisées recursive, semantic, Markdown headings, code, sentence, paragraph et parent-child existent avec defaults : `api/config.py:589-616`.
- La configuration affirme explicitement que plusieurs nouvelles stratégies ne sont **pas encore câblées** dans `process_document()` : `api/config.py:589-610`.
- Tests : `tests/test_chunking.py`, `tests/test_chunking_strategy_wiring.py`, `tests/test_chunk_config.py`, `tests/test_markdown_chunking.py`, `tests/test_mmr.py`.

##### 8. Embeddings/dimensions — **CONTRADICTOIRE**

- Génération d’embeddings via `generate_embeddings()`/embedder configuré : `api/security/documents.py:411-430`, appelé pendant `process_document()` : `api/security/documents.py:3218-3791`.
- Defaults providers : HuggingFace `sentence-transformers/all-MiniLM-L6-v2`, dimension 384 ; OpenAI 1536 ; Voyage 1024 ; Cohere 1024 : `api/config.py:792-814`.
- Dimension pgvector fixe : `EMBEDDING_VECTOR_DIM=384` : `api/config.py:748-762`; migration `vector(384)` et HNSW cosine : `api/alembic/versions/0128_pgvector_embeddings.py:65-89`.
- La colonne pgvector n’est remplie que si la dimension correspond ; les autres dimensions restent sur le JSON/numpy : `api/alembic/versions/0128_pgvector_embeddings.py:18-30`.
- Gestion de changement de modèle/dimension : provenance `embedding_model`/`embedding_dim`, regroupement par dimension côté cosine et reindex séparé : `api/alembic/versions/0128_pgvector_embeddings.py:18-30`.
- Contradiction : le code historique documente une recherche numpy sans ANN, tandis que la migration pgvector/HNSW existe désormais : `api/services/retrieval_pipeline.py:1-55`.
- Tests : `tests/test_embedding_config.py`, `tests/test_embedding_dimension_safety.py`, `tests/test_embedding_staleness_route.py`, `tests/test_embedder_warmup.py`.

##### 9. Persistance/indexation — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Les chunks sont persistés dans `document_chunks`, avec embedding JSON et, selon dimension, `embedding_vector` : `api/alembic/versions/0128_pgvector_embeddings.py:65-89`; persistance appelée depuis `process_document()` : `api/security/documents.py:3218-3791`.
- HNSW pgvector est créé par migration, mais le chemin de recherche inspecté décrit/calculait encore numpy : `api/services/retrieval_pipeline.py:1-55`.
- Risque déduit du code : chargement en mémoire de tous les chunks d’une organisation.

#### 10–16. Retrieval et transformations de requête

##### 10. Recherche lexicale/BM25 — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- `rank_bm25.BM25Okapi`, cache par organisation et invalidation transactionnelle : `api/services/retrieval_pipeline.py:1-150`.
- Cache limité à 16 entrées : `api/services/retrieval_pipeline.py:45-75`.
- Test : `tests/test_bm25_index_cache.py`.

##### 11. Recherche vectorielle — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Recherche principale `search()` : `api/services/retrieval_pipeline.py:859-1154`; orchestration `search_with_context()` : `api/services/retrieval_pipeline.py:1155-1244`.
- Embedding de requête et similarité cosine numpy sont présents ; HNSW existe en migration mais son usage effectif par `search()` n’est pas démontré.
- Test : `tests/test_retrieval_pipeline.py`.

##### 12. Filtres metadata — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- `search_knowledge_base()` valide puis applique les filtres après recherche : `api/tools/search_kb.py:38-74`.
- Recherche metadata-only via `fetch_organization_chunks()` : `api/tools/search_kb.py:76-91`.
- Limitation documentée : certains champs (`author`, `tags`, `document_type`, etc.) ne sont pas peuplés au niveau attendu et peuvent ne rien retourner : `api/tools/search_kb.py:1-34`.
- Tests : `tests/test_metadata_filtering.py`, `tests/test_metadata_normalization.py`.

##### 13. Filtrage tenant dans les requêtes — **CONTRADICTOIRE**

- Le pipeline de retrieval filtre explicitement `DocumentChunk.organization_id` : `api/services/retrieval_pipeline.py:1-55`, fonctions `fetch_organization_chunks`, `search`.
- Les appels chat transmettent `agent.organization_id` : `api/routers/chat_stream.py:83-89`.
- Cependant `get_outdated_documents()` sélectionne les organisations membres plutôt qu’un unique tenant, ce qui est intentionnel pour cet endpoint : `api/security/documents.py:3290-3320`.
- Aucun audit exhaustif de chaque requête de retrieval annexe n’est établi ; le statut global ne permet donc pas de conclure à « chaque requête ».

##### 14. Fusion hybride/RRF — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Stratégies connues : `hybrid`, `vector_only`, `bm25_only`, `hybrid_reranked`, `semantic` : `api/services/agent_knowledge_base.py:118-133`.
- RRF est configurable (`MULTI_QUERY_RRF_K=60`) : `api/config.py:779`; fusion et scores sont référencés dans `api/services/citation_secondary.py:43-58`.
- Test : `tests/test_rrf_fusion.py` si présent dans `tests/`.

##### 15. Reranking — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- `hybrid_reranked` utilise le reranker/cross-encoder via `search_with_context()` : `api/tools/search_kb.py:58-74`; résolveurs à `api/services/retrieval_pipeline.py:35-55`.
- Defaults : `RERANKER_MAX_TOKENS=512`, `TOP_K_MAX=100` : `api/config.py:766-773`.
- Test : `tests/test_reranking.py` si présent.

##### 16. Rewriting, HyDE, MMR, multi-query, compression — **CONTRADICTOIRE**

- Des résolveurs existent pour rewriting, HyDE, MMR, multi-query, adaptive routing et context compression : `api/services/retrieval_pipeline.py:35-55`.
- Leur activation/consommation réelle dans chaque stratégie n’est pas prouvée par les extraits inspectés.
- Tests dédiés présents : `tests/test_hyde.py`, `tests/test_mmr.py`, `tests/test_query_rewriting.py`, `tests/test_multi_query.py`, `tests/test_context_compression.py`.
- Statut par fonctionnalité : **NON DÉTERMINÉ** sauf lorsqu’un test/wiring spécifique confirme le branchement.

#### 17–25. Contexte, génération, réponses

##### 17. Sélection du contexte — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- `build_llm_context()` construit le contexte à partir des chunks : `api/services/retrieval_pipeline.py:1245-1276`.
- Limite configurée : 3 000 tokens : `api/config.py:771-779`.

##### 18. Prompt — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Le contexte et les chunks citables sont transmis à `stream_agent_response()` : `api/routers/chat_stream.py:96-100`.
- Construction détaillée du prompt dans `api/services/streaming.py`/services génération non entièrement établie.

##### 19. LLM — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Provider par défaut Anthropic, modèle `claude-sonnet-5-5`, timeout 60 s, retries 3 : `api/config.py:783-790`.
- Providers alternatifs OpenAI, Gemini, Mistral, Ollama et OpenAI-compatible : `api/config.py:791-850`.
- Appel via streaming/génération : `api/routers/chat_stream.py:96-100`.

##### 20. Contexte insuffisant — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Refus avant génération si aucun chunk et si `citation_required` ou `answer_only_from_context` : `api/routers/chat_stream.py:40-50`, `86-95`.
- C’est opt-in ; sinon le modèle peut répondre sans contexte.

##### 21. Citations — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Les `citation_chunks` sont conservés depuis retrieval jusqu’au streaming : `api/routers/chat_stream.py:86-100`.
- Modèles/services de citations et migration réponses/citations : `api/services/citations.py:1-90`, `api/alembic/versions/0066_responses_and_citations.py`.
- Tests : `tests/test_citations.py`, `tests/test_citation_correctness.py`, `tests/test_agent_citation_required.py`.

##### 22. SSE — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- GET et POST `/chat/stream`, `StreamingResponse`, événements start/token/done : `api/routers/chat_stream.py:103-133`.
- La reconnexion client est laissée à `EventSource`; aucune annulation serveur garantie n’est établie : `api/routers/chat_stream.py:1-25`.
- Test : `tests/test_streaming.py`, `tests/test_chat_stream_policy_wiring.py`.

##### 23. Mémoire conversationnelle — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- `conversation_id` est validé et transmis au streamer : `api/routers/chat_stream.py:65-100`.
- Les modèles/routes conversation existent : `api/models/conversation.py`, `api/routers/conversations.py`.
- Limite exacte de messages injectés non établie dans cette vérification.

##### 24. Guardrails/injection — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Guardrails agents, OPA/policy-aware retrieval et détection d’injection existent : `api/services/agent_guardrails.py`, `api/services/policy_aware_retrieval.py`, `api/alembic/versions/0125_prompt_injection_detection.py`.
- Dans le flux chat inspecté, `user_context` est transmis au retrieval : `api/routers/chat_stream.py:74-89`.
- Tests : `tests/test_agent_guardrails.py`, `tests/test_injection_test_set.py`, `tests/test_prompt_injection_detection.py`.

##### 25. Évaluation/observabilité — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Services d’évaluation et DeepEval : `api/services/deepeval_validation.py`, `api/services/evaluation_results.py`.
- Tests : `tests/test_deepeval_validation.py`, `tests/test_answer_quality_metrics.py`, `tests/test_faithfulness.py`, `tests/test_groundedness.py`.
- Recall@K/MRR/NDCG exacts : **NON TROUVÉ** dans `api/eval` (répertoire absent lors de la recherche).
- Diagnostics/retrieval metrics : `api/services/flight_recorder.py`, `api/services/retrieval_pipeline.py`.

#### 26–27. Suppression, fraîcheur, tâches asynchrones

##### 26. Suppression/reindex/staleness — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Soft delete marque `deleted_at`, ne supprime pas S3, invalide le cache BM25 : `api/security/documents.py:3320-3345`.
- Documents obsolètes dérivés de `last_modified > processed_at` : `api/security/documents.py:3290-3320`.
- Reindex/staleness et migration d’embeddings existent : `api/services/embedding_reindex.py`, `api/routers/reindex_schedules.py`, `tests/test_embedding_staleness_route.py`.
- Staleness du contenu déjà indexé après modifications externes : géré par routes/checks spécifiques, mais absence de preuve d’exécution.

##### 27. Celery, retries, reprise — **IMPLÉMENTATION OBSERVÉE — FONCTIONNEMENT NON PROUVÉ**

- Upload dispatch `schedule_document_processing()` : `api/security/documents.py:1113-1125`.
- Tâche Celery d’ingestion : `api/tasks/document_processing.py:69-111`, `process_document_task`, `max_retries=5`.
- Batch possède traitement et reprise : `api/tasks/batch_jobs.py:48-55`.
- Échec d’extraction/embedding met le document en `failed` : `api/security/documents.py:3218-3791`.
- Le dispatch est best-effort : une panne broker peut laisser l’upload créé sans traitement : `api/security/documents.py:602-678`.
- Tests : `tests/test_celery_integration.py`, `tests/test_celery_dispatch_fail_fast.py`, `tests/test_document_status.py`, `tests/test_document_progress.py`.

#### Code mort, mocks, risques et incohérences

- **Alternatives non câblées ou incertaines** : chunking avancé déclaré non intégré : `api/config.py:589-610`; pgvector ajouté mais usage effectif non établi : `api/alembic/versions/0128_pgvector_embeddings.py:65-89`.
- **Mocks/démos** : nombreux tests mockent providers, Celery et LLM ; le fonctionnement de production ne peut pas être déduit des seuls tests.
- **N+1 / charges non bornées — risque déduit du code** : `fetch_organization_chunks()`/BM25 chargent potentiellement tous les chunks d’une organisation en mémoire : `api/services/retrieval_pipeline.py:204-250`.
- **Unbounded loads — risque déduit du code** : fallback numpy et metadata-only sans pagination apparente ; `top_k` est borné par configuration mais les candidats intermédiaires peuvent être volumineux.
- **Tenant** : les requêtes centrales filtrent `organization_id`, mais une garantie exhaustive pour tous les chemins annexes n’est pas établie.
- **Quarantaine** : scan CLAMAV observé, stockage/quarantaine dédiée non trouvé.
- **Fonctions possiblement mortes** : extracteurs autonomes (`extract_epub_text`, stratégies de chunking avancées) existent, mais leur appel depuis le pipeline principal n’est pas démontré : `api/services/epub_extraction.py`, `api/services/chunking.py`.

#### Questions non établies

- Le chemin de retrieval utilise-t-il effectivement HNSW/pgvector ou toujours numpy/BM25 ?
- Chaque stratégie déclarée (HyDE, MMR, rewriting, multi-query, compression) est-elle activée dans le flux HTTP par défaut ?
- La détection de langue est-elle appelée dans `process_document()` ou seulement exposée comme service/test ?
- Quelle est la limite réelle de taille générique appliquée par `validate_document_upload()` ?
- Le prompt final exact et la limite de mémoire conversationnelle.
- Les métriques Recall@K, MRR, NDCG sont-elles réellement calculées en production.
- Tous les chemins de retrieval annexes filtrent-ils systématiquement `organization_id` ?
- Un échec Celery après création de document est-il automatiquement replanifié/résumable au-delà des cinq retries ?
- La suppression physique S3 et la suppression/reconstruction complète des chunks sont-elles effectuées par le chemin de delete.
