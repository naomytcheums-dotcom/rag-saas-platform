# Pricing — the 4 real plan tiers

Seeded automatically the first time `GET /billing/plans` (or any
subscription endpoint) runs (`api/services/admin_subscriptions.py`'s
`ensure_default_plans_seeded`) — real rows, editable afterward via
`/admin/plans`, not fixed constants.

| Plan | Monthly | Yearly | Documents | Agents | Members | Priority support | Advanced features | SLA |
|---|---|---|---|---|---|---|---|---|
| Free | €0 | €0 | 50 | 3 | 5 | no | no | no |
| Starter | €49 | €490 | 100 | 3 | 5 | no | no | no |
| Pro | €199 | €1,990 | 1,000 | 10 | 20 | yes | yes | no |
| Enterprise | €999 | €9,990 | unlimited | unlimited | unlimited | yes | yes | yes |

Every organization gets a real, free Subscription automatically, with
a real 14-day trial (`Subscription.trial_ends_at`, `BILLING_TRIAL_DAYS`
in `.env`). Real limit enforcement: document upload
(`POST /organizations/{org_id}/documents`) checks the real document
count against the plan's real `max_documents` and returns a real `402
Payment Required` when exceeded (`api/services/billing_usage.py`'s
`check_plan_resource_limit`) — the same function is ready to gate
agents/members too, wired for documents first as the concrete,
verified example.
