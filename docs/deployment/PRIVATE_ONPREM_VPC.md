# Dedicated, private, on-premise and VPC deployments (specs 10.4.7 - 10.4.11)

One stack per customer, on the customer's own infrastructure, with nothing shared with other customers. Everything here is `deploy/dedicated-tenant/` (Docker Compose) or
`deploy/terraform/aws/` (the VPC profile). The same image (`Dockerfile.api`) is used everywhere.

| Spec | Profile | How |
|---|---|---|
| 10.4.7 Dedicated tenant | one compose project per customer: own API, worker, beat, network, volumes, secrets and encryption keys | `TENANT=acme ./provision.sh` |
| 10.4.8 Dedicated database | that project's own PostgreSQL (pgvector), never reachable from another project nor published on the host | same, `db` service |
| 10.4.9 Private deployment | everything on one host you control; the API is bound to `127.0.0.1` unless `BIND_ADDRESS` opens it, TLS is yours (reverse proxy or ingress) | same, behind your proxy |
| 10.4.10 On-premise / air-gapped | the overlay `docker-compose.airgapped.yml`: every container on an `internal` network (no route to the internet, no DNS), models loaded from a local volume, a local LLM (Ollama) on the same private network | `AIRGAPPED=1 MODELS_DIR=/srv/models COMPOSE_PROFILES=llm TENANT=acme ./provision.sh` |
| 10.4.11 VPC deployment | AWS: ECS Fargate services in private subnets, **internal** ALB, VPC endpoints for ECR / Secrets Manager / Logs / S3 (no NAT, no internet gateway) | `deploy/terraform/aws` with `internal_load_balancer=true create_vpc_endpoints=true` |

## What `provision.sh` does

1. Generates every secret once into `.env.<tenant>` (mode 600, git-ignored): database password, `JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `AUDIT_LOG_HMAC_SECRET_KEY`,
   `ENCRYPTION_MASTER_KEY`, `SECRET_ENCRYPTION_KEY`, the storage credentials. Two tenants never share a value. **Back this file up separately from the database: without
   `ENCRYPTION_MASTER_KEY` the stored credentials are unreadable** (see `docs/security/ENCRYPTION_AT_REST.md`).
2. Starts `db`, `redis`, `minio`, `api`, `worker`, `beat` with health checks (`docker compose up --wait`), creates the three buckets, runs `alembic upgrade head`.
3. Publishes only the API port, on the loopback address by default. The database, Redis and MinIO have no published port.

## Air-gapped checklist

- Build or load the image on a connected machine (`docker save` / `docker load`), together with `pgvector/pgvector:pg16`, `redis:7-alpine`, a MinIO image, `nginx:alpine` (the edge proxy).
- Fill the model cache on a connected machine and copy it: the Hugging Face cache holding `sentence-transformers/all-MiniLM-L6-v2` (embeddings) and `cross-encoder/ms-marco-MiniLM-L-6-v2` (reranking) goes to `MODELS_DIR`; `HF_HUB_OFFLINE=1` is forced by the overlay.
- For answers: `COMPOSE_PROFILES=llm` starts an Ollama container on the private network; pull the model on a connected machine and copy `ollamadata`, or attach an existing Ollama (`docker network connect --alias ollama`).
- In this mode e-mail delivery, hosted LLMs, billing providers and telemetry are unreachable by design; configure local equivalents (an internal SMTP relay is not part of the stack).
- Docker cannot publish a port of a container that is only on an internal network: the `edge` nginx is the only container with a route out and publishes the API; API, worker, beat and databases have none.

## Sizing (measured on the machine used for the tests)

Each API process loads the ML dependencies (about 1 GB resident): set `WEB_CONCURRENCY` (default 4) according to the RAM, a stack with `WEB_CONCURRENCY=1` needs roughly 3 GB for
the API, worker and beat plus the databases. CPU-only answers from a 3-billion-parameter local model take tens of seconds.

## What was executed

See the table in `deploy/README.md` and the evidence file `docs/project-handover/e2e_evidence/infra_registry.json`. The end-to-end test is
`RUN_DEPLOY_E2E=1 DEDICATED_IMAGE=<image> HF_CACHE_DIR=<hf cache> scripts/run_tests_local.sh tests/test_deploy_dedicated_tenant_e2e.py -q`.
Not executed: a real AWS apply (the Terraform validates but was never planned against an account), Kubernetes on a cluster, a multi-host on-premise installation.
