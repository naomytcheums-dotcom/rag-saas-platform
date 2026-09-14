# Security Policy

This file covers vulnerability reporting for this repository. For the
platform's built-in security *features* (encryption, RBAC, audit
logging, compliance tooling, security scanning), see
[`docs/security/PARTIE_10_SECURITY.md`](docs/security/PARTIE_10_SECURITY.md).

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Email naomytcheums@gmail.com with:

- A description of the vulnerability and its potential impact.
- Steps to reproduce (a minimal reproduction is ideal).
- Any relevant logs, request/response samples, or affected versions.

You should receive an acknowledgment within a few days. Please allow a
reasonable amount of time for a fix to be developed and released before
any public disclosure.

## Scope

In scope: the `api/` backend, `frontend/` application, `sdks/*`
client libraries, and the self-hosted deployment tooling
(`docker-compose*.yml`, `install.sh`, `scripts/`).

Out of scope: the original single-tenant demo under `src/` — it's a
portfolio/evaluation project, not a production deployment target; see
[`src/README.md`](src/README.md#current-limitations) for its own
documented limitations.

## Supported versions

This project does not yet maintain multiple parallel release branches —
security fixes are applied to `main` and documented in
[`CHANGELOG.md`](CHANGELOG.md).
