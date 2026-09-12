# Partner onboarding

## 1. Register

```bash
curl -X POST https://<your-domain>/partners/register \
  -H "Content-Type: application/json" \
  -d '{"organization_name": "Acme Resellers", "email": "you@acme.example", "password": "..."}'
```

This creates your own account, your own organization, and marks it as
a reseller at the platform's default commission rate (see
`docs/sales/PARTNER_PROGRAM.md` for the exact percentage).

## 2. Sign in

Use the same email/password at `/auth/login` -- registering as a
partner does not auto-issue a session; sign in normally afterward.

## 3. View your dashboard

`/dashboard/partners` shows your commission rate, status, and the full
history of commission payouts (`GET /partners/me`,
`GET /partners/me/commissions`).

## 4. Get clients assigned to you

Bringing on a client today is a manual step: ask the platform's own
team to run `POST /reseller/{your_reseller_id}/clients` with the new
client organization's id (find your own `reseller_id` via
`GET /partners/me`). A fully self-service "sign up under my link" flow
is not built yet -- see `docs/sales/PARTNER_PROGRAM.md`'s honest gaps
section.

## 5. Get paid

Once your sub-clients are on real, paid subscriptions, the platform's
own monthly job calculates your commission and records it (`GET
/partners/me/commissions` shows `pending` rows). A daily job pays out
any reseller whose pending total has reached the platform's minimum
payout threshold -- below that, your commission stays real and
pending until it does. Payouts are a ledger status change today, not
an automatic bank transfer; the platform's own team settles payment
manually once a commission is marked ready.
