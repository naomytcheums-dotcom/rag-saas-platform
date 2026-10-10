# 16 — Index des preuves

Audit du 2026-10-10, HEAD `59d5ec9`. Les lignes citées sont celles observées à la date de l'audit ; les numéros issus des sous-agents sont « approximatifs ».

## Git / historique
| Affirmation | Preuve |
|---|---|
| HEAD = fusion PR n°20 à 11:40, parents `bb0a89d` et `eb2e8e5`, identique à `origin/main` | `git log -1`, `git rev-list --left-right --count HEAD...origin/main` = `0 0` |
| 131 commits depuis `2e7bfaa` ; 565 commits au total | `git rev-list --count` |
| Commits de correction R1–R7 : `913f91b`, `288d481`, `8907f03`, `7a19b2d`, `663df87`, `d4e7b32`, `574ecd2` | `git log` |
| BILL-011/020 `4b0a810` ; BILL-013 `2b5b583` ; BILL-014 `e543e41` ; BILL-015 `40d973a` ; BILL-017 `8bb5ede` ; TEN-003 `01f90f4` ; TEN-005 `a324fcf` ; MAP-003 `5a26f51` ; TEN-009 garde `1fd0810` ; TEN-012 `eb2e8e5` (utilisatrice) | `git log` |
| Correctifs CI : `60dee60`, `53c8868`, `77f4cbf`, `4ee2c22`, `86f7c94`, `b336483` | `git log` |

## Mesures (scripts hors dépôt `D:\rag-work\audit-scripts\`)
| Valeur | Source |
|---|---|
| 943 opérations / 788 chemins / POST 356, GET 420, DELETE 85, PATCH 80, PUT 2 ; 84 sans dépendance d'auth détectée ; 183 sans test référençant le chemin | `routes.py` → `04_API_ENDPOINTS.csv`, `routes_summary.json` |
| 177 modèles / 177 tables / 80 avec `organization_id` / 312 FK / 214 index / 62 unicités ; 136 migrations, tête `0136` ; 57 `ENABLE RLS`, 0 `FORCE`, 0 `CREATE POLICY` | `db.py` → `db_summary.json` |
| 150 lignes d'inventaire (130/18/2) ; 275 identifiants N.N.N ; 323 jetons ; « 515 » : 1 occurrence (ligne 5) | `cahier.py`, `cahier2.py` → `cahier_summary.json` |
| 6 130 tests collectés (+23 désélectionnés) ; 473 fichiers `test_*.py` ; 518 tests dans 43 fichiers `test_p0_/p1_/p2_` | `pytest --collect-only` → `collect.txt` |
| 180 lignes de registre : 173 identifiants d'origine + 7 identifiants R1–R7 ; statuts : 45 CORRIGÉ, 7 NON VÉRIFIABLE, 122 OUVERT (NON REVÉRIFIÉ), 3 PARTIELLEMENT CORRIGÉ, 1 TOUJOURS PRÉSENT, 1 OBSOLÈTE, 1 DOUBLON | `findings.py` → `findings_summary.json` |
| 57 `page.tsx` ; 10 layouts ; 187 composants | `Get-ChildItem`, `git ls-files` |
| vitest 27 fichiers / 178 tests ; tsc 0 ; eslint 0 ; ruff propre | exécutions du 2026-10-10 |

## CI distante (lecture API publique, sans authentification)
| Résultat | Référence |
|---|---|
| GitHub `CI` success sur `59d5ec9` | run 38045720816 ; jobs `backend-tests` 10:40→11:22, `backend-security`, `build-*`, `frontend-checks` |
| GitHub `CI` success sur `4ee2c22` | run 38041400768 |
| GitHub `CI` failure sur `b8a0471` (5 échecs, 6 021 passés, 46 ignorés) | run 38039631445 / job 114164431007 |
| CircleCI `api-tests` success sur `59d5ec9` (build #494, 3 256 s, couverture 77,41 %) ; success sur `eb2e8e5` (#491) | `circleci.com/api/v1.1/project/github/naomytcheums-dotcom/rag-saas-platform/494` |
| CircleCI `api-tests` failed sur `4ee2c22` (#490) : MinIO exit 137 puis erreurs de connexion localhost:9000 | build #490 |
| Workflow « Celery worker (scheduled burst) » success sur `59d5ec9` | `actions/runs` |

## Code (observé)
| Sujet | Fichier |
|---|---|
| RLS non contraignant | `api/alembic/versions/0098_rls_coverage_gap.py`, `0002`, `0032`, `0131` |
| Dimension vectorielle 384, HNSW | `api/alembic/versions/0128_pgvector_embeddings.py`, `api/config.py` (`EMBEDDING_VECTOR_DIM`) |
| API sans worker | `Dockerfile.api` (CMD gunicorn + commentaire), `render.yaml`, `docker-entrypoint.sh` |
| `/metrics` jeton optionnel | `api/main.py:426-444` |
| Métriques de retrieval | `api/services/retrieval_metrics.py` |
| Règles de factures | `api/services/billing_invoices.py`, `api/routers/billing.py`, `api/routers/admin_subscriptions.py`, `docs/admin/BILLING.md` |
| Verrous | `api/services/admin_subscriptions.py`, `api/services/billing_credits.py`, `api/services/billing_stripe.py`, `api/services/billing_paystack.py` |
| MCP stdio contrôlé | `api/routers/mcp_servers.py` (`_require_stdio_allowed`) |
| Pages MAP-003 | `frontend/app/{restore-account,reactivate-consent,2fa-lockout-recovery}/page.tsx`, `frontend/components/auth/TokenConfirmForm.tsx` |
| Cahier des charges | `docs/CAHIER_DES_CHARGES.md` lignes 5, 3051-3066 (« Total recompté »), 2412 (Partie 15), 3654 (archive), 3836 (addendum) |

## Autres livrables
`00` synthèse · `01` inventaire · `02` matrice · `03` architecture · `04` routes · `05` frontend · `06` RAG · `07` sécurité · `08` base · `09` facturation · `10` tests/CI · `11` constats · `12` risques · `13` plan · `14` environnements · `15` méthodologie.
