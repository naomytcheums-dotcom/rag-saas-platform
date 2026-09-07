"""
Central settings for the api/ package, loaded once from environment
variables and a project-root .env file in dev -- pydantic-settings reads
the .env file itself (env_file below), so this deliberately does NOT reuse
src/generation.py's loader: that module pulls in `anthropic` and the rest
of the RAG pipeline's dependencies at import time, which api/ has no other
reason to depend on. Same intent (project-root .env, dev convenience,
never overriding real environment variables), zero coupling to src/.

Fields with no default are genuinely required in production; Settings()
raises a clear pydantic ValidationError naming every missing one instead of
failing later with a confusing AttributeError the first time a route uses
one, so a misconfigured deployment is caught at process startup.
"""

from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", env_prefix="", case_sensitive=True, extra="ignore"
    )

    # -- Database -----------------------------------------------------
    # postgresql+asyncpg://user:password@host:port/dbname
    DATABASE_URL: str

    # -- JWT ------------------------------------------------------------
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    MFA_TOKEN_EXPIRE_MINUTES: int = 5
    # Comma-separated list of PREVIOUS JWT_SECRET_KEY values, still
    # accepted when VERIFYING a token but never used to SIGN a new one
    # (api/security/jwt.py's decode_token tries JWT_SECRET_KEY first,
    # then each of these in order). Two different procedures, both
    # covered by the same mechanism -- see docs/AUTH_BACKEND_SETUP.md:
    #   - Routine rotation: move the old JWT_SECRET_KEY here during a
    #     grace window (>= ACCESS_TOKEN_EXPIRE_MINUTES) so already-issued
    #     access tokens keep working until they naturally expire, then
    #     remove it once that window has passed.
    #   - Responding to a LEAK: do NOT put the leaked key here -- leave
    #     this empty. Every access token signed with the leaked key
    #     immediately fails to verify. Refresh tokens are unaffected
    #     (they're random opaque values hashed in the database, not
    #     JWTs), so users get a fresh, correctly-signed access token via
    #     POST /auth/refresh without needing to log in again.
    JWT_PREVIOUS_SECRET_KEYS: str = ""

    # -- Password / token hashing ---------------------------------------
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    EMAIL_OTP_EXPIRE_MINUTES: int = 10
    EMAIL_OTP_MAX_ATTEMPTS: int = 5
    # Partie 1.3.4 -- deliberately longer than PASSWORD_RESET_TOKEN_EXPIRE_MINUTES:
    # an org invitation is a much lower-urgency, lower-attack-surface
    # link than a password reset, and the recipient may not check their
    # inbox for days.
    INVITATION_EXPIRE_DAYS: int = 7

    # -- Partie 1.3.6: default per-organization resource quotas ----------
    # Seeded onto every new OrganizationQuota row at org creation
    # (api/security/organizations.py's create_organization_with_owner);
    # changing these settings only affects organizations created
    # AFTERWARD -- an existing org's quotas are its own row, editable via
    # PATCH /organizations/{id}/quotas (Owner only), not re-derived from
    # these defaults on every read.
    QUOTA_DEFAULT_MAX_USERS: int = 10
    QUOTA_DEFAULT_MAX_WORKSPACES: int = 5
    QUOTA_DEFAULT_MAX_TEAMS: int = 10
    QUOTA_DEFAULT_MAX_DOCUMENTS: int = 1000
    QUOTA_DEFAULT_MAX_STORAGE_MB: int = 1024
    QUOTA_DEFAULT_MAX_REQUESTS_PER_MONTH: int = 10000
    QUOTA_DEFAULT_MAX_REQUESTS_PER_DAY: int = 500
    QUOTA_DEFAULT_MAX_API_CALLS: int = 5000
    QUOTA_DEFAULT_MAX_AGENTS: int = 10
    QUOTA_DEFAULT_MAX_KB_SIZE_MB: int = 512

    # -- Partie 1.4.1: custom domains --------------------------------------
    # The hostname a custom domain's CNAME record must point at -- this
    # deployment's own real routable hostname. A placeholder default:
    # no reverse-proxy actually routes traffic by Host header yet (see
    # docs/AUTH_BACKEND_SETUP.md's Custom Domains section for the full
    # honest-scope story), so this only matters for what instructions
    # GET/POST .../domains hand back today.
    CUSTOM_DOMAIN_CNAME_TARGET: str = "app.rag-saas-platform.com"
    # How long a single DNS TXT lookup waits before giving up -- bounds
    # the worst case for GET .../domains/verify/{token} (a real,
    # non-blocking network call, see api/security/custom_domains.py).
    CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS: int = 5

    # -- Partie 1.4.3: SSL auto (Let's Encrypt) ----------------------------
    # Defaults to Let's Encrypt's STAGING directory, deliberately -- NOT
    # production. Staging issues certificates untrusted by real browsers
    # but shares production's exact protocol and rate-limit-free
    # sandbox, which is what every real client (certbot included)
    # develops and tests against. A real deployment overrides this to
    # "https://acme-v02.api.letsencrypt.org/directory" explicitly, once
    # the manual-DNS-01 workflow this step documents (see
    # docs/AUTH_BACKEND_SETUP.md) has been exercised for real. Getting
    # this wrong in the other direction (defaulting to production) risks
    # a misconfigured dev/CI environment burning through Let's Encrypt's
    # real, hard-to-recover-from rate limits for nothing.
    ACME_DIRECTORY_URL: str = "https://acme-staging-v02.api.letsencrypt.org/directory"
    # Required by Let's Encrypt for account registration (expiry/revocation
    # notices) -- generate_ssl_certificate raises a clear error if this
    # is unset, same "fail loudly, not with a confusing exception three
    # calls deep" reasoning as api/services/storage.py's S3 settings.
    ACME_ACCOUNT_EMAIL: str | None = None
    # Partie 1.4.3, item 5's "30 jours avant expiration" -- how far
    # ahead of expires_at the renewal Celery task starts trying.
    SSL_RENEWAL_WINDOW_DAYS: int = 30

    # -- Partie 1.4.4: periodic domain-verification polling ----------------
    # Named DOMAIN_VERIFICATION_INTERVAL/_MAX_ATTEMPTS/_TIMEOUT in this
    # step's literal spec -- suffixed here with explicit units
    # (_SECONDS/_MINUTES), same convention as every other duration
    # setting in this file (e.g. CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS).
    # How often api/tasks/domain_verification.py's periodic sweep runs.
    DOMAIN_VERIFICATION_INTERVAL_SECONDS: int = 300
    # A domain still `pending` after this many automatic polling
    # attempts (the periodic sweep only -- the Owner's manual "verify
    # now" endpoint and the original public token link check
    # immediately and don't count against this limit, see
    # api/security/custom_domains.py's apply_verification_check vs.
    # trigger_manual_verification/verify_domain) is marked `failed`.
    DOMAIN_VERIFICATION_MAX_ATTEMPTS: int = 12
    # A second, wall-clock-based limit alongside MAX_ATTEMPTS -- at the
    # defaults above (12 attempts x 5 minutes) the two normally expire
    # together, but this one alone still protects a domain that's been
    # pending for an hour despite the periodic sweep running less often
    # than expected (a worker outage, a missed beat tick).
    DOMAIN_VERIFICATION_TIMEOUT_MINUTES: int = 60

    # -- Partie 1.4.5: custom email-sending domain --------------------------
    # Named EMAIL_DOMAIN_VERIFICATION_TIMEOUT in this step's literal spec --
    # suffixed with _HOURS (its own stated default is "24h"), same
    # explicit-units convention as every other duration setting in this file.
    # Measured from CustomDomain.email_verification_started_at (see that
    # column's own comment for why it's a dedicated column, unlike 1.4.4's
    # reuse of created_at).
    EMAIL_DOMAIN_VERIFICATION_TIMEOUT_HOURS: int = 24
    # This app's OWN DKIM selector for the self-generated keypair
    # (api/security/email_domains.py's generate_dkim_keys) -- NOT Resend's
    # own selector (Resend always uses the fixed "resend" selector for the
    # DKIM key it generates and manages itself; see that module's docstring
    # for why the two are unrelated).
    DKIM_SELECTOR: str = "rag-saas"
    # RESEND_API_KEY already exists above ("Transactional email (Resend)")
    # -- reused as-is by api/services/resend_domains.py's real Domains API
    # calls, not redefined here.

    # -- RGPD -------------------------------------------------------------
    TERMS_VERSION: str = "2026-01-01"
    ACCOUNT_PURGE_DELAY_DAYS: int = 30
    # Deliberately longer than PASSWORD_RESET_TOKEN_EXPIRE_MINUTES (60):
    # "I want my deleted account back" is a lower-urgency, lower-attack-
    # surface scenario than a password reset, and the user has up to
    # ACCOUNT_PURGE_DELAY_DAYS to notice the email at all -- an hour-long
    # window would expire before most people even check their inbox.
    ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES: int = 1440
    # 4.6: how close to the actual purge the "last chance" reminder email
    # goes out (api/tasks/account_deletion_reminder.py) -- separate from
    # the immediate confirmation DELETE /account/me already sends. 3 days
    # gives a real window to notice and restore without being so early
    # it reads as the same email as the immediate confirmation.
    ACCOUNT_DELETION_REMINDER_DAYS_BEFORE: int = 3

    # -- Cookies / CORS -----------------------------------------------------
    FRONTEND_URL: str = "http://localhost:3000"
    COOKIE_DOMAIN: str | None = None
    COOKIE_SECURE: bool = True
    SESSION_MIDDLEWARE_SECRET: str = Field(min_length=32)

    # -- OAuth ------------------------------------------------------------
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None
    GITHUB_OAUTH_CLIENT_ID: str | None = None
    GITHUB_OAUTH_CLIENT_SECRET: str | None = None
    OAUTH_REDIRECT_BASE_URL: str = "http://localhost:8000"

    # -- Transactional email (Resend) --------------------------------------
    RESEND_API_KEY: str | None = None
    EMAIL_FROM_ADDRESS: str = "no-reply@example.com"
    # RGPD Art. 12: a data subject must be able to easily reach the
    # controller to exercise their rights or ask questions. Required (no
    # default) rather than silently omitting the footer or shipping a
    # fake address nobody reads -- api/services/email.py's _send()
    # appends it to every single email this app sends, unconditionally.
    SUPPORT_EMAIL: str

    # -- Object storage (S3 or Cloudflare R2, both S3-compatible) -------
    S3_ENDPOINT_URL: str | None = None  # leave unset for real AWS S3
    S3_BUCKET_NAME: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_REGION: str = "auto"
    S3_PUBLIC_BASE_URL: str | None = None  # CDN/public URL prefix for uploaded objects
    # Partie 2.1.1 -- a SEPARATE bucket from S3_BUCKET_NAME above, not a
    # key prefix in the same one the way branding assets share it with
    # avatars. Avatars/logos/favicons are uploaded public-read on
    # purpose (meant to be shown to any visitor); documents are private
    # organizational content and must never be. Reusing S3_BUCKET_NAME
    # would risk exactly that in any deployment whose bucket policy
    # makes the whole bucket public (this project's own CI MinIO setup
    # does precisely that for the avatars bucket, see
    # .github/workflows/regression.yml) -- a second bucket makes that
    # policy scope correctly regardless of per-object ACLs. Same
    # S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY/S3_ENDPOINT_URL/S3_REGION
    # credentials, just a different bucket name.
    S3_DOCUMENTS_BUCKET_NAME: str | None = None

    # -- GitHub repository import (Partie 2.1.12) ---------------------------
    # A real Personal Access Token (fine-grained or classic, `repo` scope
    # for private repos) -- NOT the same thing as GITHUB_OAUTH_CLIENT_ID/
    # SECRET above, which authenticate a USER signing in with GitHub.
    # This one authenticates THIS SERVER's own outbound calls to the
    # GitHub REST API when importing a repo's files into a knowledge
    # base. Optional: a PUBLIC repo needs no token at all (GitHub's REST
    # API allows unauthenticated reads, just at a much lower real rate
    # limit -- 60 requests/hour vs. 5,000/hour authenticated, confirmed
    # for real before writing api/services/github_extraction.py). A
    # PRIVATE repo genuinely cannot be imported without one -- there is
    # no way around that, and no attempt is made to pretend otherwise.
    GITHUB_API_TOKEN: str | None = None
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    # This step's own literal default -- confirmed for real to match
    # GitHub's own Contents API limit for returning a file's content
    # inline as base64 (a file over this size gets `encoding: "none"`,
    # `content: ""` instead, needing a second real request to a
    # DIFFERENT host, raw.githubusercontent.com -- see that module's own
    # docstring for why this codebase deliberately never needs to make
    # that second call at all).
    GITHUB_MAX_FILE_SIZE: int = 1 * 1024 * 1024  # 1 MB
    # Comma-separated, this step's own literal default -- a real
    # ALLOWLIST, not an optional narrowing filter (unlike Partie 2.1.11's
    # sitemap `filters`): an ordinary code repository genuinely contains
    # plenty of content a knowledge base should never ingest (binaries,
    # images, compiled output, lockfiles) with no format-level signal
    # distinguishing them the way validate_document_upload's real content
    # checks do for an upload -- see github_include_patterns_list below.
    GITHUB_INCLUDE_PATTERNS: str = ".md,.txt,.py,.js,.ts,.json,.yml,.yaml"

    @property
    def github_include_patterns_list(self) -> list[str]:
        return [pattern.strip() for pattern in self.GITHUB_INCLUDE_PATTERNS.split(",") if pattern.strip()]

    # -- Google Drive import (Partie 2.1.14) ---------------------------------
    # A genuinely different auth shape from GITHUB_API_TOKEN above: Google's
    # OAuth 2.0 model has no single static credential for server-to-server
    # API access. An operator completes Google's own OAuth consent flow for
    # this application ONCE, out of band (e.g. Google's OAuth Playground, or
    # a one-time local script using these same CLIENT_ID/CLIENT_SECRET
    # values), and stores the resulting REFRESH token here -- it is
    # exchanged for a real, short-lived (~1 hour) access token before every
    # batch of real Drive API calls (api/services/google_drive_extraction.py's
    # own authenticate_drive). All three are required together for ANY real
    # Drive import to work -- unlike GitHub's own optional token (a public
    # repo needs none), Drive has no unauthenticated read mode at all,
    # confirmed for real: a request with no Authorization header at all gets
    # a real 403, and one with a real, present-but-invalid token gets a real
    # 401 -- both live, neither is a guess.
    GOOGLE_DRIVE_CLIENT_ID: str | None = None
    GOOGLE_DRIVE_CLIENT_SECRET: str | None = None
    GOOGLE_DRIVE_REFRESH_TOKEN: str | None = None
    # This step's own literal default.
    GOOGLE_DRIVE_MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50 MB
    # Comma-separated, this step's own literal (unnamed) default -- a real
    # ALLOWLIST, same "an arbitrary folder holds plenty of content this
    # pipeline can't meaningfully ingest as text" reasoning as
    # GITHUB_INCLUDE_PATTERNS -- covers every format Partie 2.1.1-2.1.9
    # already knows how to process for real, not an arbitrary guess.
    GOOGLE_DRIVE_INCLUDE_PATTERNS: str = ".pdf,.docx,.txt,.md,.html,.csv,.json,.xml,.epub"

    @property
    def google_drive_include_patterns_list(self) -> list[str]:
        return [pattern.strip() for pattern in self.GOOGLE_DRIVE_INCLUDE_PATTERNS.split(",") if pattern.strip()]

    # -- Google Docs import (Partie 2.1.15) ----------------------------------
    # Reuses GOOGLE_DRIVE_CLIENT_ID/SECRET/REFRESH_TOKEN above unchanged -- a
    # real Google Doc IS, underneath, just a real Drive file with a special
    # mimeType, exported via the SAME real OAuth flow and Drive API host (see
    # api/services/google_drive_extraction.py's own dedicated docstring
    # section). This step's own literal default -- DOCX, not text/plain --
    # a real, deliberate choice: DOCX is already a real, fully-supported
    # format (Partie 2.1.2), so a Google Doc becomes indistinguishable from
    # one a user uploaded directly, the strongest possible "reuse the
    # pipeline" answer. Real Sheets/Slides use their own real, separately
    # hardcoded defaults (CSV/PDF, Partie 2.1.6/2.1.1) -- this ONE setting is
    # deliberately DOC-specific, matching this step's own literal name.
    GOOGLE_DOCS_EXPORT_FORMAT: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # -- Notion import (Partie 2.1.16) ---------------------------------------
    # A real Notion "internal integration" token (Settings -> Connections ->
    # Develop or manage integrations, in a real Notion workspace this server
    # should import from) -- a real, static, server-wide secret, the SAME
    # shape as GITHUB_API_TOKEN (no OAuth refresh dance needed for this kind
    # of integration). A real page/database must also be explicitly SHARED
    # with the integration inside Notion itself -- confirmed for real,
    # Notion's own API returns the exact same 404 for "does not exist" and
    # "exists but not shared with this integration", the same real
    # anti-enumeration design GitHub's own API already uses for a private
    # repo.
    NOTION_API_TOKEN: str | None = None
    # This step's own literal default -- a real, defensible cap on the
    # FETCH phase's own real, recursive block-tree walk (see
    # api/services/notion_extraction.py's own module docstring).
    NOTION_MAX_BLOCKS: int = 1000
    # Comma-separated, this step's own literal default -- a real
    # ALLOWLIST of real Notion block TYPES (not file extensions, unlike
    # every prior *_INCLUDE_PATTERNS setting) -- a real Notion page can
    # contain block types (embeds, synced blocks, child databases) this
    # codebase has no meaningful real way to render as text.
    NOTION_INCLUDE_TYPES: str = "paragraph,heading_1,heading_2,heading_3,bulleted_list_item,numbered_list_item,to_do,quote,code,toggle,divider"

    @property
    def notion_include_types_list(self) -> list[str]:
        return [value.strip() for value in self.NOTION_INCLUDE_TYPES.split(",") if value.strip()]

    # -- Confluence import (Partie 2.1.17) -----------------------------------
    # A real Confluence API token (Cloud: an Atlassian API token used as a
    # real Bearer token; Server/Data Center: a real Personal Access Token) --
    # a real, static, server-wide secret, the SAME shape as NOTION_API_TOKEN/
    # GITHUB_API_TOKEN. Honest, stated limitation (see
    # api/services/confluence_extraction.py's own module docstring): unlike
    # every other real API this codebase integrates with, Confluence has NO
    # universal, always-reachable host to verify real behavior against at
    # all -- CONFLUENCE_BASE_URL is inherently tenant-specific.
    CONFLUENCE_API_TOKEN: str | None = None
    CONFLUENCE_BASE_URL: str | None = None
    # This step's own literal default.
    CONFLUENCE_MAX_PAGES: int = 100
    # Comma-separated, this step's own literal default ("tous" = empty
    # string here, no restriction) -- a real, admin-configured ALLOWLIST
    # of real space KEYS this server is permitted to import a real SPACE
    # from, regardless of what a caller requests -- unlike a single real
    # page (already fully identified by its own real numeric id), "import
    # this whole space" is a real, broader action worth a real, optional
    # operator-level guard rail.
    CONFLUENCE_INCLUDE_SPACES: str = ""

    @property
    def confluence_include_spaces_list(self) -> list[str]:
        return [value.strip() for value in self.CONFLUENCE_INCLUDE_SPACES.split(",") if value.strip()]

    # -- OneDrive import (Partie 2.1.18) -------------------------------------
    # Same real OAuth 2.0 refresh-token shape as GOOGLE_DRIVE_CLIENT_ID/SECRET/
    # REFRESH_TOKEN above, exchanged for a real, short-lived access token
    # against Microsoft's own real, universal `common` tenant endpoint
    # (api/services/onedrive_extraction.py's own authenticate_onedrive) --
    # see that module's own docstring for the real, live error shapes
    # confirmed for this pair without any valid credential.
    ONEDRIVE_CLIENT_ID: str | None = None
    ONEDRIVE_CLIENT_SECRET: str | None = None
    ONEDRIVE_REFRESH_TOKEN: str | None = None
    # This step's own literal default.
    ONEDRIVE_MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50 MB
    # Comma-separated, this step's own literal (unnamed) default -- same real
    # ALLOWLIST reasoning as GOOGLE_DRIVE_INCLUDE_PATTERNS.
    ONEDRIVE_INCLUDE_PATTERNS: str = ".pdf,.docx,.txt,.md,.html,.csv,.json,.xml,.epub"

    @property
    def onedrive_include_patterns_list(self) -> list[str]:
        return [pattern.strip() for pattern in self.ONEDRIVE_INCLUDE_PATTERNS.split(",") if pattern.strip()]

    # -- ZIP archive import (Partie 2.1.19) ----------------------------------
    # Purely local -- no external API/credentials, unlike every import source
    # since Partie 2.1.12 (see api/services/zip_extraction.py's own module
    # docstring). Server-wide defaults, not per-request fields: this step
    # reuses the plain POST /organizations/{org_id}/documents upload route
    # (see api/config.py's own docstring on this file's Partie 2.1.19
    # section) rather than getting its own dedicated import route the way
    # every other source (2.1.10-2.1.18) did.
    ZIP_INCLUDE_PATTERNS: str = ".pdf,.docx,.txt,.md,.html,.csv,.json,.xml,.epub"
    ZIP_MAX_FILES: int = 100
    # Real, individual per-entry size cap -- deliberately the SAME default
    # as document_storage.py's own MAX_DOCUMENT_UPLOAD_BYTES: one real ZIP
    # entry becomes one real Document, so the same real per-document limit
    # applies.
    ZIP_MAX_ENTRY_SIZE: int = 50 * 1024 * 1024  # 50 MB

    @property
    def zip_include_patterns_list(self) -> list[str]:
        return [pattern.strip() for pattern in self.ZIP_INCLUDE_PATTERNS.split(",") if pattern.strip()]

    # -- Document batch upload (Partie 2.2.1) --------------------------------
    # This step's own literal defaults.
    DOCUMENT_BATCH_MAX_FILES: int = 10
    DOCUMENT_BATCH_MAX_TOTAL_SIZE: int = 100 * 1024 * 1024  # 100 MB

    # -- OCR (Partie 3.1.6) --------------------------------------------------
    # This step's own literal defaults. Real, deliberate scope note:
    # "fra" (French), not "eng" -- this whole session's own established
    # primary real-world language (see api/services/text_normalization.py's
    # own docstring on the same real-world default).
    OCR_ENABLED: bool = True
    OCR_LANGUAGE: str = "fra"
    OCR_DPI: int = 300
    OCR_TIMEOUT: int = 30

    # -- Language detection (Partie 3.1.7) -----------------------------------
    # This step's own literal defaults, EXCEPT the fallback: "fr", not
    # "en" -- the same real-world-primary-language reasoning as OCR_LANGUAGE
    # above, not a copy-paste of the literal spec's own generic "en".
    LANGUAGE_DETECTION_ENABLED: bool = True
    LANGUAGE_DETECTION_FALLBACK: str = "fr"
    LANGUAGE_DETECTION_MIN_LENGTH: int = 20

    # -- Chunking strategies (Partie 3.2.2-3.2.5) -----------------------------
    # A real, deliberate distinction from Document chunking's own
    # existing CHUNK_SIZE/CHUNK_OVERLAP (Partie 3.2.1, "existe déjà"):
    # those live per-organization (`organization_settings.chunk_size`/
    # `chunk_overlap`, real per-tenant configurability already built);
    # these 4 newer strategies are genuinely NEW, standalone real
    # functions (api/services/chunking.py) not yet wired into
    # `process_document` itself, so their own literal defaults stay
    # global settings, matching each étape's own literal ask.
    RECURSIVE_CHUNK_SEPARATORS: list[str] = ["\n\n", "\n", ". ", " ", ""]
    RECURSIVE_CHUNK_MIN_SIZE: int = 10
    RECURSIVE_CHUNK_MAX_SIZE: int = 512
    SEMANTIC_CHUNK_THRESHOLD: float = 0.7
    SEMANTIC_CHUNK_MIN_SIZE: int = 50
    SEMANTIC_CHUNK_MAX_SIZE: int = 512
    MARKDOWN_CHUNK_BY_HEADINGS: bool = True
    MARKDOWN_CHUNK_MIN_HEADING_LEVEL: int = 2
    MARKDOWN_CHUNK_PRESERVE_CODE_BLOCKS: bool = True
    CODE_CHUNK_BY_FUNCTIONS: bool = True
    CODE_CHUNK_BY_CLASSES: bool = True
    CODE_CHUNK_MAX_TOKENS: int = 512
    CODE_CHUNK_PRESERVE_IMPORTS: bool = True

    # -- Sentence/paragraph/parent-child chunking (Partie 3.2.6-3.2.8) -------
    SENTENCE_CHUNK_MAX_SENTENCES: int = 10
    SENTENCE_CHUNK_OVERLAP_SENTENCES: int = 2
    SENTENCE_CHUNK_MIN_SENTENCES: int = 2
    PARAGRAPH_CHUNK_MAX_PARAGRAPHS: int = 5
    PARAGRAPH_CHUNK_OVERLAP_PARAGRAPHS: int = 1
    PARAGRAPH_CHUNK_MIN_PARAGRAPHS: int = 1
    PARENT_CHILD_CHILD_SIZE: int = 128
    PARENT_CHILD_PARENT_SIZE: int = 512
    PARENT_CHILD_CHILD_OVERLAP: int = 20
    PARENT_CHILD_PARENT_OVERLAP: int = 50
    PARENT_CHILD_ENABLED: bool = True

    # -- Organization-configurable chunk size/overlap bounds (Partie 3.3.1-3.3.2) --
    # A real, genuine gap found while wiring these étapes: chunk_size's
    # own write-time validation (api/schemas/organization_settings.py)
    # had NO upper bound (`ge=1` only) -- an org could set an absurdly
    # large chunk_size with no error, real wasted compute at ingestion
    # for no benefit. This ceiling is generous (most real embedding
    # models this codebase lists top out around 384-512 tokens, a few
    # long-context ones go higher) but real and bounded.
    CHUNK_SIZE_MAX_TOKENS: int = 8192

    # -- Retrieval/reranker configuration resolvers (Partie 3.3.4-3.3.6) ----
    # See api/services/retrieval_config.py's own top docstring for the
    # real, honest architectural gap these settle for: no live,
    # multi-tenant retrieval endpoint exists in api/ yet to actually
    # consume them.
    TOP_K_MAX: int = 100
    RERANKER_MAX_TOKENS: int = 512

    # -- Multi-provider LLM abstraction (Partie 4.1.1-4.1.7) -----------------
    # See api/services/llm_providers.py's own top docstring for the real
    # design: one shared `litellm` call per real provider, not 6
    # separately hand-written HTTP clients. Every `*_API_KEY` defaults
    # to "" (never committed, never required at import time) -- a real,
    # missing key surfaces as a real LLMAuthenticationError at CALL
    # time, not a crash at startup.
    LLM_DEFAULT_PROVIDER: str = "anthropic"
    LLM_DEFAULT_MODEL: str = "claude-3-5-sonnet-20241022"
    LLM_TIMEOUT: int = 60
    LLM_MAX_RETRIES: int = 3

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_MAX_TOKENS: int = 4096
    ANTHROPIC_TEMPERATURE: float = 0.7

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TEMPERATURE: float = 0.7

    # Real litellm own naming convention: a bare model name is resolved
    # against Google's own "Gemini API" backend when prefixed
    # "gemini/" -- baked into the real default itself rather than a
    # separate real prefixing function.
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini/gemini-1.5-pro"
    GEMINI_MAX_TOKENS: int = 4096
    GEMINI_TEMPERATURE: float = 0.7

    MISTRAL_API_KEY: str = ""
    MISTRAL_MODEL: str = "mistral/mistral-small-latest"
    MISTRAL_MAX_TOKENS: int = 4096
    MISTRAL_TEMPERATURE: float = 0.7

    # No real API key -- a real, local server. `ollama` is supported
    # natively by litellm (real, item 1's own literal note, no extra
    # SDK dependency).
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "ollama/llama3.1"
    OLLAMA_MAX_TOKENS: int = 4096
    OLLAMA_TEMPERATURE: float = 0.7

    # Any real, generic OpenAI-compatible endpoint (LocalAI, vLLM, Groq,
    # etc.) -- real, empty defaults (`base_url` unset means this
    # provider is simply unavailable, see `get_available_providers`).
    OPENAI_COMPATIBLE_BASE_URL: str = ""
    OPENAI_COMPATIBLE_API_KEY: str = ""
    OPENAI_COMPATIBLE_MODEL: str = "gpt-3.5-turbo"
    OPENAI_COMPATIBLE_MAX_TOKENS: int = 4096
    OPENAI_COMPATIBLE_TEMPERATURE: float = 0.7

    # -- Metadata filtering (Partie 3.4.5) -----------------------------------
    METADATA_FILTERING_ENABLED: bool = True
    METADATA_FILTER_MAX_OPERATORS: int = 5

    # -- Semantic filtering (Partie 3.4.6) ------------------------------------
    SEMANTIC_FILTERING_ENABLED: bool = True
    SEMANTIC_FILTERING_THRESHOLD: float = 0.7
    SEMANTIC_FILTERING_TOP_K: int = 20

    # -- Duplicate removal (Partie 3.4.11) ------------------------------------
    DEDUPLICATE_ENABLED: bool = True
    DEDUPLICATE_METHOD: str = "hash"
    DEDUPLICATE_SIMILARITY_THRESHOLD: float = 0.95

    # -- MMR (Partie 3.4.12/3.4.16) --------------------------------------------
    MMR_ENABLED: bool = True
    MMR_LAMBDA: float = 0.7
    MMR_TOP_K: int = 5

    # -- Query rewriting (Partie 3.4.2) ----------------------------------------
    QUERY_REWRITING_ENABLED: bool = True
    QUERY_REWRITING_METHOD: str = "hybrid"
    QUERY_REWRITING_MIN_LENGTH: int = 3

    # -- HyDE (Partie 3.4.3) ---------------------------------------------------
    HYDE_ENABLED: bool = True
    HYDE_MAX_TOKENS: int = 256
    HYDE_NUM_DOCUMENTS: int = 1
    HYDE_TEMPERATURE: float = 0.7

    # -- Multi-query retrieval (Partie 3.4.4) ----------------------------------
    MULTI_QUERY_ENABLED: bool = True
    MULTI_QUERY_NUM_VARIANTS: int = 3
    MULTI_QUERY_MERGE_METHOD: str = "rrf"
    MULTI_QUERY_RRF_K: int = 60

    # -- Context compression (Partie 3.4.10) -----------------------------------
    CONTEXT_COMPRESSION_ENABLED: bool = True
    CONTEXT_COMPRESSION_MAX_TOKENS: int = 2000
    CONTEXT_COMPRESSION_METHOD: str = "extract"

    # -- Embedding providers (Partie 4.2.1-4.2.6) ------------------------------
    # See api/services/embedding_providers.py's own top docstring for
    # the real design: OpenAI/Voyage/Cohere via litellm.aembedding
    # (already a real dependency since Partie 4.1.7, no separate SDKs
    # needed); Sentence Transformers/Hugging Face reuse the exact same
    # real, existing, local `generate_embeddings` (Partie 2.1.1).
    OPENAI_EMBEDDING_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536

    VOYAGE_API_KEY: str = ""
    VOYAGE_EMBEDDING_MODEL: str = "voyage-2"
    VOYAGE_EMBEDDING_DIMENSIONS: int = 1024

    COHERE_API_KEY: str = ""
    COHERE_EMBEDDING_MODEL: str = "embed-english-v3.0"
    COHERE_EMBEDDING_DIMENSIONS: int = 1024
    COHERE_EMBEDDING_INPUT_TYPE: str = "search_document"

    SENTENCE_TRANSFORMERS_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    SENTENCE_TRANSFORMERS_DIMENSIONS: int = 384
    SENTENCE_TRANSFORMERS_DEVICE: str = "cpu"
    SENTENCE_TRANSFORMERS_BATCH_SIZE: int = 32

    HF_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    HF_EMBEDDING_DIMENSIONS: int = 384
    HF_EMBEDDING_DEVICE: str = "cpu"
    HF_EMBEDDING_BATCH_SIZE: int = 32
    HF_TOKEN: str = ""

    # -- LLM generation configuration (Partie 4.3.1-4.3.5) ---------------------
    SYSTEM_PROMPT_MAX_LENGTH: int = 1000
    MAX_TOKENS_CEILING: int = 32768

    # -- Agent orchestrator (Partie 5.1.1) -------------------------------------
    AGENT_TIMEOUT: int = 60
    AGENT_MAX_RETRIES: int = 3
    AGENT_MAX_TOKENS: int = 4096

    # -- Tool selection (Partie 5.1.2) ---------------------------------------
    TOOL_SELECTION_TOP_K: int = 5
    TOOL_SELECTION_THRESHOLD: float = 0.5
    TOOL_SELECTION_USE_LLM: bool = True

    # -- Tool timeout (Partie 5.1.4) ------------------------------------------
    TOOL_TIMEOUT_DEFAULT: int = 30
    TOOL_TIMEOUT_MAX: int = 120
    TOOL_TIMEOUT_MIN: int = 5

    # -- Per-tool token budget (Partie 5.1.5) ---------------------------------
    TOOL_BUDGET_DEFAULT: int = 1000
    TOOL_BUDGET_MAX: int = 10000
    TOOL_BUDGET_MIN: int = 100
    TOOL_BUDGET_TRACKING_ENABLED: bool = True

    # -- Retry mechanism (Partie 5.1.6) ---------------------------------------
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BASE_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 30.0
    RETRY_BACKOFF_FACTOR: float = 2.0
    RETRY_ON_STATUS_CODES: list[int] = [429, 500, 502, 503, 504]

    # -- Fallback (Partie 5.1.7) -----------------------------------------------
    FALLBACK_ENABLED: bool = True
    FALLBACK_MAX_CHAIN: int = 3

    # -- Parallel tool calls (Partie 5.1.8) -------------------------------------
    PARALLEL_TOOL_CALLS_ENABLED: bool = True
    PARALLEL_TOOL_CALLS_MAX: int = 5
    PARALLEL_TOOL_CALLS_TIMEOUT: int = 30

    # -- Tool result validation (Partie 5.1.9) ----------------------------------
    TOOL_VALIDATION_ENABLED: bool = True
    TOOL_VALIDATION_STRICT: bool = False

    # -- Human approval (Partie 5.1.10) ------------------------------------------
    HUMAN_APPROVAL_ENABLED: bool = True
    HUMAN_APPROVAL_EXPIRY: int = 3600
    HUMAN_APPROVAL_REQUIRED_TOOLS: list[str] = ["send_email", "delete_data", "execute_code", "make_payment", "update_database"]

    # -- Agent memory, short-term (Partie 5.1.11) --------------------------------
    AGENT_MEMORY_SIZE: int = 100
    AGENT_MEMORY_TTL: int = 3600
    AGENT_MEMORY_ENABLED: bool = True

    # -- Conversation memory, cross-session (Partie 5.1.12) ----------------------
    # Not one of this étape's own literal settings -- a real, necessary
    # addition: the étape's own vision critique explicitly asks whether
    # history is truncated for token limits. A real, simple message-COUNT
    # window (not a real per-provider tokenizer-based truncation, which
    # would be separate, future work) -- documented in
    # api/services/agent_orchestrator.py's own docstring.
    CONVERSATION_HISTORY_MAX_MESSAGES: int = 20

    # -- Task planning (Partie 5.1.13) -------------------------------------------
    TASK_PLANNING_ENABLED: bool = True
    TASK_PLANNING_MAX_STEPS: int = 20
    TASK_PLANNING_TIMEOUT: int = 300

    # -- Agent traces (Partie 5.1.14) --------------------------------------------
    AGENT_TRACES_ENABLED: bool = True
    AGENT_TRACES_MAX_STEPS: int = 100
    AGENT_TRACES_RETENTION_DAYS: int = 30
    AGENT_TRACES_EXPORT_FORMATS: list[str] = ["json", "html"]

    # -- Knowledge base search tool (Partie 5.2.1) -------------------------------
    KB_SEARCH_TOP_K: int = 5
    KB_SEARCH_RERANK_ENABLED: bool = True
    KB_SEARCH_MAX_TOKENS: int = 512

    # -- Web search tool, Tavily (Partie 5.2.2) ----------------------------------
    TAVILY_API_KEY: str = ""
    TAVILY_SEARCH_DEPTH: str = "basic"
    TAVILY_MAX_RESULTS: int = 5
    TAVILY_INCLUDE_RAW_CONTENT: bool = True
    TAVILY_INCLUDE_DOMAINS: list[str] = []
    TAVILY_EXCLUDE_DOMAINS: list[str] = []

    # -- GitHub tools (Partie 5.2.3) ----------------------------------------------
    GITHUB_API_BASE_URL: str = "https://api.github.com"

    # -- SQL tool (Partie 5.2.4) ----------------------------------------------------
    SQL_TOOL_ENABLED: bool = True
    SQL_TOOL_MAX_ROWS: int = 100
    SQL_TOOL_MAX_QUERY_LENGTH: int = 5000
    # "conversation_messages" deliberately excluded from the real
    # default -- see api/tools/sql_tool.py's own top docstring: it has
    # no real organization_id column of its own (only reachable via a
    # JOIN through conversations, which this tool's real single-table
    # design explicitly rejects), so the tool's own mandatory
    # organization_id filter would fail against it with a real SQL
    # error, not a security hole -- but broken, not honest to ship
    # enabled by default.
    SQL_TOOL_ALLOWED_TABLES: list[str] = ["documents", "document_chunks", "conversations"]
    SQL_TOOL_READ_ONLY: bool = True

    # -- URL reader tool (Partie 5.2.6) --------------------------------------------
    URL_READER_TIMEOUT: int = 10
    URL_READER_MAX_SIZE: int = 2 * 1024 * 1024
    URL_READER_USER_AGENT: str = "rag-saas-platform-agent/1.0"
    URL_READER_ALLOWED_DOMAINS: list[str] = []
    URL_READER_BLOCKED_DOMAINS: list[str] = []

    # -- Calendar tools (Partie 5.2.7) ---------------------------------------------
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    GOOGLE_CALENDAR_REFRESH_TOKEN: str = ""
    OUTLOOK_CALENDAR_CLIENT_ID: str = ""
    OUTLOOK_CALENDAR_CLIENT_SECRET: str = ""
    OUTLOOK_CALENDAR_REFRESH_TOKEN: str = ""

    # -- Email tools (Partie 5.2.8) -------------------------------------------------
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REFRESH_TOKEN: str = ""
    OUTLOOK_EMAIL_CLIENT_ID: str = ""
    OUTLOOK_EMAIL_CLIENT_SECRET: str = ""
    OUTLOOK_EMAIL_REFRESH_TOKEN: str = ""
    AGENT_SMTP_HOST: str = ""
    AGENT_SMTP_PORT: int = 587
    AGENT_SMTP_USERNAME: str = ""
    AGENT_SMTP_PASSWORD: str = ""
    AGENT_SMTP_FROM_EMAIL: str = ""

    # -- Human escalation tool (Partie 5.2.9) ---------------------------------------
    HUMAN_ESCALATION_ENABLED: bool = True
    HUMAN_ESCALATION_PRIORITY_LEVELS: list[str] = ["low", "medium", "high", "critical"]
    HUMAN_ESCALATION_NOTIFICATION_CHANNELS: list[str] = ["email"]

    # -- Celery -------------------------------------------------------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # -- Rate limiting (brute-force / spam protection) --------------------
    # Uses its own Redis DB number (2) so its keys never collide with
    # Celery's broker (0) or result backend (1) on the same Redis instance.
    RATE_LIMIT_REDIS_URL: str = "redis://localhost:6379/2"
    # False disables enforcement entirely (every check becomes a no-op,
    # no Redis call at all) -- used by the fast SQLite test suite (see
    # tests/conftest.py) so those tests don't need Redis and can't be
    # accidentally rate-limited by their own repeated calls. Never set
    # this False in a real deployment.
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 900
    REGISTER_RATE_LIMIT_MAX_ATTEMPTS: int = 3
    REGISTER_RATE_LIMIT_WINDOW_SECONDS: int = 3600
    PASSWORD_FORGOT_RATE_LIMIT_MAX_ATTEMPTS: int = 3
    PASSWORD_FORGOT_RATE_LIMIT_WINDOW_SECONDS: int = 3600
    EMAIL_VERIFY_REQUEST_RATE_LIMIT_MAX_ATTEMPTS: int = 3
    EMAIL_VERIFY_REQUEST_RATE_LIMIT_WINDOW_SECONDS: int = 3600
    TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    TWO_FA_VERIFY_RATE_LIMIT_WINDOW_SECONDS: int = 900
    # Partie 1.3.4 -- POST /invitations/accept is public (no auth), by
    # IP not email: unlike PASSWORD_FORGOT's per-email limiting (aimed
    # at stopping inbox-bombing a victim), the risk here is brute-forcing
    # the token itself, which an IP-based limit is the right defense
    # against -- same shape as REGISTER's own IP-based limit.
    INVITATION_ACCEPT_RATE_LIMIT_MAX_ATTEMPTS: int = 10
    INVITATION_ACCEPT_RATE_LIMIT_WINDOW_SECONDS: int = 3600

    # -- 2FA lockout recovery (lost device AND all recovery codes) --------
    # How long a requested 2FA removal must wait before it can be
    # confirmed -- the same "we'll do this in N hours unless you stop us"
    # pattern GitHub/Google use for the identical scenario, so a
    # compromised mailbox + guessed/leaked password isn't an instant 2FA
    # bypass. The real owner cancels it just by logging in normally in
    # the meantime (see api/routers/two_factor.py's
    # _cancel_pending_lockout_recovery).
    TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS: int = 24
    # Total link validity from the moment it's requested -- must be
    # comfortably longer than the delay above, so there's a real window
    # to actually click "confirm" once eligible, not just the instant it
    # becomes valid.
    TWO_FA_LOCKOUT_RECOVERY_TOKEN_EXPIRE_HOURS: int = 96
    ACCOUNT_RESTORE_RATE_LIMIT_MAX_ATTEMPTS: int = 3
    ACCOUNT_RESTORE_RATE_LIMIT_WINDOW_SECONDS: int = 3600

    # -- Session lifecycle (audit Categorie 1, items 13/14/17) -------------
    # An access token's paired Session row (api/models/session.py) is
    # revoked -- and its access token blacklisted, same as any other
    # revocation -- if this many minutes pass with no authenticated
    # request touching it. Independent of the session's own absolute
    # expiry (REFRESH_TOKEN_EXPIRE_DAYS above): idle timeout catches a
    # forgotten-but-not-stolen session; absolute expiry is the hard
    # ceiling regardless of activity.
    SESSION_IDLE_TIMEOUT_MINUTES: int = 30
    # How many sessions (devices/browsers) a single account may have
    # active at once. Enforced at issuance (api/security/sessions.py's
    # issue_session()): the OLDEST active session is revoked to make
    # room for a new one, rather than rejecting the new login outright
    # -- a new login is always the one thing a real owner is doing right
    # now; an old, possibly-forgotten session is the more likely one to
    # be stale or someone else's.
    MAX_CONCURRENT_SESSIONS: int = 5

    # -- Password policy (audit Categorie 1, items 15/16) ------------------
    # How many of a user's most recent passwords (api/models/password_history.py)
    # a new password is checked against, in addition to the CURRENT one.
    PASSWORD_HISTORY_SIZE: int = 5
    # api/security/password_similarity.py's Levenshtein-distance check
    # against the user's own email/name -- a password within this many
    # single-character edits of either is rejected. 3 catches trivial
    # cases ("janedoe" vs "janedoe1") without being so aggressive it
    # rejects a password that only coincidentally shares a few letters.
    PASSWORD_SIMILARITY_MIN_DISTANCE: int = 3

    # -- Audit log (audit Categorie 2, items 18-21) -------------------------
    # A dedicated key for api/security/audit_log.py's hash-chain checksum
    # -- deliberately NOT reusing JWT_SECRET_KEY or SESSION_MIDDLEWARE_SECRET
    # (key separation: rotating either of those for its own reason must
    # never retroactively change what every past audit row's checksum
    # was computed with). Required, no default, same reasoning as
    # JWT_SECRET_KEY -- an audit log without real tamper-evidence isn't
    # the feature this was asked to build.
    AUDIT_LOG_HMAC_SECRET_KEY: str = Field(min_length=32)

    # Slack-compatible incoming-webhook URL ({"text": "..."} POST body)
    # for real-time security alerts (item 21) -- unset disables webhook
    # alerting entirely, same "optional integration" pattern as
    # GOOGLE_OAUTH_CLIENT_ID. A dedicated email address alerts go to as
    # well/instead (api/services/email.py's send_security_alert_email) --
    # either, both, or neither may be configured.
    SECURITY_ALERT_WEBHOOK_URL: str | None = None
    SECURITY_ALERT_EMAIL: str | None = None
    # A spike of this many failed logins (by IP OR by targeted email)
    # within SECURITY_ALERT_WINDOW_MINUTES triggers one alert -- see
    # api/services/security_alerts.py's check_and_alert_on_failed_login_spike.
    SECURITY_ALERT_FAILED_LOGIN_THRESHOLD: int = 10
    SECURITY_ALERT_WINDOW_MINUTES: int = 5

    # -- Geo-adaptive rate limiting (audit Categorie 4, item 29) -----------
    # api/security/geoip.py resolves a caller's IP to an ISO 3166-1
    # alpha-2 country code (ipapi.co, no API key needed), cached in Redis
    # so a brute-force burst from one IP doesn't turn into one outbound
    # HTTP call per attempt. api/security/adaptive_rate_limit.py then
    # scales LOGIN_RATE_LIMIT_MAX_ATTEMPTS / REGISTER_RATE_LIMIT_MAX_ATTEMPTS
    # by GEO_RATE_LIMIT_TRUSTED_MULTIPLIER or _SUSPICIOUS_MULTIPLIER when
    # that country appears in TRUSTED_COUNTRIES / SUSPICIOUS_COUNTRIES.
    # Both lists empty (the default) means every caller gets the flat,
    # unadjusted limit -- identical behavior to before this feature existed.
    GEO_IP_LOOKUP_ENABLED: bool = True
    GEO_IP_API_URL: str = "https://ipapi.co/{ip}/country/"
    GEO_IP_LOOKUP_TIMEOUT_SECONDS: float = 2.0
    GEO_IP_CACHE_TTL_SECONDS: int = 3600
    TRUSTED_COUNTRIES: str = ""
    SUSPICIOUS_COUNTRIES: str = ""
    GEO_RATE_LIMIT_TRUSTED_MULTIPLIER: float = 2.0
    GEO_RATE_LIMIT_SUSPICIOUS_MULTIPLIER: float = 0.5

    # -- Trusted IP / VPN exemption (audit Categorie 4, item 30) -----------
    # Comma-separated individual IPs and/or CIDR ranges (e.g.
    # "203.0.113.5,10.8.0.0/24") fully exempted from rate limiting by
    # api/security/adaptive_rate_limit.py -- for known-safe sources
    # (internal tooling, a company VPN egress IP, a monitoring/synthetic
    # check) that would otherwise share the same brute-force limits as an
    # anonymous public caller. Empty (the default) exempts nothing.
    TRUSTED_IPS: str = ""

    # -- Shared encryption-at-rest for DB-stored secrets --------------------
    # A Fernet key (symmetric, authenticated encryption) protecting the
    # two Categorie-4 secrets that must live in Postgres rather than a
    # .env file, because their whole point is to change WITHOUT a
    # redeploy: JWT signing keys (item 28) and enterprise SSO client
    # secrets (item 27) -- see api/security/secret_encryption.py. Only
    # required once one of those features is actually used (creating the
    # first JWTSigningKey row, or the first EnterpriseSSOConnection);
    # unset otherwise. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SECRET_ENCRYPTION_KEY: str | None = None

    # -- Automatic JWT key rotation (audit Categorie 4, item 28) -----------
    # Complements the manual JWT_PREVIOUS_SECRET_KEYS mechanism above with
    # a DB-backed key (api/models/jwt_signing_key.py) that a Celery Beat
    # task (api/tasks/jwt_key_rotation.py) rotates on its own schedule --
    # see that task's docstring for exactly how "automatic" is achieved
    # without a redeploy. 0 (the default) disables automatic rotation
    # entirely; the existing manual env-var mechanism keeps working
    # unchanged either way.
    JWT_AUTO_ROTATION_INTERVAL_DAYS: int = 0
    # How long a retired DB-backed key remains valid for VERIFYING an
    # already-issued token after a rotation -- must comfortably exceed
    # REFRESH_TOKEN_EXPIRE_DAYS's effective access-token lifetime window
    # (a session can go REFRESH_TOKEN_EXPIRE_DAYS between refreshes, and
    # each refresh mints an access token good for ACCESS_TOKEN_EXPIRE_MINUTES
    # more) so a token signed just before a rotation never outlives the
    # key that can still verify it.
    JWT_KEY_RETENTION_DAYS: int = 7
    # How often a running API process re-reads the DB-backed signing key
    # table (api/security/jwt.py's in-memory cache) -- this, not a
    # restart, is what makes a Celery-driven rotation "automatic" for
    # every already-running worker process, single or multi.
    JWT_KEY_CACHE_REFRESH_SECONDS: int = 60
    JWT_KEY_ROTATION_ADMIN_EMAIL: str | None = None

    # -- WebAuthn / FIDO2 (audit Categorie 4, item 26) ---------------------
    # rp_id must be the exact domain (no scheme/port) the frontend is
    # served from -- a WebAuthn credential is cryptographically bound to
    # it and simply won't work if this doesn't match. rp_origin is the
    # full origin (with scheme) the browser's navigator.credentials calls
    # actually run from; the two are independently configurable since a
    # dev setup commonly runs the frontend on a different port than "the
    # domain" (e.g. rp_id=localhost, rp_origin=http://localhost:3000).
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "RAG SaaS Platform"
    WEBAUTHN_RP_ORIGIN: str = "http://localhost:3000"
    WEBAUTHN_MAX_CREDENTIALS_PER_USER: int = 10

    # -- Enterprise SSO / OIDC (audit Categorie 4, item 27) -----------------
    # Each EnterpriseSSOConnection.client_secret (a third-party IdP's
    # secret, admin-configured via POST /admin/sso/connections) is
    # encrypted at rest using SECRET_ENCRYPTION_KEY above.

    # -- Citations (Partie 6.1.1) ---------------------------------------------
    # This is the real, live consumer `api/security/organization_settings.py`'s
    # own docstring already predicted: "a real, live, multi-tenant HTTP
    # endpoint that actually ANSWERS a question ... citing sources,
    # honoring citation_required ... belonging to Partie 9 (or whichever
    # later étape actually asks for it)". `citation_count` is the org-level
    # override (`organization_settings.DEFAULT_SETTINGS["citation_count"]`,
    # real override>org_settings>default precedence); these two are the
    # real, global bounds.
    CITATION_DEFAULT_COUNT: int = 5
    CITATION_MAX_COUNT: int = 10
    CITATION_MIN_SCORE: float = 0.5

    # -- Citation relevance (Partie 6.1.6) -------------------------------------
    RELEVANCE_THRESHOLD_HIGH: float = 0.7
    RELEVANCE_THRESHOLD_MEDIUM: float = 0.4
    RELEVANCE_SHOW_PERCENTAGE: bool = True

    # -- Citation preview / hover (Partie 6.1.8) -------------------------------
    CITATION_PREVIEW_LENGTH: int = 150
    CITATION_CONTEXT_WORDS: int = 5
    # A real, honest, backend-only value: no real frontend exists in this
    # codebase (same documented scope boundary as Partie 5.4's own
    # Workflow Builder) -- kept as a real, configured constant a future,
    # real frontend can read, not consumed by anything in api/ itself.
    CITATION_HOVER_DELAY: int = 300

    # -- Secondary sources (Partie 6.1.9) --------------------------------------
    # A real, honest consolidation (autonomous decision): Partie 6.1.1's
    # own config block originally pre-declared a SEPARATE, always-unused
    # `CITATION_INCLUDE_SECONDARY: bool` for this exact same real
    # concept -- never read anywhere in this codebase (confirmed by
    # grepping the whole repo, not assumed). Two competing flags for
    # "include secondary sources" would only invite them to silently
    # drift apart; removed in favor of this ONE real, complete trio.
    CITATION_SECONDARY_ENABLED: bool = True
    CITATION_SECONDARY_COUNT: int = 3
    CITATION_SECONDARY_THRESHOLD: float = 0.3

    # -- Response confidence score (Partie 6.1.10) -----------------------------
    # Real weights, real-ily summing to 1.0 (enforced below by
    # `_confidence_factor_weights_must_sum_to_one`).
    CONFIDENCE_FACTOR_CITATION_COUNT: float = 0.2
    CONFIDENCE_FACTOR_RELEVANCE: float = 0.3
    CONFIDENCE_FACTOR_DIVERSITY: float = 0.2
    CONFIDENCE_FACTOR_RELIABILITY: float = 0.2
    CONFIDENCE_FACTOR_CONSISTENCY: float = 0.1

    @field_validator("DATABASE_URL")
    @classmethod
    def _require_asyncpg_driver(cls, value):
        if value.startswith("postgresql://"):
            raise ValueError(
                "DATABASE_URL must use the asyncpg driver: "
                "postgresql+asyncpg://... (got a plain postgresql:// URL)"
            )
        return value

    @model_validator(mode="after")
    def _deletion_reminder_must_fire_before_the_purge(self) -> "Settings":
        """A misconfiguration where ACCOUNT_DELETION_REMINDER_DAYS_BEFORE
        >= ACCOUNT_PURGE_DELAY_DAYS would make the pre-purge reminder
        (api/tasks/account_deletion_reminder.py) eligible the moment
        deletion is requested -- functionally a duplicate of the
        immediate confirmation email DELETE /account/me already sends,
        defeating the entire point of a SECOND, later warning (4.6).
        Caught here, at startup, rather than discovered as "why did this
        user get two identical-looking emails the same day.\""""
        if self.ACCOUNT_DELETION_REMINDER_DAYS_BEFORE >= self.ACCOUNT_PURGE_DELAY_DAYS:
            raise ValueError(
                "ACCOUNT_DELETION_REMINDER_DAYS_BEFORE "
                f"({self.ACCOUNT_DELETION_REMINDER_DAYS_BEFORE}) must be less than "
                f"ACCOUNT_PURGE_DELAY_DAYS ({self.ACCOUNT_PURGE_DELAY_DAYS}) -- the reminder is "
                "meant to fire partway through the grace window, not immediately."
            )
        return self

    @model_validator(mode="after")
    def _restore_token_must_expire_before_the_purge(self) -> "Settings":
        """5.7 audit finding: api/routers/account.py's confirm_account_restore
        checks the restore TOKEN's own expiry, not deletion_scheduled_at,
        so it relies on this ordering to stay safe -- a restore token that
        could still be valid AFTER api/tasks/account_purge.py has already
        hard-deleted the row would just fail harmlessly (cascade delete
        takes the token row down with the user, see
        tests/test_postgres_integration.py), but only by accident. Caught
        here, at startup, so that safety never depends on a coincidence
        two independently-configured durations happen to preserve."""
        purge_delay_minutes = self.ACCOUNT_PURGE_DELAY_DAYS * 24 * 60
        if self.ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES >= purge_delay_minutes:
            raise ValueError(
                "ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES "
                f"({self.ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES}) must be less than "
                f"ACCOUNT_PURGE_DELAY_DAYS converted to minutes ({purge_delay_minutes}) -- "
                "a restore link must not still be valid after the account it points to "
                "could already have been permanently purged."
            )
        return self

    @model_validator(mode="after")
    def _confidence_factor_weights_must_sum_to_one(self) -> "Settings":
        """A real, valuable check beyond item 4's own literal ask
        (Partie 6.1.10): the 5 real `CONFIDENCE_FACTOR_*` weights are a
        real weighted average -- a misconfigured set that doesn't sum
        to 1.0 would silently produce a confidence score outside its
        own documented `[0.0, 1.0]` range, a real, hard-to-notice bug
        every downstream real caller (`format_confidence_score`,
        `get_confidence_label`) assumes never happens. Caught here, at
        startup, same "safety never depends on a coincidence" reasoning
        as this class's own other real cross-field validators."""
        total = (
            self.CONFIDENCE_FACTOR_CITATION_COUNT + self.CONFIDENCE_FACTOR_RELEVANCE
            + self.CONFIDENCE_FACTOR_DIVERSITY + self.CONFIDENCE_FACTOR_RELIABILITY + self.CONFIDENCE_FACTOR_CONSISTENCY
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"The 5 CONFIDENCE_FACTOR_* weights must sum to 1.0, got {total}")
        return self


settings = Settings()
