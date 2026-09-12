# White-label email sender identity (Partie 19)

`POST/DELETE /organizations/{org_id}/whitelabel/email` sets
`email_sender_name`/`email_sender_email` -- the reply-to display name
and address a recipient sees on outbound emails from that organization.

**This is deliberately a different, narrower thing than Partie 1.4.5's
custom-domain email** (`docs/sales/PARTNER_PROGRAM.md` and
`api/routers/email_domains.py`), which actually SENDS from a verified
custom domain via Resend. This white-label field is just the display
identity -- real and honest regardless of whether a custom domain is
even configured, since not every white-label customer needs (or has
verified) their own sending domain yet.

## Configuring

```bash
curl -X POST https://api.yourplatform.example/organizations/{org_id}/whitelabel/email \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"sender_name": "Acme Support", "sender_email": "support@acme-agency.com"}'
```

Both fields are validated as a real display name and a real email
address shape (`422` otherwise) -- neither is checked for deliverability
or domain ownership; that verification belongs to Partie 1.4.5's
custom-domain flow if/when this organization also sets one up.

## Removing

```bash
curl -X DELETE https://api.yourplatform.example/organizations/{org_id}/whitelabel/email \
  -H "Authorization: Bearer <token>"
```

Clears both fields back to `null`.
