# RESUME — état au 2026-10-13 (session Copilot « Bob »)

Dernière mise à jour : parcours Ollama exécuté, 3 défauts/limites trouvés, chantier billing relancé. Rien n'est fusionné dans `main` par cette session.

## Exécuté et prouvé (cette session)
| Quoi | Résultat | Preuve |
|---|---|---|
| Pile locale : Docker, `rag-test-pg`, Redis 26390, MinIO 9000, Mailpit, Ollama (qwen2.5:3b/7b, nomic-embed-text), API 8030 + worker Celery, base `rag_test_rag` à la révision 0144 (tête de cette branche ; la branche billing a une tête 0145) | démarrée | `docker ps`, `/health` = ok |
| Parcours complet `scripts/e2e_full_journey.py --base http://127.0.0.1:8030 --model qwen2.5:3b` (inscription → organisation → import de 7 formats → traitement asynchrone → recherche 4 stratégies → chat Ollama cité → réindexation → remplacement → suppression → isolation entre 2 organisations) | **64 réussis, 1 échec** | `journey_ollama_qwen2.5-3b_2026-10-13.json` |
| L'échec : « What was the third quarter revenue? » : la réponse est juste (« 4.2 million XAF ») mais le modèle 3B émet un jeton espace (« 4. 2 »), la vérification textuelle de « 4.2 » échoue | limite du modèle 3B, pas un défaut du code (jetons SSE capturés : `['4','.',' ','2']` émis par Ollama) | script de reproduction dans la session |

## Défaut produit trouvé et corrigé (avec test qui échoue sans le correctif)
- `bm25_search` renvoyait des chunks **sans aucun terme commun** avec la requête (score 0,0), et dans un très petit corpus un vrai résultat (score négatif) passait derrière un non-résultat. Corrigé dans `api/services/retrieval_pipeline.py`. Test : `tests/test_bm25_no_match.py` (4 réussis avec le correctif, 2 échecs sans). Voisins : 122 réussis (`test_retrieval_pipeline`, `test_metadata_filtering`, `test_chat_stream_policy_wiring`, `test_citation_validation`).

## Script d'ingestion/recherche : résultat PARTIEL (à relancer)
`scripts/e2e_rag_ingestion_search.py` (phases A et B) a duré plus d'une heure (corpus FastAPI : 121 pages sur 155 indexées en 4 017 s, worker `-P solo` sur CPU). Le jeton d'accès a expiré : les échecs `401` (suppression douce/définitive, mesures Recall = 0,0) **ne sont pas des résultats valides**. Corrigé : `scripts/rag_chain_lib.py` se reconnecte seul sur un 401 (vérifié sur l'API). **À refaire** : relancer le script, ou `scripts/e2e_retrieval_baseline.py` pour Recall@k/MRR/NDCG sur `data/test_set.json` (mesure de référence antérieure : Recall@5 0,91, Recall@10 1,00, MRR 0,69, NDCG@10 0,763).
Autres échecs réels de ce script, **non traités** :
1. Choisir un modèle d'embedding d'API sans clé (`openai/text-embedding-ada-002`, `cohere/embed-english-v3.0`) est accepté (HTTP 200) au lieu d'être refusé. À décider : refuser à l'enregistrement, ou accepter parce qu'une organisation peut avoir sa propre clé (BYOK).
2. Un modèle 768 dimensions non chargeable (hors ligne) fait passer le document en `failed` ; l'erreur est bien stockée (`indexing_error`) ; le script ne la lisait pas dans la liste. À vérifier côté interface.
3. Les échecs `AutoTokenizer` de 05:40 et 05:57 sont antérieurs au verrou `api/services/transformers_import.py` : non revus depuis.

## Chantier billing (`wt-billing`, branche `bob/auto-fix-20261013-billing`)
- Après installation de `stripe==11.4.1` (déclaré dans `requirements-api.txt`, absent du venv local) et de `S3_DOCUMENTS_BUCKET_NAME=documents` pour le MinIO local : `tests/test_billing_plans_limits_postgres.py` 42 réussis ; `tests/test_domains_email_postgres.py` 13 réussis après correction d'un test jamais exécuté (`probe(request)` sans annotation `Request` → 422).
- Preuves ajoutées dans `apply_fixes_overlay.py` pour 1.4.1, 1.4.5, 1.4.9, 5.3.10 (décision D19), 12.1.2, 12.1.6, 12.1.7, 12.1.8, 12.2.1–12.2.4, 12.3.1.
- **Non fait** : 12.1.10 (achat de crédits par Paystack non supporté, incohérence de devise BILL-018 : à vérifier), 12.2.5 (on-premise), régénération du CSV, PR, CI.

## Reste à faire (ordre recommandé)
1. billing : régénérer le CSV (`cd audit-reports/functional-audit-2026-10-10 && python apply_fixes_overlay.py && python apply_test_runs.py && python build_final_status.py`), commit, push, PR, CI bloquante verte, fusion (voir DANGER ci-dessous), puis 12.1.10 et 12.2.5.
2. infra : `terraform fmt/validate`, `helm lint/template`, `kubeconform`, `docker build`, `docker compose up` + health checks, couverture 13.1.6 (ma mesure : 85 %), test `test_celery_worker_workflow` à exécuter pour de bon.
3. external : voix (TTS local, VAD), recherche web, calendrier, TLS, traçage LLM, suivi d'erreurs, sonde de disponibilité ; `IMPLEMENTED_EXTERNAL_VALIDATION_REQUIRED` pour chaque fournisseur sans clé.
4. rag : relancer ingestion/recherche (phases A/B), puis `scripts/e2e_rag_chat_scenarios.py`, `scripts/e2e_rag_evalab.py`, vérification des correctifs de la PR #26.

## Pièges rencontrés
- Variables d'environnement requises en plus de `run_tests_local.sh` : `JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `AUDIT_LOG_HMAC_SECRET_KEY`, `SUPPORT_EMAIL`, `S3_DOCUMENTS_BUCKET_NAME=documents`, `SECRET_ENCRYPTION_KEY` (clé Fernet jetable), `HF_HUB_OFFLINE=1`. Sans HF hors ligne, un test peut échouer sur une erreur réseau (`WinError 10054`).
- Docker Desktop s'arrête parfois : le relancer (`Docker Desktop.exe`) puis `docker start rag-test-pg rag-test-redis rag-e2e-redis rag-e2e-mailpit rag-test-minio-9000 rag-test-ollama`.
- DANGER fusion : `main` lit `users.job_title` (0142) ; ne pas déployer `main` sur une base de production non migrée. Vérifier si Render/Vercel déploient automatiquement sur `main` avant toute fusion.
