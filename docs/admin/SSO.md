# Single Sign-On (SSO)

Enterprise SSO lets members authenticate via your identity provider
instead of a platform password — see `api/routers/enterprise_sso.py`.

## Setting up SSO

**Admin → Security → SSO**. Configure your identity provider's SAML/
OAuth details as provided by your IdP (Okta, Azure AD, Google
Workspace, etc.).

## OAuth (non-enterprise)

Separately from enterprise SSO, standard OAuth login (e.g. "Sign in
with Google") may be available depending on configuration — see
`api/routers/oauth.py`.

## Enforcing SSO

Once configured, SSO can be made mandatory for the organization,
disabling direct password login for members — use this carefully, and
confirm at least one admin has a working SSO login before enforcing it.

## Provisioning

New members can be auto-provisioned on first SSO login rather than
requiring a manual invite — see
[Members & Invitations](MEMBERS_AND_INVITATIONS.md#enterprise-sso).
