# test-remediation-summary.md

État au 2026-10-11, 07:45. Branche `bob/auto-fix-20261010-1555`, HEAD `0c4dfcf`. **Les critères d'acceptation ne sont pas atteints** : la suite complète n'a pas été rejouée de bout en bout sur l'environnement isolé. Une exécution par lots est en cours (voir §6) ; rien dans ce document n'en anticipe le résultat.

## 1. Ce qui est vérifié maintenant (sortie conservée)
| Contrôle | Résultat |
|---|---|
| Dépôt : branche, HEAD, `0c4dfcf` présent et ancêtre de HEAD, aucune modification depuis, fichiers du lanceur / tests / liste des dépendances externes présents | oui (`git`) |
| Aucun fichier versionné ne dépend de `D:` | oui (recherche sur `scripts/` et `tests/`) |
| Pile locale : PostgreSQL 17.11, Redis 7.4.11, MinIO ; ports liés à 127.0.0.1 ; 3 bases à `0137` ; buckets ; worker Celery répond au ping | oui (`phase3-checks.txt`) |
| Le lanceur refuse 5 cibles interdites (code 2) | oui (`runner-refusals.txt`) |
| **84 tests passés** : les 81 annoncés (1 + 4 + 49 + 17 + 10) + 3 tests PostgreSQL du handler de logs ; `ruff` propre | oui (`v1-81plus3.xml`, code 0) |
| Inventaire : **6348 tests collectés**, 0 erreur de collecte, sans `--ignore` ni désélection | oui (`collect-all.txt`) |
| Les 23 tests désélectionnés : identifiants exacts | oui, égalité d'ensemble avec la liste de la session (`collect-network.txt`) |
| Résultat de la CI GitHub de `main` (`78ab2b7`) : 6256 passés, 47 ignorés, 23 désélectionnés | observé via l'API GitHub, non exécuté par moi |

## 2. Résultats historiques non vérifiables (HISTORICAL_RESULT_UNVERIFIED)
Tous les passages antérieurs (premier passage 6037/3/194/23, rejeu des 27 fichiers 223 passés, OCR, 23 tests réseau, passage interrompu 4736 passés / 16 échecs / 136 erreurs) dont les sorties brutes étaient sur `D:`. Chiffres dans `full-suite-results.md`, détail par test ou par groupe dans `test-failures.csv`, `test-skips.csv`, `test-deselections.csv`. Je ne les transforme pas en résultats vérifiés.

## 3. Constats nouveaux ou corrigés par cette relecture
1. **75 tests exclus par `--ignore` (7 fichiers)** que ni la CI ni mon premier passage n'exécutaient ; ils ne figuraient dans aucun de mes décomptes (`test-ignored-files.csv`). Réconciliation exacte : 6257 + 16 (nouveaux tests) + 75 = 6348.
2. **Décompte erroné de ma part** : j'avais annoncé 24 tests dépendant de services externes ; la liste observée en contient **27** (`test-skips.csv`).
3. **Limite de produit dissimulée par la forme de mon test** : `mask_sensitive` ne masque pas `Authorization: Bearer <jeton>` ni `token=valeur` sans guillemets. J'ai écrit mon nouveau test avec la forme prise en charge au lieu de modifier du code de sécurité (règle : pas de modification du code de sécurité sans revue). **Non corrigé, non couvert par un test.** Décision requise.
4. **Premier passage : le `.env` réel était chargé** dans le processus (la conftest le lit) : qu'aucun service hébergé n'ait été contacté est NOT_VERIFIED. Le lanceur isolé ne charge jamais `.env`.
5. **CI de `main`** : avant le 2026-10-10 le job `backend-tests` utilisait le secret `DATABASE_URL`, donc la vraie base (corrigé sur `main`, commit `beebb48`). Ma branche contient encore l'ancienne version du job ; ne pas pousser sans avoir intégré `main`. Ce que ces tests ont écrit dans la base réelle avant le correctif : NOT_VERIFIED (secrets illisibles).
6. **`main` a 44 commits d'avance** ; un seul conflit textuel prévisible (`api/services/evaluation_datasets.py`). Rien fusionné. `main` a aussi retiré les langues `de`, `es`, `pt`, `ar` : l'échec i18n `de` préexistant est probablement sans objet là-bas (à vérifier).
7. **Skips qui masquent une erreur** (`HARDEN_CANDIDATE`, `skip-sites-static.csv`) : `test_bugs_found_by_the_real_data_sweep.py:24` et `:103` (échec de préparation transformé en skip), `docs/test_examples.py:34` (document manquant transformé en skip). Le mode strict les ferait échouer ; aucun n'a été modifié.
8. **Tests live qui ne peuvent jamais passer** : `test_billing_stripe_live.py:69` et `test_billing_paystack_live.py:71` contiennent un `pytest.skip("paste a real captured webhook payload…")` inconditionnel.
9. **Couverture TLS absente** : les tests SSL exercent la tâche de renouvellement, pas une poignée de main TLS réelle (certificat invalide, connexion refusée) : manque de couverture, pas un résultat.
10. **Docker s'est bloqué** pendant le dernier passage ; cause non établie ; mémoire libre faible observée (237 à 645 Mo sur 16 Go). Le lecteur `D:` a disparu, avec toutes les sorties brutes.

## 4. Statut de chaque catégorie (état actuel)
| Catégorie | Nombre | Statut |
|---|---|---|
| Collectés | 6348 | vérifié |
| Passés, vérifiés | 84 (+ lots en cours) | PASS_VERIFIED |
| Passés, annoncés (anciens passages) | voir §2 | HISTORICAL_RESULT_UNVERIFIED |
| Échecs du passage interrompu | 16 échecs + 136 erreurs | HISTORICAL ; 1 échec réel déjà corrigé (F04) ; le reste BLOCKED_INFRASTRUCTURE probable ou à réexaminer, **cause non lue** |
| Ignorés par dépendance externe | 27 | NOT_RUN_EXTERNAL_DEPENDENCY (commande reproductible : `resume-session.md`) |
| Désélectionnés `network_flaky` | 23 | identifiants vérifiés ; passage historique non vérifié |
| Exclus par `--ignore` | 75 | NOT_RUN (réalisables, lot `B8`) |
| Ignorés réalisables en local (infrastructure) | ~170 des 194 | à rejouer dans la suite par lots |

## 5. Fichiers créés ou modifiés depuis `0c4dfcf` (non commités)
`audit-reports/test-remediation-2026-10-10/*` (rapports), `scripts/test_env/Run-IsolatedBatches.ps1`, `scripts/run_live_tests.py`, `tests/test_live_test_runner.py`. Aucun test existant modifié, aucune assertion retirée, aucune exclusion ajoutée.

## 6. Exécution en cours
`Run-IsolatedBatches.ps1` : 8 lots (B1 à B6 par ordre alphabétique des fichiers, B7 attrape-tout, B8 les 7 fichiers `--ignore`), un pytest à la fois, `--junitxml` par lot, sans nouvelle tentative automatique. Démarrée le 2026-10-11 à 07:29. Avancement : `…\run1\progress.txt`. Résultat à intégrer à `full-suite-results.md` à la fin.
