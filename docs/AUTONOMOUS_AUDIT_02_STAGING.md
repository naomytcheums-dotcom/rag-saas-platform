# Audit autonome 02 — configuration staging

Rapport canonique : [STAGING_TEST_REPORT.md](./audit/STAGING_TEST_REPORT.md).
Décision : [RLS_STAGING_DECISION.md](./security/RLS_STAGING_DECISION.md).

Date : 2026-10-03. Aucun accès base réalisé. Résolution alternative IPv6
réussie, mais TCP `errno=10051`; résolution locale `11001`.
Configuration locale template, credential non provisionné, aucun fallback
vers production, aucune migration/extension/policy exécutée.

Les contrôles des FK/unique/check et comptes de tables sont **UNKNOWN** en
staging; seul l'inventaire ORM local est disponible.
Outils gardés et tests PostgreSQL préparés. Skips ≠ PASS live.
