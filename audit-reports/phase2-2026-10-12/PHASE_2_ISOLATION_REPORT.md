# PHASE 2 — Isolation des tests et de la CI : partie code (2026-10-12)

Suite de `../phase0-2026-10-12/PHASE_0_READ_ONLY_SECURITY_AUDIT.md` (constats CI-005, CI-006, CI-007) et de `../phase1-2026-10-12/`.
Périmètre appliqué : gardes côté tests et scripts, avec tests de contrat. **Non touchés** : `.github/workflows/*`, `.circleci/config.yml`, secrets GitHub, hébergement du worker, base de production. Rien n'est poussé, fusionné ni déployé.
Commits locaux : `d219f48` (phase 2) et `c8fb325` (phase 1), tous deux non poussés.

## 1. Exécuté et prouvé

| Constat | Correction | Preuve |
|---|---|---|
| CI-006(a) le garde ignorait les services hébergés et les clés payantes | `tests/_remote_guard.py` refuse désormais : `LOKI_HOST`, `TEMPO_HOST`, `LANGFUSE_HOST`, `SENTRY_DSN`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `SECURITY_ALERT_WEBHOOK_URL` non locaux (y compris un nom d'hôte sans schéma) ; 13 clés de fournisseurs payants (Anthropic, OpenAI, Gemini, Mistral, embeddings, Voyage, Cohere, Tavily, Deepgram, Google TTS, ElevenLabs, watsonx, Twilio) sauf `RUN_REAL_LLM_TESTS=1` | 6 + 13 tests paramétrés ; les messages n'affichent jamais la valeur |
| CI-007 un tunnel local vers la vraie base passait (« hôte local » ne suffit pas) | Une `DATABASE_URL` / `DATABASE_URL_TRANSACTION` locale doit avoir un nom contenant `test`, `pytest`, `disposable`, `scratch`, `throwaway` ou `tmp` | `test_a_local_database_with_a_real_looking_name_is_refused…` ; les noms de la CI GitHub, de CircleCI et de ma pile (`rag_saas_test`, `pytest_p0`, `rag_test_roundtrip_scratch`) passent |
| CI-006(c) les scripts `api.*` n'avaient aucun garde | `scripts/local_only_guard.py` (mêmes règles) appelé avant le premier import `api` de `export_openapi.py` et `measure_injection_two_stage.py` | Exécution réelle sans `.env` : URL de pooleur distante factice → refus (code 1) ; clé payante → refus (code 1) ; pile locale → accepté (code 0). Aucun mot de passe affiché |
| Nouveaux scripts non gardés | Test de contrat : tout script important `api.*` appelle `require_local_services()` avant le premier import `api`, ou figure dans une liste justifiée (6 scripts : inventaire statique, vérification des dépendances, serveur isolé, deux benchmarks de retrieval, parcours de staging) | `test_every_script_importing_the_application_is_guarded_or_explicitly_classified` + test des entrées périmées |
| Cohérence avec le script de lancement | `scripts/run_tests_local.sh` vide aussi `TWILIO_AUTH_TOKEN` ; un test vérifie que le script vide tout ce que le garde refuserait | `test_the_local_test_runner_blanks_everything_the_guard_would_refuse` |
| Câblage | `tests/conftest.py` transmet tous les réglages gardés et l'accord `RUN_REAL_LLM_TESTS` | `test_conftest_passes_every_guarded_setting…` |

* **Les 28 nouveaux tests échouent sans la correction** : fichiers rétablis à l'état commité, collecte en erreur (`module '_remote_guard' has no attribute 'PAID_KEY_SETTINGS'`), puis mes versions restaurées (empreintes identiques).
* **Avec la correction** : 50 passés (nouveaux tests + `test_remote_guard.py` + `test_disposable_pg_guard.py`, inchangés) ; 418 passés sur les tests voisins (config, environnement, i18n, migration, docs, délai de CI, erreurs LLM) ; `ruff check api/ tests/ scripts/` propre. Tout via `scripts/run_tests_local.sh` sur la pile jetable.

## 2. Non fait (dépend d'une décision ou d'un accès)

| Élément du plan | Raison |
|---|---|
| Retirer `DATABASE_URL` des secrets au niveau du dépôt / secrets d'environnement avec relecteur (CI-009, CI-010) | réglage GitHub : seule la propriétaire peut le faire |
| Sortir le worker Celery de GitHub Actions (CI-008) | décision d'hébergement ouverte ; `celery-worker.yml` inchangé et toujours exécuté avec les secrets de production |
| Réconcilier les deux CI (job PostgreSQL dédié de la branche `…-1555`, aller-retour 0137) | dépend de la collision de migration `0137` (phase 4) |
| Plafonner CircleCI (xlarge × 4) et diagnostiquer l'échec du run 603 (CI-011) | journaux CircleCI inaccessibles ; décision de coût |
| Tests PostgreSQL en transaction annulée ou schéma temporaire (CI-003) | refonte plus large des fixtures, à concevoir avec toi ; aujourd'hui ces tests valident puis nettoient à la main (base jetable obligatoire désormais) |
| Garde « confirmation du nom » (`RAG_DISPOSABLE_PG_CONFIRM`) pour les 22 fichiers écrivant en base (CI-007) | la règle de nom jetable est posée ; l'exigence de confirmation explicite pourrait gêner la CI, à décider |
| Corriger le caractère de contrôle du runbook (ligne 38) | non fait : mon outil d'édition ne peut pas cibler ce caractère invisible sans réécrire le fichier |

## 3. Limites et risques de régression
* Le garde est évalué à l'import de `conftest.py` sur les réglages chargés (`.env` compris) : un développeur avec un `.env` réel doit passer par `scripts/run_tests_local.sh` (déjà le cas documenté). La CI GitHub et CircleCI ne définissent aucune des clés ni des services nouvellement gardés : **non vérifié en conditions réelles** (aucune CI lancée, rien n'est poussé).
* `llm-tests.yml` (clé Anthropic + `RUN_REAL_LLM_TESTS=1`) reste autorisé par construction ; l'exécution réelle n'a pas été rejouée.
* Une base locale légitime dont le nom ne contient aucun des mots listés sera désormais refusée (contournement : `ALLOW_REMOTE_TEST_SERVICES=1`).
* Aucun test existant n'a été modifié ou supprimé.

## 4. Critères d'entrée de la phase 3 (isolation multi-tenant, rôles, RLS)
1. Réponses de la propriétaire aux requêtes de lecture (`owner_scripts/`) : au minimum révision et rôle de connexion.
2. Décision D2/D8 : RLS par étapes sur staging ; staging disponible ou à provisionner (le mot de passe de l'ancien staging a été partagé en conversation, rotation à faire).
3. Décision sur la collision `0137` (le pilote RLS de l'autre session).
4. Accord pour que la phase 3 commence par des tests d'isolation A/B et la revue des 77 recherches par identifiant signalées, avant toute migration.
