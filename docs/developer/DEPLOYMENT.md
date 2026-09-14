# Deployment

Full deployment detail — environment setup, database migration, process
management — is in the existing, authoritative
[`docs/DEPLOYMENT_GUIDE.md`](../DEPLOYMENT_GUIDE.md). This page is a
pointer into it plus the newer, more specific install guides.

## Self-hosted vs. SaaS

- Self-hosting: [`docs/install/SELF_HOSTED.md`](../install/SELF_HOSTED.md)
- Managed SaaS: [`docs/install/SAAS.md`](../install/SAAS.md)

## Docker

[`docs/install/DOCKER.md`](../install/DOCKER.md) — local and
production Docker Compose usage.

## Environment variables

[`docs/install/ENVIRONMENT.md`](../install/ENVIRONMENT.md) — full
reference, generated from `.env.example`.

## Database

[`docs/install/DATABASE_SETUP.md`](../install/DATABASE_SETUP.md) and
[Database](DATABASE.md).

## Kubernetes

There are no ready-made Kubernetes manifests in this repository —
[`docs/install/KUBERNETES.md`](../install/KUBERNETES.md) documents this
honestly and gives a manual adaptation path from the Docker Compose
setup, rather than pretending manifests exist.

## Backups and upgrades

[`docs/install/BACKUP_AND_RESTORE.md`](../install/BACKUP_AND_RESTORE.md),
[`docs/install/UPGRADING.md`](../install/UPGRADING.md).
