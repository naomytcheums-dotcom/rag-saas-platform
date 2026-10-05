# Audit autonome 04 — tests IDOR PostgreSQL préparés

Date : 2026-10-03. **BLOCKED_EXTERNAL**, aucun IDOR PostgreSQL exécuté.

Fichiers :

- `tests/staging_support.py` : cible exacte, deux tenants/users et ressources,
  transaction externe avec savepoints, rollback à fermeture.
- `tests/test_staging_idor.py` : GET document A/B et test RLS rôle restreint,
  contexte absent, contextes A/B et tentative de déplacement refusée.
- `tests/test_staging_full_idor.py` : huit GET représentant document, agent,
  workflow, conversation, évaluation, média, MCP, facture, plus agent card
  A2A avec deux API keys réellement créées dans la transaction.

Chaque test HTTP exige d'abord un owner control 200 : un 404 de route
inexistante ne peut pas constituer un PASS d'isolation.
Cela ne couvre pas toutes les méthodes/routes ni tous les tools MCP/A2A.

Activation via `scripts/staging_validate.py tests --execute` seulement;
`RAG_STAGING_TESTS=YES` et URL settings exacte exigés par fixture.
Sans opt-in : 11 cas skippés explicitement, aucun SQLite de substitution.

Lecture API (rôle postgres) et RLS (rôle non-BYPASS) sont preuves distinctes.
Dernière validation locale des outils/config/loader : 18 passed; 11 cas live
skippés. Réseau et credential restent bloquants selon le
[rapport staging](./audit/STAGING_TEST_REPORT.md).
