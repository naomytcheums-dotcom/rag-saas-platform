# Running a real A/B test

1. **Create the test** with a real `target_metric` (one of
   `conversion_rate`/`user_satisfaction`/`task_completion_rate`/
   `avg_response_time`/`error_rate`/`retention_rate`) and a real
   `min_sample_size` -- without a target metric, the automatic decision
   endpoint (`POST .../decide`) will refuse to run; you can still
   decide manually via `POST .../variants/choose` at any time.
2. **Start it** (`POST .../start`) -- only a `running` test actually
   buckets real traffic; a draft/paused/completed test always resolves
   to variant A (the safe, honest default).
3. **Bucket real requests** by calling `assign_ab_test_variant`
   (backend-internal, not an HTTP endpoint by design) with a real,
   stable `request_id` (a user id, a session id) -- the same id always
   maps to the same variant, and a real `ABTestAssignment` row is
   recorded. Use the plain, synchronous `get_ab_test_variant` instead
   (same real hash, unchanged since Partie 7.3.10) when you only need
   the variant and don't want a database write.
4. **Track real outcomes** as they happen (`POST .../track`) -- one
   call per real event, incrementally aggregated, never a raw,
   unbounded event log.
5. **Check results** (`GET .../results` or `.../statistics` -- the
   latter also persists a real historical snapshot) once
   `min_sample_size_reached` is true for both variants. A `p_value`/
   `significant` before that point is honestly `None`, not a
   premature answer.
6. **Decide**: `POST .../decide` for a real, statistics-gated automatic
   winner (only when both variants are ready and the result is
   significant), or `POST .../variants/choose` for a real human call
   at any time, for any reason (business context a p-value can't
   capture).

## A real, honest caveat on sample size

`min_sample_size` and `confidence_level` are real, per-test knobs, not
a substitute for actually understanding your own real traffic volume
and expected effect size. A test with a tiny real effect and a small
real `min_sample_size` can report `significant: false` correctly and
honestly -- that is not a bug, it's the real math telling you there
isn't enough real evidence yet.
