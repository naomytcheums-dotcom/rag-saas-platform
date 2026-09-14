# FAQ — Self-hosting

**What do I need to self-host?** Docker Engine + Docker Compose v2, a
Postgres database (bundled or external), and an S3-compatible bucket.
See [System Requirements](../install/SYSTEM_REQUIREMENTS.md) and
[Self-hosted](../install/SELF_HOSTED.md).

**Is there a Kubernetes deployment option?** Not out of the box — no
manifests exist in this repository. See
[Kubernetes](../install/KUBERNETES.md) for the honest current state and
a manual adaptation path from Docker Compose.

**How do I back up my data?** `./scripts/backup.sh` (real `pg_dump`).
Object storage (documents/media/datasets) needs its own separate backup
per your storage provider. See [Backup & Restore](../install/BACKUP_AND_RESTORE.md).

**How do I upgrade?** `./update.sh` — takes a real backup first, then
pulls, rebuilds, and migrates, with an explicit rollback path on
failure. See [Upgrading](../install/UPGRADING.md).

**How do I uninstall without losing data?** `./uninstall.sh` (default)
never touches your `.env`, backups, or database volume. Only
`./uninstall.sh --purge-data` removes them, explicitly. See
[Uninstall](../install/UNINSTALL.md).

**Can I run this on a single small VPS?** Yes for trial/small use — see
[System Requirements](../install/SYSTEM_REQUIREMENTS.md) for baseline
sizing, and [Scaling](../install/SCALING.md) for when to grow beyond it.
