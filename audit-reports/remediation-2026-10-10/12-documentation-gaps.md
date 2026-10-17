# 12 — Lacunes et contradictions de documentation

Référence prise : le code et les comportements vérifiés. Aucune exigence du cahier des charges n'a été supprimée.

| # | Document | Contradiction / lacune | Action | Statut |
|---|---|---|---|---|
| 1 | `agents.md` | endpoints `/api/eval/*` et `/mcp/v1/servers*` inexistants (0 sur 943 opérations), dossier `api/eval/` inexistant, Python 3.11 | réécrit avec les routes réelles + test de contrat `tests/docs/test_agents_md_routes.py` | FIXED |
| 2 | `render.yaml` | ne décrit que le prototype Streamlit | en-tête d'avertissement ; exemple de worker/beat dans `deploy/render.worker.example.yaml` ; la configuration réelle de l'API (tableau de bord Render) n'est pas versionnée | PARTIAL (BLOCKED_EXTERNAL pour décrire la production réelle) |
| 3 | `docs/CAHIER_DES_CHARGES.md` | « 515 fonctionnalités » non reproductible ; « 110 lignes » ≠ 150 ; Partie 15 tronquée ; « GitHub Actions désactivé » périmé | note d'audit sous l'en-tête (comptes mesurables) ; rien supprimé ; Partie 15 : source introuvable ⇒ à compléter par la propriétaire (ne pas reconstituer) | PARTIAL |
| 4 | `audit-reports/radiographie-2026-10-10/14_*.md` | liste des variables obligatoires incomplète (3 au lieu de 5) | corrigé ci-dessous (REM-015) | FIXED |
| 5 | Docker / CI | `docker-entrypoint.sh` décrit un worker embarqué non utilisé par `Dockerfile.api` | documenté dans `docs/devops/CELERY_WORKERS.md` | FIXED (doc) |
| 6 | README, ROADMAP, SDK docs | non relus ligne à ligne dans cette session | — | NOT_VERIFIED |
| 7 | Documentation API | `docs/api/openapi.json` régénéré (paramètre `verify_documents`) ; test d'égalité chemins existant | FIXED |
| 8 | Instructions de migration, lancement local, test, déploiement | pas de runbook unique | `14-deployment-runbook.md`, `docs/devops/SENSITIVE_SETTINGS.md`, `docs/devops/CELERY_WORKERS.md`, `docs/evaluation/RAG_EVALUATION.md` | FIXED (nouveaux documents) |
| 9 | Variables d'environnement | noms dispersés (`.env.example` 27 Ko, `config.py` 912 champs) | liste par nom dans l'audit `14_*` et le runbook ; inventaire automatique des 5 obligatoires | PARTIAL |
| 10 | Python | `agents.md` 3.11, Bandit en 3.11, Docker/CI 3.13 | `agents.md` corrigé ; workflow Bandit non modifié | PARTIAL |

Documents de travail et fichiers non suivis (`FGbms…`, `scripts/pending/`, `audit-reports/functional-audit-2026-10-10/` d'un autre agent) : **non touchés**.
