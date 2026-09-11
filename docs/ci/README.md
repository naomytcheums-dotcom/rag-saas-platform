# CI: CircleCI only — GitHub Actions disabled

## Current state

`.github/workflows/` was renamed to `.github/workflows.disabled/`
(2026-09-18) — GitHub only ever runs workflow files that live inside
`.github/workflows/`, so this stops every job from running at all,
with zero cost, while keeping the real, working workflow file in the
repo (not deleted) for later.

## Why

This repo's GitHub account has a real billing problem: every job on
every push fails in ~2 seconds with `The job was not started because
recent account payments have failed or your spending limit needs to be
increased` (confirmed via `gh run view <run-id>` on multiple pushes,
across multiple commits — this is an account-level billing state, not
a bug in any workflow file). Since the explicit decision here is not
to add a payment method, leaving `.github/workflows/regression.yml` in
place would just keep generating real, visible "failure" rows in the
Actions tab and in `gh run list` forever, on every future push, for a
reason that has nothing to do with the code being pushed. Disabling it
removes that noise.

## What replaces it

**CircleCI** — see `docs/ci/CIRCLECI_SETUP.md` for the exact connection
steps. `.circleci/config.yml` is real and already committed; it mirrors
`regression.yml`'s two most important jobs (the RAG pipeline
regression check, and the real Postgres/Redis/MinIO-backed `api/`
suite, including Node.js for the plugin sandbox tests). CircleCI's
free tier (6,000 build-minutes/month, no card required) works on
private repos and needs no billing decision at all.

## Re-enabling GitHub Actions later

If the billing issue is ever resolved (a payment method added, or the
account's spending limit raised in Billing & plans):

```bash
git mv .github/workflows.disabled .github/workflows
git commit -m "Re-enable GitHub Actions"
git push
```

Nothing else needs to change — `regression.yml` itself was never
edited as part of disabling it, only moved.
