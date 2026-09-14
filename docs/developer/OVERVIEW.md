# Developer Overview

This section covers building against the platform: the API, SDKs,
integrations, webhooks, and self-hosting/deployment.

## Where to start

- Building a UI or automation against the REST API directly? Start with
  [API](API.md) and [Authentication](AUTHENTICATION.md).
- Using a client library instead of raw HTTP? See the SDKs:
  [Python](SDK_PYTHON.md), [JavaScript](SDK_JS.md),
  [React](SDK_REACT.md), [Vue](SDK_VUE.md).
- Reacting to platform events instead of polling? See
  [Webhooks](WEBHOOKS.md).
- Connecting an external system (Slack, Teams, Discord, n8n, Airbyte)?
  See [Integrations](INTEGRATIONS.md).
- Embedding chat on your own site? See [Widget Embed](WIDGET_EMBED.md).
- Extending the platform itself with a plugin? See [Plugins](PLUGINS.md).
- Deploying or self-hosting? See the [Install Guide](../install/OVERVIEW.md).

## System design

For the system-level architecture (components, data flow, the
agents-vs-autonomous-agents split, litellm as the LLM abstraction), see
the root [`ARCHITECTURE.md`](../../ARCHITECTURE.md) and this section's
own [Architecture](ARCHITECTURE.md) page.
