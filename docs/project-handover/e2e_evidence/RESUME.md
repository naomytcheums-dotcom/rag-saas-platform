# RESUME — état au 2026-10-20 (branche `bob/auto-fix-20261020-validation`, partie de `main` au commit `711aebb`)

Les PR #26 à #33 sont dans `main` (travail précédent). Cette branche contient les validations et tests de la session du 2026-10-20. **Aucune PR n'est ouverte** pour elle : lien `https://github.com/naomytcheums-dotcom/rag-saas-platform/pull/new/bob/auto-fix-20261020-validation`.

## Catalogue (514 lignes, régénéré avec les 3 scripts)
VERIFIED_COMPLETE 283, FIXED_AND_TESTED 150, DECISION_OR_CORRECTION 46, IMPLEMENTED_EXTERNAL_VALIDATION_REQUIRED 18, VALIDATED_NOT_DEPLOYED 14, WRITTEN_NOT_EXECUTED 3.
Restent : **10.1.14 fermé** (cette session) ; 13.1.6 (couverture), 14.2.7 et 14.3.2 (démo) toujours « non exécutés » ; 14 « validés non déployés » (10.4.7–10.4.11, 13.4.4–13.4.12) ; 18 validations externes (clés fournisseurs de la propriétaire).

## Exécuté et prouvé aujourd'hui
| Id | Résultat observé |
|---|---|
| 10.1.14 chiffrement au repos | `tests/test_encryption_at_rest_e2e.py` + `test_encryption.py` + `test_s3_encryption_e2e.py` : 18 réussis sur un vrai MinIO (couche applicative ; le chiffrement disque de Supabase n'est pas vérifiable ici) |
| Test Celery (phase 6 PR #26) | `tests/test_celery_worker_workflow.py` : 10 réussis sous Windows ; un doublon tronqué (reste de fusion) qui masquait le vrai test a été retiré |
| Lint | `ruff check api tests scripts` : propre (5 F841 + 1 F811 corrigés) |
| Terraform / Helm / Kubernetes / `docker build` | `fmt -check`, `validate` (aws, azure, gcp), `helm lint` + `template` (3 variantes), `kubeconform` (11 ressources) : réussis ; `app.yaml` DigitalOcean : seul `doctl apps spec validate` (compte requis) la valide pour de vrai |

## Couverture (13.1.6) — chiffre de référence 85,4 % (mesure du 2026-10-12, 49 442 instructions) ; **non re-mesuré**
Tests ajoutés (mesure par module avec `--cov`) : tâches Celery sur PostgreSQL réel (`tests/test_tasks_pg_*.py`, `tests/pg_tasks_support.py`) : api_key_maintenance 100 %, ab_tests 99 %, sales 95 %, analytics 100 %, notifications 100 %, plugins 79 %, workflows 69 %, billing 97 %, compliance 98 %, integrations 99 %, external_source_sync 99 %, fine_tuning 100 % ; clients HTTP contre faux serveurs locaux : airbyte_client 100 % (`tests/test_airbyte_client_contract.py`), billing_paystack (partie REST, `tests/test_paystack_client_contract.py`). Total ≈ 800 instructions de plus ; il en faut ≈ 2 300 pour atteindre 90 %.
Modules encore peu couverts (référence 2026-10-12) : `security/documents.py` (315 manquantes), `routers/crm.py` (242), `tasks/media.py` (95), `tasks/autonomous_agents.py` (78), `services/metadata_filtering.py` (70), `tools/email_tools.py` (66), `services/notifications.py` (58), `security/plugin_sandbox.py` (47), `security/loki_handler.py` (38), `services/alerting.py` (38), `security/ssl_certificates.py` (36), `tools/calendar_tools.py` (35).
Mesure complète à faire (longue : ~6 h) par lots : `pytest tests/ --cov=api --cov-report=term-missing` avec `--cov-append`, base de test jetable, `HF_HUB_OFFLINE=1`.

## Reste à faire, dans l'ordre
1. **Tenant dédié (10.4.x, 13.4.x)** : `docker build -f Dockerfile.api -t rag-saas-api:infra-test .` est en cours (téléchargements à ~0,1 Mo/s : plusieurs heures ; journal `C:\Users\NITROV15\rag-work\rag-logs\docker_build_api_final.txt`). Quand l'image existe : `RUN_DEPLOY_E2E=1 DEDICATED_IMAGE=rag-saas-api:infra-test HF_CACHE_DIR=~/.cache/huggingface sh scripts/run_tests_local.sh tests/test_deploy_dedicated_tenant_e2e.py -q`. Sans Ollama dans Docker, l'étape « réponse » est ignorée.
2. **Démo (14.2.7, 14.3.2)** : `scripts/demo/record_demo.mjs` exige API + worker + frontend (`next dev --webpack`) + Ollama avec un modèle, plus `cd e2e && npm ci`. Docker est neuf : il n'y a plus d'image Ollama ni de modèle ; tout se télécharge (`ollama/ollama` ~1,4 Go, `qwen2.5:0.5b` ~0,4 Go, `qwen2.5:3b` 1,9 Go). `frontend/node_modules` existe seulement dans le checkout principal (autre session) : ne pas y toucher ; le recréer par `npm ci` ou par une jonction `mklink /J`.
3. **Couverture** : continuer les modules ci-dessus, puis mesure complète.
4. **Parcours Ollama (phase 2)** : relancer `scripts/e2e_full_journey.py`, `e2e_rag_ingestion_search.py`, `e2e_rag_chat_scenarios.py`, `e2e_rag_evalab.py` quand Ollama et un modèle sont revenus.

## Environnement / pièges
- **Disque** : le disque virtuel de Docker avait grossi à 47 Go, il a été supprimé et recréé (2026-10-19). Garde-fous en place : `~/.wslconfig` (8 Go RAM, 2 Go swap), `~/.docker/daemon.json` (journaux 3×10 Mo, cache de build 5 Go), `scripts/docker_space_guard.ps1` (tâche hebdomadaire `RagSaas-DockerSpaceGuard`). Ne jamais lancer `docker system prune -a`, `docker volume prune`, `wsl --shutdown` sans accord ; si C: < 15 Go, s'arrêter.
- **Internet ≈ 0,11 Mo/s** : éviter tout gros téléchargement non nécessaire.
- Pile de test : `rag-test-pg` (25432, base `pytest_p0` à la tête **0145**), `rag-test-redis` (26379), `rag-test-minio-9000` (9000, buckets `documents`, `avatars`, `voice` créés). ClamAV : image non téléchargée (délai TLS) ; seuls les tests antivirus en ont besoin.
- Variables à fournir en plus de `scripts/run_tests_local.sh` : `JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `AUDIT_LOG_HMAC_SECRET_KEY`, `SUPPORT_EMAIL`, `S3_DOCUMENTS_BUCKET_NAME=documents`, `SECRET_ENCRYPTION_KEY` (clé Fernet jetable), `ENCRYPTION_MASTER_KEY` (32 octets en base64 urlsafe, jetable), `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. Mot de passe PostgreSQL : `docker exec rag-test-pg printenv POSTGRES_PASSWORD` (jetable, local).
- Les tests `tests/test_tasks_pg_*.py` se sautent seuls si `DATABASE_URL` n'est pas un PostgreSQL joignable.
- `gh` n'est pas connecté sur cette machine : la fusion se fait via Claude Code ou à la main sur GitHub.

## À rappeler à la propriétaire
Régénérer la clé de chiffrement collée dans un ancien chat ; appliquer les migrations 0143–0145 sur la base de production après sauvegarde ; variables Render (`ENCRYPTION_MASTER_KEY`, `COOKIE_SECURE=true`, `CREDITS_ALLOW_UNPAID_TOPUP=false`), worker Celery + beat.
