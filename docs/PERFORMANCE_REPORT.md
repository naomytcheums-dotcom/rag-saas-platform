# Performance — état des preuves au 2026-10-03

**Aucun benchmark de production ou PostgreSQL staging effectué.**
Source historique :
[README](../README.md#L130) et [ROADMAP](../ROADMAP.md).

## Mesures de cette mission

- Frontend Vitest, première exécution : 13 fichiers, 112 tests passés,
  144.28 secondes, un worker.
- Rejeu après correctifs : 13 fichiers, 112 tests passés, 118.26 secondes.
- Variation observée entre runs, pas amélioration attribuable au correctif :
  import/cache/système et environnement jsdom diffèrent.
- Le rapport Vitest relève jsdom créé 13 fois; optimisation éventuelle
  doit conserver isolation des tests, pas désactiver isolate sans preuve.
- Ruff backend initial : 3 253 diagnostics; coût/performance API n'en
  découle pas.
- Pendant pytest complet, processus principal ~1.36 Go de working set
  observé une fois; ce n'est pas un pic mémoire ni une limite garantie.

## Limites du retrieval documentées

Le README indique benchmark portable à 100/1 000 documents, pas la route
HTTP concurrente ni pgvector/HNSW à 10 000 documents. BM25 calculé par
requête sur chunks d'organisation; index full-text persistant planifié.

Latence p50/p95 API, throughput, coût/req, plan SQL live, N+1 sous charge,
performance audio et coût RTC : **UNKNOWN** dans cette mission.
Pas d'index nouveau ou de refactoring conjectural sans profil.

## Prochaine validation

Staging accessible, corpus synthétique représentatif, jobs isolés,
providers sandbox/budget, p95 SQL/HTTP, concurrence et tests de fuite
tenant. Toute optimisation doit comparer au baseline sur la même machine
et conserver les tests de sécurité.

## Cross-encoder reranker, measured on 2026-10-11 (spec 3.4.4)
Model `cross-encoder/ms-marco-MiniLM-L-6-v2` loaded through `api.services.retrieval_pipeline._get_reranker`, CPU only (Intel 16 logical cores, no GPU), passages of about 600 characters, 5 timed runs after one warm-up:

| Measure | Value |
|---|---|
| Load time (model files already on disk) | 20.6 s |
| Memory added by the loaded model | +561 MB (process peak 715 MB) |
| Rerank 10 candidates | median 152 ms (min 118, max 232) |
| Rerank 20 candidates | median 222 ms (min 200, max 286) |
| Rerank 50 candidates | median 596 ms (min 539, max 756) |

What it means: the first reranked request after a process start pays about 20 s, and each worker process keeps about 0.6 GB for this model on top of the embedding model, so the hosting plan must be sized for that (the 512 MB free plan cannot hold it). These are the numbers of one developer machine, not of the hosting provider's CPU; measure again on the real plan.
