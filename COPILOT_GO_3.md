# COPILOT — MISE À JOUR DU 2026-10-20 : l'état que tu décris est périmé. Lis ceci, puis TRAVAILLE.

Réponds en français. Ne réécris pas de prompt, de plan ni de rapport de préparation. Ta sortie utile = code, tests exécutés avec résultat, commits, pushs. Les règles de `COPILOT_GO.md` restent valables (jamais le `.env`, jamais une migration existante modifiée, jamais `--force`, jamais de secret, un mock n'est jamais présenté comme un vrai service). Le reste de `COPILOT_GO.md` / `COPILOT_GO_2.md` qui parle de « ouvrir les PR », « jeton gh » ou « 47 restantes » est **obsolète**.

## 1. Ce qui est déjà fait (ne le refais pas)
Une autre session (Claude Code) a ouvert **et fusionné dans `main`** les PR #26, #28 (facturation), #29 (rag), #30 (fournisseurs externes), #31 (infra), #32 (rag, test de plan) et #33 (portage des lots A–F : mode aperçu, /metrics fail-closed, bornes Celery, job CI PostgreSQL, adaptateur SQuAD, outillage de test). Toutes avaient leurs contrôles bloquants verts (`backend-tests`, CircleCI `api-tests`, `frontend-checks`, `build-*`; `mypy`/`bandit`/`snyk` sont non bloquants). **Tout ton travail local est donc déjà sur GitHub dans `main`** : tu n'as plus de PR à ouvrir pour ces branches et tu n'as **pas besoin du jeton GitHub** pour elles. Fais `git fetch origin && git checkout -B <ta-branche> origin/main` avant tout nouveau travail.
- Le pilote RLS (`4b4063b`, migration 0137 en collision) est **volontairement exclu** (sauvegardé sur la branche `bob/auto-fix-20261010-1555`). Ne le réintègre pas sans une migration renumérotée (≥ 0146), un rôle dédié au lieu de `TO PUBLIC`, et `FORCE`.
- Migrations à appliquer par la propriétaire sur sa base de production : 0143, 0144, 0145. Il y a une seule tête Alembic (`0145`).

## 2. État du catalogue (ne compte pas de mémoire)
Régénère-le d'abord : `cd audit-reports/functional-audit-2026-10-10 && python apply_fixes_overlay.py && python apply_test_runs.py && python build_final_status.py`, puis lis `01c-feature-verification-after-test-runs.csv` (colonne `status_final`). Au dernier relevé (avant les fusions #31/#32) il restait **39 fonctionnalités** :
- **18 `IMPLEMENTED_EXTERNAL_VALIDATION_REQUIRED`** (code + tests de contrat terminés, validation réelle impossible sans les clés de la propriétaire) : 1.4.3 4.1.1–4.1.4 4.2.1–4.2.3 5.2.2 5.2.7 5.2.8 5.4.11 9.4.1–9.4.3 10.3.9 12.1.10 13.5.8. Ne les retouche pas, sauf pour exécuter `scripts/validate_<fournisseur>_live.py` si une clé de test apparaît dans l'environnement du processus.
- **4 `WRITTEN_NOT_EXECUTED`** : 10.1.14 (chiffrement au repos sur MinIO), 13.1.6 (couverture ≥ 90 %), 14.2.7 et 14.3.2 (enregistrer la démo).
- **14 `VALIDATED_NOT_DEPLOYED`** : 10.4.7–10.4.11, 13.4.6–13.4.8, 13.4.10–13.4.12 + 13.4.4/13.4.5/13.4.9. Terraform fmt/validate (aws/azure/gcp), helm lint/template, kubeconform et `docker build` sont déjà validés ; reste `docker compose up` de la pile « tenant dédié » avec health checks. Pas de déploiement cloud réel (comptes de la propriétaire).

## 3. Ce que TOI tu dois faire maintenant (ordre)
Docker a été remis à neuf (disque virtuel recréé, 65 Go libres, **aucune image, aucun modèle Ollama, aucune donnée Airbyte**). Internet est lent (~0,1 Mo/s) : évite les gros téléchargements ; essaie d'abord un petit modèle (`qwen2.5:1.5b` ou `qwen2.5:0.5b`) pour les scénarios de plomberie, le `qwen2.5:3b` (1,9 Go) seulement en arrière-plan pour les mesures de qualité.
1. **Pile de test** : vérifie `docker ps` (PostgreSQL 25432, Redis 26379/26390, MinIO 9000). Si ClamAV manque, ignore-le sauf pour les tests antivirus. Applique `python -m alembic upgrade head` sur une base dont le nom contient « test ».
2. **Les 19 tests ignorés de `tests/test_s3_encryption_e2e.py` et `tests/test_deploy_dedicated_tenant_e2e.py`** : lance-les pour de vrai (image MinIO : variable `MINIO_TEST_IMAGE`, voir le message de skip ; sinon `docker pull` de l'image indiquée). Corrige ce qui casse, enregistre la preuve (10.1.14).
3. **`docker compose` de `deploy/dedicated-tenant/`** : `up`, health checks, `down` (13.4.x / 10.4.x). Preuve dans `apply_fixes_overlay.py` seulement si exécuté (préfixe « tests pass »).
4. **Couverture 13.1.6** : `pytest tests/ --cov=api --cov-report=term-missing` par lots (RAM limitée), écris de vrais tests sur les modules les moins couverts jusqu'à 90 % ou documente le chiffre mesuré.
5. **Parcours Ollama de bout en bout** : `scripts/test_env/rag_stack_env.sh` / `rag_stack_start.sh` (API 8030, worker Celery propre), puis `scripts/e2e_full_journey.py`, `scripts/e2e_rag_ingestion_search.py`, `scripts/e2e_rag_chat_scenarios.py`, `scripts/e2e_rag_evalab.py` (re-login automatique corrigé ; les organisations de test doivent être sur le plan Enterprise depuis la migration 0145). Scénarios : ingestion en échec puis reprise, Ollama coupé puis rétabli, deux organisations sans fuite, utilisateur sans permission, documents contradictoires, question sans réponse, conversations simultanées, réindexation après modification, suppression avec nettoyage vérifié en base. Mesure Recall@k/MRR/NDCG sur `data/test_set.json` sans jamais modifier les réponses attendues.
6. **Démo (14.2.7, 14.3.2)** : utilise le recordeur Playwright ajouté par la PR #31 (voir `docs/` et `scripts/` pour son nom exact) sur la pile en marche.
7. **Petits défauts connus** : 5 avertissements `ruff F841` (variables inutilisées) dans `scripts/e2e_rag_chat_scenarios.py`, `scripts/e2e_rag_evalab.py`, `tests/test_billing_plans_limits_postgres.py` (3) : corrige-les sans changer l'intention des tests.
8. Pour chaque point fermé : preuve dans `apply_fixes_overlay.py`, régénération du CSV avec les 3 scripts, commit, push **sur une nouvelle branche** `bob/auto-fix-20261020-<sujet>` (jamais `main`), pull/rebase avant push (une autre session pousse sur le même dépôt).

## 4. Pour ouvrir/fusionner une PR
Tu n'as pas de jeton `gh`. Pousse la branche et donne à la propriétaire le lien `https://github.com/naomytcheums-dotcom/rag-saas-platform/pull/new/<branche>`. La fusion est faite par Claude Code (qui a `gh`) une fois les contrôles bloquants verts ; ne demande pas de jeton à la propriétaire.

## 5. Garde-fous machine (la propriétaire a perdu des fenêtres et du travail à cause de redémarrages)
- Ne redémarre jamais Windows, ne lance pas `wsl --shutdown`, ne tue pas Docker Desktop sans l'accord explicite de la propriétaire, et ne supprime jamais `docker_data.vhdx`.
- `.wslconfig` (8 Go RAM / 2 Go swap), `daemon.json` (journaux 3×10 Mo, cache de build 5 Go) et `scripts/docker_space_guard.ps1` (tâche hebdomadaire) sont en place : ne les contourne pas. Si le disque C: passe sous 15 Go, arrête-toi et préviens.
- Pas de `docker volume prune`, pas de `docker system prune -a`.

## 6. Message final
Liste des identifiants fermés avec preuve (commande + résultat observé), ce qui reste et pourquoi (clés fournisseurs, comptes cloud), défauts trouvés/corrigés, branches poussées, commandes de reproduction. Rappelle à la propriétaire : régénérer la clé de chiffrement collée dans un ancien chat ; appliquer 0143–0145 sur sa base ; variables Render (`ENCRYPTION_MASTER_KEY`, `COOKIE_SECURE=true`, `CREDITS_ALLOW_UNPAID_TOPUP=false`), worker + beat.

**Premier geste : `git fetch origin`, régénère le catalogue, puis la section 3, point 1. Maintenant.**
