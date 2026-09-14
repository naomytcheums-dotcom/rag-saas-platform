# A/B Testing

Full documentation: [`docs/ab-testing/OVERVIEW.md`](../ab-testing/OVERVIEW.md),
[`BEST_PRACTICES.md`](../ab-testing/BEST_PRACTICES.md),
[`STATISTICS.md`](../ab-testing/STATISTICS.md).

## What can be A/B tested

Prompts, model choices, and retrieval settings (e.g. chunk size,
reranking blend weight) — configured as experiment variants and
compared against real usage or evaluation data.

## Statistical rigor

See [`docs/ab-testing/STATISTICS.md`](../ab-testing/STATISTICS.md) for
the significance testing approach used to determine whether an observed
difference between variants is real rather than noise — the same
"don't overclaim from a small or leaked sample" discipline documented
throughout this platform's evaluation tooling (see
[Reranking](RERANKING.md#evaluation-caveat) for a concrete example of
that discipline applied elsewhere).

## Relationship to the Evaluation Lab

A/B testing compares configurations against real/live usage patterns
over time; the Evaluation Lab (see [`docs/CAHIER_DES_CHARGES.md`](../CAHIER_DES_CHARGES.md),
Partie 7) compares configurations against a fixed, labeled evaluation
dataset. Use A/B testing when you want a live-traffic answer, the
Evaluation Lab when you want a repeatable, offline one.
