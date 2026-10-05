# Feature checks - 2026-10-04

## Parallel follow-up

Eight diagnostic API probes against actual staging transactions and the
original browser A/B identities have been launched, with rollback cleanup.
They exercise TXT upload, document progress, chat stream, workflow validation,
minimal evaluation question creation, jobs listing, STT/TTS and image upload.
Existing extraction, embedding, voice, chat, workflow and results endpoint
tests are included as alternatives, with their existing mock boundaries.
Final run: 117 completed, zero failures/errors/skips in 1438.999s:
109 existing assertion-based alternatives pass, eight diagnostic probes
recorded actual outcomes without asserting success. No blocked live journey
is reclassified as end-to-end PASS. TXT/PNG APIs raise missing-S3 errors;
STT/TTS return 400 for absent provider configuration. Chat opens HTTP 200
but returns an SSE error for absent Anthropic key, not an answer.
Workflow validation 200 applies to an empty draft; question creation 201
and empty jobs listing 200 prove preparation/read paths only. Document
progress 200 is fixture-seeded, not evidence of live processing.
The direct shared-browser API attempt could not connect to CDP within 30s;
ASGI against guarded PostgreSQL is the chosen non-browser alternative.
See [PARALLEL_TASKS_REPORT.md](./PARALLEL_TASKS_REPORT.md).

## Method and scope

The browser agent stopped producing useful progress (seven completed tool
calls, no final report); no success is attributed to it. Direct API requests
were executed from the shared browser against `127.0.0.1:18039`, connected
to Supabase staging. Existing account A was used; secrets were not returned.
Expired JWTs initially returned 401. A real CSRF-protected refresh returned
200, and the same requests then succeeded. This was not an auth bypass.

PASS means the bounded action below succeeded, not the entire product.
PARTIAL means only a sub-action is verified. BLOCKED means the complete
requested journey lacks evidence; it is not a passing test.

## Twenty requested journeys

| # | Journey | Status | Actual evidence / remaining limit |
|---|---|---|---|
| 1 | Create workspace | PASS API | POST 201, GET list 200; workspace 43130442-9c4b-4487-9762-e4392b5aa892. No workspace UI form certification. |
| 2 | Upload PDF, DOCX, TXT | BLOCKED_EXTERNAL | Real storage profile absent: full suite skipped 24 document pipeline cases for missing S3_DOCUMENTS_BUCKET_NAME. No three-format live upload claimed. |
| 3 | Chunking and embedding | BLOCKED_EXTERNAL | No live document ingestion in this profile; storage missing, current live worker not responding in full-suite ping. Unit tests are not pipeline evidence. |
| 4 | Create agent | PASS API | POST 201, GET 200; agent b67850e3-fd26-48e4-9d8a-d249dbb24eda. |
| 5 | Configure prompt, tools, knowledge base | PARTIAL | Custom prompt and citation_required submitted on creation; tools and KB endpoints 200. No populated knowledge base or executable tool connection tested. |
| 6 | Chat response and citations | BLOCKED_EXTERNAL | No sandbox LLM key in isolated backend; no ingested corpus. No generated response/citation quality claimed. |
| 7 | Create workflow | PASS API | POST 201, workflow b2a287f7-8c1e-4df1-a6a0-09343d507afb. Empty draft, not a runnable workflow certification. |
| 8 | Execute workflow | BLOCKED_EXTERNAL | No responding live worker in full-suite ping; runnable workflow execution not demonstrated. |
| 9 | Create evaluation dataset | PASS API | POST 201, dataset 99db4f40-47f9-4f00-99e4-5de9fd2fe363; list 200. Empty dataset, no quality benchmark. |
| 10 | Run evaluation | BLOCKED_EXTERNAL | Dataset has no corpus/questions, isolated provider unavailable; no real evaluation started or claimed. |
| 11 | See evaluation results | BLOCKED_EXTERNAL | No completed live evaluation. Evaluation IDOR test passes with seeded resources, not generated metrics. |
| 12 | Create MCP server | PARTIAL | Registration POST 201, list 200; server 6c161914-cb74-4042-af0a-e303e07223f7. example.com placeholder stored, not contacted; no discovery/tool execution. |
| 13 | A2A agent card | PARTIAL | Staging IDOR card checks pass with scoped API keys. Direct browser JWT attempt returned 422 requiring X-API-Key; this is the expected different auth surface, not proof of browser card viewing. |
| 14 | Voice STT and TTS | BLOCKED_EXTERNAL | No configured sandbox transcription/speech provider in isolated backend; live audio exchange not performed. |
| 15 | Multimodal image upload | BLOCKED_EXTERNAL | Storage profile absent; no live image upload/pipeline performed. Local model tests do not replace it. |
| 16 | See credits | PASS API | GET billing/credits 200 with organization_id and balance. No purchase/payment certified. |
| 17 | Notifications and alerts | PARTIAL | Notification SMS list 200, empty. Alert creation/delivery and real provider not demonstrated. |
| 18 | White-label branding | PARTIAL | GET branding 200 with default colors/font. No branding mutation/logo upload/custom-domain journey demonstrated. |
| 19 | Create webhook | PASS API | Invalid event document.created correctly rejected 400; corrected document.uploaded returns 200, webhook 5f71f303-b0d0-4ede-b7d8-4a269f7c0f0c. No outbound delivery attempted. |
| 20 | Analytics | PARTIAL | GET analytics/product/usage 200 with by_metric and period_days; no populated dashboard/browser visualization or load test. |

Summary: **6 bounded API passes, 6 partial, 8 blocked journeys**. All twenty
are classified; they are not twenty successful browser end-to-end tests.
No production service was contacted. Audit resources remain clearly named
in organization A; no accounts or user data were deleted. MCP/webhook URLs
are inert registration fixtures, not configured integrations.

Separate browser evidence already verified registration/login/logout for
both A/B, and backend readiness was rechecked 200 with DB/Redis/cache OK.

## Exact eight blocked journeys and testable alternatives

| Journey | External dependency blocking live success | Alternative, not equivalent to E2E |
|---|---|---|
| PDF/DOCX/TXT upload | S3 document bucket/access configuration absent | Existing extraction and document-router tests with mocked storage; live metadata APIs do not prove upload |
| Chunking/embedding | No live uploaded document pipeline, no responding worker | Existing chunking/embedding unit cases; synthetic vectors cannot certify real ingestion |
| Chat/citations | Sandbox LLM and ingested corpus absent | Existing mocked-provider chat/citation tests; agent creation/read/config API already verified |
| Workflow execution | Live worker absent, draft has no executable graph | Existing workflow executor tests with isolated fixtures; creation/list API already verified |
| Evaluation run | No populated corpus/questions or sandbox model | Existing evaluation service tests with mocked model; dataset creation/list API already verified |
| Evaluation results | No completed live evaluation | Seeded real-staging evaluation IDOR already verified; cannot invent a benchmark result |
| Voice STT/TTS | Sandbox audio provider absent | Existing mocked voice router/provider tests; cannot replace live audio quality |
| Image upload | Storage integration configuration absent | Existing extraction/media tests and real-staging media IDOR; cannot certify object upload or processing |

These existing unit/API alternatives are covered by the newly launched full
suite where selected; final post-correction counts remain pending. Mock
success must not change a live journey from BLOCKED_EXTERNAL to PASS.
