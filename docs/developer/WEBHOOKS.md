# Webhooks

Webhooks let you receive outbound HTTP callbacks on platform events
instead of polling — `api/routers/webhooks.py`.

## Configuring a webhook

Under your organization's developer settings, add an endpoint URL and
select which events to subscribe to (e.g. document processed,
conversation created, agent run completed, fine-tuning job status
change).

## Payload

Each delivery is a JSON payload describing the event type, the
affected resource, and a timestamp. See [Webhooks](../api/WEBHOOKS.md)
in the API reference for the exact shape.

## Verifying deliveries

Deliveries are signed; verify the signature header against your
webhook's configured secret before trusting the payload.

## Retries

Failed deliveries (non-2xx response) are retried with backoff for a
limited period before being marked failed. Check your webhook's
delivery log under developer settings if events seem to be missing.
