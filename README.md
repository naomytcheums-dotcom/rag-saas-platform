# IBM BOB 2.0 — RAG EVOLUTION FACTORY

**An IBM Bob-powered autonomous engineering system that creates, evaluates, diagnoses and improves RAG agents through a closed-loop workflow.**

> **IBM Bob** is the autonomous engineering brain.
> **RAG Evolution Factory** is the orchestration system.
> **The RAG platform** is the real environment Bob operates, measures and evolves.
> **MCP** is the control interface between Bob and the platform.

🌐 **Live demo**: https://rag-saas-platform-rho.vercel.app
🔧 **Live API**: https://rag-saas-api-sjsm.onrender.com
📖 **Submission doc**: [docs/ibm_bob_2/SUBMISSION.md](docs/ibm_bob_2/SUBMISSION.md)

---

## The closed loop

```
+----------------------+
|     IBM BOB 2.0      |
|  Autonomous Engineer |
+----------+-----------+
           |
           v
+-------------------------+
|   RAG EVOLUTION FACTORY |
+------------+------------+
             |
   +---------+---------+---------+
   v         v         v         v
+---------+ +----------+ +---------+ +------------+
| FACTORY | | GUARDIAN | | AUTOPSY | | CHANGELAB  |
+---------+ +----------+ +---------+ +-----+------+
                                           |
                                    tests + benchmark
                                           |
                                           v
                                 +------------------+
                                 | KEEP / ROLLBACK  |
                                 +--------+---------+
                                          |
                                          v
                                      GUARDIAN
```bash
git clone https://github.com/naomytcheums-dotcom/rag-saas-platform.git
cd rag-saas-platform
cp .env.example .env
./install.sh
docker compose -f docker-compose.selfhosted.yml up -d
SaaS (Vercel + Render)
Frontend: https://rag-saas-platform-rho.vercel.app

Backend: https://rag-saas-api-sjsm.onrender.com

Documentation
Full documentation lives under docs/ — start at docs/index.md:

docs/user/ — end-user guides

docs/admin/ — org + platform administration

docs/developer/ — architecture, API, SDKs, webhooks

docs/install/ — deployment, environment, upgrades, backups

docs/api/ — REST API, OpenAPI, Swagger, Redoc

docs/advanced/ — RAG pipeline internals

docs/diagrams/ — architecture, database, RAG, auth, deployment

docs/ibm_bob_2/SUBMISSION.md — IBM Bob 2.0 submission document

agents.md — IBM Bob 2.0 contract (10 sections)

See also:

ARCHITECTURE.md — system-level overview

ROADMAP.md — what's planned + [Bob-Auto-Fixes]

GLOSSARY.md — platform-specific terminology

Tests
bash
pytest tests/ -x
pytest tests/eval/ -x
ruff check api/
cd frontend && npm run type-check
314 backend test files, all green.

Internationalization
6 languages: English (default), French, Spanish, German, Portuguese, Arabic

~4,200 translations in locales/

i18n system: custom (frontend/lib/i18n.tsx), backend (api/services/i18n.py)

License
MIT — see LICENSE.

Project history
Built incrementally across 25 documented development parts, each with its own audit, real (never fabricated) test results, and honest documentation of gaps and limitations.

The full history is in docs/CAHIER_DES_CHARGES.md.

IBM Bob 2.0 integration (Phase 5): see ROADMAP.md.

Contributing
See CONTRIBUTING.md and CODE_OF_CONDUCT.md. Security issues should be reported per SECURITY.md.

IBM Bob 2.0 Submission — 2026
