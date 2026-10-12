# 11 - Known issues, current status of each, and the work remaining to a commercial product

Tags: **[V]** state checked in code on 2026-10-12; **[R]** executed in project sessions; **[D]** documented only; **[U]** unknown. For each earlier finding the *current* state was re-checked where the code allowed it; where it could not be, the entry says so. Nothing was fixed during this dossier mission (documentation only, plus the already-pushed CI work of the same day).

## Part A - Issue sheets (the why, not only the what)

### A1. Embedding dimension mismatch (384 vs 768) - **mostly fixed, one gap remains**
1. *Plain terms:* different embedding models produce vectors of different lengths; comparing a 384-number query with 768-number chunks is meaningless or crashes.
2. *Expected:* an organization can change its embedding model without breaking search. 3. *Observed originally:* search crashed or silently lost recall on older documents.
4. *Cause:* vectors stored without recording which model produced them; ranking assumed one dimension.
5. *Files:* `api/services/retrieval_pipeline.py` (`_split_chunks_by_dimension`, `rank_chunks_by_embedding`, `_pgvector_rank_chunks`), `api/models/document.py` (`embedding_model`, `embedding_dim`, `embedding_vector Vector(384)`), `api/security/documents.py::get_embedding_staleness_summary`, migrations 0128/0113.
6-7. *Risk:* lost recall (business); no security impact.
8. *Done:* per-chunk provenance; dimension guard (excluded chunks logged and counted in `dimension_mismatch_excluded`); NumPy fallback for non-384 spaces; staleness summary and reindex tooling [V].
9. *Proof:* unit tests for mixed dimensions exist; real pgvector search test passed [R].
10. *Still to verify:* behaviour in the live database; whether the UI shows `dimension_mismatch_excluded` to users [U].
11-12. *Remaining gap and recommendation:* models that share a dimension (MiniLM-L6, bge-small, multilingual-MiniLM are all 384) are not distinguished at query time; filter by `embedding_model == current model` or force re-index on model change. 13. *Impact:* retrieval layer only.

