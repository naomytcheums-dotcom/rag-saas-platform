# GitHub Actions billing block

## The real, confirmed problem

Every GitHub Actions run on this repo fails within ~2-4 seconds, on
every job, with this exact annotation (confirmed via
`gh run view <run-id>`, checked across multiple separate commits):

```
The job was not started because recent account payments have failed
or your spending limit needs to be increased. Please check the
'Billing & plans' section in your settings
```

This is a GitHub **account-level** billing state — it has nothing to
do with any workflow file, any commit, or this repo's code. No
workflow-file change can fix it.

## How to actually resolve it (if wanted later)

1. Go to `github.com/settings/billing` (account-level, not
   repo-level) while logged in as the account that owns this repo.
2. Look for a **failed payment** notice — update the payment method on
   file, or add one for the first time.
3. Check the **spending limit** for GitHub Actions specifically (same
   billing page) — a limit of $0 blocks every private-repo Actions run
   even with a valid payment method, since private-repo Actions
   minutes are a paid feature past the free tier.
4. Once either is fixed, re-enable the workflows:
   ```bash
   git mv .github/workflows.disabled .github/workflows
   git commit -m "Re-enable GitHub Actions"
   git push
   ```

## The decision made here

Per explicit instruction: no payment method is being added. GitHub
Actions stays disabled (`docs/ci/README.md`) and **CircleCI is the
only CI for this repo** going forward — free, no card required, works
on private repos. See `docs/ci/CIRCLECI_SETUP.md`.
