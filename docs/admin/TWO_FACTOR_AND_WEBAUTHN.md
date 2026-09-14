# Two-Factor Authentication & WebAuthn

## Two-factor authentication (2FA)

Members can enable time-based one-time-code 2FA individually from their
own Settings (see [Account Setup](../user/ACCOUNT_SETUP.md)) —
`api/routers/two_factor.py`. As an admin, you can require 2FA
organization-wide under **Admin → Security**.

## WebAuthn

Hardware security keys and platform authenticators (Touch ID, Windows
Hello) are supported as an alternative to or in addition to 2FA —
`api/routers/webauthn.py`.

## Requiring stronger auth

**Admin → Security → Authentication policy** lets you require 2FA
and/or WebAuthn for all members, or only for members with elevated
roles (admins, owners).

## Lost second factor

If a member loses access to their 2FA device or security key, an admin
can reset their 2FA enrollment from **Admin → Members**, forcing
re-enrollment on next login.
