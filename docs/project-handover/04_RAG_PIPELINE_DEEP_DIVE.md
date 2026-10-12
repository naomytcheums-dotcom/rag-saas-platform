# 04 - The RAG pipeline, end to end (ingestion -> retrieval -> generation -> evaluation)

Everything here was read in the code on 2026-10-12 unless tagged **[R]** (run/measured in project sessions), **[D]** (documented only) or **[U]** (unknown). File references are relative to the repository root; line numbers are those of branch `bob/auto-fix-20261010-gaps` at commit `c31b178` and drift with edits.

## 0. One-page summary
1. A document is stored in S3 and a `documents` row is created (`status=pending`); a Celery task (`api/tasks/document_processing.py` -> `api/security/documents.py::process_document`, line ~3218) extracts text, splits it into chunks of **512 tokens with 50 tokens of overlap by default**, embeds each chunk with a local **sentence-transformers** model (default `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions) and stores text + vector in `document_chunks`.
2. At question time `api/services/retrieval_pipeline.py::search` retrieves chunks **only from the caller's organization** using the organization's strategy (default **`hybrid`** = pgvector cosine search + BM25, fused by Reciprocal Rank Fusion), optionally with rewriting, HyDE, multi-query, MMR, a cross-encoder reranker, a policy filter; it ends with a **relative** score threshold.
3. The chat router (`api/routers/chat_stream.py`) builds an LLM context from the chunks, the `AgentOrchestrator` calls the LLM (LiteLLM) with guardrails, streams tokens by SSE and stores a `Response` with numbered `Citation` rows.
4. The Eval Lab re-runs that retrieval (and generation) on questions with known expected documents and computes Recall@k, MRR, NDCG, precision, hallucination rate, latency, tokens and cost.

---
## 1. Ingestion

### 1.1 Entry points and validation [V]
| Entry | Function | Notes |
|---|---|---|
| File upload | `api/security/documents.py::upload_document` (line 602) | validates **before** touching S3 or the DB |
| Batch upload / ZIP | `start_document_batch_upload`, `schedule_zip_processing` | a ZIP is unpacked into one `Document` per member |
| URL / sitemap | `import_document_from_url`, `process_sitemap` | per-page Celery fan-out with stagger |
| GitHub repo / issues, Drive, Docs, Notion, Confluence, OneDrive | `process_*` functions + `api/tasks/*_import.py` | credentials resolved **per organization** (migration 0143, `connector_scope`) |
| Re-index | `reindex_document`, `reindex_organization`, `schedule_*`, beat `check-scheduled-reindexes` | |
Validation (`api/services/document_storage.py::validate_document_upload`): maximum size **50 MB** (`MAX_DOCUMENT_UPLOAD_BYTES`), content sniffing of the real type (PDF, DOCX, TXT, Markdown, HTML, CSV, JSON, XML, EPUB, ZIP; the filename is also used for Markdown/CSV), quota checks per organization (`QUOTA_DEFAULT_MAX_DOCUMENTS=1000` default).
**Antivirus:** `if settings.CLAMAV_ENABLED: await ascan_document_for_malware(...)`. The default is **`CLAMAV_ENABLED=False`** and `CLAMAV_REQUIRED=False`; a real-daemon test exists and passed locally [R].
**Duplicates:** SHA-256 `content_hash` (`compute_content_hash`); an identical non-deleted document in the same organization and file type returns the existing row with `is_duplicate=True` and does nothing else.
**Workspace check:** a `workspace_id` must belong to the same organization (cross-tenant modelling guard).
**Storage:** `upload_document_file(...)` writes the original to S3-compatible storage under a key built from organization and document ids; boto3 runs in `asyncio.to_thread` so the event loop is not blocked (TEN-003).
**Plugin hook:** `on_document_uploaded` fires best-effort.

### 1.2 Processing [V: `process_document`]
Status machine: `pending -> processing -> completed | failed`; any exception is recorded in `Document.metadata_json` and ends in `failed` (never stuck in `processing`). A beat task `requeue-stale-pending-documents` re-queues documents whose task was lost or ran early (fix RAG-002/RAG-003, 2026-10-09). Progress is published to Redis for the UI (`send_progress_update`).
1. **Download** the file to a temp path; **extract** through `api/services/document_extraction.py::extract_document_content(path, file_type, pdf_engine=...)`. PDF text engine is an organization setting (`pdf_extraction_engine`; an alternative IBM Docling engine exists, optional). OCR (Tesseract, `OCR_LANGUAGE=fra`, 300 dpi, 30 s timeout) applies to images and to scanned content, **only if the Tesseract/poppler binaries are installed**; `OCRNotAvailableError` is caught and logged, not fatal.
2. **Sections:** extraction returns sections with metadata (headings, pages, table rows capped at 100 and structure elements at 200 in metadata).
3. **Chunking** per section, strategy from `organization_settings.chunking_strategy` (default **`fixed`**; others: `recursive`, `markdown`, `code` (tree-sitter), `semantic`, `sentence`, `paragraph`, `parent_child`). A strategy that raises falls back to `fixed` for that section. `fixed` = sliding window over **tokenizer offsets** of the embedding model (`chunk_text`, line 385): `chunk_size=512`, `chunk_overlap=50` (so step = 462 tokens). `parent_child` stores wide *parent* chunks (text copied into `metadata_json["parent_context"]` of each *child*) and small *child* chunks; the LLM receives the parent text, the citation quotes the child.
4. **Language detection** on a text sample; **images** extracted from PDF/DOCX/EPUB are stored (`document_images`) with optional OCR text.
5. **Embedding:** `generate_embeddings(texts, model_name)` -> `SentenceTransformer.encode(batch_size=64)`; the embedder is cached under a lock (`get_embedder`), warmed at start-up (`start_embedder_warmup`).
6. **Persist:** one `DocumentChunk` per piece with `content`, `metadata_json` (including `chunking_strategy`, section metadata), `embedding` (JSON list), **`embedding_model`**, **`embedding_dim`**, and `embedding_vector` (pgvector) **only if the dimension equals `settings.EMBEDDING_VECTOR_DIM` (384)**; `chunk_index`, `parent_chunk_id`, `chunk_role` (`parent|child|...`).
7. Document row finalised (`processed_at`, `status`), BM25 corpus revision advanced (see 3.3), plugin/webhook events, optional GraphRAG ingestion and agent-memory side effects when enabled.

### 1.3 Deletion and retention [V/D]
Soft delete (`deleted_at`), replace (new version row), permanent delete (removes S3 object and chunks; "Mem0/GraphRAG per-document deletion" is claimed in README - see 11_KNOWN_ISSUES for the residual-data question), retention beat tasks purge conversations, voice messages and old audit logs. Retrieval excludes soft-deleted documents (`Document.deleted_at.is_(None)`) and chunks of documents not yet processed.

---
## 2. Embeddings and the 384 vs 768 dimension problem

### 2.1 What exists [V]
* `api/services/embedding_config.py::EMBEDDING_MODELS`: MiniLM-L6-v2 (384), all-mpnet-base-v2 (768), multi-qa-mpnet-base-dot-v1 (768); OpenAI ada-002 (1536) and Cohere (1024) are listed **but marked unavailable for the live ingestion pipeline** (they cannot be loaded through `SentenceTransformer`). `api/services/embedding_providers.py` is a *separate* standalone service for OpenAI/Voyage/Cohere/HF (and bge, multilingual-MiniLM at 384/768) that is **not** what ingestion uses.
* Per-chunk provenance: `embedding_model`, `embedding_dim` columns (nullable for legacy rows).
* Native index: `embedding_vector Vector(384)` + HNSW (migration 0128). A chunk of another dimension is **not** in the indexed column but is still searchable through a NumPy fallback.
* Query time: `_split_chunks_by_dimension` keeps only chunks whose stored vector has the **same length** as the query vector; excluded chunks are logged and counted in `dimension_mismatch_excluded` (returned to the caller so a UI can recommend re-indexing). `_pgvector_rank_chunks` returns `None` (use the NumPy path) when the query dimension is not 384, on SQLite, or if `PGVECTOR_ENABLED=False`.
* Re-index tooling: `reindex_organization`, `get_embedding_staleness_summary` (compares each chunk's `embedding_model` with the organization's current setting; flags stale and legacy chunks).

### 2.2 Current status of the historical problem
The original failure (384-d MiniLM chunks vs a 768-d MPNet query) **no longer crashes**: mixed dimensions are excluded and reported rather than compared. What is **not** guarded: **two different models that happen to share 384 dimensions** (for example MiniLM-L6-v2, `BAAI/bge-small-en-v1.5` and `paraphrase-multilingual-MiniLM-L12-v2`, all 384 in `embedding_providers.py`). Ranking compares vector length only, not `embedding_model`, so after changing between such models without re-indexing, old and new vectors would be compared in different spaces without any error. Mitigation exists only as an advisory (staleness summary). **Recommended fix:** filter candidates by `embedding_model == current model` (or force re-index on model change). Status: open, low frequency, [V by reading `_split_chunks_by_dimension` and the ranking code].

---
## 3. Retrieval (`api/services/retrieval_pipeline.py`, 1,281 lines)

### 3.1 Entry points
`search(db, organization_id, query, top_k, strategy, reranker, score_threshold, org_settings, metadata_filters, document_ids, user_context, trace_stages)` (line 859) is the single live entry; `search_with_context` (line 1161) wraps it with graph context. `tools/search_kb.py` forces `hybrid_reranked` for the agent tool. The chat router calls `search_with_context` directly (`api/routers/chat_stream.py:93`).

### 3.2 Order of operations inside `search()` [V]
1. Empty query -> `[]`. Metadata filters normalised/validated.
2. **Query rewriting** (`query_rewriting_enabled`, default off): LLM/rule rewrite; any failure falls back to the raw query. **Synonym expansion** (`query_expansion_enabled`, off).
3. **Adaptive routing** (`adaptive_routing_enabled`, off): `query_router.suggest_retrieval_strategy` picks a strategy when none is forced.
4. Strategy resolved from `_STRATEGY_FUNCTIONS`: `hybrid` (default), `vector_only`, `bm25_only`, `hybrid_reranked`, `semantic` (=vector).
5. **HyDE** (`hyde_enabled`, off; not for `bm25_only`): an LLM writes a hypothetical answer; its embedding replaces the query embedding **for the vector leg only**; BM25 still ranks the raw query. Failure -> plain query embedding.
6. **Candidate sizing:** `top_k` default **5** (`DEFAULT_SETTINGS["top_k"]`, max `TOP_K_MAX=100`); with MMR on, `fetch_top_k = top_k*3`; with policy-aware retrieval, over-fetch by `POLICY_OVERFETCH_FACTOR`.
7. **Dispatch** (optionally **multi-query**: variants generated by LLM, searches run in parallel, merged by RRF, deduplicated, re-ranked).
8. **Policy filter** (`policy_aware_retrieval_enabled` and a `user_context`; OPA/Rego): applied after retrieval, before MMR.
9. **MMR** (`mmr_enabled`, off; lambda 0.7): diversifies the final list using each chunk's stored embedding; relevance term uses the *query* embedding, never HyDE's.
10. **Score threshold** (`score_threshold`, default **0.5**): scores are **min-max normalised within the result list** and chunks with normalised score `< 0.5` are dropped. Return `results[:top_k]`.
11. Every stage can be timed into `trace_stages` (flight recorder) when requested.

### 3.3 The strategies
* **Vector** (`vector_search` -> `rank_chunks_by_embedding`): query embedded with the organization's model; **pgvector** path `ORDER BY embedding_vector <=> :q` (cosine distance, HNSW, iterative scan enabled via `_enable_iterative_hnsw_scan`, `PGVECTOR_MAX_SCAN_TUPLES=20000`) with filters `organization_id`, non-deleted documents, optional `document_ids`/metadata; otherwise load the organization's chunks and compute cosine in NumPy. **Which path ran in production is [U]** (depends on the live database; the README says native pgvector is used on PostgreSQL).
* **BM25** (`bm25_search`): `rank_bm25.BM25Okapi` over **all chunk texts of the organization** (tokenizer `[a-zA-Z0-9_]+`, i.e. **no accents/stemming**, which matters for French), cached per `(organization, corpus revision, filters)`; the revision `organizations.bm25_corpus_revision` is advanced by database triggers (migration 0133) so other workers invalidate; the index is built in a thread executor. Cold cost is O(N) in the organization's chunk count (documented in the README as a known scaling limit).
* **Hybrid** (`hybrid_search`): vector and BM25 each fetch a candidate pool (`resolve_reranker_top_k`), then **RRF** `score = sum 1/(k+rank+1)` with `rrf_k=60`; top_k kept. Filters apply identically to both legs.
* **Hybrid reranked** (`hybrid_reranked_search`): hybrid candidates re-scored by `cross-encoder/ms-marco-MiniLM-L-6-v2` (`CrossEncoder.predict` in an executor), sorted descending.

### 3.4 Consequences of the current defaults (important for tuning)
* **The chat route hard-codes `top_k=5`** (`api/routers/chat_stream.py:93`), so an organization's own `top_k` setting does not apply to the chat stream; it applies to other callers (public API, evaluation, tools using the default).
* Advanced options are all **off** per organization, so a fresh organization runs **hybrid, top-5, threshold 0.5, no reranker, no rewriting**. The reranker is only on when the strategy is `hybrid_reranked` or via the agent tool `search_knowledge_base`.
* The 0.5 threshold is **relative**: the best candidate always normalises to 1.0 and about the lower half of any list is dropped, whatever their true relevance. So (a) the platform will almost never return "no context" because of a low absolute score, and (b) with `top_k=5` you often get fewer than 5 chunks. An absolute relevance floor (e.g. on cosine or cross-encoder score) does not exist in the live path.
* BM25 ignores accents and language; French queries lean on the vector leg.
* Tenant isolation here is a SQL filter on `DocumentChunk.organization_id`; there is no database-level barrier (RLS has no policies, D2/D8).

---
## 4. Generation and answers

### 4.1 The chat path (what users actually exercise) [V]
`api/routers/chat_stream.py` -> `search_with_context(...)` -> `build_llm_context(citation_chunks, org_settings)` (numbered `[n]` blocks) -> optional `_no_context_refusal` (refuses when the agent requires context and nothing was retrieved) -> `stream_agent_response` (`api/services/streaming.py`) -> `AgentOrchestrator.stream_response(context=..., citation_chunks=...)`. The orchestrator: resolves the LLM configuration (`resolve_llm_config` - agent override, organization setting, provider default; default provider anthropic, model `claude-sonnet-5-5`); builds the system prompt (agent prompt + optional plan, tool catalog, session memory, long-term memory, context); runs the **function-calling loop** (up to `AGENT_MAX_TOOL_ITERATIONS=8`, parallel tool calls with `asyncio.gather`); checks credits before each LLM call and debits after (BYOK bypass); applies **guardrails** (`validate_guardrails`, includes the two-stage injection detector on the input and on the retrieved context); streams `start/thinking/token/citation/done/error` SSE events; persists a `Response`, `Citation` rows, a confidence snapshot and anti-hallucination quality metrics (context relevance, citation correctness, claim verification where enabled).
### 4.2 The agent-less path
`api/services/generation.py::generate_response` (retrieval -> optional context compression -> system prompt with `CITATION_INSTRUCTIONS` -> toxicity and injection checks -> `chat_completion` -> output guard -> persisted `Response` + citations + lineage events). In the current code its only production call sites are the **voice** pipeline (`api/services/voice.py`); it is also the reference implementation tests rely on. **Difference worth knowing:** this path uses the classifier-only `detect_prompt_injection` (not the two-stage `detect_prompt_injection_confirmed`), and only if the organization enabled `prompt_injection_detection_enabled` (default **False**); the two-stage version is used by agent guardrails.
### 4.3 Citations [V: `api/services/citations.py` and `citation_*.py`]
Default 5 citations (`CITATION_DEFAULT_COUNT`, max 10, `CITATION_MIN_SCORE=0.5`); each `Citation` links to the chunk, document, page/section, URL, passage, a relevance label, a preview; secondary (supporting but not cited) sources up to 3. Citations always quote the **original** chunk even when the prompt used compressed or parent text. Citation correctness (is `[n]` present, accurate, well-formed) is scored per response.
### 4.4 Other answer controls
Refusal modes per agent: `citation_required`, `context_only`, "I don't know" confidence floor (`agent_idk`); `toxicity_filter_enabled`, `output_guard_enabled` (+ PII masking) per organization; `context_compression_enabled` (extract/summarize/LLM; only in the agent-less path); spend caps and credit checks before LLM calls.

---
## 5. Evaluation: how quality is computed

### 5.1 Data model [V: `annex/database_tables.md`]
`evaluation_datasets(organization_id, name, version, is_active, ...)` -> `evaluation_questions(dataset_id, question, expected_answer, expected_documents JSON, difficulty, category, expected_answer_type, split tuning|held-out)` ; `question_sets` (reusable groupings); `evaluation_jobs(dataset_id, question_set_id, agent_id, model_config_json, split, status, progress, total/completed, results JSON)` -> `evaluation_results(question_id, agent_id, evaluation_job_id, model_config_json, retrieved_documents, retrieved_chunks, actual_answer, metrics JSON, latency_ms)` and `evaluation_failures(category RETRIEVAL_FAILURE | GENERATION_HALLUCINATION | GENERATION_INCOMPLETE | OTHER)`.
Notes on the historically flagged fields: `organization_id` exists only on `evaluation_datasets` (questions, jobs and results inherit tenancy through `dataset_id`); `agent_id` is stored on jobs and results (FK to `agents`); `run_id` in older docs corresponds to `evaluation_job_id` ("jobs" in the API); `evaluation_results` has no `dataset_id` (summaries are computed in Python by joining on questions - a documented portability decision). A `split` column (migration 0137, 2026-10-11) separates tuning from held-out questions so that tuning on one set cannot inflate the reported score on the other.

### 5.2 Running an evaluation [V: `api/services/evaluation_results.py::run_evaluation`]
For each question: retrieve with `search_with_context` using the **candidate** `model_config` (which may differ from the organization's live configuration), generate an answer with the same building blocks as production (not by calling `generate_response`; results are stored in `EvaluationResult`, not in `Response`/`Citation`), time it (`EVALUATION_TIMEOUT` per question; empty answer recorded on timeout), then compute metrics against the question's ground truth. `compute_metrics=False` is used by the latency job so that quality metrics are not recomputed (fix 2026-10-11).
### 5.3 Metrics [V: `retrieval_metrics.py`, `ground_truth_documents.py`, `answer_quality_metrics.py`]
Recall@1/3/5/10 (document-level against `expected_documents`), Precision@k, MRR, DCG/IDCG/NDCG (graded relevance when `expected_documents` carry relevance), faithfulness and answer relevance, context relevance, citation correctness, hallucination rate, latency, tokens and cost per request. Each metric handles empty expected/retrieved lists explicitly.
**Corpus used by an evaluation job:** by default the job searches the organization's **whole corpus** like production (`EVALUATION_RESTRICT_RETRIEVAL_TO_GROUND_TRUTH_DOCS=False`). Until the fix of Hardening Mission §9 the job was restricted to the dataset's own expected documents, which inflated every retrieval metric because distractor documents could never be retrieved; each job now records `results.corpus_constrained`.
**Conditions for a correct Recall/MRR/NDCG:** the question must have `expected_documents` that exist as documents in the evaluated organization; an organization with no matching documents scores 0 by construction. Evaluation over seeded demonstration data proves the plumbing, not retrieval quality.
### 5.4 What has actually been measured
* Legacy single-tenant pipeline (`src/`, FastAPI docs corpus, 50 questions): Recall@5 88 % -> 90 %, MRR ~0.79 [D, `src/README.md`]; hyper-parameter tuned on the same set (acknowledged in `AUDIT.md`), a 15-question held-out check gave 100 % / 0.769.
* IBM Bob experiment on real documents: Recall@5 improved by 0.40 after a configuration change [D, `docs/ibm_bob_2/POST_BOB_LOCAL_VALIDATION.md`].
* **The current platform pipeline has no published baseline on a real corpus** (backlog item R-06: FastAPI-docs corpus, Recall@k/MRR/NDCG, HyDE and multi-query A/B) - not done. Four vertical datasets (FastAPI, legal, HR, finance) exist for import tests only.
* Calibration: `calibration/human_annotations.json` supports checking automatic judgments against human labels [D].
### 5.5 Regression and comparison
`comparison-jobs` compare configurations on the same dataset; `regression_detections`/`regression_thresholds` flag drops; `benchmark_versions` freeze a benchmark; `deployment_evaluations` gate a deployment; Guardian alert rules (`alert_rules`) fire on thresholds from `agents.md` (Recall@5 < 0.80 warning / < 0.70 critical, etc.).

---
## 6. Optional retrieval-adjacent systems
* **GraphRAG** (LightRAG, `api/services/graph_rag.py`): `graphrag_enabled` per organization; adds an *uncitable* synthesis block to the prompt.
* **Long-term memory** (Mem0 and `agent_long_term_memory_items`) and short-term session memory.
* **Query router**, **RAG genome / experiments**, **Evolution engine** (`rag_evolution_engine.py`): propose configuration changes and recommend them only on a measured gain.
* **Flight recorder** (`flight_recordings`) stores per-stage timing/data when `trace_enabled`; `GET /responses/{id}/trace` joins retrieval, generation, checks, agent steps and citations.
* **Provenance/lineage**: OpenLineage events if `LINEAGE_ENABLED`.
