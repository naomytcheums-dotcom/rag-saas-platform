# Project handover dossier (2026-10-12)

Start with `14_AI_HANDOVER_CONTEXT.md` (self-contained) or `00_EXECUTIVE_OVERVIEW.md`. Files:

| File | Content |
|---|---|
| 00_EXECUTIVE_OVERVIEW.md | what the product is, state, size, journey |
| 01_PROJECT_HISTORY.md | origin, timeline, structural changes, incidents |
| 02_PRODUCT_FUNCTIONAL_SPEC.md | functional specification by module and role |
| 03_TECHNICAL_ARCHITECTURE.md | stack, layout, flows, mandatory vs optional components |
| 04_RAG_PIPELINE_DEEP_DIVE.md | ingestion, embeddings, retrieval, generation, evaluation |
| 05_AGENTS_AND_AUTOMATIONS.md | agents, workflows, Bob modes, MCP, A2A, BeeAI |
| 06_SECURITY_AND_TENANCY.md | authentication, authorization, isolation, guard-rails, crypto |
| 07_DATABASE_AND_MIGRATIONS.md | tables, relations, migrations, integrity |
| 08_API_FRONTEND_AND_SDKS.md | routes, pages, SDKs |
| 09_BILLING_CONNECTORS_AND_EXTERNAL_SERVICES.md | plans, credits, payments, connectors, vendors |
| 10_TESTS_CI_CD_AND_DEPLOYMENT.md | test levels, CI, PR #25, environments, local run |
| 11_KNOWN_ISSUES_AND_REMAINING_WORK.md | issue sheets and remaining work by category |
| 12_COMPLETE_FEATURE_CATALOG.md | 514 features (generated from the audit CSV) |
| 13_GLOSSARY_AND_DEVELOPER_GUIDE.md | vocabulary, conventions, commands, diagnostics |
| 14_AI_HANDOVER_CONTEXT.md | single-file context for another AI assistant |
| 15_END_TO_END_VALIDATION_REPORT.md | real end-to-end validation with Ollama, defects fixed, dashboard |
| e2e_evidence/ | JSON/log evidence of that validation |
| annex/ | generated inventories (routes, tables, migrations, pages, modules, tests) and the generator scripts |

Evidence tags: **[V]** verified in code that day, **[R]** run in project sessions, **[D]** documented only, **[U]** unknown. No secret values appear in this dossier.
