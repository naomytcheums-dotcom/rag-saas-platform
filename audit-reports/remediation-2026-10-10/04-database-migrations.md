# 04 — Base de données et migrations

## Alembic (recalculé aujourd'hui)
| Fait | Résultat | Preuve |
|---|---|---|
| Fichiers de migration | 137 (`0001` … `0137`) | `api/alembic/versions` |
| Têtes | **1** (`0137`) ; historique linéaire, ids = numéros de fichier | `tests/test_migration_chain_integrity.py` (4 réussis) |
| Chaîne complète sur base vide PostgreSQL 17 (pgvector) | `alembic upgrade head` code 0, 5 à 16 s | exécuté 3 fois sur `rag_remediation_scratch` (conteneur jetable `rag-pr1-disposable-pg`, hôte 127.0.0.1) |
| Aller-retour | `0136 → 0137 → 0136 → 0137` : 6 / 0 / 6 politiques | exécuté |
| Extensions | `vector` créée par `0128`, index HNSW `ix_document_chunks_embedding_vector_hnsw` présent ; colonne `embedding_vector vector(384)` | requêtes catalogue |
| Dérive ORM ↔ schéma migré | **155 différences** (voir ci-dessous) | `alembic.autogenerate.compare_metadata` sur la base fraîche |
| État de la production | **INCONNU** : `0134` et `0135` appliquées, `0136` non appliquée (déclaré par la propriétaire, non vérifié) ; `0137` non appliquée | BLOCKED_EXTERNAL |
| Procédure de déploiement des migrations | aucune automatisation dans `render.yaml`, `Dockerfile.api`, `docker-entrypoint.sh` : exécution manuelle (`14-deployment-runbook.md`) | lecture des fichiers |

Aucune commande `alembic` n'a été lancée contre une base distante. Aucune migration existante n'a été modifiée.

## Dérive modèles ↔ migrations (REM-008, VERIFIED, non corrigée)
- **107 colonnes** sont `NULL`ables en base alors que le modèle les déclare `NOT NULL` (surtout `created_at` / `updated_at` : les migrations n'ont pas posé le `NOT NULL`). Le code suppose une valeur ; une ligne insérée hors ORM peut contenir `NULL`.
- **11 colonnes** `TIMESTAMP` (sans fuseau) en base contre `DateTime` du modèle (`call_records`, `conversation_shares`, `follow_up_questions`…) : risque de comparaisons naïf/aware (le bug réglé dans `_extend_period_from_invoice` est de cette famille).
- **1 longueur** : `notification_templates.title` `VARCHAR(500)` (migration 0136) contre 200 (modèle).
- **Table `casbin_rule`** présente en base, sans modèle.
- **25 index** en base absents des modèles (dont le HNSW, attendu : créé par migration seulement) et 4 contraintes/index déclarés par les modèles mais absents de la base (`ix_agent_api_keys_key_hash`, `ix_permissions_key`, `ix_widget_configs_public_key`, `ix_payment_customers_organization_id`, contraintes d'unicité `call_records.call_sid`, `conversation_shares.token`).
- Détail : `D:\rag-work\audit-scripts\schema_diff.csv` (hors dépôt, 155 lignes).
Correction proposée : une migration **par famille**, avec contrôle préalable des données (`SELECT count(*) WHERE col IS NULL`), sauvegarde et rollback ; jamais de `autogenerate` brut. Non faite : elle demande une base représentative.

## Cohérence demandée
- Tables d'évaluation, questions, datasets, organisations, memberships, documents, chunks, runs, crédits, notifications : toutes présentes dans la chaîne ; `notification_templates` (TEN-006) créée par `0136`. Écart de longueur ci-dessus.
- Dimensions d'embedding : colonne vectorielle fixe à 384 ; les autres dimensions restent dans la colonne JSON (voir `08-rag-evaluation.md` / rapport d'audit `06_RAG_PIPELINE.md`).
- Clés étrangères manquantes sur certaines ressources (point cité par l'audit) : **NOT_VERIFIED** (non recherché table par table dans cette session).

## Migrations en attente en production (selon la propriétaire) et dépendances
`0136` (additive, crée `notification_templates`), `0137` (additive : 6 politiques inertes tant que le rôle contourne RLS). Ordre : sauvegarde → `0136` → `0137`. Dépendance externe : accès autorisé à la base de production.
