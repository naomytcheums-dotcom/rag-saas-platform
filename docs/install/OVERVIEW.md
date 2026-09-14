# Install Overview

## Choose a deployment model

- **[SaaS](SAAS.md)** — use the hosted platform, no installation.
- **[Self-hosted](SELF_HOSTED.md)** — run the platform on your own
  infrastructure via Docker Compose.

## Self-hosted quick path

```bash
git clone <this repo>
cd rag-saas-platform
./install.sh          # copies .env.example -> .env, generates a real
                       # random SESSION_MIDDLEWARE_SECRET, then tells you
                       # what else to fill in and stops
# edit .env: DATABASE_URL, RESEND_API_KEY, LICENSE_KEY, etc. --
# see docs/install/ENVIRONMENT.md
./install.sh           # re-run: starts the stack, waits for Postgres,
                        # runs migrations
```

See [Environment Variables](ENVIRONMENT.md) for what needs filling in,
[Docker](DOCKER.md) for the compose files involved, and
[System Requirements](SYSTEM_REQUIREMENTS.md) before you start.

## After install

- [Backup & Restore](BACKUP_AND_RESTORE.md)
- [Upgrading](UPGRADING.md) (`./update.sh` — takes a real backup first,
  with an explicit rollback path on failure)
- [SSL & Domains](SSL_AND_DOMAINS.md)
- [Observability Stack](OBSERVABILITY_STACK.md)

## Kubernetes

Not provided out of the box — see [Kubernetes](KUBERNETES.md) for the
honest current state and a manual adaptation path.
