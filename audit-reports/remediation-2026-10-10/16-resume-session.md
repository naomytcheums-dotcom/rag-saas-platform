# 16 — Point de reprise

- Branche : `bob/auto-fix-20261010-1555` (locale, non poussée). Fichiers non suivis à ne pas toucher : `FGbmsPryLaJXqu5hfC24RTZe`, `scripts/pending/`, `audit-reports/functional-audit-2026-10-10/` (autre agent).
- Git : `C:\Program Files\Git\cmd\git.exe` (pas dans le PATH).
- Suite complète : `D:\rag-work\audit-scripts\full_suite.txt` ; `full_suite_time.txt` n'existe qu'à la fin. À lire : passés/échecs/ignorés, puis corriger ce qui vient du code sans toucher aux assertions.
- Base jetable : conteneur `rag-pr1-disposable-pg`, bases `rag_remediation_scratch` (migrée `0137`), `rag_sec_roundtrip`, `isolated_tests` ; tests opt-in avec `RAG_DISPOSABLE_PG_URL` et `RAG_DISPOSABLE_PG_CONFIRM` = nom de la base.
- Scripts de génération des CSV : `D:\rag-work\audit-scripts\` (`register.py`, `reconcile.py`, `preserve.py`…).
- Non traité : retries/backoff par tâche, verrou Redis pour tâches périodiques, vérification des constats NOT_VERIFIED, IDOR par identifiant (REM-021), migration de dérive ORM ↔ schéma, tests pgvector, benchmark RAG.
- Autorisations à demander : push (CI), accès hébergeur, nettoyage des comptes de test, décisions remboursement/devise, budget benchmark.
