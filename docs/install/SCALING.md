# Scaling

## Stateless services scale horizontally

`api` and `frontend` are stateless — run multiple replicas behind a load
balancer as traffic requires. `celery-worker` also scales horizontally;
add more workers to increase background-job throughput (document
ingestion, evaluation runs, media processing, fine-tuning polling).

## Do not scale `celery-beat`

`celery-beat` (the scheduler for periodic tasks — reindexing, domain
verification, fine-tuning status polling, backups) must run as exactly
one instance. Running more than one causes duplicate scheduled task
execution.

## Database

Postgres is the primary scaling constraint for most deployments. Use a
managed Postgres (e.g. Supabase) with connection pooling
(PgBouncer or equivalent) before scaling `api` replicas significantly —
async SQLAlchemy connections multiply quickly with concurrent replicas.

## Redis

Used as the Celery broker/result backend. A single Redis instance is
sufficient for most deployments; consider Redis Cluster or a managed
Redis only at high background-job volume.

## Vision/media workloads

YOLO object detection and CLIP embedding run local inference and are
CPU/GPU-bound — if media volume is high, dedicate `celery-worker`
capacity (or a separate worker pool bound to the media queue) rather
than letting media processing compete with lighter background jobs.
