# Phase 1 Complete — Workspace + Database Forensics

## Scope exécuté

Inspection du workspace, Git, configuration DB non sensible, graphe Alembic
local, statut des migrations, modèles déclarés, RLS et pgvector. Aucun refactoring,
mutation DB, changement de stratégie RLS, suppression, stage ou commit.

## WORKSPACE

- Workspace : `C:\Users\NITROV15\Downloads\rag-saas-platform`.
- Branche `main`, HEAD `2e7bfaa` (2026-09-27).
- 132 chemins suivis modifiés + 145 non suivis à la clôture (le dépôt était
  déjà sale avant nos corrections).
- `.env`, `frontend/.env.local`, dump Redis, binaires, venvs/caches existent;
  noms/existence uniquement, valeurs non consultées; fichiers ignorés par Git.
- Faits complets : [WORKSPACE_FORENSICS.md](./WORKSPACE_FORENSICS.md).

## DATABASE

- Configuration locale présente, driver `postgresql+asyncpg`, host
  Supabase/non-local; URL et identifiants non exposés.
- Environnement de destination **non déterminé** : DEV / TEST / STAGING /
  PRODUCTION inconnu.
- Métadonnées ORM : 177 tables, 79 avec colonne directe `organization_id`;
  les autres demandent analyse de leurs relations et ne sont pas classées
  automatiquement non-tenant.
- Connexion SQL live non tentée dans cette Phase 1. Révision réellement
  appliquée, catalogues, sauvegarde/restauration : inconnus.
- **DATABASE_MUTATION = BLOCKED.**

## ALEMBIC

- `alembic heads`, `history` et inspection ScriptDirectory ont été limités aux
  fichiers locaux; aucune connexion DB.
- 131 révisions chargées, une tête `0131`, une base, zéro merge, zéro parent
  manquant. 124 migrations sont suivies au HEAD Git.
- La commande `alembic current` échouait lors de l'audit initial (code 1);
  aucune version DB n'a été établie.

## MIGRATIONS

- 0125–0131 sont présentes mais non suivies dans le worktree; leur inclusion
  locale dans le graphe ne signifie pas qu'elles sont commitées ou appliquées.
- 0132 est dans `scripts/pending/`, hors du graphe Alembic. L'endpoint/schema
  public exposent `description`, alors que `Workspace` ne déclare pas ce
  champ; persistance à vérifier/corriger dans une phase ultérieure.
- Le scan statique a identifié des opérations structurelles à évaluer :
  `0010` copie le rôle puis supprime l'ancien champ; `0115` remplace des
  contraintes d'unicité/clé primaire; downgrade 0128/0131/0132 risque de retirer
  respectivement des données vectorisées, RLS et descriptions.
- Aucune migration appliquée.
- Détails : [DATABASE_FORENSICS.md](./DATABASE_FORENSICS.md).

## PENDING MIGRATIONS

| Révision | Situation locale | Risque / condition |
|---|---|---|
| 0125–0127 | Dans `api/alembic/versions/`, non suivies par Git | Existence/applicabilité en DB inconnue. |
| 0128 | Dans le dossier de versions, non suivie | pgvector/HNSW/backfill ne sont pas vérifiés sur données réelles. |
| 0129–0131 | Dans le dossier de versions, non suivies | 0131 active RLS sans policies; rôle DB réel inconnu. |
| 0132 | `scripts/pending/`, non suivie et hors du chemin Alembic | Synchroniser modèle `Workspace`, schéma/API et migration avant intégration. |

## RLS

- Recherche statique : migrations `ENABLE ROW LEVEL SECURITY`; aucun `CREATE
  POLICY`, `FORCE ROW LEVEL SECURITY` ou policy ORM identifié.
- Les tests PostgreSQL du dépôt affirment zéro policy et rôle applicatif
  `BYPASSRLS`, mais ces tests n'ont pas été lancés sur la DB actuelle; ce sont
  des assertions du code de test, pas une observation live actuelle.
- L'isolation DB de la cible réelle n'est donc pas vérifiée; le dépôt s'appuie
  sur la vérification applicative des tenants.
