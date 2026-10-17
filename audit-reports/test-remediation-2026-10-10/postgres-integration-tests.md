# postgres-integration-tests.md

Statuts utilisés : **PASS_VERIFIED** (sortie conservée), **FAIL_VERIFIED**, **BLOCKED_INFRASTRUCTURE**, **NOT_RUN_EXTERNAL_DEPENDENCY**, **HISTORICAL_RESULT_UNVERIFIED** (résultat annoncé pendant la session, sortie brute perdue avec le lecteur `D:`).
Aucune sortie n'est reconstituée : chaque ligne « vérifié » renvoie à un fichier de preuve listé en fin de document.

## 1. Cible PostgreSQL (vérifié le 2026-10-11 à 07:12, `evidence/phase3-checks.txt`)
| Élément | Constat |
|---|---|
| Serveur | PostgreSQL 17.11 (image `pgvector/pgvector:pg17`), conteneur `rag-test-pg` |
| Liaison réseau | `127.0.0.1:25432` uniquement (idem Redis `26379`, MinIO `29000`) |
| Bases | `rag_test_integration` (applicative), `rag_test_roundtrip_scratch` (destructive : RLS, concurrence), `pytest_p0` (preuve SQL tenant) |
| Migrations | les 3 bases à `0137` (`select version_num from alembic_version`) ; 6 politiques RLS et 179 tables dans `rag_test_roundtrip_scratch` |
| Rôle | `rag_test`, superutilisateur du conteneur jetable (voir limites) |

## 2. Garde-fous : refus vérifiés (`evidence/runner-refusals.txt`, 07:13)
Le lanceur `scripts/run_isolated_tests.py` a été exécuté pour de vrai avec des cibles interdites ; il s'arrête avec le **code 2** avant toute connexion :
| Cas | Résultat |
|---|---|
| base sur un pooler hébergé (hôte non local) | refusé |
| hôte local mais nom de base non marqué (`postgres`) | refusé |
| Redis hébergé | refusé |
| stockage objet hébergé | refusé |
| aucune base configurée | refusé |
PASS_VERIFIED. Les mêmes règles sont testées sans infrastructure par `tests/test_isolated_test_runner.py` (10 tests, **passés**, voir `full-suite-results.md`). Les tests destructifs exigent en plus `tests/disposable_pg_guard.py` : hôte local, nom contenant `disposable|roundtrip|scratch|throwaway`, `RAG_DISPOSABLE_PG_CONFIRM` égal au nom, cible différente de `DATABASE_URL` (17 tests de la garde : **passés**).
Limite : `DATABASE_URL_TRANSACTION` et `DATABASE_URL` sont toutes deux alignées par le lanceur sur la base locale ; les variables équivalentes du parent (`STAGING_DATABASE_URL`, `MAIN_DATABASE_URL`) ne sont pas transmises à l'enfant (environnement assaini).

