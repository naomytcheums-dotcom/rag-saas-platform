# Backup / restore — procédure et preuves

## Current evidence - 2026-10-04 22:13 local time (UTC+1)

**Real Supabase staging backup: SUCCESS. Restore: BLOCKED_EXTERNAL.**
The older client/tool blockers below are historical and superseded.

- Native `pg_dump (PostgreSQL) 17.11` installed and verified.
- File: `staging-artifacts/staging_backup_20261004_211042.sql`.
- Dump start: 2026-10-04 21:10:42 UTC / 22:10:42 local.
- Size: **911502 bytes** (about **0.87 MiB**).
- SHA256: `7009870d53c6050b6b42102c529b9d2142f564c75f3cff06a1153a6d1e95fd67`.
- `pg_dump` exit 0; **178 public CREATE TABLE statements** counted in
  the file. This is a dump inventory, not 178 restored tables.
- First 20 lines checked: PostgreSQL 17.11 dump header and SQL SET commands.
  Only header/settings printed, no data rows or credentials.
- Exact target: official staging pooler, port 5432, database postgres,
  user <STAGING_DB_USER>; TLS required.
- Initial strict `.env.staging` read refused its placeholder credential.
  User then explicitly supplied the staging password; reused through
  memory-only PGPASSWORD / guarded target injection. It was not saved to
  code or printed. The dotenv file still contains a placeholder.
- Concurrent backend suite was not stopped or relaunched. PostgreSQL dump
  has its own consistent snapshot; it is not tied to that test transaction.

### Exact dump procedure

Create ignored `staging-artifacts`, refuse an existing destination, validate
the exact staging host/user/database, set `PGPASSWORD` privately,
`PGSSLMODE=require`, `PGCONNECT_TIMEOUT=15`, then execute:

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\pg_dump.exe' `
  --no-owner --no-privileges --clean --if-exists `
  --host=<STAGING_POOLER_HOST> `
  --port=5432 --username=<STAGING_DB_USER> `
  --dbname=postgres `
  --file=staging-artifacts\staging_backup_20261004_211042.sql --verbose
```

The command contains no password. The dump contains tenant data, including
account/security records: keep it ignored, local and access-controlled.
Do not upload it or print its contents.

### Restore attempt and exact blocker

- Second Supabase project unavailable: user verified the account's limit
  of two active free projects. No existing project was deleted, paused,
  upgraded or modified to bypass this limit.
- User authorized Docker-only disposable restore next.
- Docker client works: **29.7.2**, build a7dcaa6.
- `docker info --format '{{.ServerVersion}}'` on desktop-linux timed out
  after 20 seconds. Explicit default context also timed out after 20s.
  Both short diagnostic child processes were terminated by subprocess
  timeouts. No shared Docker services/processes were restarted or killed.
- Therefore no `rag-restore-test` container was created, no restore was
  performed, no table/revision/vector/HNSW/policy counts are claimed on a
  restored DB, and no created container needed cleanup.

### Portability prerequisite for the eventual Docker restore

The full dump includes Supabase-managed auth/storage/realtime schemas and
`supabase_vault`, not only the public application schema. Plain pgvector
PostgreSQL images do not necessarily provide those platform extensions or
roles. `--no-owner --no-privileges` does not remove roles mentioned by RLS
policies: provision `rag_staging_tenant` NOLOGIN/NOBYPASS before restoring
the 77 policies.

Do not silently ignore restore errors. On a responsive disposable Docker
target, restore with psql ON_ERROR_STOP and verify the exact 178 public tables,
0132 revision, vector extension version, HNSW and 77 policies. If platform
extensions prevent the full dump restore, retain this untouched dump and
produce a separate explicitly scoped public-schema dump; do not claim a
public-only restore validates the entire Supabase platform backup.

RTO/RPO and restore/rollback remain unverified. No production touched.

Parallel feature verification completed separately: 109 existing alternative
tests pass, eight staging diagnostic API probes completed with explicit
storage/provider blockers; total 117 cases, zero runner failures/skips.
This does not validate backup contents, restoration or live provider journeys.
See ../audit/PARALLEL_TASKS_REPORT.md for per-journey evidence.

## Historical evidence before the successful native dump

Date : 2026-10-04. **BLOCKED_EXTERNAL : aucun backup ni restore
du vrai Supabase staging effectue.**
Sources : [audit backup](../audit/BACKUP_AUDIT.md) et
[rapport staging](../audit/STAGING_TEST_REPORT.md).

## Correctifs locaux vérifiés — 2026-10-04

Les scripts self-hosted ne publient plus un dump partiel sous un nom
final : temporaire/nettoyage, validation gzip et publication sans
écrasement. Le filesystem doit supporter les liens durs.
Restore vérifie gzip avant accès DB et psql utilise ON_ERROR_STOP.
Six tests shell, Docker substitué, passent; avec CI worker : 15/15,
Ruff PASS. Cela ne constitue pas une sauvegarde/restauration live,
une preuve de cohérence SQL ou de RTO/RPO. Un échec SQL peut laisser
une restauration partielle; exercer uniquement sur clone jetable.

## Blocages verifies - etat actuel

- `pg_dump` et `psql` absents du PATH observé.
- Docker CLI present mais la verification de version serveur ne repond pas;
  le seul processus de diagnostic lance par cette mission a ete arrete.
- Supabase staging est maintenant accessible via son session pooler officiel.
  L'ancien blocage IPv6 ne concerne plus ce chemin.
- Pas de seconde DB restore identifiée; aucune base de production touchée.
- Aucun dump, taille, compte restauré ou résultat de rollback inventé.

L'absence d'outils natifs et de destination jetable identifiee bloque
backup/restore dans la limite de temps demandee. Aucune installation
globale PostgreSQL ni mutation des autres services de ce poste partage
n'a ete effectuee. Le backup/restore et downgrade/upgrade deja executes
sur PostgreSQL Docker local sont des preuves historiques locales,
**pas** une sauvegarde Supabase. Le snapshot documentaire de 178 tables
ne remplace pas un dump. Statut RTO/RPO toujours UNKNOWN.

## Backup préparé

`scripts/staging_validate.py backup --execute` vérifie outil et cible
exacte, passe password via environnement `PGPASSWORD`, SSL requis,
connexion timeout, pas de password dans argv. Sortie vers
`staging-artifacts/staging_backup.sql`, dossier Git ignoré.
Refuse d'écraser une sauvegarde existante; un fichier créé après échec ne
constitue pas une sauvegarde utilisable.

## Restore futur

1. Installer client PostgreSQL compatible seulement après vérification du
   serveur, démarrer/provisionner une DB **jetable**, vérifier son identité.
2. Dump de staging validé, hash et taille stockés hors Git, ACL limitées.
3. Restore vers DB jetable seulement. Ne jamais réutiliser DATABASE_URL
   principale comme valeur par défaut de destination.
4. Comparer revision, tables/rows, FK/unique/check, vector/HNSW, RLS/policies
   et grants. Tester accès de l'application et IDOR.
5. Rejouer rollback 0132 sur clone en vérifiant perte des descriptions;
   downgrade 0131 modifie RLS. Pas sur staging sans copie restaurable.
6. Conserver les logs redigés, définir rétention sur préfixe dédié.

Le dump PostgreSQL n'inclut pas automatiquement les fichiers S3/R2.
Sauvegarde storage et stratégie de récupération doivent être indépendantes.
RTO et RPO : **UNKNOWN**, à mesurer sur restore réussi.