### A2. Prompt-injection guard-rails and where they run - **wired, with an asymmetry**
*Plain terms:* a malicious sentence in a question or in a retrieved document could make an assistant ignore its rules. *Observed (historic):* the detector existed but was not called on every path. *Now [V]:* the agent runtime calls `validate_guardrails` (two-stage detector on the input and on the retrieved context) for chat, public API, bots and regenerate; `generate_response` (agent-less, used by voice) uses the classifier only and only if the organization enabled it (default off); a bare agent has the flag off while agents built by the Factory have it on. *Cause of the asymmetry:* the second opinion was added to `validate_guardrails` only (`prompt_injection_detection.py`, `agent_guardrails.py`, `generation.py`). *Risk:* injection through the voice path. *Proof:* tests for both; measured accuracy in `docs/DECISIONS.md` D15 (7B second opinion: recall 0.930, false positives 0.020 on a 92-sentence set tuned on the same set). *To do:* use `detect_prompt_injection_confirmed` in `generate_response`; measure on fresh sentences; configure a second-opinion provider in production (otherwise the classifier's 12 % false-positive rate stands); decide block vs flag (D15 recommends flagging until measured on real traffic).

### A3. Policy engine (OPA) without user context - **fixed for chat only**
The policy-aware retrieval filter needs the user's attributes. `chat_stream.py` now builds `{user_id, organization_id, role}` and passes it [V]. Other callers of `search_with_context` pass none, so the filter is skipped there (public API, bots, evaluation). OPA is off by default (`OPA_ENABLED=False`) and the Rego policy itself is the operator's. *To do:* decide whether public API/bot calls must carry a synthetic subject.

### A4. Permission inconsistencies (webhooks Manager role; Owner-only routers open to Admin)
Five routers documented as Owner-only were open to Admin and were corrected (Hardening §9). `api/routers/webhooks.py` now documents the default key `webhooks:read` held by Manager/Member/Viewer and restricts writes to owner/admin [V]. *Proof:* route/role matrix tests. *To do:* re-run the matrix after any permission change; the semantic question "should a Manager manage webhooks?" is a product decision (custom roles can grant it).

### A5. LLM cost budget - **implemented**
Credit balance check before each LLM call, per-organization daily/monthly caps, per-tool token budgets, optional per-request budget routing, BYOK bypass [V]. *Open:* atomicity under heavy concurrency not proven (BILL-012); 24 PostgreSQL concurrency tests passed, no stress test of the cap itself.

### A6. No per-organization concurrency control in Celery - **open [V by search: nothing found]**
Heavy tenants can occupy all workers (no per-organization queue/limit). Staggering exists for fan-out imports (per-file delays) and sitemap/GitHub batches. *Risk:* noisy neighbour; *Recommendation:* per-organization rate limits at enqueue time or dedicated queues.

### A7. Webhook replay and integrity
Inbound: Stripe/Paystack signatures verified, events recorded in `payment_events` for idempotence (race fixed in Hardening §5) [D]; Slack signature includes a 5-minute replay window; Discord/Teams use a shared secret / audience check [V/D]. Outbound webhooks are signed with HMAC-SHA256 in `X-Webhook-Signature` over the body **without a timestamp**, so receivers cannot reject replays [V: `api/services/webhooks.py`]. *Recommendation:* add a timestamp header covered by the signature.

### A8. Rate limiting coverage - **partial**
44 of 107 router files use limiters; the highest-risk surfaces (auth, search, public API, widget, licence, partner registration) are covered and a fail-open case was fixed [V/D]. *Gap:* no global default limit; admin and dashboard CRUD routes mostly unlimited.

### A9. Missing foreign keys and orphan data - **partly open**
Evaluation results/questions rely on parent keys; JSON document references inside `expected_documents` are not constrained; several derived stores are cleaned by explicit calls. *To do:* a CI schema-drift check (`alembic check`), orphan-detection queries per table, FK additions via new migrations.

### A10. Deletion of derived data (Mem0, GraphRAG, caches) - **implemented, completeness unproven**
`purge_organization_memory` is called on organization deletion and account purge; `delete_document_from_graph` on permanent delete [V]. Not verified: flight recordings, lineage events, logs, embeddings cached in Redis, backups. *Risk:* GDPR erasure claims. *To do:* an erasure test that creates data in every store then deletes and queries each.

### A11. Connectors sharing one token - **fixed for importers/CRM; open for agent tools**
See D17 and `09_...`. Residual: DNS-rebinding window, OAuth consent flow absent, agent tools (Gmail, Calendar, Outlook, SMTP, GitHub) still use server identities and must stay unset.

### A12. Evaluation data persistence and metric validity - **fixed, with caveats**
Datasets/questions/jobs/results are persisted (migrations 0071-0077, 0123, 0137). *Validity bug fixed:* evaluation used to restrict retrieval to the dataset's own expected documents, which inflated Recall/MRR/NDCG; the default is now the whole organization corpus (`EVALUATION_RESTRICT_RETRIEVAL_TO_GROUND_TRUTH_DOCS=False`) and each job records `corpus_constrained` [V]. *Caveats:* tuning vs held-out split exists (0137) but older datasets have no split; no baseline on a real corpus has been published (R-06); demonstration annotations must never be reported as measurements.

### A13. Documentation vs code vs environment drift
`agents.md` says Python 3.11, runtime is 3.13; root `render.yaml` describes the old Streamlit service; `docs/CAHIER_DES_CHARGES.md` says 515 features, the catalog has 514; the README "operator checkpoint" says production revision 0130 while the real one was 0136 before 2026-10-11; SDKs default to a domain not shown to exist; some roadmap statuses claimed completion that audits later reversed (see `01_PROJECT_HISTORY.md` section 6). *Rule:* trust executed evidence; update docs in the same commit as behaviour.

### A14. Static analysis alerts
`mypy` is red (many type errors; non-blocking); only the *ratchet* of annotation coverage is enforced (69.1 %). `bandit`: 5 alerts (Hugging Face `from_pretrained` without pinned revision) left after triaging 12 [R]. *To do:* pin model revisions; reduce mypy errors by package and then make it blocking.

### A15. Search quality properties that surprise
(a) Relative score threshold (0.5 after min-max normalisation) always drops about half of any candidate list and never produces an absolute "not relevant" signal; (b) `chat_stream.py` calls `search_with_context(..., top_k=5)` with a hard-coded 5, ignoring the organization's `top_k`; (c) BM25 tokenisation ignores accents and language; (d) the cross-encoder reranker is not used unless the strategy is `hybrid_reranked`; (e) advanced retrieval options are all off by default. [V] *To do:* decide on an absolute relevance floor, wire `top_k` from settings, accent-folding tokenizer.

### A16. Infrastructure risks
No persistent worker/beat in the documented free-tier deployment (see `10_...` section 4.2); Supabase pooler limits (`EMAXCONNSESSION` history); 512 MB web hosts cannot hold the ML stack; backup restore never rehearsed; encryption at rest of hosted DB/storage unverified (D12); production was exposed to CI tests until 2026-10-10 (rows read and deleted by tests through the repository secret) - data created by tests may exist in production (README: 63/71 users @example.com, 1,523/1,576 organizations named "test"; cleanup proposed, **not executed**).

### A17. Secrets hygiene
A generated encryption master key was pasted into a chat on 2026-10-11 and must not be used. `scripts/export_openapi.py` imported the app with production settings once and touched the production pooler (~14:25 UTC on 2026-10-11); two real Anthropic calls came from an opt-in test before keys were blanked in the runner. *To do:* rotate the key before first use, review Supabase connection logs, review provider usage dashboards, add a startup/CI guard that refuses non-local targets in scripts.

## Part B - What remains to build, by category

| Cat. | Item | Why needed | Blocker / owner | Dependencies | Acceptance criterion (verifiable) |
|---|---|---|---|---|---|
| **A. Missing in code** | CinetPay (or alternative) payment adapter implementing `BillingProvider` | no way to collect money | needs CinetPay official docs + test keys (owner) | provider decision D16 | checkout in provider test mode creates a subscription/credits via webhook; webhook signature verified; idempotent replay test |
| A | Refunds/disputes (BILL-016) | money-back flows | schema change + policy (owner) | A: provider adapter | `charge.refunded`-style event reverses credits per policy; invoice linked to provider charge |
| A | Coupon application at checkout | marketing | provider coupon objects | provider adapter | discounted charge in sandbox |
| A | Per-organization agent-tool credentials (Gmail, Calendar, Outlook, SMTP, GitHub) | finish D17 | design + OAuth apps | connector credentials | agent tool refuses without org credentials; test per tool |
| A | OAuth "Connect with Google/Microsoft" for Drive/OneDrive | usability | OAuth apps registered by operator | none | consent flow yields stored refresh token; revoke works |
| A | Absolute relevance floor; `top_k` from settings in chat; accent-aware BM25 | retrieval correctness | none | measurement set | metric improvement on held-out set; no regression |
| A | Timestamped outbound webhook signatures | replay protection | none | none | receiver sample rejects replay older than N minutes |
| A | `docs/SANDBOX_SETUP.md` listing free developer sandboxes per vendor | test without buying accounts | none | none | document exists, each entry tested |
| **B. Implemented, unverified** | 34 catalog items `IMPLEMENTED_UNVERIFIED` | see `12_...` | run in CI/with services | varies | status moves to VERIFIED or FIXED |
| **C. Tested locally, not deployed** | 13 `VALIDATED_NOT_DEPLOYED` (Terraform x4, Helm, kubeconform, compose, scripts) | proves nothing until applied | needs cloud accounts or a local kind cluster | none | apply to a throwaway cluster/account; smoke passes |
| **D. Blocked externally** | 26 items: Slack/Teams/Discord sandboxes, Twilio, STT/TTS, hosted LLM providers, Resend, hosted observability | real-service proof | accounts/keys (owner) | `SANDBOX_SETUP.md` | one recorded real call per vendor |
| **E. Security/compliance** | RLS policies with non-bypass role (staged plan D2/D8); encryption-at-rest verification; erasure test; DNS-rebinding fix for connector hosts; SAML only on customer demand | defence in depth, GDPR | staging DB (owner) | CI against non-bypass role | listed per step in D2; erasure test green |
| **F. Reliability/operations** | persistent worker + beat; monitoring/alerts (Sentry, metrics); restore rehearsal; per-org Celery limits; domain + TLS | run a service | hosting budget decision | Render blueprint | smoke test; documents process end to end; restore into a scratch DB passes |
| **G. RAG quality** | R-06 baseline on a real corpus (Recall/MRR/NDCG, HyDE and multi-query A/B); held-out sentences for the injection detector; model-identity guard for embeddings | evidence for claims | none | datasets | numbers in `PERFORMANCE_REPORT.md` with split discipline |
| **H. UX** | landing page completion (5 sections + tablet/mobile), logo, server-side route guard, check thin pages against live backend | sellable front door | design assets | none | Playwright journey covers each page |
| **I. Commercial prep** | onboarding flow, pricing page truth (plans in code: 49/199/999 USD), terms/privacy, support channel, status page, quotas messaging | acquire customers | owner decisions | payment | trial sign-up to paid upgrade in sandbox |
| **J. Differentiators to preserve** | Eval Lab + Evolution engine + Guardian loop, MCP server/client with firewall, A2A, policy-aware retrieval, per-org connectors, two-stage injection guard, BYOK/credits | what separates it from generic RAG tools | none | none | keep tests green; finish rather than remove |

### Release steps (ordered by dependency and risk)
1. Merge PR #25 only when `backend-tests` and CircleCI `api-tests` are green (production schema already at 0143).
2. On the host: new `ENCRYPTION_MASTER_KEY` (vault), `COOKIE_SECURE=true`, `CREDITS_ALLOW_UNPAID_TOPUP=false`, `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS=false`, `CONNECTORS_ALLOW_PLATFORM_CREDENTIALS=false`, `METRICS_AUTH_TOKEN`, server tokens of Gmail/Calendar/Outlook/SMTP/GitHub left empty; decide `render.yaml`; start a worker (and beat).
3. `scripts/post_deploy_smoke.py --api ... --frontend ...`, then a manual journey (register, verify e-mail, upload, ask, citations, connectors page); delete the test account.
4. Review Supabase logs for the 2026-10-11 incident; clean historical test data (proposal exists, not executed).
5. Choose and implement the payment route (CinetPay) before any paid plan is shown to customers.
