# Tutorial: Set Up SSO

See [SSO](../admin/SSO.md) for the full reference.

## 1. Gather your IdP details

From your identity provider (Okta, Azure AD, Google Workspace, etc.),
you'll need the SAML metadata URL (or the OAuth client ID/secret,
depending on protocol).

## 2. Configure in the dashboard

**Admin → Security → SSO → Configure**. Paste in your IdP's details.

## 3. Test before enforcing

Log in via the new SSO connection in a separate/incognito session while
your existing password login still works, to confirm the SSO flow
completes correctly end to end.

## 4. Enforce (optional)

Once confirmed working, you can require SSO for all members under the
same page — this disables direct password login. Confirm at least one
admin account has a working SSO login before doing this; there's no
built-in "undo" if your own SSO connection breaks after enforcement.

## 5. Auto-provisioning

New members can be created automatically on first SSO login rather than
requiring a manual invite — see
[Members & Invitations](../admin/MEMBERS_AND_INVITATIONS.md#enterprise-sso).
