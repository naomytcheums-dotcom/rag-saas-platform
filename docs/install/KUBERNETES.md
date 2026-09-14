# Kubernetes

**Honest status: there are no Kubernetes manifests in this repository.**
Deployment is Docker Compose-based
(`docker-compose.yml`/`docker-compose.selfhosted.yml`/`docker-compose.observability.yml`,
see [Docker](DOCKER.md)). This page documents the gap rather than
implying support that doesn't exist, and gives a manual adaptation path
for teams that need Kubernetes anyway.

## Why this isn't ready-made

The self-hosted install path (`install.sh`/`update.sh`/`uninstall.sh`)
was built around Docker Compose because it's what the self-hosted sales
model (see [`docs/sales/SELF_HOSTED.md`](../sales/SELF_HOSTED.md))
actually targets. A production-grade Kubernetes deployment (Helm chart,
ingress, secrets management, HPA, a StatefulSet or managed Postgres for
the database) is real, additional work that hasn't been done.

## Adapting manually

The Compose services map roughly to these Kubernetes resources:

| Compose service | Kubernetes shape |
|---|---|
| `postgres` | External managed Postgres strongly recommended over a self-managed StatefulSet |
| `redis` | Deployment + Service, or a managed Redis |
| `api` | Deployment + Service, horizontally scalable (stateless) |
| `celery-worker` | Deployment, scaled independently of `api` |
| `celery-beat` | Deployment with `replicas: 1` (must not run more than one instance) |
| `frontend` | Deployment + Service |

Environment variables map directly from [`.env.example`](../../.env.example)
to a Kubernetes `Secret`/`ConfigMap` — see
[Environment Variables](ENVIRONMENT.md). Everything the `api` container
needs at runtime is already externalized via env vars, so no
container-image changes should be needed to run under Kubernetes.

## If you build this

There's no committed Helm chart or manifest set to contribute to yet.
If you build a working Kubernetes deployment for your own use, consider
opening a PR — see [`CONTRIBUTING.md`](../../CONTRIBUTING.md).
