# Baseline forensique — Phase 2

Date : 2026-10-03. Baseline Git locale uniquement; aucune connexion à la base.

## Snapshot au démarrage de Phase 2

| Élément | Valeur observée |
|---|---|
| Branche initiale | `main` |
| HEAD initial | `2e7bfaa` (`2026-09-27`) |
| Fichiers suivis modifiés | 132 |
| Fichiers non suivis | 150 |
| Fichiers staged | 0 |
| Fichiers supprimés | 0 |
| Environnement DB | `UNKNOWN` |
| Lecture DB / mutation DB | `BLOCKED` / `BLOCKED` |

Les 132 chemins modifiés et 150 non suivis sont le snapshot complet du
workspace partagé, pas une attribution à cette phase. Le worktree était déjà
fortement modifié; il n'a été ni nettoyé, ni stashé, ni réinitialisé. Pas de
fichier préexistant supprimé ou staged.

## Écart historique de cinq fichiers (145 → 150)

Le rapport Phase 1 et le journal ont consigné 145 non suivis. Le `git status`
rejoué à l'ouverture de la Phase 2 donne 150. L'écart est exactement constitué
des cinq rapports forensics Phase 1 qui existaient dans le workspace à ce
moment mais avaient été créés après le snapshot de 145 :

- `docs/audit/WORKSPACE_FORENSICS.md`
- `docs/audit/DATABASE_FORENSICS.md`
- `docs/audit/RLS_FORENSICS.md`
- `docs/audit/CHANGE_LEDGER.md`
- `docs/audit/PHASE_1_REPORT.md`

Les cinq rapports initiaux (`INITIAL_SYSTEM_AUDIT.md`, `FEATURE_MATRIX.md`,
`DATABASE_AUDIT.md`, `SECURITY_AUDIT.md`, `PRODUCTION_BLOCKERS.md`) expliquent
un premier incrément de cinq entre le snapshot de 140 décrit dans le journal
et celui de 145. Il s'agit d'écarts de moment de capture, pas de suppressions
ou d'une anomalie Git.

## Actions de Phase 2 et provenance

- Création de la branche locale `bob/auto-fix-20261003-1518`, au même HEAD
  `2e7bfaa`; aucun commit, push, stage ou changement de contenu Git antérieur
  n'a été effectué par ce changement de branche.
- Les fichiers `0125`–`0131` demeurent des fichiers préexistants non suivis.
- `scripts/pending/0132_workspace_description.py` n'a pas été déplacé ni
  modifié. Une révision Alembic `0132` correspondante a été ajoutée sous
  `api/alembic/versions/` afin de rendre cette révision découvrable dans le
  chemin configuré par Alembic.
- La matrice relationnelle est un nouvel artefact généré depuis les
  métadonnées ORM du worktree. Elle n'est pas un snapshot du schéma DB.
- Les modifications Workspace/API/tests sont des hunks ciblés dans le
  worktree existant. Comme celui-ci était déjà sale, les autres hunks des
  mêmes fichiers ne sont pas réattribués à cette phase.

## Limites de preuve

- Aucun contenu de `.env` n'a été lu ou reproduit. L'import de configuration
  annonce seulement un host Supabase/non-local et le port; cela n'identifie pas
  DEV, TEST, STAGING ou PRODUCTION.
- Aucun appel réseau DB, requête SQL, `alembic current`, test PostgreSQL,
  migration, changement de rôle ou inspection de catalogue n'a été lancé.
- Les commandes Alembic `heads`/`history` utilisées ici inspectent seulement
  les fichiers locaux.
- Le snapshot final (132 suivis modifiés, 156 non suivis, zéro staged ou
  supprimé) est consigné dans `PHASE_2_REPORT.md`; ce snapshot initial reste
  immuable comme référence de delta.
