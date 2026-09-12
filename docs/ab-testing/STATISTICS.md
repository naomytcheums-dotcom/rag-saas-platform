# A/B testing statistics (Partie 21)

All formulas live in `api/services/ab_tests.py`. Same "no scipy"
discipline as the rest of this codebase's evaluation/statistics code --
real, standard, large-sample NORMAL approximations, honestly disclosed
as approximations, not exact distributions.

## p-value

Welch's t-test, normal approximation (pre-existing, Partie 7.3.10,
unchanged): `z = (mean_b - mean_a) / standard_error`, two-sided
p-value via `math.erf`. Honestly `None` below 2 real samples in either
variant.

## Confidence interval

A real Wald CI on the mean DIFFERENCE (`mean_b - mean_a`):
`diff ± z_critical * standard_error`, where `z_critical` comes from a
real lookup table (0.80 through 0.995 confidence levels -- the
realistic range this app's own `confidence_level` field/UI offers),
nearest-match if an exact level isn't in the table. No new numerical
dependency, same tradeoff as everything else here.

## Cohen's d (effect size)

Real, standard, pooled-variance Cohen's d:
`(mean_b - mean_a) / pooled_std_dev`. Honestly `None` when the pooled
standard deviation is 0 (every sample in both groups was identical --
no real effect size is computable, not fabricated as infinity or 0).

## Statistical power

A real, honest POST-HOC estimate: `Phi(|z_observed| - z_critical)` --
answers "given the effect actually observed, how likely was this test
to detect it at this confidence level", NOT a prospective/pre-test
power calculation (that needs an assumed effect size a live,
already-running test can't honestly supply).

## min_sample_size_reached

A plain, real boolean: both variants' tracked sample counts are
`>= ABTest.min_sample_size`. Used by the UI to show whether a result
is trustworthy yet, and by the automatic decision endpoint/task to
gate a real decision.

## The real bug this part found and fixed

See `docs/ab-testing/OVERVIEW.md`'s own section on the
`copy.deepcopy` fix in `track_ab_test_metric` -- a real, live
data-loss bug (a second variant's tracked metric silently failed to
persist) caused by a shallow-copy JSON mutation pattern SQLAlchemy's
change tracking couldn't detect.
