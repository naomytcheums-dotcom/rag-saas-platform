# CircleCI setup (free CI for this private repo)

## Why CircleCI, not GitLab CI or Google Cloud Build

GitHub Actions is disabled outright for this repo (`.github/workflows/`
renamed to `.github/workflows.disabled/` -- see `docs/ci/README.md`
and `docs/ci/GITHUB_ACTIONS_BILLING.md`): every job was failing in
~2 seconds with `The job was not started because recent account
payments have failed or your spending limit needs to be increased` --
a real GitHub account billing issue, unrelated to this repo's code,
and the explicit decision here is not to add a payment method.
**CircleCI is the only CI for this repo now.**

Compared:

- **CircleCI** -- 6,000 build-minutes/month free, no card required,
  works on private repos, connects directly to this GitHub repo via
  CircleCI's own GitHub App (no separate account/mirror needed). Once
  connected, it auto-detects `.circleci/config.yml` on every push.
  **Simplest to set up.**
- **GitLab CI** -- only 400 minutes/month free, and this repo lives on
  GitHub -- using GitLab CI would mean either mirroring this repo to
  GitLab (an extra moving part to keep in sync) or moving it there
  entirely. More setup, less free minutes.
- **Google Cloud Build** -- 2,500 build-minutes/month free, but
  requires a full GCP project + billing account on file (even for the
  free tier) + IAM/service-account setup + connecting the GitHub repo
  via Cloud Build's own GitHub App -- meaningfully more setup steps
  than CircleCI for a comparable result, and "a billing account on
  file" is exactly what this whole exercise is trying to avoid needing
  to trust with a card.

**Recommendation: CircleCI.** Fewest steps, most free minutes, no
payment method needed.

## Status: already connected

Confirmed connected as of 2026-09-18 -- the project
`naomytcheums-dotcom/rag-saas-platform` is already set up in CircleCI
(`app.circleci.com/pipelines/github/naomytcheums-dotcom/rag-saas-platform`),
and pipeline #1 already ran against commit `7b7de8f` -- it failed on
the real `<<` heredoc bug documented below, now fixed. The steps below
are kept for reference (re-connecting after disconnecting, or setting
this up on a fresh clone) -- you don't need to repeat them.

## Connection procedure (one-time, done by you -- I cannot create
accounts or click through OAuth on your behalf)

1. Go to <https://circleci.com/signup/> and choose **"Sign Up with
   GitHub"** -- this authenticates via GitHub OAuth, no new password to
   manage, and immediately grants CircleCI read access to your repos
   (nothing is enabled yet).
2. On the CircleCI dashboard, go to **Projects** in the left sidebar.
3. Find `rag-saas-platform` in the list (search if it's a private repo
   you own -- it shows up because your GitHub account authorized
   CircleCI in step 1) and click **Set Up Project**.
4. CircleCI asks how to find the config: choose **"Fastest"** (it will
   detect `.circleci/config.yml`, already committed in this repo, at
   the root) -- do NOT use the "Add config" editor, since the real file
   is already here.
5. Click **Set Up Project**. CircleCI triggers a first real pipeline
   run against the current `main` branch immediately.
6. That's it -- every future `git push` to any branch of this repo now
   triggers this same pipeline automatically. No webhook to configure
   by hand; CircleCI's GitHub App sets that up as part of step 3-4.

## What the pipeline actually runs

Two jobs, mirroring `.github/workflows/regression.yml`'s two most
important jobs (see `.circleci/config.yml`'s own top comment for why
the other two -- `docker-build`, the Snyk/OWASP ZAP `security-scan` --
are deliberately left out of this first pass):

- **`rag-pipeline-regression`** -- the original RAG ingestion/retrieval
  regression check (`tests_pipeline/test_ingestion.py`,
  `tests_pipeline/test_retrieval.py`, `tests/test_regression.py`).
- **`api-tests`** -- the real, Postgres/Redis/MinIO-backed `api/` auth
  backend + RAG-agent test suite (the same ~250-file list
  `regression.yml`'s `api-tests` job runs), including the four new
  Partie 15 test files (`test_connections.py`, `test_mappings.py`,
  `test_inbound_webhooks.py`, `test_transformations.py`) and the sales/
  notifications tests. Real Postgres, Redis, and MinIO run as CircleCI
  secondary containers (`cimg/postgres:16.4`, `cimg/redis:7.4`,
  `minio/minio`), same as GitHub Actions' `services:` containers --
  no mocked infrastructure.

## Real bug found and fixed (first live run)

The first real pipeline run failed immediately with `Error calling
workflow: 'regression-check' ... Unclosed '<<' tag ('<<' must be
escaped as '\<<' in config v2.1+)`, pointing at a `python -
<<'PYEOF'` heredoc inside the `api-tests` job's own bucket-creation
step. CircleCI 2.1 YAML reserves a literal `<<` (the merge key), so a
shell heredoc using it breaks parsing. Fixed by moving that Python
script into a real repo file, `scripts/ci_create_buckets.py`, and
calling `python scripts/ci_create_buckets.py` instead -- this avoids
the whole class of bug rather than escaping one instance of it (any
other embedded heredoc would hit the same problem). Verified the fix
by parsing the corrected YAML with Python's own `yaml.safe_load` (no
syntax errors) -- the CircleCI CLI itself (`circleci config validate`)
could not be installed in this environment (its install script
returned a 404), so the actual next real check happens on the first
live pipeline run once you connect the project (step below).

## Secrets

None needed for these two jobs -- every `DATABASE_URL`/`JWT_SECRET_KEY`/
etc. value in `.circleci/config.yml`'s `environment:` block is a
throwaway CI-only value (see that file's own comment), never a real
secret, exactly like `regression.yml`. If a later pass adds the Snyk
scan job, that one DOES need a real secret (`SNYK_TOKEN` from a free
snyk.io account) added via CircleCI's own **Project Settings →
Environment Variables** -- never committed to this repo either way.

## Checking a run

CircleCI's own dashboard (`app.circleci.com`) shows every pipeline run,
same as GitHub Actions' own `Actions` tab -- no `gh`-equivalent CLI
lookup is set up in this repo, since that would need a personal
CircleCI API token stored somewhere. Ask directly and I can walk
through what a specific run's log shows once you paste its URL or tell
me what you see.
