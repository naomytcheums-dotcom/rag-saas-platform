# Security Scanning

Full platform security architecture — encryption, compliance tooling,
security scanning — is documented in
[`docs/security/PARTIE_10_SECURITY.md`](../security/PARTIE_10_SECURITY.md).
This page is the admin-facing operational summary.

## What gets scanned

`api/routers/security_scan.py` covers scanning of uploaded content and
configured integrations for known risk patterns before they're fully
active in your organization.

## Running a scan

**Admin → Security → Scans** shows scan history and lets you trigger an
on-demand scan where supported.

## Encryption

Data-at-rest and data-in-transit encryption settings are covered in
[`docs/security/PARTIE_10_SECURITY.md`](../security/PARTIE_10_SECURITY.md#encryption)
— see `api/routers/encryption.py`.

## Plugin security

Third-party plugins go through their own security review path — see
[`docs/plugins/SECURITY.md`](../plugins/SECURITY.md).
