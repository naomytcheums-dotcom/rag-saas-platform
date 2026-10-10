# 16 — Point de reprise

- Branche : `bob/auto-fix-20261010-1555` (locale, non poussée). Fichiers non suivis à ne pas toucher : `FGbmsPryLaJXqu5hfC24RTZe`, `scripts/pending/`, `audit-reports/functional-audit-2026-10-10/` (autre agent).
- Git : `C:\Program Files\Git\cmd\git.exe` (pas dans le PATH).
- Suite complète terminée (voir `10-test-results.md`) : 6037 passés, 3 échecs d'environnement rejoués verts, 194 ignorés.
- Base jetable : conteneur `rag-pr1-disposable-pg`, bases `rag_remediation_scratch` (migrée `0137`), `rag_sec_roundtrip`, `isolated_tests` ; tests opt-in avec `RAG_DISPOSABLE_PG_URL` et `RAG_DISPOSABLE_PG_CONFIRM` = nom de la base.
- Scripts de génération des CSV : `D:\rag-work\audit-scripts\` (`register.py`, `reconcile.py`, `preserve.py`…).
- Non traité : retries/backoff par tâche, verrou Redis pour tâches périodiques, vérification des constats NOT_VERIFIED, IDOR par identifiant (REM-021), migration de dérive ORM ↔ schéma, tests pgvector, benchmark RAG.
- Autorisations à demander : push (CI), accès hébergeur, nettoyage des comptes de test, décisions remboursement/devise, budget benchmark.
