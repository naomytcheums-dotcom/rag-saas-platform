# full-suite-results.md — RÉSULTAT FINAL VÉRIFIÉ (suite complète rejouée de bout en bout)

Dernière mise à jour : 2026-10-12. Vocabulaire : **PASS_VERIFIED**, **FAIL_VERIFIED**, **BLOCKED_INFRASTRUCTURE**, **NOT_RUN_EXTERNAL_DEPENDENCY**, **HISTORICAL_RESULT_UNVERIFIED** (annoncé pendant la session, sortie brute perdue avec `D:`), **NOT_RUN**.
Preuves hors dépôt : `C:\Users\NITROV15\rag-test-evidence\2026-10-11\` (`run1\`, `run2\`, `run3\`, `raw\`).

## 0. Résultat final (PASS_VERIFIED) sur le commit `c161b83`
Commande : `.\scripts\test_env\Run-IsolatedBatches.ps1 -OutDir …\run3` (pile locale 127.0.0.1, `RAG_STRICT_SKIPS=1`, worker Celery réel, Tesseract + poppler, aucune nouvelle tentative automatique). Début 08:06, fin 10:56 (2 h 50). Les 8 lots ont tous le **code de sortie 0** (`run3\progress.txt`).
| Lot | Fichiers | Passés | Ignorés | Échecs / erreurs |
|---|---|---|---|---|
| B1 (`tests/backend`, `tests/docs`) | 34 | 510 | 0 | 0 |
| B2 (`test_a`…`test_c`) | 116 | 1465 | 8 | 0 |
| B3 (`test_d`…`test_i`) | 82 | 1191 | 4 | 0 |
| B4 (`test_j`…`test_o`) | 54 | 638 | 3 | 0 |
| B5 (`test_p`…`test_r`) | 110 | 1282 | 1 | 0 |
| B6 (`test_s`…`test_z`) | 89 | 1147 | 11 | 0 |
| B7 (attrape-tout) | 1 | 9 | 0 | 0 |
| B8 (les 7 fichiers que la CI ignore) | 7 | 75 | 0 | 0 |
| **Total suite principale** | 493 | **6317** | **27** | **0** |
Les 27 ignorés sont **tous** des dépendances externes documentées (`tests/external_skip_allowlist.py`) : Stripe 4, Paystack 4, Google Drive 4, OneDrive 2, Notion 1, staging hébergé 12 (11 + `test_rls_policies_exist_on_staging`). En mode strict, tout autre skip aurait été un échec. **Ils ne sont pas comptés comme réussis.**
**Tests réseau (`network_flaky`, désélectionnés par défaut) : 23 passés**, lancés à part (`Run-IsolatedSuite.ps1 -Network`, code 0, `raw\network-run.xml`, le 2026-10-11 après `run2` ; quota GitHub 57 requêtes restantes avant, aucun jeton). Ce passage précède mes derniers commits, qui n'ont pas touché le code qu'il exerce (extraction GitHub / import) : il n'a pas été rejoué sur `c161b83`.
Réconciliation : 6317 + 27 + 23 = **6367** = 6348 collectés au départ + 19 tests ajoutés pendant la reprise (13 `test_live_test_runner`, 4 `test_system_log_handler_dedupe`, 1 `test_celery_worker_workflow`, 1 `test_isolated_test_runner`). Aucun test supprimé, aucune exclusion ajoutée, aucune assertion retirée.
Réserves : (1) cette passe vérifie les tests sur **PostgreSQL 17 / Redis 7 / MinIO locaux** ; ce n'est pas la production (rôle de base, pooler, quotas). (2) Les 27 tests externes restent **non exécutés**. (3) Le premier passage de ce lot (`run1`, 6295 passés / **3 échecs** / 27 ignorés) a révélé les trois échecs corrigés ensuite (voir `test-failures.csv`, V01-V03) ; `run2` (B2, B4, B5 rejoués : 0 échec) puis `run3` confirment. (4) Aucune CI GitHub / CircleCI n'a été exécutée sur cette branche (rien poussé).

---

# Rapport antérieur de ce fichier (état au 2026-10-11 07:30, conservé pour la traçabilité)

Dernière mise à jour : 2026-10-11 (07:30). Vocabulaire : **PASS_VERIFIED**, **FAIL_VERIFIED**, **BLOCKED_INFRASTRUCTURE**, **NOT_RUN_EXTERNAL_DEPENDENCY**, **HISTORICAL_RESULT_UNVERIFIED** (annoncé pendant la session, sortie brute perdue avec `D:`), **NOT_RUN** (réalisable, pas encore lancé).
Aucun résultat historique n'est présenté comme vérifié. Les sorties vérifiées sont dans `C:\Users\NITROV15\rag-test-evidence\2026-10-11\raw\` (hors dépôt).

## 1. Inventaire exact des tests (PASS_VERIFIED : collecte réelle)
Commande : `Run-IsolatedSuite.ps1 -PytestArgs --collect-only,-q,-o,addopts=,--continue-on-collection-errors,-p,no:cacheprovider` (lanceur isolé, `RAG_STRICT_SKIPS=1`), code de sortie 0, 2 min 26 s, fichier `collect-all.txt`.
**6348 tests collectés dans 490 fichiers, 0 erreur de collecte.** `-o addopts=` retire la désélection `network_flaky` ; aucun `--ignore`.

### Réconciliation avec le premier passage complet (17:42-20:15, résultat HISTORICAL_RESULT_UNVERIFIED)
| Ligne | Tests |
|---|---|
| passés | 6037 |
| échoués | 3 |
| ignorés | 194 |
| désélectionnés (`network_flaky`) | 23 |
| **total du premier passage** | **6257** |
| tests que j'ai ajoutés depuis (`test_isolated_test_runner` 10, `test_postgres_system_log_handler` 3, 3 tests du snapshot de prix) | + 16 |
| tests des 7 fichiers exclus par `--ignore` (CI et premier passage) | + 75 |
| **total attendu** | **6348** |
Le total mesuré (6348) égale la somme : la réconciliation est arithmétiquement cohérente (les 6257 viennent de chiffres annoncés, donc cette cohérence n'est pas une preuve indépendante du premier passage).

### Exclusion jamais signalée jusqu'ici : 7 fichiers `--ignore`
`ci.yml` (job `backend-tests`) et mon premier passage excluaient ces fichiers (prototype « legacy » sous `src/`). Ils ne sont **ni** dans les 194 ignorés **ni** dans les 23 désélectionnés : c'est une troisième exclusion, silencieuse.
| Fichier | Tests collectés | Statut |
|---|---|---|
| `sdks/python/tests/test_client.py` | 13 | NOT_RUN (collecte possible depuis que `rag_saas_sdk` est installé en mode éditable dans le venv local ; hors dépôt) |
| `tests/test_agent.py` | 27 | NOT_RUN |
| `tests/test_injection_test_set.py` | 7 | NOT_RUN |
| `tests/test_integrations.py` | 8 | NOT_RUN |
| `tests/test_regression.py` | 0 (script de garde, pas de tests) | n/a : exécuté par la CI de régression, pas par pytest |
| `tests/test_voice.py` | 10 | NOT_RUN |
| `tests_pipeline/test_retrieval.py` | 10 | NOT_RUN |
Total : **75 tests réalisables non exécutés**. À lancer et à classer à la reprise ; je ne retire pas l'exclusion de la CI sans les avoir vus passer.

## 2. Résultats vérifiés (cette session de reprise)
| Contrôle | Commande (résumé) | Code | Résultat | Preuve |
|---|---|---|---|---|
| 84 tests : 81 annoncés + 3 tests PostgreSQL du handler de logs | `Run-IsolatedSuite.ps1 -PytestArgs tests/test_ci_postgres_job.py,tests/test_isolated_test_runner.py,tests/test_default_models_are_routable.py,tests/test_admin_dashboard.py::test_system_log_handler_writes_real_rows,tests/test_disposable_pg_guard.py,tests/test_postgres_system_log_handler.py` | 0 | **84 passés** (1 + 4 + 49 + 17 + 10 + 3), 23,79 s | `v1-81plus3.xml`, `.txt`, `.byfile.txt` |
| Ruff | `ruff check api scripts/run_isolated_tests.py tests/test_isolated_test_runner.py tests/external_skip_allowlist.py tests/test_postgres_system_log_handler.py tests/test_default_models_are_routable.py tests/test_admin_dashboard.py tests/conftest.py` | 0 | « All checks passed! » | `ruff.txt` |
| Refus du lanceur sur 5 cibles interdites | voir `postgres-integration-tests.md` | 2 (attendu) | 5 refus | `runner-refusals.txt` |
| Migrations sur les 3 bases jetables | `select version_num from alembic_version` | n/a | `0137` x3 ; 6 politiques, 179 tables | `phase3-checks.txt` |
Les 81 tests annoncés dans le compte rendu précédent sont donc **confirmés** (PASS_VERIFIED) ; avant cette relecture ils étaient HISTORICAL_RESULT_UNVERIFIED.

## 3. Résultats historiques (HISTORICAL_RESULT_UNVERIFIED : sortie brute perdue)
| Annonce | Chiffres rapportés |
|---|---|
| premier passage complet (SQLite, base factice, **`.env` réel chargé**) | 6037 passés, 3 échecs, 194 ignorés, 23 désélectionnés, 2 h 30 53 |
| rejeu des 27 fichiers ignorés sur la pile locale, avec worker Celery | 223 passés, 30 ignorés, 2 désélectionnés, 9 erreurs (configuration P0), 10 min 38 |
| OCR avant / après installation de `fra.traineddata` | 2 échecs, 54 passés / 18 passés |
| 23 tests `network_flaky` | 23 passés, 28 désélectionnés (3 fichiers), 4 min 07 |
| passage complet interrompu (22:19 - environ 01:00) | à environ 77 % : 4736 passés, 16 échecs, 136 erreurs, 16 ignorés (voir `test-failures.csv`) |
| prix litellm | 49 passés (carte locale forcée) et 49 passés (carte distante) |
Le total des 194 ignorés a été réconcilié (27 fichiers) ; les 24 « dépendances externes » annoncées dans mon dernier message étaient un **décompte erroné** : la liste observée contient **27** tests externes (voir `test-skips.csv`, lignes E01-E24 : Stripe 4, Paystack 4, Google Drive 4, OneDrive 2, Notion 1, staging hébergé 12 dont le test de politiques `test_rls_policies_exist_on_staging`).

## 4. Résultat observé à distance : CI de `main` (PASS_VERIFIED côté GitHub, non exécuté par moi)
GitHub Actions, workflow `CI`, run n°202, commit `78ab2b7`, job `backend-tests` : **6256 passés, 47 ignorés, 23 désélectionnés, 15 avertissements, 41 min 22 s** (lu dans le journal du job via l'API GitHub). Ce n'est pas mon travail et pas ma branche ; cela corrobore que la suite large est verte sur `main` avec un PostgreSQL et un MinIO de service (voir `ci-test-matrix.md`).

## 5. Ce qui reste à exécuter
1. Suite complète avec le lanceur isolé, par lots (mémoire), `--junitxml` pour obtenir un identifiant par test : NOT_RUN. Raison de l'arrêt : le moteur Docker s'est bloqué pendant le dernier passage (environ 23 h 50) ; cause **non établie**. Constat associé, non prouvé comme cause : mémoire libre de 237 à 645 Mo sur 16 Go pendant les passages (navigateurs, VM WSL, processus Claude/Code).
2. Les 75 tests des 7 fichiers `--ignore`.
3. Les cinq groupes à réexaminer (`test_inbound_webhooks`, `test_mcp_builtin_tools_security`, `test_latency_metrics`, `test_json_extraction`, `test_markdown_extraction`) plus `test_mcp_idor` : causes inconnues, jamais lues.
4. Tests externes : 27 (liste et commande reproductible dans `resume-session.md`).
