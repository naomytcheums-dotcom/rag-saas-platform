# Tutorial: Run an A/B Test

See [A/B Testing](../advanced/AB_TESTING.md) for the concept.

## 1. Define variants

Go to **Admin → A/B Tests → New test**. Define two (or more) variants —
e.g. Variant A: current reranking blend; Variant B: a different blend
weight.

## 2. Set the traffic split

Choose what fraction of real traffic each variant receives (e.g. 50/50,
or a smaller percentage for the new variant if you want to limit
exposure early on).

## 3. Let it run

Traffic is routed automatically per the split you configured. Avoid
peeking at results too early or stopping the moment one variant looks
ahead — see
[`docs/ab-testing/STATISTICS.md`](../ab-testing/STATISTICS.md) for why
premature stopping undermines the significance test.

## 4. Read the results

Once enough samples have accumulated, the test's results page reports
which variant performed better and whether the difference is
statistically significant, not just numerically larger — see
[`docs/ab-testing/BEST_PRACTICES.md`](../ab-testing/BEST_PRACTICES.md).

## 5. Promote the winner

Once you're confident in a result, apply the winning configuration as
your new default and close the test.