- Aucun changement RLS fait.
- Détails : [RLS_FORENSICS.md](./RLS_FORENSICS.md).

## PGVECTOR

- Migration 0128 déclare extension `vector`, colonne dimensionnée,
  backfill et index HNSW cosine; modèle déclaratif contient
  `embedding_vector`.
- `retrieval_pipeline.py` a un chemin pgvector serveur avec filtres
  organisation/métadonnées/documents, et retombe sur le chemin numpy si le
  dialecte/flag/dimension ne convient pas ou si la requête native échoue.
- Un chemin de code et des tests statiques ne prouvent pas l'extension/index
  existant, le planner qui utilise HNSW ni la latence/recall sur la DB réelle.
- Validation live/EXPLAIN/benchmark : `BLOCKED_EXTERNAL` tant que la cible DB
  n'est pas explicitement identifiée et autorisée.

## GIT RISKS

- Modifications préexistantes nombreuses; leur provenance n'a pas été établie.
- 0125–0131 migrations de sécurité/produit non suivies; scripts pending 0132
  non suivis; aucun ajout au staging.
- État sur `main`; aucune branche de sécurité créée, car ce jalon demande
  uniquement l'inventaire et interdit la mutation Git.
- Plusieurs worktrees locaux enregistrés; leurs contenus n'ont pas été touchés.
- Voir [CHANGE_LEDGER.md](./CHANGE_LEDGER.md).

## SECURITY RISKS

- RLS active sans policy ne filtre pas le rôle applicatif qui bypass RLS selon
  la conception/tests du dépôt; aucun rôle live n'a été interrogé.
- 98 tables ORM n'ont pas de colonne directe `organization_id`; plusieurs
  peuvent être liées par FK ou non-tenants. Une cartographie relationnelle
  exhaustive demeure à réaliser.
- Les risques précédemment corrigés de recharge gratuite et débit A2A sont
  consignés dans [SECURITY_AUDIT.md](./SECURITY_AUDIT.md); changements locaux
  et tests ciblés ne valident pas la configuration production ou les verrous
  PostgreSQL concurrents.
- Aucune stratégie de sécurité n'a été changée pendant cette Phase 1.

## BLOCKED_EXTERNAL

- Base Supabase distante : environnement et autorisation non confirmés; pas de
  SQL/catalogue/pgvector/RLS live.
- Sauvegarde exploitable/restauration réelle non observées.
- Services externes dépendant de la DB : aucun test de provider/Redis/Celery
  nécessaire ou réalisé pour ce jalon.

## FILES CREATED

- [WORKSPACE_FORENSICS.md](./WORKSPACE_FORENSICS.md)
- [DATABASE_FORENSICS.md](./DATABASE_FORENSICS.md)
- [RLS_FORENSICS.md](./RLS_FORENSICS.md)
- [CHANGE_LEDGER.md](./CHANGE_LEDGER.md)
- [PHASE_1_REPORT.md](./PHASE_1_REPORT.md)

## FILES MODIFIED

- Aucun fichier applicatif/modèle/migration/configuration n'a été modifié
  pendant la Phase 1. Les cinq rapports ci-dessus sont les seuls nouveaux
  fichiers de cette phase.
- Les corrections autorisées antérieures et les rapports initiaux préexistants
  sont enregistrés dans `CHANGE_LEDGER.md`.

## TESTS EXECUTED

- Phase 1 : **aucun test applicatif**, aucune migration, aucun SQL live.
- Contrôles statiques locaux : graphe Alembic, comptage ORM, Git, références
  RLS et pgvector.
- Suite ciblée de la phase corrective antérieure :
  84 tests passés, 2 avertissements A2A `ActiveTask`; détails et commandes dans
  `CHANGE_LEDGER.md`. Ruff présente encore les constats documentés.

## NEXT PHASE

**STOP à la demande du prompt Phase 1.** Ne pas commencer Phase 2 sans
validation utilisateur. Prochaine proposition lorsque la suite sera autorisée :
résoudre d'abord l'incertitude d'environnement DB et la provenance des
changements, puis établir une cible staging explicitement isolée, obtenir
revision/catalogues/sauvegarde read-only et préparer une matrice migration/RLS
sans mutation.
