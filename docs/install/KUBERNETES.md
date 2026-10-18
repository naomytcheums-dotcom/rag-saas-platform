# Kubernetes and Helm

Manifests and a Helm chart for the API, the Celery worker and the single Celery beat live in `deploy/`:

| Path | What |
|---|---|
| `deploy/kubernetes/rag-saas.yaml` | Namespace, API Deployment (2 replicas, readiness `/health/ready`, liveness `/health`), Service, worker, **beat as one `Recreate` pod**, Ingress (cert-manager), HorizontalPodAutoscaler 2-6 |
| `deploy/helm/rag-saas/` | the same as a chart (`values.yaml`: image, `existingSecret`, env, replicas and resources, `worker.enabled`, `beat.enabled`, `ingress.*`) |

PostgreSQL (with pgvector) and Redis are **not** in the chart: use a managed PostgreSQL / Redis (or your own operator). The environment contract (the variables the
`rag-saas-secrets` Secret must hold, including the Redis URLs the application actually reads) is in [`deploy/README.md`](../../deploy/README.md).

```
kubectl create namespace rag-saas
kubectl -n rag-saas create secret generic rag-saas-secrets --from-literal=DATABASE_URL=... (the full list is in deploy/README.md)
helm upgrade --install rag-saas deploy/helm/rag-saas -n rag-saas --set image.repository=<your registry>/rag-saas-api --set image.tag=<tag>
kubectl -n rag-saas exec deploy/rag-saas-api -- python -m alembic upgrade head      # once, after a database backup
```

## What was checked, and what was not

Executed on this repository: `helm lint`, `helm template` (default values, ingress on, worker and beat off) and `kubeconform -strict` on the Kubernetes 1.30 schemas for the manifest
and for every rendering; `tests/test_deploy_artifacts.py` (beat is a single `Recreate` pod, probes call endpoints that exist, the secret documents the whole contract).
`RUN_DEPLOY_TOOLING=1 scripts/run_tests_local.sh tests/test_deploy_artifacts.py` repeats the tool runs in Docker.
**Not** done unless the evidence file says otherwise (`docs/project-handover/e2e_evidence/infra_registry.json`): an installation on a cluster. The `Ingress` assumes cert-manager and an
ingress controller; there is no NetworkPolicy, PodDisruptionBudget or `runAsNonRoot` securityContext yet (the image runs as a non-root user, but Kubernetes cannot verify it without a numeric UID).
