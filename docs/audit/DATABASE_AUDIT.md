# Database Audit — Initial

Date : 2026-10-03. Inspection statique seulement; aucune migration n'a été
appliquée et aucun schéma de production n'a été modifié.

## Architecture et inventaire

- ORM : SQLAlchemy 2 async; registre construit dans `api/models/` et importé
  par `api/alembic/env.py`.
- Base déclarée : PostgreSQL; tests rapides SQLite. Migrations sous
  `api/alembic/versions/`.
- Inventaire : 86 modules de modèles et 131 fichiers de migration dans le
  workspace courant.
- Domaines présents dans les modèles/migrations : utilisateurs/sessions,
  organisations/membres, workspaces, documents/chunks, agents/exécutions,
  conversations/réponses/citations, workflows, évaluations, médias, billing,
  integrations, MCP, notifications, audit et observabilité.
- Les modèles consultés montrent des FK et clés d'organisation sur des objets
  tels que `Organization`, `Document` et `Agent`; cet échantillon n'est pas une
  vérification exhaustive de chaque table, index, contrainte ou cascade.

## État Alembic

| Contrôle | Résultat |
|---|---|
| Révisions présentes | 0001 à 0131 (131 fichiers) |
| `alembic heads` | `0131 (head)` |
| `alembic current` | Échec, code de sortie 1; aucune révision réelle établie |
| Révision 0132 | `scripts/pending/0132_workspace_description.py`, hors `api/alembic/versions/` |
| 0125 / 0126 / 0127 | Présentes sous `api/alembic/versions/`; présence locale ne signifie pas appliquée |
| Test live schéma/catalogue | Non établi dans cette phase |

Le fichier 0132 ajoute `workspaces.description` et indique `down_revision=0131`,
mais il n'est pas encore un élément du graphe Alembic chargé. L'intégrer
nécessiterait une décision et une vérification de cohérence, pas une
application automatique.

## RLS et isolation tenant

- Des migrations activent RLS depuis les premières tables et la migration
  0131 l'active sur onze tables, dont notifications, diagnostics, recordings,
  expériences et exécutions de nœuds.
- `tests/test_postgres_integration.py` contient un test qui attend que RLS soit
  activé sur les tables et un test qui constate zéro policy RLS dans `public`.
  Il affirme également que le rôle utilisé par l'application possède
  `BYPASSRLS`.
- Conséquence : le RLS actuel n'applique pas de filtre d'organisation pour le
  rôle API. L'isolation repose sur les filtres applicatifs et le RBAC. Il
  s'agit d'une limite architecturale de sécurité, pas d'une preuve qu'une
  fuite tenant a été observée.
- La vérification de chaque table (présence colonne tenant, rôle, policies
  SELECT/INSERT/UPDATE/DELETE, FORCE RLS, grants et accès Supabase/PostgREST)
  reste à exécuter sur une base de test avec rôle sûr.

## pgvector et index

- Migration 0128 crée conditionnellement l'extension `vector`, une colonne
  `vector(EMBEDDING_VECTOR_DIM)`, un backfill et un index HNSW cosine sur
  `document_chunks`.
- Elle garde le JSON d'embedding et un chemin de repli pour les dimensions
  différentes.
- L'index réel, son utilisation par le planner, ses dimensions déployées et
  les plans `EXPLAIN ANALYZE` ne sont pas vérifiés. La migration est non
  destructive en intention, mais son état d'application et ses prérequis
  PostgreSQL/extension sont inconnus.

## Transactions, contraintes et risques connus

- L'ORM montre des FK et contraintes uniques (par exemple une adhésion
  organisation/utilisateur unique); aucune comparaison générale modèle ↔
  migrations ↔ catalogues n'a été possible.
- Débit A2A postérieur à l'exécution et top-up sans paiement conditionnel
  constituent des risques métier reliés au stockage/crédits; voir
  [SECURITY_AUDIT.md](./SECURITY_AUDIT.md).
- Les tests PostgreSQL sont conditionnés à `DATABASE_URL` accessible et
  peuvent être sautés; les assertions SQLite ne prouvent ni le comportement
  RLS, ni les courses et verrous Postgres.

## Décision d'audit

**État DB : `UNVERIFIED`.** Ne pas appliquer de migration à la base réelle
avant d'obtenir la révision courante, une sauvegarde vérifiée, un diff du
schéma et une revue ciblée du graphe, surtout 0131 et le fichier pending 0132.
