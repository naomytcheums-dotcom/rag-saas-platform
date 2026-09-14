# Feedback

## Rating an answer

Every assistant response has thumbs up/down feedback controls. Use them
— this is real signal, not decorative: feedback feeds into the
platform's evaluation and quality-dashboard tooling that admins use to
catch regressions.

## Reporting a specific problem

If an answer is wrong, ungrounded, or miscited, thumbs-down it and, if
prompted, add a short note on what was wrong. See
[Citations](CITATIONS.md) for what "ungrounded" means here.

## What happens to feedback

Feedback is stored per-message and surfaced to admins via the
[Quality Dashboard](../admin/DASHBOARD.md). It is not used to silently
retrain or fine-tune a model without an explicit fine-tuning job being
created — see [Fine-tuning](../advanced/FINE_TUNING.md).
