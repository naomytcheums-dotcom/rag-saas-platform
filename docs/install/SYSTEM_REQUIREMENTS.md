# System Requirements

## Self-hosted (Docker Compose)

- Docker Engine + Docker Compose v2.
- A reasonable baseline for small deployments: 4 vCPU / 8 GB RAM for
  the combined stack (`api`, `celery-worker`, `frontend`, `postgres`,
  `redis`). Increase worker/API replicas and resources with usage — see
  [Scaling](SCALING.md).
- Additional CPU (or GPU, if configured) headroom if you enable local
  vision inference (YOLOv8 object detection, CLIP embedding) — these
  run local model inference rather than calling an external API.

## Database

An external managed Postgres (e.g. Supabase) with `pgvector` enabled is
recommended over the bundled `postgres` container for anything beyond
small/trial deployments — see [Database Setup](DATABASE_SETUP.md).

## Object storage

An S3-compatible bucket for documents, media, and fine-tuning datasets.

## Network

Outbound HTTPS access is required for LLM provider calls (via litellm),
transactional email (Resend), and any configured integrations
(Slack/Teams/Discord/Twilio/Airbyte/n8n).

## Browser support (frontend)

A current Chromium-, Firefox-, or Safari-based browser. Voice features
specifically work most consistently on Chromium-based browsers — see
[Voice](../user/VOICE.md).
