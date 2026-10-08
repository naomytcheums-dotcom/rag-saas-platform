# Feature Matrix — Initial Audit

État du workspace observé le 2026-10-03. Les statuts ne déclarent pas une
fonctionnalité vérifiée uniquement parce qu'une route, une migration ou un test
existe. Aucun test applicatif ou parcours externe n'a été lancé dans cette
phase. `BLOCKED_EXTERNAL` signifie que la validation réelle exige un service,
compte ou secret qui n'a pas été validé.

Valeurs permises : `VERIFIED`, `PARTIAL`, `UNVERIFIED`, `BROKEN`,
`NOT_IMPLEMENTED`, `BLOCKED_EXTERNAL`.

| Feature | Backend | Database | Frontend | Unit | Integration | E2E | Security | Persistence | External validation | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| Auth / sessions / OAuth | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | UNVERIFIED |
| Organisations / RBAC / multi-tenant | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | PARTIAL | UNVERIFIED | UNVERIFIED | PARTIAL |
| Billing Stripe / Paystack | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | PARTIAL | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Credits / spend caps / BYOK | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | PARTIAL | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Documents / ingestion / extraction | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| RAG vector / BM25 / hybrid | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| pgvector / HNSW | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | UNVERIFIED |
| Agents / tools / memory | PARTIAL | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | PARTIAL | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Workflow builder / execution | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| MCP client / server | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| A2A | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | PARTIAL | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Eval Lab | PARTIAL | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Guardian / alerts | PARTIAL | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Autopsy / failure diagnostics | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Evolution / ChangeLab | PARTIAL | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Multimodal / media | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Voice | PARTIAL | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | BLOCKED_EXTERNAL |
| SDK Python / JS / React / Vue | PARTIAL | UNVERIFIED | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| White-label / domaines / SSL | PARTIAL | PARTIAL | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Redis / cache / rate limit | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Celery / workers | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Prometheus / tracing / Sentry | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | PARTIAL |
| Docker / deploy / backup | PARTIAL | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | BLOCKED_EXTERNAL | UNVERIFIED |

## Éléments probants et réserves

- Après l'audit initial, le défaut de top-up et le débit A2A ont reçu des
  correctifs locaux avec tests ciblés; cela ne valide pas le paramétrage
  déployé ni le comportement PostgreSQL concurrent.
- Surfaces et limites détaillées : [INITIAL_SYSTEM_AUDIT.md](./INITIAL_SYSTEM_AUDIT.md).
- La revue sécurité a trouvé le risque de top-up sans paiement conditionnel et
  le débit A2A post-exécution : [SECURITY_AUDIT.md](./SECURITY_AUDIT.md).
- La connexion à la base n'a pas donné de révision Alembic; migrations
  appliquées, policies, extensions, index et données restent `UNVERIFIED`.
- Les providers, paiements, domaines, stockage objet, DNS et intégrations
  MCP/A2A restent `BLOCKED_EXTERNAL` tant qu'un essai réel contrôlé n'a pas
  été fait.
- `UNVERIFIED` ne signifie pas « absent » ou « cassé »; il signifie qu'aucune
  preuve suffisante n'a été produite dans cette phase.