## 3. Tests PostgreSQL : statut par fichier (mis à jour : suite rejouée sur `c161b83`, 2026-10-12)
| Fichier | Ce qu'il prouve | Statut actuel |
|---|---|---|
| `test_postgres_system_log_handler.py` (3, nouveau) | le handler écrit une ligne commitée, visible d'une autre connexion ; secret au format pris en charge masqué ; une panne de base ne remonte pas à l'appelant | **PASS_VERIFIED** : 3 passés, `v1-81plus3.xml`, code 0 |
| `test_disposable_pg_guard.py` (17) | la garde de base jetable | **PASS_VERIFIED** (pur, sans base) |
| `test_postgres_tenant_rls.py` (8) | avec `SET LOCAL ROLE` d'un rôle simple, seule l'organisation déclarée est visible ; le contexte survit au commit ; sans politique la fuite réapparaît | **PASS_VERIFIED** : 8 passés sur la base destructive `rag_test_roundtrip_scratch` (run3, `c161b83`). Les erreurs du passage interrompu étaient donc d'infrastructure (Docker bloqué) : BLOCKED_INFRASTRUCTURE confirmé par le rejeu. |
| `test_postgres_invoice_concurrency.py` (5), `test_postgres_credits_concurrency.py` (1), `test_postgres_subscription_concurrency.py` (1) | transactions réellement simultanées (`asyncio.gather` / `create_task`, première transaction maintenue ouverte pour les factures, vérifié en lisant le code) : paiements doubles, annulation contre paiement, balayage des retards, dérive du registre de crédits | **PASS_VERIFIED** : factures 5, crédits 1, abonnements 1 passés (run3). Les 7 échecs du passage interrompu ne se sont pas reproduits. |
| `test_postgres_integration.py` (24) | contraintes, RLS activé sur toutes les tables, rôle de l'application, index/extensions | **PASS_VERIFIED pour 23** (run3) ; **1 NOT_RUN_EXTERNAL_DEPENDENCY** (`test_rls_policies_exist_on_staging`, exige le catalogue du staging hébergé : 77 politiques ou plus créées hors migrations) |
| `test_p0_sql_tool_tenant_bypass.py` (9 PostgreSQL) | l'outil SQL ne renvoie jamais les lignes d'une autre organisation | **PASS_VERIFIED** : 38 passés au total dans le fichier, dont les 9 tests PostgreSQL (run3) |
| `test_rbac_integration.py` (38), `test_jwt_key_rotation_integration.py` (13), `test_oauth_logic_integration.py` (7), `test_domain_verification_integration.py` (5), `test_ssl_certificate_renewal_integration.py` (5), `test_email_domains_integration.py` (2) | RBAC, rotation des clés, OAuth, domaines, SSL (tâche de renouvellement), e-mail | **PASS_VERIFIED** (run3) : RBAC 38, JWT 13, OAuth 16, domaines 5, SSL 5, e-mail 7 passés |
| `test_documents_integration.py` (23), `test_celery_integration.py` (8), `test_avatar/branding_storage_integration.py` (13), `test_e2e_lifecycle.py` (1) | pipeline documents, purge Celery avec worker réel, stockage S3, cycle de vie bout en bout | **PASS_VERIFIED** (run3) : documents 26 passés + 2 ignorés externes (Google Drive), Celery 8 (worker réel), avatars 7, branding 6, e2e 1 |

Pour SSL : les tests ciblent la tâche de renouvellement et son état en base, pas une poignée de main TLS réelle. Aucune vérification TLS n'a été désactivée (aucun changement n'a touché ce code) ; la couverture TLS réelle (certificats invalides, connexion refusée) n'existe pas dans la suite : **NOT_VERIFIED**, à traiter comme un manque de couverture, pas comme un résultat.

## 4. Limites à ne pas oublier
1. Le rôle `rag_test` est superutilisateur : il contourne RLS. Les tests RLS prouvent la **logique des politiques** avec un rôle simple créé pour l'occasion, **pas** l'effet en production (rôle d'exécution réel inconnu : NOT_VERIFIED, voir `remediation-2026-10-10/13-external-blockers.md`).
2. `test_the_apps_own_role_bypasses_rls` documente ce contournement : avec un autre rôle d'exécution, ce test échouera, et c'est voulu.
3. Aucune base hébergée (Supabase, Render) n'a été utilisée ou touchée par ces vérifications.

## 5. Défaut du premier passage : l'environnement du processus
Le premier passage complet (17:42-20:15) a chargé le `.env` réel dans `os.environ` (la conftest le lit) tout en visant une base factice. Je n'ai relevé aucun trafic réseau : **NOT_VERIFIED** qu'aucun service hébergé n'ait été contacté (variables S3 / e-mail possibles). Le lanceur isolé élimine ce risque pour la suite.

## 6. Preuves (hors dépôt : `C:\Users\NITROV15\rag-test-evidence\2026-10-11\raw\`)
`phase3-checks.txt`, `runner-refusals.txt`, `v1-81plus3.xml|.txt|.byfile.txt|.exit.txt|.cmd.txt`, `ruff.txt`. Les sorties brutes ne sont pas copiées dans le dépôt (elles peuvent contenir des chemins locaux) ; les empreintes SHA-256 figurent dans `resume-session.md`.
