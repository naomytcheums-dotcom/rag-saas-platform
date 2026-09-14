# Multi-tenancy Diagram

See [Multi-tenancy](../advanced/MULTI_TENANCY.md) for the narrative.

```mermaid
graph TD
    subgraph "Organization A (org_id = A)"
        WA1[Workspace A1]
        WA2[Workspace A2]
        TA[Team A]
        DA[(Documents A)]
        AA[Agents A]
    end

    subgraph "Organization B (org_id = B)"
        WB1[Workspace B1]
        TB[Team B]
        DB2[(Documents B)]
        AB[Agents B]
    end

    subgraph "Enforcement"
        APP[Application-layer check:<br/>org_id on every request]
        RLS[(Postgres RLS:<br/>row-level org_id filter)]
    end

    WA1 -.enforced by.-> APP
    WB1 -.enforced by.-> APP
    APP --> RLS
    DA -.-> RLS
    DB2 -.-> RLS

    note1["Retrieval, chat context, and agent tool access\nare all scoped by org_id.\nOrg A can never retrieve Org B's documents."]
```

Workspaces and teams group resources/members *within* one organization
— neither is a tenancy boundary on its own.
