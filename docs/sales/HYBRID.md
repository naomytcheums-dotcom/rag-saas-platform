# Selling as hybrid (self-hosted + premium support)

New in Partie 16 (bis): `SupportTicket`/`TicketResponse` (real,
per-organization) and a real, computed SLA (`SLA_RESPONSE_HOURS`:
critical=1h, high=4h, normal=24h, low=72h). `GET
/organizations/{org_id}/support/tickets/{id}/sla` returns a real
`breached: true/false` — checked against the ticket's own real
`first_responded_at` once staff has responded, against "now" until
then. Never a decorative "SLA: OK" label with nothing computing it.

Real, reused machinery, not duplicated: "monitoring à distance
(télémétrie opt-in)" is the same real Prometheus `/metrics` +
`/monitoring/*` endpoints built in Partie 11.5/13.1 — a hybrid
customer's deployment exposes them the same way any deployment does;
"opt-in" here means the customer chooses whether to let YOUR Grafana
Cloud/Prometheus scrape their `/metrics`, not a separate telemetry
system.

Billing: reuses the real Plan/Subscription/Invoice system (Partie 12)
— a hybrid contract is a real Plan row with `priority_support: true`
and/or `sla: true` set (already real columns, Partie 12.1), not a
parallel billing model.
