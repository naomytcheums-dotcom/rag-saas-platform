# SESSION CONTEXT — IBM Bob 2.0 Submission

## Project
- Name: IBM Bob 2.0 — RAG Evolution Factory
- Repo: https://github.com/naomytcheums-dotcom/rag-saas-platform
- Live: https://rag-saas-platform-rho.vercel.app
- API: https://rag-saas-api-sjsm.onrender.com

## Goal
Submit to IBM Bob 2.0 hackathon (lablab.ai). Deadline: 2026-09-27 15:00 UTC.

## The 4 Modes (the competition contract)
| Mode | MCP Tool | Underlying service |
|------|----------|-------------------|
| 1 FACTORY | create_rag_agent | api/models/agent.py |
| 2 GUARDIAN | run_eval_benchmark | api/services/evaluation_jobs.py |
| 3 AUTOPSY | get_failure_report | api/models/evaluation.py |
| 4 CHANGELAB | update_retrieval_config | Agent.knowledge_base_config |

## MCP Interface
- GET  /mcp/v1/tools              -> list 13 tools (4 IBM Bob + 9 builtin)
- POST /mcp/v1/tools/{name}/call  -> execute a tool
- Auth: X-API-Key header with mcp:tools scope

## What's DONE (commits)
- 32ece39: 4 MCP tools (api/services/mcp/builtin_tools.py)
- b7db49e: fix bug create_job -> create_evaluation_job
- c965699: README repositioned with IBM Bob as hero
- 30019c9: agents.md harmonized (Next.js 16, MCP endpoints)
- b1d3259: bob/ dedicated documentation (5 files)
- 57cbe54: docs/ibm_bob_2/SUBMISSION.md
- 8b65376: run example in ROADMAP.md
- 636593e: 7 screenshots in bob/evidence/screenshots/
- a65d6e5: tests/eval/dataset_demo.json (20 questions)

## Evidence (live tests)
- bob/evidence/json/ (10 files)
- bob/evidence/screenshots/ (7 files)
- bob/evidence/README.md (details)

## Demo dataset
- tests/eval/dataset_demo.json
- 20 questions
- 10 fail with top_k=5 (succeed with top_k=10)
- Categories: definition, comparison, how_to, troubleshooting

## Live tests already run (2026-09-25)
| # | Test | Result |
|---|------|--------|
| 1 | GET /mcp/v1/tools | OK, 13 tools |
| 2 | create_rag_agent (no org) | clean validation error |
| 3 | execute_sql_query (allowlist) | security enforced |
| 4 | create_rag_agent (fake org) | real INSERT + FK |
| 5 | get_failure_report | is_error: false |
| 6 | update_retrieval_config | "Agent not found" |
| 7 | run_eval_benchmark | bug found + fixed |

## What's LEFT
- [ ] Use IBM Bob (execute the demo script)
- [ ] Record video demo (2-3 min)
- [ ] Submit to lablab.ai
- [ ] Create final tag v1.0-ibm-bob-2.0 (ONLY at the very end)

## Tech stack
- Frontend: Next.js 16.3.4, React, TypeScript, TailwindCSS
- Backend: FastAPI, SQLAlchemy 2.0 async, PostgreSQL + pgvector
- Background: Celery + Redis
- LLM: litellm (Anthropic, OpenAI, Mistral, BYOK)
- Tests: pytest (314 files), Vitest
- MCP: server (outbound) + client (inbound)

## Key numbers
- 89 API routers
- 17 frontend sections
- 314 backend test files
- 52 RBAC permissions
- 36 CRM connectors
- 6 i18n languages (~4,200 translations)
- 118 Alembic migrations

## Rules to follow (learned)
- NEVER tag until the user says so (only at the very end)
- NEVER delete anything from the existing README
- ALWAYS keep Bob IBM as the hero, RAG as the underlying platform
- Use Python scripts (not heredoc) for complex text replacement
- Test live before committing
- Verify with pytest before pushing

## Next.js version
- package.json: 16.3.4 (verified)
- agents.md: 16 (corrected)
- README.md: 16 (corrected)
- Guide Gemini: 14 (WRONG, ignore)

## Contact
- User: naomytcheums-dotcom
- Email: test1@gmail.com
