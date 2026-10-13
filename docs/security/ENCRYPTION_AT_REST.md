# Encryption at rest (spec 10.1.14)

What is encrypted, by whom, with which key, and how each claim was checked. Two layers, because the application cannot encrypt what it must search.

## 1. Encrypted by the application (secrets stored in PostgreSQL)

| Stored value | Table.column | Algorithm / key |
|---|---|---|
| Webhook signing secret | `webhooks.secret` | AES-256-GCM, `ENCRYPTION_MASTER_KEY` |
| Per-organization connector credentials (Jira, Zendesk, Shopify, ...) | `connector_credentials.encrypted_payload` | AES-256-GCM, `ENCRYPTION_MASTER_KEY` |
| MCP server credential | `mcp_server_configs.auth_credential_encrypted` | AES-256-GCM, `ENCRYPTION_MASTER_KEY` |
| BYOK LLM key | `organization_llm_configs.encrypted_api_key` | Fernet (AES-128-CBC + HMAC-SHA256), `SECRET_ENCRYPTION_KEY` |
| JWT signing keys, SSO client secrets, DKIM keys, ACME / TLS private keys, chat-integration tokens, external-source configs | various | Fernet, `SECRET_ENCRYPTION_KEY` |

`ENCRYPTION_MASTER_KEY` is 32 random bytes (urlsafe base64). Each value has its own random 96-bit nonce and is authenticated: a flipped bit, another key or a missing
key makes decryption fail loudly. `ENCRYPTION_MASTER_KEY_PREVIOUS` keeps old values readable during a rotation; `POST /encryption/rotate-keys` (superadmin) re-encrypts
**every** AES-256-GCM store (webhooks, connector credentials, MCP credentials; found incomplete while testing, it used to cover webhooks only), after which the old key can be dropped.
The Fernet stores use `SECRET_ENCRYPTION_KEY`, a separate key with its own rotation. **Losing a key makes the values it protects unreadable**: back it up separately from the database.

Proved by `tests/test_encryption_at_rest_e2e.py` on a real PostgreSQL: four stores written through their real routes, the raw column read with plain SQL is an envelope (never the
marker), a scan of every text / json / bytea column of every table finds no marker (with a negative control proving the scan can find one), tamper / foreign key / missing key
fail, rotation then dropping the old key still decrypts every store.

## 2. Encrypted by the storage layer (uploaded files)

Uploaded documents, extracted images, voice recordings, fine-tuning datasets and plugin sources go to S3-compatible storage. Set `S3_SERVER_SIDE_ENCRYPTION=AES256` (SSE-S3) or
`aws:kms` with `S3_SSE_KMS_KEY_ID` (SSE-KMS) and the application requests encryption on every write to those private buckets (`api/services/s3_encryption.py`).
Public-read buckets (avatars, branding) are public by design and are not covered. Left unset, the store's default applies: AWS S3 and Cloudflare R2 encrypt every new object, a bare MinIO does not.

Proved by `tests/test_s3_encryption_e2e.py` against a disposable MinIO with a KMS key: without the setting the marker is readable in the store's data directory (negative control); with
`AES256` the store reports `ServerSideEncryption: AES256`, the marker is on no file of the store's disk, and the application still downloads the original bytes. **Not proved:** SSE-KMS
against a real AWS KMS key (needs an AWS account; the header and key id forwarding are unit-tested only).

## 3. Not encrypted by the application, on purpose

- **Document text, chunks and embeddings in PostgreSQL** must be searchable (full-text, vectors): column-level encryption would defeat retrieval. Their protection at rest is the database
  volume's: enable disk encryption (Supabase and RDS encrypt storage by default; for a self-hosted PostgreSQL use LUKS / an encrypted cloud volume / a provider-encrypted disk). The
  application cannot verify it; the operator must.
- **Backups** (`scripts/backup.sh`) are plain dumps: encrypt them where they are stored (encrypted bucket, `gpg`, or an encrypted backup volume).
- **Redis** holds task arguments, rate-limit counters and cached answers: use `rediss://` + password over any untrusted network (enforced at startup) and an encrypted volume if it persists to disk.
- **Application logs** must not contain secrets; the audit and log scrubbers cover known patterns (`scripts/scrub_system_logs.py`).

## 4. Checklist for an operator

1. Generate `ENCRYPTION_MASTER_KEY` and `SECRET_ENCRYPTION_KEY`; store them in a secret manager, separately from database backups.
2. Set `S3_SERVER_SIDE_ENCRYPTION` (and the KMS key id when using `aws:kms`); confirm with `aws s3api head-object` that `ServerSideEncryption` is present.
3. Confirm the PostgreSQL volume and the backup destination are encrypted by the platform.
4. Rotate: set the new key, move the old one to `..._PREVIOUS`, restart, call `POST /encryption/rotate-keys`, then remove the previous key.
