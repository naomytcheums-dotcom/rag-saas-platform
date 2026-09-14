# Deployment Diagram

See [Docker](../install/DOCKER.md) and
[Self-hosted](../install/SELF_HOSTED.md) for the narrative.

```mermaid
graph TD
    subgraph "docker-compose.selfhosted.yml"
        FE[frontend]
        API[api]
        CW[celery-worker]
        CB["celery-beat (single instance only)"]
        PG[(postgres<br/>named volume: postgres-data)]
        RD[(redis<br/>named volume: redis-data)]
    end

    S3EXT[(External S3-compatible storage)]
    LLMEXT[External LLM providers<br/>via litellm]

    LB[Reverse proxy / load balancer] --> FE
    LB --> API
    FE --> API
    API --> PG
    API --> RD
    API --> S3EXT
    API --> LLMEXT
    RD --> CW
    RD --> CB
    CW --> PG
    CW --> S3EXT
    CB --> CW
```

No Kubernetes manifests exist for this topology today — see
[Kubernetes](../install/KUBERNETES.md) for the honest gap and a manual
adaptation table.
