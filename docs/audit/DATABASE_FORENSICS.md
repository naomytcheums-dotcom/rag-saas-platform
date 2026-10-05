# Database Forensics — Phase 1

Date : 2026-10-03. Statique et sans connexion DB. Cette note complète
[DATABASE_AUDIT.md](./DATABASE_AUDIT.md) avec le contrôle forensique demandé.

## Cible configurée et garde-fous

- `DATABASE_URL` est défini dans l'environnement local et utilise
  `postgresql+asyncpg`; le host est Supabase/non-local.
- `DATABASE_URL_TRANSACTION` est aussi configuré. `api/database.py` sélectionne
  ce paramètre si présent pour le moteur applicatif; `api/alembic/env.py`
  construit ses connexions depuis `settings.DATABASE_URL`.
- La cible n'est pas classée avec certitude DEV / TEST / STAGING / PRODUCTION.
- Le contenu de `.env` n'a pas été lu ni divulgué. Aucun `SELECT`, ping, test
  PostgreSQL ou connexion réseau n'a été fait dans cette phase.
- **Décision :** `DATABASE_MUTATION = BLOCKED` et inspection SQL live
  `BLOCKED` jusqu'à identification explicite de l'environnement et de son
  autorisation de lecture.

## Structure déclarée par le code

- Configuration Alembic : `alembic.ini` pointe sur `api/alembic`.
- `api/alembic/env.py` importe `api.models.Base.metadata` pour autogenerate.
- Registre ORM importable : **177 tables**; **79** ont une colonne directe
  `organization_id`, les **98** autres ne peuvent pas être qualifiées comme
  non-tenant sans analyser leurs relations (plusieurs peuvent être des objets
  personnels, globaux ou tenant-scope via FK).
- Ces nombres décrivent les métadonnées Python chargées localement; ils ne
  prouvent pas l'existence ni la définition des tables en DB.
- SQLAlchemy async; le suite rapide utilise SQLite en mémoire. Tests
  PostgreSQL séparés existent et indiquent qu'ils sautent lorsque la DB n'est
  pas joignable.

## Graphe de révisions

Lecture de `ScriptDirectory`, sans connexion :

| Contrôle | Résultat local |
|---|---|
| Révisions découvertes sous `api/alembic/versions` | 131 |
| HEAD(s) | `0131` |
| Base(s) | 1 |
| Révisions merge | 0 |
| Parents absents du graphe | 0 |
| Nombre de révisions suivies dans Git au HEAD | 124 |
| Révision courante de la DB | **Inconnue** |

Le graphe local chargé est une chaîne linéaire de 0131 révisions et n'a pas de
branche/parent manquant. Ce contrôle est uniquement structurel; il ne prouve
pas l'ordre de déploiement réel.

## Révisions locales non suivies / en attente

Les fichiers 0125 à 0131 sont présents localement sous
`api/alembic/versions/`, **tous non suivis par Git** à l'observation de phase 1.
Le graphe local les charge quand même car Alembic inspecte les fichiers locaux.
La révision **0132** est sous `scripts/pending/0132_workspace_description.py`,
hors du chemin Alembic, et n'est pas suivie par Git non plus.

0132 se déclare comme `Revises: 0131` et ajoute une colonne `workspaces.description`.
Le modèle courant `api/models/workspace.py` n'expose pas cette colonne. Le schéma
Pydantic public accepte `description` et la route renvoie la valeur du payload;
le fichier pending lui-même décrit une valeur perdue en persistance. Ce correctif
n'est donc ni dans le graphe de migrations, ni complet dans la synchronisation
modèle ↔ schéma.

## Migrations sensibles à examiner avant toute application

- `0128_pgvector_embeddings.py` crée extension/colonnes et un HNSW, backfill
  `embedding` JSON en vector PostgreSQL, et garde les autres dimensions dans
  l'ancien chemin. Les valeurs existantes et le support extension serveur ne
  sont pas vérifiés; un JSON non conforme au tableau attendu peut faire échouer
  le backfill.
- `0131_enable_rls_on_remaining_tables.py` active RLS sur onze tables; aucune
  policy n'est ajoutée. Le downgrade désactive RLS pour ces tables.
- `0132_workspace_description.py` est nullable/additive en upgrade; son
  downgrade supprime la colonne et détruit les descriptions qui y auraient été
  persistées.
- Le scan AST des fonctions `upgrade()` trouve quatre opérations
  structurellement destructrices candidates : `0010` supprime
  `users.is_superadmin` après copie vers `users.role`; `0115` supprime trois
  contraintes d'unicité/clé primaire après renommage, puis crée leurs versions
  multi-provider. Les migrations sont historiques et aucune n'a été exécutée
  durant cette phase. Ce scan statique n'est pas une évaluation exhaustive du
  comportement SQL ni des données.
- Ne pas utiliser une downgrade comme rollback générique sans analyser les
  écritures réalisées depuis l'upgrade.

## Résultats indisponibles

Révision réelle, migrations en attente côté DB, schéma des catalogues,
extensions/index présents, état de RLS, policies, rôle courant et sauvegardes
restaurables : **non vérifiés**. Ne pas en déduire une migration manquante ou
appliquée.
