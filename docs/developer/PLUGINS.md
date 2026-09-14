# Plugins

The plugin system lets third parties extend the platform, discoverable
through the marketplace — `api/routers/plugins.py`.

## Developing a plugin

See [`docs/plugins/DEVELOPER_GUIDE.md`](../plugins/DEVELOPER_GUIDE.md)
for the full plugin API and lifecycle.

## Publishing to the marketplace

See [`docs/plugins/MARKETPLACE.md`](../plugins/MARKETPLACE.md) and
[`docs/marketplace/PARTIE_16_TER_MARKETPLACE.md`](../marketplace/PARTIE_16_TER_MARKETPLACE.md)
for listing, review, and distribution.

## Plugin security

Plugins go through a security review before being listed — see
[`docs/plugins/SECURITY.md`](../plugins/SECURITY.md) and
[Security Scanning](../admin/SECURITY_SCANNING.md).

## Installing a plugin

As an admin, install a plugin for your organization from the
marketplace UI or via `api/routers/plugins.py` directly. Installed
plugins are scoped to the organization that installed them.
