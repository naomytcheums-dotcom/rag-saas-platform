# 14 — Runbook de déploiement et de rollback

**Aucun déploiement n'a été exécuté.** Procédure à faire valider avant usage. Chaque étape distante est une action de la propriétaire (ou autorisée explicitement).

## 0. Pré-requis (local, sans risque)
1. Branche `bob/auto-fix-20261010-1555` à jour, `ruff check api` propre, `cd frontend && npx tsc --noEmit && npx eslint . && npx vitest run`.
2. Tests : suite backend (CI GitHub + CircleCI) verte **et** job `backend-postgres-tests` vert (nouveau : à valider au premier push autorisé).
3. Revue du diff des migrations `0136` et `0137` (additives) ; **ne jamais modifier une migration existante**.
4. Variables : tableau « nom → définie ? » (jamais les valeurs) contre `docs/devops/SENSITIVE_SETTINGS.md` et `14_ENVIRONNEMENTS_ET_DEPENDANCES.md` de l'audit.

## 1. Staging d'abord (jamais directement la production)
1. Base de staging distincte (copie restaurée d'une sauvegarde récente si possible).
2. `DATABASE_URL` = connexion de **migration** (session mode, port 5432) ; `RAG_RUN_MODE` non défini.
3. `python -m alembic current` → noter la version ; `python -m alembic upgrade head` ; **si échec : arrêt** (ne pas modifier la migration en échec ; en créer une nouvelle, la tester sur une base jetable, puis relancer).
4. Vérifier : `select version_num from alembic_version` = `0137` ; `select count(*) from pg_policies where schemaname='public'` = 6.
5. Démarrer API + worker + **un seul** beat ; `GET /health/ready` ; `celery -A api.tasks.celery_app inspect ping`.
6. Parcours de recette : inscription (compte de test), organisation, upload + ingestion, chat avec citations, crédit/facture (mode test fournisseur), suppression RGPD d'un compte de test.

## 2. Production (autorisation explicite requise)
1. **Sauvegarde** fraîche (voir `05-backup-restore.md`) et notée (heure, identifiant).
2. Fenêtre de faible trafic ; annoncer.
3. Migrations : `alembic upgrade head` par vous, depuis une machine de confiance, avec la connexion de migration ; **jamais** depuis l'API au démarrage. Condition d'arrêt : toute erreur ⇒ stop, ne pas relancer en boucle. `api/alembic/env.py` exécute **toutes les migrations en attente dans une seule transaction** (DDL transactionnel PostgreSQL, pas de `transaction_per_migration`) : un échec annule en principe le lot entier ; vérifier quand même `alembic current` avant de décider d'une restauration.
4. Déployer l'API (image `Dockerfile.api`), puis le worker, puis le beat (instance unique).
5. Variables à vérifier avant ouverture : `CREDITS_ALLOW_UNPAID_TOPUP=false`, `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS=false`, `COOKIE_SECURE=true`, `METRICS_AUTH_TOKEN` défini et `METRICS_REQUIRE_AUTH=true`, `MCP_STDIO_ENABLED=false`, `RAG_RUN_MODE` **non défini**.
6. Vérifications post-déploiement : `/health/ready`, une requête authentifiée, un upload de test, `inspect ping`, logs sans erreur 5xx, `/metrics` répond 401 sans jeton.

## 3. Rollback
| Situation | Action |
|---|---|
| Régression applicative sans changement de schéma | redéployer l'image précédente (API, puis worker) |
| Politiques `0137` gênantes | `alembic downgrade -1` (supprime uniquement les 6 politiques ; aucune donnée) ; vérifié sur base jetable |
| `0136` (table `notification_templates`) | `alembic downgrade -1` après `0137` (supprime la table : seulement si elle est vide ou sauvegardée) |
| Schéma incohérent / perte de données | restauration dans une **nouvelle** base (checklist de `05-backup-restore.md`), bascule de `DATABASE_URL`, redémarrage |
| Tâches périodiques en double | arrêter le second beat ; vérifier les factures et rappels de la période |

## 4. Aperçu local sans risque
```
set RAG_PREVIEW_DATABASE_URL=postgresql+asyncpg://user:pw@127.0.0.1:15432/rag_preview   # base locale jetable
.venv\Scripts\python.exe scripts\run_local_preview.py --check      # valide l'isolation, ne démarre rien
.venv\Scripts\python.exe scripts\run_local_preview.py --port 8000  # démarre l'API sur 127.0.0.1 uniquement
```
Le lanceur n'hérite d'aucune variable de service du shell, ne charge pas `.env`, neutralise Redis/S3/e-mail/paiements/LLM ; `RAG_RUN_MODE=preview` fait refuser le démarrage de tout processus dont la configuration atteindrait un service réel. Le schéma doit être appliqué par vous sur cette base locale (`alembic upgrade head` avec la même variable).

## 5. CI
`ci.yml` : `backend-tests` (SQLite + Redis, 75 min), `backend-postgres-tests` (nouveau), `backend-security` (pip-audit), builds et checks frontend. CircleCI : `api-tests` (~55 min, sensible à la durée et à la stabilité de MinIO), `rag-pipeline-regression`.
