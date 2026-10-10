# Deliverables

Rebuild the PDFs with `python scripts/build_deliverable_pdfs.py` (needs Chrome or Edge installed).

| File | Source |
|---|---|
| architecture.pdf, deployment-guide.pdf, api-documentation.pdf, setup-guide.pdf, benchmark-report.pdf | the Markdown documents under `docs/` and `deploy/` |
| security-audit.pdf | `docs/SECURITY_REPORT.md` and the 2026-10-10 audit reports |
| feature-list.pdf | `audit-reports/functional-audit-2026-10-10/01-feature-verification.csv` (rebuilt after each audit update) |
| product-tour.mp4 | 40-second silent tour made from the screenshots in `docs/screenshots/`, taken on an isolated local database with a throw-away demo account (see `scripts/dev_isolated_server.py`) |

The benchmark report contains no answer-quality figures because none has been measured yet on a real dataset.
