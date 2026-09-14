# Roadmap

This file tracks what's genuinely planned next, as distinct from what's
already built. For the full history of what has been delivered — audited,
built, tested — see [`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md),
which covers all 25 development parts.

## Shipped

All 25 planned development parts are complete as of this documentation
pass (Partie 25). Core platform, multi-tenancy, billing, RBAC, RAG
pipeline, agents, autonomous agents, workflows, evaluation lab,
fine-tuning, media/vision (YOLO, CLIP), A/B testing, analytics,
white-labeling, marketplace/plugins, security/compliance, admin
dashboard, and now documentation are all built and tested. See
[`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md) for the
itemized breakdown of each part.

## Known, honestly-documented gaps

These are real, current limitations — not silently missing, but not
fixed either:

- **No Kubernetes manifests.** Deployment is Docker Compose-based
  (`docker-compose.yml`, `docker-compose.selfhosted.yml`,
  `docker-compose.observability.yml`). A Kubernetes path exists only as
  a manual adaptation guide, not ready-made manifests — see
  [`docs/install/KUBERNETES.md`](docs/install/KUBERNETES.md).
- **Anthropic fine-tuning is not supported**, because Anthropic has no
  public fine-tuning REST API. Jobs targeting Anthropic fail fast with a
  clear error rather than silently hanging — see
  [`docs/fine-tuning/OVERVIEW.md`](docs/fine-tuning/OVERVIEW.md).
- **Autonomous agent collaboration is intentionally bounded** to one
  real LLM call per collaboration, not full nested autonomous sub-runs,
  to avoid unbounded agent-calls-agent recursion — see
  [`docs/autonomous/COLLABORATION.md`](docs/autonomous/COLLABORATION.md).
- **SSL automation for custom domains is DNS-01 only**, verified against
  Let's Encrypt staging; it is not "fully automatic" without a DNS
  provider API integration — see
  [`docs/whitelabel/DOMAIN.md`](docs/whitelabel/DOMAIN.md).

## Under consideration (not committed)

- A Kubernetes/Helm deployment path, if self-hosted demand justifies the
  maintenance cost of a second deployment target.
- DNS-provider API integrations (e.g. Cloudflare, Route53) to make
  custom-domain SSL fully automatic instead of manual DNS-01.
- Additional fine-tuning providers as they publish public REST APIs.

Nothing in this section is scheduled. If you're evaluating the platform
for a specific gap, check the linked docs above first — the honest
answer for most "is X supported" questions is already written down
rather than left implicit.
