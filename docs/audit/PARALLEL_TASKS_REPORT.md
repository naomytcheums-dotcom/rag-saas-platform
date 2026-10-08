# Parallel tasks report - 2026-10-04

## Backup

Real Supabase staging dump completed with native pg_dump 17.11, exit 0.
Start 21:10:42 UTC (22:10:42 local UTC+1).
File `staging-artifacts/staging_backup_20261004_211042.sql`,
**911502 bytes / 0.87 MiB**, **178 public CREATE TABLE statements**.
SHA256 `7009870d53c6050b6b42102c529b9d2142f564c75f3cff06a1153a6d1e95fd67`.
Header SQL checked without displaying rows. Secret supplied privately by
the user after the staging dotenv placeholder was detected; injected only
in memory. No fallback to a production DATABASE_URL.

## Restore

**BLOCKED_EXTERNAL**, no target restored.
Supabase free-project limit reached (two projects), verified by the user.
Docker client 29.7.2 available, but both desktop-linux and default daemon
checks timed out after 20s each. No container created/deleted, no shared
service restarted, no restored catalog numbers fabricated.
Full dump includes Supabase platform schemas/extensions: portable restore
requires checking those dependencies and creating the lab RLS role.
See [BACKUP_RESTORE.md](../operations/BACKUP_RESTORE.md).

## Feature alternatives

The exact original eight blocked journeys are unchanged:
PDF/DOCX/TXT upload, chunking/embedding, chat/citations, workflow execution,
evaluation execution, evaluation results, STT/TTS and image upload.
MCP and payments are separate integration limits, not silently substituted
for two original journeys.

Direct shared-browser attempts failed to connect to the browser CDP within
30s. Alternative launched: ASGI API calls against real staging transactions
and original browser A/B identities, with rollback, plus existing isolated
unit/provider tests. Probe completion is not a live end-to-end success.
Final alternative run: **117 completed, 0 failures/errors/skips**, 1438.999s.
Of these, 109 are existing assertion-based alternative tests and eight are
diagnostic probes recording responses/errors without asserting live success.
Do not describe the eight probes as eight successful feature journeys.
Evidence: `parallel-feature-alternatives.xml` and its redacted session log.

| Original journey | Direct/API alternative | Live status |
|---|---|---|
| PDF/DOCX/TXT upload | TXT API raises OSError naming absent S3 document bucket/key settings; existing PDF/DOCX/TXT extraction alternatives PASS | BLOCKED_EXTERNAL: storage not configured; exception is not a successful HTTP upload |
| Chunking/embedding | Document progress 200, completed/100 for a fixture-seeded document; embedding-dimension alternatives PASS | BLOCKED_EXTERNAL: no real ingestion demonstrated; seeded progress is not processing evidence |
| Chat/citations | Stream starts HTTP 200 then SSE error: Anthropic API key absent; existing chat alternatives PASS | BLOCKED_EXTERNAL: no generated answer/citations; HTTP 200 does not mean generation success |
| Workflow execution | Validation 200, valid=true for an empty fixture draft; existing workflow engine alternatives PASS | BLOCKED_EXTERNAL: live execution not dispatched or completed |
| Evaluation execution | Minimal question creation 201 with expected answer Paris; rolled back afterward | BLOCKED_EXTERNAL: preparation works, no live evaluation executed |
| Evaluation results | Jobs list 200, zero items; existing results endpoint alternatives PASS | BLOCKED_EXTERNAL: no completed live result exists |
| STT/TTS | TTS 400: ELEVENLABS_API_KEY absent; STT 400: OPENAI_API_KEY absent; mocked voice alternatives PASS | BLOCKED_EXTERNAL: real audio providers unavailable |
| Image upload | Generated 2x2 PNG API raises missing-S3 OSError; existing image extraction alternatives PASS | BLOCKED_EXTERNAL: storage unavailable; no live image ingestion |

## Backend suite and remaining limits

Full post-correction suite was left running; last observed progress 67%,
no failures recorded at that checkpoint, no final JUnit yet. Do not claim
completion from this interim number. No production connected.

All final counts will come from persistent logs/JUnit, not estimated totals.
