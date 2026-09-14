# Database Diagram

A simplified view of the core tables and their major relationships. See
[Database](../developer/DATABASE.md) for the full model reference under
`api/models/`.

```mermaid
erDiagram
    ORGANIZATION ||--o{ WORKSPACE : contains
    ORGANIZATION ||--o{ TEAM : contains
    ORGANIZATION ||--o{ MEMBER : has
    ORGANIZATION ||--o{ DOCUMENT : owns
    ORGANIZATION ||--o{ AGENT : owns
    ORGANIZATION ||--o{ AUTONOMOUS_AGENT : owns
    ORGANIZATION ||--o{ FINE_TUNING_JOB : owns
    ORGANIZATION ||--o{ MEDIA_ASSET : owns

    DOCUMENT ||--o{ CHUNK : "split into"
    CHUNK ||--o| EMBEDDING : has

    CONVERSATION ||--o{ MESSAGE : contains
    MESSAGE ||--o{ CITATION : cites
    CITATION }o--|| CHUNK : references

    AUTONOMOUS_AGENT ||--o{ AGENT_PLAN : creates
    AGENT_PLAN ||--o{ AGENT_STEP : contains
    AUTONOMOUS_AGENT ||--o{ AGENT_MEMORY : stores
    AUTONOMOUS_AGENT ||--o{ AGENT_COLLABORATION : "collaborates via"

    FINE_TUNING_DATASET ||--o{ FINE_TUNING_JOB : "used by"
    FINE_TUNING_JOB ||--o| FINE_TUNED_MODEL : produces
    FINE_TUNED_MODEL ||--o{ FINE_TUNING_EVALUATION : "evaluated by"

    MEDIA_ASSET ||--o| CLIP_EMBEDDING : has
```

## Notes

- Nearly every table above carries an `org_id`, omitted from the
  diagram for readability — see [Multi-tenancy](../advanced/MULTI_TENANCY.md).
- `AGENT` (configured chatbot persona) and `AUTONOMOUS_AGENT` are
  deliberately separate tables, not a shared hierarchy — see
  [Autonomous Agents](../advanced/AUTONOMOUS_AGENTS.md).
