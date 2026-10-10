# 08 — Base de données et migrations

Audit du 2026-10-10, HEAD `59d5ec9` (fusion de la PR n°20). **Le schéma réel de la base distante (Supabase) n'a pas été inspecté** : aucune connexion, aucune requête, aucune migration. Tout ce qui suit décrit le code (modèles SQLAlchemy, migrations Alembic).

## Chiffres mesurés (script `db.py`, import des modèles puis lecture de `Base.metadata`)
| Mesure | Valeur | Méthode / limite |
|---|---:|---|
| Modèles mappés (classes SQLAlchemy) | 177 | `Base.registry.mappers` après import de tous les modules `api/models/*` (87 fichiers) |
| Tables dans les métadonnées | 177 | `Base.metadata.tables` (1 modèle = 1 table dans ce dépôt) |
| Tables avec une colonne `organization_id` | 80 | présence de la colonne dans le modèle |
| Tables sans `organization_id` | 97 | à interpréter : tables enfants (reliées par FK à une table avec org), tables d'authentification, tables globales. **Aucune vérification table par table de l'isolation n'a été faite.** |
| Clés étrangères déclarées | 312 | modèles |
| Index déclarés dans les modèles | 214 | n'inclut pas les index créés seulement par migration (ex. HNSW) |
| Contraintes d'unicité déclarées | 62 | modèles |
| Fichiers de migration | 136 | `api/alembic/versions/0001_create_auth_tables.py` … `0136_notification_templates.py` |
| Têtes Alembic | 1 (`0136`) | analyse des `revision`/`down_revision` |
| Schémas Pydantic (fichiers) | 80 | `api/schemas/*.py` |
| Colonnes vectorielles | 1 : `document_chunks.embedding_vector`, dimension 384 | modèle + migration `0128_pgvector_embeddings.py` |

## État de production connu (déclaratif, non vérifié ici)
- Selon l'utilisatrice (conversation du 2026-10-10) : migrations `0134` et `0135` **déjà appliquées** en production ; **`0136` non appliquée** (à lancer après fusion). Source : message utilisateur, pas une vérification.
- `docs/audit/PRODUCTION_BLOCKERS.md` (2026-10-03) : « `alembic current` termine en échec ; aucune version appliquée n'a été établie » — état ancien.
- Aucun `alembic upgrade head` n'est présent dans `render.yaml`, `Dockerfile.api` ni `docker-entrypoint.sh` (voir `10_TESTS_CI_DEPLOIEMENT.md`) : **qui exécute les migrations en production n'est pas établi par le dépôt**.

## RLS PostgreSQL — constat
- 57 fichiers de migration contiennent `ENABLE ROW LEVEL SECURITY` ; **0** contiennent `FORCE ROW LEVEL SECURITY` ; **0** contiennent `CREATE POLICY` (recherche textuelle sur `api/alembic/versions`).
- `0098_rls_coverage_gap.py` et `docs/CAHIER_DES_CHARGES.md` indiquent que l'application se connecte avec un rôle `postgres` susceptible de posséder `rolbypassrls` : RLS y est qualifié de « signal de conformité / défense en profondeur, pas une isolation fonctionnelle ».
- **Conclusion (CONFIRMÉ PAR LECTURE DU CODE, schéma réel non vérifié)** : sans politique ni `FORCE`, et avec un rôle propriétaire/contournant, RLS ne protège pas contre un oubli de filtre `organization_id` dans le code. L'isolation multi-tenant repose sur les filtres de la couche service/routeurs et sur les tests (voir `07_AUTH_TENANT_SECURITY.md`).

## Embeddings et index vectoriels
- `EMBEDDING_VECTOR_DIM=384` (défaut de `api/config.py`), colonne `vector(384)` + index HNSW cosinus (migration `0128`). Les embeddings d'une autre dimension restent dans la colonne JSON historique (pas de ANN pour eux).
- **CONTRADICTOIRE** (voir `06_RAG_PIPELINE.md`) : la documentation du pipeline de recherche décrit encore une similarité numpy en mémoire, alors que l'index HNSW existe ; quel chemin la requête de production emprunte n'est pas prouvé par exécution.

## Divergences SQLite (tests) / PostgreSQL (production)
La suite de tests utilise SQLite en mémoire (`tests/conftest.py`, confirmé par le commentaire de `ci.yml` : « the test suite itself runs against an in-memory SQLite DB »). Conséquences établies ou observées pendant ce travail :
- `SELECT … FOR UPDATE` est ignoré par SQLite : les verrous (R4, BILL-011) ne se prouvent que sur PostgreSQL. Preuves disponibles : tests opt-in `tests/test_postgres_subscription_concurrency.py`, `tests/test_postgres_credits_concurrency.py`, `tests/test_postgres_invoice_concurrency.py` exécutés le 2026-10-10 sur la base jetable locale `rag-pr1-disposable-pg` (garde `tests/disposable_pg_guard.py`). **Ils ne sont pas exécutés en CI** (ignorés sans `RAG_DISPOSABLE_PG_URL`).
- SQLite ne vérifie pas les clés étrangères (un test sur « organisation fantôme » a dû être écrit autour de cette limite) et renvoie parfois des datetimes sans fuseau (bug corrigé dans `_extend_period_from_invoice`, commit `7a19b2d`).
- RLS, types `vector`, contraintes d'unicité partielles et index HNSW ne sont pas testés par SQLite. Des tests PostgreSQL existent derrière `P0_PG_TEST_URL` (9 tests ignorés en l'absence de la variable).

## Migrations : points à surveiller
- `agents.md` interdit de modifier les migrations existantes ; aucun fichier de migration existant n'a été modifié par cet audit (lecture seule).
- Compatibilité : un aller-retour 0→0136 a été exécuté sur la base jetable le 2026-10-09 (ROADMAP, entrée « Audit P1/P2 »). **Non rejoué dans cet audit.**
- Migration `0136_notification_templates` : crée la table du modèle `NotificationTemplate` (qui n'avait aucune migration, constat TEN-006) ; pas encore appliquée en production selon l'utilisatrice.

## Non établi
- Version réelle du schéma de production, présence de la table `notification_templates`, privilèges réels du rôle applicatif (`BYPASSRLS`), index réellement présents, volumétrie.
