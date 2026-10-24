# Suivi du 2026-10-23 — intégration de `main`, durcissement des tests, masquage des logs

Branche de travail : `bob/auto-fix-20261023-tests-hardening`, créée depuis `origin/main` (`711aebb`) dans un worktree séparé (`C:\Users\NITROV15\rag-work\wt-tests-hardening`). Rien n'est poussé, fusionné ni déployé. Les statuts reprennent le vocabulaire de `audit-reports/test-remediation-2026-10-10/` (PASS_VERIFIED, FAIL_VERIFIED, NOT_RUN, NOT_RUN_EXTERNAL_DEPENDENCY, NOT_VERIFIED).

## 1. « Intégrer main » : ce que j'ai constaté et décidé
`git fetch origin` : `origin/main` a **173 commits** d'avance sur la branche `bob/auto-fix-20261010-1555` (HEAD `25710a4`, qui a reçu depuis deux commits de sauvegarde et de prompts).
`git cherry -v origin/main HEAD` (comparaison par contenu) : **tous mes commits sont déjà dans `main`** (portés sous d'autres SHA par la PR n°33), sauf :
- `4b4063b` : le **pilote RLS** (migration `0137_tenant_rls_policies_pilot`). `main` possède déjà un `0137_evaluation_split` : un merge produirait **deux têtes Alembic `0137`**. Exclusion volontaire des PR précédentes ; voir §5.
- `264ec34` et `25710a4` : sauvegarde de la branche, prompts de continuation, audit fonctionnel de l'autre session (pas de moi).
Décision : **pas de merge** dans l'ancienne branche (elle reste intacte comme sauvegarde, y compris du pilote RLS). Le travail neuf part d'`origin/main`. `main` contient déjà, entre autres, le masquage `Bearer`/`Basic` et l'inventaire des skips que j'avais demandés.

## 2. Changements (4 commits, tous testés)
| Commit | Sujet | Tests |
|---|---|---|
| `640de93` | `mask_sensitive` : 4 fuites réelles sur 16 formes sondées corrigées (`refresh_token=`, `client_secret=`, valeurs de `Cookie`/`Set-Cookie`, clés `sk_live_`/`sk_test_`/`rk_live_`/`whsec_`). **Défaut de performance préexistant sur `main`** corrigé : le motif d'URL à identifiants était quadratique sur une longue suite de lettres, chiffres, points et tirets (jeton base64url par exemple) : 4,7 s pour 40 000 caractères, sur une fonction exécutée à chaque ligne de log ; 26 ms après | `tests/test_log_secret_masking_more_shapes.py` : **30 cas** (le message du commit en annonce 35 par erreur) ; 14 échouaient avant (12 de forme, 2 de temps), tous passent ; les 19 tests de `test_log_secret_masking.py` passent sans modification |
| `f63c468` | 3 skips qui masquaient une erreur de préparation deviennent des assertions ; les 2 tests live de webhook (Stripe, Paystack), qui avaient un `pytest.skip` inconditionnel et ne pouvaient jamais passer, deviennent exécutables avec un événement capturé fourni hors dépôt ; `scripts/run_live_tests.py` transmet les variables facultatives du fournisseur choisi | 13 tests des sites durcis (0 ignoré) ; 2 tests synthétiques nommés `..._NOT_a_live_test` prouvent l'assistant avec un secret factice ; contrôle de mutation : sans épinglage de l'horloge, Stripe refuse un événement ancien ; 25 tests des lanceurs |
| `86f95c0` | 4 variables inutilisées `ruff F841` retirées (appels conservés) | `py_compile` ; `ruff --select F841` : il reste 3 cas laissés volontairement (§4) |
| `9e1d2a8` | `test_detect_objects_yolo_real_end_to_end_against_a_real_photo` téléchargeait les poids YOLO depuis GitHub à chaque exécution (chemin temporaire) : il bloquait plusieurs minutes sur un réseau lent. Il réutilise désormais le cache `storage/ml_models/yolov8n.pt` s'il existe ; sans cache, comportement inchangé | 5 passés en 60 s, sans ignoré ; assertions identiques |

Piège rencontré et corrigé : ma première version du motif de nom (préfixe non borné) était elle-même quadratique ; la mesure l'a montré, le préfixe est borné à 3 segments de 24 caractères. Une exécution intermédiaire semblait montrer que le correctif d'URL n'avait aucun effet : c'était un test lancé en parallèle de la modification (avant qu'elle soit enregistrée). La mesure refaite proprement confirme l'effet.

## 3. Vérifications
Chaque commit : `ruff check api` propre, `git diff --check` propre, balayage de secrets sur le diff sans résultat, tests ciblés verts. Résultat de la suite large : §6.

## 4. Ce qui n'a PAS été fait, et pourquoi
| Point | Statut | Raison |
|---|---|---|
| Suite complète avec PostgreSQL, Redis, MinIO et worker Celery sur cette branche | **NOT_RUN** | Docker Desktop est arrêté ; vos notes interdisent de le redémarrer sans accord et vous avez répondu de ne pas y toucher |
| Pilote RLS | **non intégré** | décision de conception (§5) |
| `tests/test_billing_plans_limits_postgres.py` `served` (ligne 820) | **ouvert** | le test calcule les réponses servies sans jamais les vérifier : il passe à vide si aucune n'est servie. Une assertion doit être validée par un run PostgreSQL |
| `bob/lab/run_experiment.py` (2 `F841`) | laissé | script d'expérience hors CI |
| 27 tests externes (Stripe 4, Paystack 4, Google Drive 4, OneDrive 2, Notion 1, staging 12) | **NOT_RUN_EXTERNAL_DEPENDENCY** | comptes et clés ; commandes dans `audit-reports/test-remediation-2026-10-10/resume-session.md` ; les 2 tests webhook requièrent en plus un événement capturé |
| CI GitHub / CircleCI sur cette branche | **NOT_RUN** | rien poussé |

## 5. Décision requise : pilote RLS
Le prompt de continuation exige, pour réintégrer le pilote : migration renumérotée (≥ 0146, une seule tête), rôle dédié à la place de `TO PUBLIC`, `FORCE`. Ce n'est pas qu'une renumérotation : avec `FORCE` et des politiques fondées sur `app.current_organization_id`, toute requête exécutée avant que l'organisation soit connue (webhooks, tâches Celery, lectures d'identité) **ne verrait aucune ligne**. Sans accès au rôle d'exécution réel de la base de production (NOT_VERIFIED depuis le début), je ne peux pas valider cet effet. Je ne l'ai donc pas fait.

## 6. Résultat de la suite sans services (Docker arrêté)
(Section restée vide dans le commit `46de583` par une erreur de ma part ; complétée ensuite. Les chiffres ci-dessous sont ceux mesurés l'après-midi du 2026-10-23.)
Environnement : worktree sur `C:`, venv du dépôt principal, **sans** PostgreSQL / Redis / MinIO / worker (base factice injoignable, `RAG_ENV_FILE` inexistant, `HF_HUB_OFFLINE=1`). Sorties dans `C:\Users\NITROV15\rag-test-evidence\2026-10-23\`.
| Contrôle | Résultat | Statut |
|---|---|---|
| Masquage de logs : `test_log_secret_masking_more_shapes` (30), `test_log_secret_masking` (19), `test_log_correlation`, `test_system_log_handler_dedupe`, `test_admin_dashboard` | 66 passés | PASS_VERIFIED |
| 16 fichiers qui lisent des logs capturés et parlent de jetons, secrets ou cookies (`log-reader-files.txt`) | 539 passés, 30 ignorés, 2 désélectionnés, 0 échec (13 min 23, `log-readers.xml`) | PASS_VERIFIED |
| Les 30 ignorés de ce groupe | 23 + 6 : `DATABASE_URL is not reachable` (documents, branding) ; 1 : bucket S3 non configuré | NOT_RUN (infrastructure) |
| Lanceurs, assistants webhook, sites de skip durcis, YOLO | passés (§2 ; `9e1d2a8` : 5 passés, sans ignoré) | PASS_VERIFIED |
Trois tentatives de passe complète sans services ont été interrompues par moi : deux figées sur le réseau (corrigé par `9e1d2a8`), la troisième avec 34 erreurs « E » à 3 % dont la cause est **lue en §8.1**. Aucun résultat de ces tentatives n'est utilisé. La passe complète avec services est en §8.2.

## 7. Incident de mesure, pour mémoire
Une première exécution a semblé bloquée (0 % de CPU, connexion `140.82.121.4:443` en `CloseWait`) : `tests/backend/media/test_object_detection.py` télécharge les poids YOLO depuis GitHub quand `storage/ml_models/yolov8n.pt` est absent, et le worktree neuf ne l'avait pas. J'ai **copié** ce cache (SHA-256 identique, fichier non versionné) depuis le dépôt principal. Aucun résultat de cette exécution interrompue n'est utilisé.
## 8. Passage du 2026-10-23 soir (Docker démarré avec votre accord)
Pile : conteneurs `rag-test-pg` / `-redis` / `-minio` (127.0.0.1 uniquement), 3 bases migrées à `0145` (tête unique). Les conteneurs `boutik-*` d'un autre projet n'ont pas été touchés. Sorties brutes : `C:\Users\NITROV15\rag-test-evidence\2026-10-23\` (`run-full\`, `e34\`, `*.xml`).

### 8.1 Les 34 erreurs « E » à 3 % : cause lue (PASS_VERIFIED)
Reproduites deux fois, au même endroit, sans services. Les 34 erreurs sont **toutes dans `tests/contracts/test_chat_integrations_contract.py`** et ont **la même cause** : `SecretEncryptionNotConfiguredError: SECRET_ENCRYPTION_KEY must be set`. Ce n'est **ni PostgreSQL ni Redis** : une variable de configuration que mon environnement minimal ne définissait pas. Le lanceur isolé la génère (clé aléatoire), donc ces tests passent dans la passe complète (lot B7). Aucune régression de mes commits.

### 8.2 Passage complet sur `a7349e4` (577 fichiers, 8 lots, un pytest à la fois, 2 h)
`Run-IsolatedBatches.ps1`, 2026-10-23 23:06 → 2026-10-24 01:02, lanceur isolé (PostgreSQL 17 / Redis / MinIO / worker Celery réels, `RAG_STRICT_SKIPS=1`).
| Lot | Passés | Ignorés | Erreurs | Échecs |
|---|---|---|---|---|
| B1 | 545 | 0 | 0 | 0 |
| B2 | 1622 | 8 | 8 | 0 |
| B3 | 1299 | 4 | 13 | 1 |
| B4 | 718 | 3 | 0 | 0 |
| B5 | 1469 | 1 | 2 | 0 |
| B6 | 1198 | 11 | 1 | 0 |
| B7 | 192 | 34 | 0 | 0 |
| B8 (7 fichiers exclus de la CI) | 75 | 0 | 0 | 0 |
| **Total** | **7118** | **61** | **24** | **1** (= 7204) |
**Aucun des 25 écarts ne vient du code testé** (fichier, cause, régression ?) :
| Fichier | Nb | Cause | Régression de mes commits ? |
|---|---|---|---|
| `test_domains_email_postgres::test_changing_the_sending_address_end_to_end_through_resend` | 1 échec | mon lanceur utilisait un expéditeur `@isolated-tests.invalid` : le validateur d'e-mails refuse les TLD réservés, d'où 422 au lieu de 400 | **oui, mon lanceur** (outil de test, pas le code de l'application) : corrigé (`@example.com`) |
| `test_clamav_real_daemon` | 8 | suite opt-in : daemon ClamAV absent (image volumineuse) | non : classée « lourde », ignorée |
| `test_deploy_artifacts` | 5 | opt-in : Terraform / Helm et plugins réseau | non |
| `test_deploy_dedicated_tenant_e2e` | 8 | opt-in : trois piles Docker construites depuis `Dockerfile.api` | non |
| `test_tracing_real_collector` | 1 | opt-in : Jaeger absent | non |
| `test_pgvector_real_search` | 1 | opt-in : variable `PGVECTOR_REAL_TEST` | non : **exécutée pour de vrai, passe** |
| `test_prompt_injection_measured` | 1 | opt-in : `PROMPT_INJECTION_MEASURE` (modèle de 1,4 Go déjà en cache) | non : **exécutée pour de vrai, passe** |
Comparaison avec `origin/main` : non nécessaire, chaque cause est établie et ne touche pas le code applicatif.

### 8.3 Vérifications après correction (sur `480a84d`, pas une nouvelle passe complète)
| Contrôle | Résultat | Statut |
|---|---|---|
| Les 7 fichiers en cause rejoués dans le lanceur strict | exit 0 : 0 erreur, 0 échec ; `domains_email` 13 passés ; pgvector 1 passé ; injection de prompt 1 passé ; 22 ignorés documentés (ClamAV 8, tenant dédié 8, Terraform/Helm 5, Jaeger 1) | PASS_VERIFIED |
| `test_domains_email_postgres`, 3 passages consécutifs | 13 passés à chaque fois | PASS_VERIFIED |
| 21 fichiers qui lisent `SUPPORT_EMAIL`, `EMAIL_FROM_ADDRESS` ou `.invalid` (le changement d'expéditeur n'a rien cassé) | 322 passés, 5 ignorés documentés, 0 erreur | PASS_VERIFIED |
| **Passe complète unique sur le HEAD final `480a84d`** | **non relancée** (2 h) | **NOT_RUN** |
Total reconstitué, à ne pas présenter comme une seule exécution : 7118 + 1 + 2 = 7121 passés, 61 + 22 = 83 ignorés, 0 erreur, 0 échec.

### 8.4 `served` (étape 2) : le test passait bien à vide, et un constat métier
Contrôle de mutation sur PostgreSQL (`audit-reports/.../served-*.txt`, commit `ece62d1`) :
- ancien test, solde de départ forcé à 0 (rien ne peut être servi) : **passe** → il passait bien à vide ;
- nouveau test, toutes les requêtes avec une clé invalide : **échoue** (`[401, 401, ...]`) ; sur le vrai code : passe, 5 fois de suite, et le module entier (34 passés).
**Constat, non modifié (décision métier)** : 8 requêtes simultanées sur un solde de 15 crédits ont **toutes** été servies (3 payées, 5 non payées). Le solde ne devient jamais négatif (BILL-008), mais le contrôle de solde précède l'appel au fournisseur et le débit le suit. L'ancien commentaire (« chaque réponse servie a été payée ») était faux ; il est remplacé. Réservation avant l'appel ou dépassement borné accepté : à vous de trancher.

### 8.5 Couverture (étape 3) : NOT_RUN
`--cov=api --cov-report=term` est ajouté à l'étape « Run test suite » (`a7349e4`), une seule ligne modifiée, YAML valide, aucun seuil. **Le chiffre de couverture n'a pas été mesuré** : la passe locale n'activait pas la couverture. Les 83 % annoncés plus tôt restent une borne basse. Risque : la couverture ralentit le job (41 min mesurées sans, limite de 75).

### 8.6 PR n°34 (lecture seule, aucune action)
Ouverte, non brouillon, base `main` `711aebb` (identique à la mienne). Contrôles du 2026-10-20 sur `2c9356d` : `backend-tests`, `backend-postgres-tests`, `backend-security`, `frontend-checks`, `build-*` : succès ; CircleCI `api-tests` et `rag-pipeline-regression` : succès ; `bandit` et `mypy` : échec (non bloquants) ; état « unstable » à cause d'eux. **Elle touche 4 fichiers que je modifie aussi** : `scripts/e2e_rag_chat_scenarios.py`, `scripts/e2e_rag_evalab.py`, `tests/test_celery_worker_workflow.py`, `tests/test_billing_plans_limits_postgres.py`. Dans ce dernier, elle **supprime** la variable `served` (`await asyncio.gather(...)` sans résultat), là où j'ajoute l'assertion : **la fusion de la PR n°34 en premier entraînera un conflit** et ferait perdre ce contrôle si on garde sa version. Je n'ai ni jeton `gh` ni outil de fusion ; non fusionnée.

### 8.7 Ce qui n'a pas été fait
Passe complète unique sur le HEAD final ; mesure de couverture ; les 27 tests externes (Stripe, Paystack, Google Drive, OneDrive, Notion, staging) ; l'e2e Ollama, le tenant dédié, la démo ; le pilote RLS ; toute migration ; push, PR et fusion (en attente de votre accord).
## 9. Couverture mesurée de `api/` (point 13.1.6, objectif 90 %) : 2026-10-24
Preuves hors dépôt : `C:\Users\NITROV15\rag-test-evidence\2026-10-24\` (`run-cov\` : `progress.txt`, `B1..B8.xml`, `.coverage.B1..B8`, `.coverage.OPTIN`, `.coverage.PR34`, `report-*.txt`, `summary-*.json`, `report-modules.txt` ; `ab-b4-nocov\`).

### 9.1 Comment c'est mesuré (PASS_VERIFIED)
- Commande : `Run-IsolatedBatches.ps1 -OutDir …\run-cov -Coverage` (option ajoutée dans le commit qui suit ; elle ajoute `--cov=api --cov-report=` et garde un fichier de données par lot). HEAD `3b34409`, seul ce script différait pendant la mesure ; `api/` et `tests/` sont inchangés. Pile locale PostgreSQL 17 / Redis / MinIO / worker Celery, `RAG_STRICT_SKIPS=1`, un pytest à la fois. 17:56 → 22:31 (4 h 35).
- Configuration : celle de `pyproject.toml` (`[tool.coverage.run] concurrency = ["greenlet"]`), vérifiée appliquée avec la valeur par défaut de pytest-cov (`config_file=".coveragerc"` inexistant → coverage lit `pyproject.toml`). Couverture de **lignes** (pas de branches), coverage 7.16.0, **aucun seuil, aucune ligne omise, aucune modification de la configuration**.
- Les **8 fichiers de données existent** (aucun lot manquant). Combinaison : `coverage combine --keep`.
- Tests de cette passe : 7122 passés, 83 ignorés (tous documentés), 2 erreurs (les deux suites opt-in pgvector et injection de prompt, non activées ; lacune de mon allowlist corrigée dans le commit qui suit), 0 échec.
- Les 577 fichiers de tests suivis par Git sont tous dans les 8 lots.

### 9.2 Résultat
| Périmètre | Lignes de `api/` | Manquantes | Couverture |
|---|---|---|---|
| **Variante CI : `B1`..`B7`** (les 7 fichiers `--ignore` de `backend-tests` = `B8`, exclus) | 50 683 (861 fichiers, 9 sans instruction) | 7 226 | **85,74 %** |
| Sans exclusion : `B1`..`B8` | 50 683 | 7 226 | 85,74 % (`B8` seul : 37,84 %, uniquement des imports déjà couverts : il n'ajoute aucune ligne) |
| + 2 suites opt-in (pgvector natif, injection de prompt), `RAG_TEST_OPT_IN` | 50 683 | 7 216 | 85,76 % (+10 lignes) |
| + les 12 fichiers de tests de la PR n°34 (88 passés ; copiés temporairement depuis la branche distante puis supprimés ; **PR non fusionnée**) | 50 683 | 6 448 | **87,28 %** (+778 lignes) |
| Les deux ensemble | 50 683 | 6 438 | 87,30 % |
**90 % exige au plus 5 068 lignes manquantes** : il en faut 2 158 de moins qu'aujourd'hui, **1 380 de moins après la PR n°34**.
Ce chiffre n'est **pas garanti identique** à celui de la CI (NOT_VERIFIED) : la CI tourne sous Linux et ignore des tests qui s'exécutent ici (PostgreSQL destructifs, worker Celery, OCR) ; son chiffre est donc probablement un peu inférieur à 85,74 %. Le premier run de la PR donnera le vrai chiffre.

### 9.3 Ce qui n'est pas couvert faute de services ou de suites lourdes (indicatif, rapprochement par nom de module, pas par ligne)
| Suite ignorée | Module correspondant | Lignes manquantes |
|---|---|---|
| Traçage vers un vrai Jaeger | `api/security/tracing.py` (25,4 %) | 44 |
| Voix navigateur (SAPI + node + Playwright) | `api/services/voice.py` (69,9 %) | 104 |
| Stripe live (4 tests) | `api/services/billing_stripe.py` (89,2 %) | 35 |
| Paystack live (4 tests) | `api/services/billing_paystack.py` (76,4 % ; 97,6 % avec la PR n°34) | 50 (5 avec la PR n°34) |
| Google Drive, OneDrive, Notion | `*_extraction.py` | 5 + 5 + 16 |
| ClamAV réel, pgvector, injection de prompt | `clamav.py`, `retrieval_pipeline.py`, `prompt_injection_detection.py` | 6 + 1 + 2 (pgvector et injection : mesurés avec opt-in) |
| Terraform/Helm, nginx TLS, tenant dédié (Docker) | aucun module de `api/` (fichiers `deploy/` ou conteneurs, non mesurés par pytest-cov) | 0 |
**Majorant : 223 lignes (en comptant Paystack après la PR n°34) à 268 lignes (somme du tableau), soit environ 0,5 point** : si toutes ces suites tournaient, on passerait d'environ 85,7 % à 86,3 %. **L'écart avec 90 % vient donc surtout de tests absents, pas de suites ignorées.** (Les 27 tests externes : NOT_RUN_EXTERNAL_DEPENDENCY ; je ne les ai pas lancés.)

### 9.4 Où sont les points (variante CI, par dossier)
| Dossier | Lignes | Manquantes | Couverture | Part des manquantes |
|---|---|---|---|---|
| `api/services` | 20 785 | 2 724 | 86,9 % | 37,7 % |
| `api/tasks` | 2 478 | 1 325 | 46,5 % | 18,3 % |
| `api/alembic` (145 migrations) | 2 632 | 1 316 | 50,0 % | 18,2 % |
| `api/routers` | 9 729 | 1 023 | 89,5 % | 14,2 % |
| `api/security` | 5 216 | 737 | 85,9 % | 10,2 % |
| reste (`tools`, `schemas`, `models`, racine) | 9 843 | 101 | 99 % | 1,4 % |
Les 25 fichiers les moins couverts (≥ 20 lignes) sont dans `report-ci-like.txt` : en tête `alembic/versions/0088_…` (10,3 %), `0090_partie_12_billing` (15,8 %), `tasks/ab_tests` (18,9 %), `tasks/sales` (19,8 %), `tasks/plugins` (22,0 %), `0115_paystack_billing_support` (22,7 %), puis une douzaine de `services/*_extraction.py` à 23 %.
**La PR n°34 règle déjà l'essentiel de `api/tasks`** : `ab_tests` 18,9 → 99,1 %, `sales` 19,8 → 95,3 %, `analytics` 26,5 → 100 %, `fine_tuning` 32,9 → 100 %, `api_key_maintenance` 23,9 → 100 %, `billing` 58,4 → 97,1 %, `airbyte_client` 43,8 → 100 %.

### 9.5 Si l'on vise 90 % : propositions (AUCUN test écrit, en attente de votre accord ; gains estimés, NOT_VERIFIED)
Restant après la PR n°34 : 6 448 lignes manquantes ; il en faut ≤ 5 068.
| Priorité | Proposition | Lignes visées | Points |
|---|---|---|---|
| 1 | **Migrations Alembic exécutées dans le processus de test** : un test `upgrade head` puis `downgrade base` puis `upgrade head` sur une base jetable créée et supprimée par le test (nom contenant `test`). Aujourd'hui les migrations ne sont jouées que hors pytest (job CI, `Start-TestStack.ps1`), donc leurs corps ne comptent pas ; les 1 316 lignes manquantes sont presque toutes des `upgrade()`/`downgrade()` | environ 1 100 à 1 300 | environ +2,2 à +2,6 |
| 2 | `api/security/documents.py` (310 manquantes / 1 282) : chemins d'ingestion en erreur (formats, S3, OCR, limites) avec des faux fournisseurs, comme les tests d'extraction existants | 150 à 250 | +0,3 à +0,5 |
| 3 | `api/routers/crm.py` (242 / 452) : connecteurs CRM contre des faux fournisseurs locaux (méthode des tests de contrat Airbyte/Paystack de la PR n°34) | 150 à 200 | +0,3 à +0,4 |
| 4 | `tasks/media.py` (95), `tasks/autonomous_agents.py` (78), `services/metadata_filtering.py` (70), `services/agent_orchestrator.py` (70) | 150 à 250 | +0,3 à +0,5 |
| 5 | Observabilité : `security/tracing.py` (44) avec un exportateur de spans en mémoire, `routers/observability.py` (40), `loki_handler.py` (38), `alerting.py` (38) | 100 à 150 | +0,2 à +0,3 |
Lecture : **1 + 2 + 3** couvrent en ordre de grandeur les 1 380 lignes à gagner une fois la PR n°34 fusionnée (1 400 à 1 750 lignes visées) ; 1 + 2 seules sont limites. Sans la PR n°34, il faut en plus les modules `api/tasks` qu'elle couvre. Règles tenues : aucun test affaibli, aucune ligne retirée de la mesure, configuration de couverture inchangée. Réserve sur la priorité 1 : tester des migrations dans le processus de test est un vrai test (il vérifie que la chaîne s'applique et se défait), mais il exige une base dédiée créée par le test et un compte autorisé à `CREATE DATABASE` ; à valider avec vous avant de l'écrire.

### 9.6 Durée : `backend-tests` tiendra-t-il sous 75 minutes ?
Mesure locale (même machine, mêmes lots ; temps en secondes) :
| Lot | Sans couverture (10-23) | Avec couverture | Rapport |
|---|---|---|---|
| B1 | 404 | 2 510 | 6,21 |
| B2 | 1 297 | 2 937 | 2,26 |
| B3 | 1 087 | 4 316 | 3,97 |
| B4 | 669 | 2 205 | 3,30 |
| B5 | 1 336 | 2 256 | 1,69 |
| B6 | 1 627 | 1 713 | 1,05 |
| B7 | 455 | 463 | 1,02 |
| **B1..B7** | **6 875 (115 min)** | **16 400 (273 min)** | **2,39** |
**Contrôle A/B** (même soirée, `B4` sans couverture, 22:51) : 798 s contre 669 s le 23 octobre (bruit de machine de l'ordre de 20 %), contre 2 205 s avec couverture : **×2,76**. Le surcoût de la couverture est donc réel ; la dispersion entre lots (1,0 à 6,2) montre qu'il dépend fortement du contenu des tests.
**Estimation pour la CI (NOT_VERIFIED)** : `backend-tests` a duré 41 min 22 (run n°202, 6 256 tests, dont l'installation) ; en appliquant le rapport mesuré (≈ 2,4, plage 2,0 à 2,8) soit à la durée totale (83 à 116 min), soit seulement à la partie tests (environ 36 min, plus environ 5 min d'installation : 77 à 106 min) : **environ 77 à 116 minutes dans tous les cas**. **Toutes les estimations dépassent la limite de 75 minutes.** Le garde-fou `tests/test_ci_backend_timeout.py` n'impose qu'un plancher (`limit >= 60`) : relever `timeout-minutes` (par exemple à 150) ne le casse pas. Recommandation : relever la limite dans la même PR (une ligne), ou mesurer la couverture dans un job séparé. Je n'ai rien modifié (la branche est déjà poussée) ; le premier run de la PR le confirmera ou l'infirmera.

### 9.7 Ce qui n'a pas été fait
Couverture de branches (non demandée) ; mesure sur Linux / CI ; tests de la §9.5 (en attente d'accord) ; les 27 tests externes ; push et PR.
