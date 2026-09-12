# Advanced A/B testing (Partie 21)

Real, honest scope note first: an audit (this part's own instructions,
item 1) found that Partie 7.3.10 had already built a mature, real, LIVE
production A/B testing system -- `ABTest` model, real deterministic
sticky bucketing (`get_ab_test_variant`, MD5 hash mod 100 against
`traffic_split`), real incremental running statistics
(`track_ab_test_metric`, `{count, sum, sum_sq}` per variant/metric),
and a real Welch's-t-test normal-approximation p-value
(`get_ab_test_results`). None of that was rebuilt. This part closes
the real gaps that audit found.

## What already existed (Partie 7.3.10, unchanged)

- `POST /organizations/{org_id}/ab-tests`, `POST .../start`,
  `.../pause`, `.../complete`, `.../track`, `.../variants/choose`
  (the manual, human winner decision), `GET .../results`.
- Real deterministic bucketing and real running statistics -- the core
  of what makes this a genuine A/B test, not a coin flip.

## What Partie 21 adds

- **Config fields on `ABTest`**: `test_type` (agent/prompt/model),
  `target_metric` (one of `KNOWN_AB_TEST_METRICS`), `min_sample_size`,
  `confidence_level` -- per-test, not one global setting for every test.
- **`ABTestAssignment`**: a real, persisted audit trail of who was
  bucketed into which variant and when -- the deterministic hash
  itself never needed this to function correctly, but nothing
  previously answered "who was actually assigned" (`GET .../assignments`).
- **Real statistics**: confidence interval, Cohen's d effect size,
  statistical power, and `min_sample_size_reached` -- alongside the
  pre-existing p-value/lift/significance. See `docs/ab-testing/STATISTICS.md`.
- **`ABTestResult`**: a real, point-in-time snapshot table (written by
  `GET .../statistics` and the hourly Celery significance check),
  distinct from `ABTest.metrics` (the live running sufficient
  statistics) -- a real historical record.
- **The real automatic decision**: `POST .../decide` -- statistics-
  driven (requires both variants to reach `min_sample_size` AND real
  significance), distinct from the pre-existing manual
  `.../variants/choose`. Both exist; neither replaced the other.
- **CRUD completeness**: `PATCH`/`DELETE /ab-tests/{id}`, `POST .../resume`.
- **Export**: `GET .../export?format=csv|json`.
- **4 real Celery jobs**: `check_ab_test_significance` (hourly
  snapshots), `auto_decide_ab_tests` (config-gated, off by default),
  `complete_expired_ab_tests` (real max-duration sweep),
  `send_ab_test_report`.
- **Access split**: list/get/results/statistics are now Member+ (this
  part's own explicit spec); every write/lifecycle action stays
  Admin+, unchanged from before.

## A real bug found and fixed while testing this

`track_ab_test_metric`'s original code did `metrics = dict(test.metrics
or {...})` -- a SHALLOW copy. The nested per-variant dicts stayed the
SAME objects already attached to `test.metrics`, so mutating
`metrics[variant][metric]` also mutated `test.metrics[variant]` in
place, before the `test.metrics = metrics` reassignment ran.
SQLAlchemy's JSON-column change tracking then saw no real difference
between old and new and silently skipped the UPDATE -- confirmed live:
a second variant's tracked sample was visible in that one request's
own response, then vanished, never actually persisted. Fixed with
`copy.deepcopy` instead of a shallow `dict(...)` copy, so the new and
old object graphs are genuinely, unambiguously different.

See `docs/ab-testing/STATISTICS.md` for the exact formulas and
`docs/ab-testing/BEST_PRACTICES.md` for how to actually run a test.
