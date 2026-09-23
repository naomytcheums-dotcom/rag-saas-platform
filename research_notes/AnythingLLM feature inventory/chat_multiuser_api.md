# AnythingLLM: Chat, Multi-User, and API Feature Inventory

## Chat: What are the exact definitions and behavior differences between "chat" mode and "query" mode?

### Takeaway
AnythingLLM workspaces support two chat modes — "Chat" (document context + LLM general knowledge, conversational) and "Query" (document-only, refuses to answer if no relevant context is found, with a configurable similarity threshold). Both are open-source/Community (MIT) features available in all deployment forms.

### Cited Findings
- Chat mode "uses both your documents and the AI's general knowledge," is "more conversational and flexible," and is described as good for brainstorming/exploring topics — [AnythingLLM Docs: Chat Modes](https://docs.anythingllm.com/features/chat-modes)
- Query mode "only uses information from your uploaded documents" and "will tell you if it can't find relevant information," making it best for "accurate, document-based answers" — [AnythingLLM Docs: Chat Modes](https://docs.anythingllm.com/features/chat-modes)
- Query mode "preloads chat context based on the initial query with similar results from documents, avoiding most hallucinations"; if no relevant context is found in Query mode, the system returns a refusal rather than letting the LLM hallucinate — [AnythingLLM Docs: Chat Modes](https://docs.anythingllm.com/features/chat-modes)
- Query mode exposes a "Document similarity threshold" setting (No restriction / Low / Medium / High) that filters retrieved context; this control is not present/relevant for Chat mode — [AnythingLLM Docs: Chat Modes](https://docs.anythingllm.com/features/chat-modes)
- There is a mirror docs domain (docs.useanything.com) serving the same content, suggesting a legacy/alternate domain for the docs site — [Chat Modes (useanything.com mirror)](https://docs.useanything.com/features/chat-modes)
- A tracked bug report shows the embedded/public Chat Widget historically ignored the Query mode setting and always ran in Chat mode, indicating a real product surface where mode enforcement differs between the main app UI and the embed widget — [GitHub Issue #3147](https://github.com/Mintplex-Labs/anything-llm/issues/3147)

### Inferences
- The mode toggle is a workspace-level (not thread-level) setting, since document scoping and similarity threshold are described as workspace-configured RAG behavior.
- Query mode functions similarly to a strict RAG/grounded-QA mode common in enterprise RAG tools, positioning AnythingLLM as flexible for both open-ended assistant use (Chat) and compliance/accuracy-sensitive use (Query).

### Gaps
- Docs do not specify exact context-window sizing math or streaming-behavior differences between modes — [AnythingLLM Docs: Chat Modes](https://docs.anythingllm.com/features/chat-modes) (silent on these specifics).
- Could not confirm whether Query mode's refusal text is customizable/configurable by admins.

## Chat: Is there streaming response support?

### Takeaway
Could not directly confirm current documentation language on streaming; this remains a gap requiring a dedicated docs/GitHub source check beyond what was retrieved in this pass.

### Cited Findings
- No primary source was retrieved in this research pass that explicitly documents streaming response support with a citable URL.

### Gaps
- Streaming support (SSE/websocket-based token streaming in chat responses) was not verified with a primary source in this pass; flag for follow-up against `docs.anythingllm.com` chat-ui page or the GitHub `server/utils/chats` code directly.

## Chat: How is chat history persisted, exported, deleted, and viewed?

### Takeaway
Chat/workspace logs are viewable and exportable (CSV) per-workspace and per-user with sufficient account permissions; admins can disable history viewing instance-wide, which also disables export/delete via the UI. This is a Community/MIT (open-source) feature, present in Docker self-host at minimum.

### Cited Findings
- "You can export chat logs by clicking the export button at the top of the screen once at least 10 chat logs are available. Provided you have the correct account permissions, you can view the chat logs per workspace and per user of your AnythingLLM instance." — [Workspace Chat Logs – AnythingLLM Docs](https://docs.anythingllm.com/features/chat-logs)
- "The workspace chat export as a CSV is used for auditing, review, RLHF, or general filtering and usage analysis, and the CSV exports the message and response." — [Workspace Chat Logs – AnythingLLM Docs](https://docs.anythingllm.com/features/chat-logs)
- "You can disable the frontend ability to view chat history by anyone with an account on the instance or the instance administrator, which blocks any user...from viewing chat history...via the AnythingLLM chat interface and via external embed widgets. However, disabling chat history viewing will impact the ability to export chat histories via the in-app interface as well as the ability to delete chat histories." — [Workspace Chat Logs – AnythingLLM Docs](https://docs.anythingllm.com/features/chat-logs)
- An open GitHub feature request asks for the "Ability to delete messages from conversation history," implying per-message deletion (as opposed to whole-thread/conversation deletion) may be limited or was not yet fully implemented at time of filing — [GitHub Issue #1408](https://github.com/Mintplex-Labs/anything-llm/issues/1408)
- An open GitHub feature/bug issue requests JSONL chat history export as an alternative/addition to CSV, implying CSV was the only export format at the time of filing — [GitHub Issue #341](https://github.com/Mintplex-Labs/anything-llm/issues/341)
- An open GitHub feature request calls for "Improved CSV Chat Exports," implying the existing CSV export has known limitations (format/fidelity) — [GitHub Issue #697](https://github.com/Mintplex-Labs/anything-llm/issues/697)
- A bug report states "Conversations and threads are not erased when requested," a reported defect in delete functionality — [GitHub Issue #3634](https://github.com/Mintplex-Labs/anything-llm/issues/3634)

### Inferences
- Export is CSV-only as the officially supported format as of the docs snapshot retrieved; JSONL/other formats appear to be community requests, not shipped features.
- Deletion of chat history exists at some granularity (workspace/thread level) but user reports suggest reliability issues with delete in some versions/configurations.

### Gaps
- Could not confirm current status (fixed/open) of GitHub Issues #1408, #341, #697, #3634 as of Sept 2026 — these were surfaced via search snippets, not verified against the live issue tracker for closure state.

## Chat: Does AnythingLLM support multiple parallel conversation threads per workspace?

### Takeaway
Yes — Workspaces support multiple independent "threads" (via a `WorkspaceThread` model) that isolate conversation history and thread-scoped document uploads from each other, while workspace-embedded documents remain available across all threads in that workspace. This is a Community/MIT open-source feature.

### Cited Findings
- "Workspaces support multiple independent conversation 'threads' via the WorkspaceThread model, which allows users to maintain different lines of inquiry within the same knowledge base without history overlap." — [DeepWiki: Workspace System, Mintplex-Labs/anything-llm](https://deepwiki.com/Mintplex-Labs/anything-llm/8-workspace-system)
- "Uploaded documents in the chat are workspace and thread scoped, meaning that documents uploaded in one thread will not be available in another chat." — [DeepWiki: Workspace System](https://deepwiki.com/Mintplex-Labs/anything-llm/8-workspace-system)
- "If you want a document to be available in multiple threads, you will need to upload it to the workspace as an embedded document... once embedded, documents work across all your chats in that workspace." — [DeepWiki: Workspace System](https://deepwiki.com/Mintplex-Labs/anything-llm/8-workspace-system)
- "Threads can also be automatically renamed based on content via WorkspaceThread.autoRenameThread." — [DeepWiki: Workspace System](https://deepwiki.com/Mintplex-Labs/anything-llm/8-workspace-system)
- A GitHub bug report titled "Differences in Behavior Between Threads API and Workspace in AnythingLLM" indicates the developer API's thread-based chat endpoints and the main workspace chat endpoint can behave inconsistently, a real API/product-surface discrepancy — [GitHub Issue #2526](https://github.com/Mintplex-Labs/anything-llm/issues/2526)
- A separate GitHub issue on "Managing Conversation Context...Using threadSlug" further confirms threads are addressable via a `threadSlug` identifier in the API — [GitHub Issue #2091](https://github.com/Mintplex-Labs/anything-llm/issues/2091)

### Inferences
- Threads are the mechanism for "multiple parallel conversations" within one workspace; a workspace is the document/knowledge-base container, and threads are the parallel conversation lines within it.
- The API-level thread behavior may lag or diverge from the main UI's thread behavior based on the linked bug report, worth flagging as a known inconsistency rather than a documented distinct behavior.

### Gaps
- Note: DeepWiki is a third-party AI-generated wiki over the GitHub repo, not an official Mintplex Labs source — treat as secondary/aggregator-quality; corroborated partially by GitHub issues referencing `threadSlug`, but the official docs page specifically describing thread mechanics was not directly fetched in this pass.

## Chat: Is there pinning of documents into context, or explicit context-window controls?

### Takeaway
Yes — AnythingLLM supports "pinning" a document so its full text (not chunked/embedded-search-retrieved) is injected into every prompt in that workspace, intended for documents that are small enough to fit context or are mission-critical. This is a Community/MIT open-source feature.

### Cited Findings
- "Document pinning should be reserved for documents that can either fully fit in the context window or are extremely critical for the use-case of that workspace. Click the pin icon next to any document to bypass chunking entirely — the full text is injected into every prompt (as long as it fits the context window)." — [search-derived summary citing AnythingLLM docs, per WebSearch result]
- A GitHub feature-request/discussion, "Summarize larger documents: PIN oder Summarize Document Agent?", implies pinning is one of (at least) two competing strategies for getting full-document content to the LLM, the other being an agent-based "Summarize Document" skill — [GitHub Issue #2565](https://github.com/Mintplex-Labs/anything-llm/issues/2565)
- A feature request, "Automatically pin documents that have been found based on vector search for improved RAG," implies pinning today is a fully manual, per-document toggle rather than automatic/dynamic — [GitHub Issue #3587](https://github.com/Mintplex-Labs/anything-llm/issues/3587)
- The original feature request for the capability is tracked as "[FEAT]: Document Pinning" — [GitHub Issue #729](https://github.com/Mintplex-Labs/anything-llm/issues/729)
- Separately, a document similarity threshold (No restriction/Low/Medium/High) in Query mode acts as an explicit context-relevance control — [AnythingLLM Docs: Chat Modes](https://docs.anythingllm.com/features/chat-modes)

### Inferences
- Pinning is effectively a manual override of the RAG chunk-retrieval pipeline for context inclusion, distinct from the similarity-threshold control which governs automatic retrieval quality/strictness.

### Gaps
- Could not fetch the exact current docs page for document pinning directly (only search-engine-summarized text was retrieved, not a direct WebFetch of the original docs URL) — flagged for verification against `docs.anythingllm.com/chatting-with-documents/*` pages directly.

## Chat: Is there text-to-speech / voice input support?

### Takeaway
Yes, both are supported and open-source/Community (MIT) — TTS offers 5 provider options (System Native, Browser-based, Piper local, OpenAI, ElevenLabs), and voice-to-text prompt input is supported, but voice input is explicitly NOT available on the Desktop app.

### Cited Findings
- "AnythingLLM supports multiple text to speech providers so chat responses can be read out loud. Once a provider is configured, click the speaker icon under any chat response to hear it spoken." — [Text to Speech (TTS) – AnythingLLM Docs](https://docs.anythingllm.com/features/text-to-speech)
- TTS provider options: **System Native** (default, no config needed), **Browser-Based** (uses browser's built-in speech synthesis, nothing sent externally), **Piper** (runs open-source Piper voice models locally in-browser, voice model downloaded once, all audio generated privately on-device), **OpenAI** (requires OpenAI API key + voice selection e.g. "nova"), **ElevenLabs** (requires ElevenLabs API key, voices from user's ElevenLabs account) — [Text to Speech (TTS) – AnythingLLM Docs](https://docs.anythingllm.com/features/text-to-speech)
- "Enable voice-to-text inputs for your LLM prompts. This feature is not available on Desktop." — [Text to Speech (TTS) – AnythingLLM Docs](https://docs.anythingllm.com/features/text-to-speech)
- Configuration path: Settings → Voice & Speech → Text-to-speech Preference → choose Provider → Save changes — [Text to Speech (TTS) – AnythingLLM Docs](https://docs.anythingllm.com/features/text-to-speech)
- A GitHub feature request from earlier in the project's history asked to "Add speech-to-text prompting possibility activated with a key combination," suggesting STT was added as a response to community demand (dated request, now apparently implemented per the docs page above) — [GitHub Issue #1603](https://github.com/Mintplex-Labs/anything-llm/issues/1603)
- A GitHub feature request "[FEAT]: Add TTS + STT from AnythingLLM to the embed widget" indicates that, as of that request, TTS/STT in the public embed widget (as opposed to the main app) was a gap/desired addition — [GitHub Issue #4070](https://github.com/Mintplex-Labs/anything-llm/issues/4070)

### Inferences
- TTS/STT are Community-tier (no paid gating language found); OpenAI/ElevenLabs options require the user's own paid API keys but the AnythingLLM feature itself is free/open-source.
- Voice input's absence on Desktop is a concrete, verified self-host-vs-desktop distinction.

### Gaps
- Could not confirm whether TTS/STT in the embed widget (as opposed to main chat UI) has since shipped — Issue #4070 date/status not verified as open or closed as of Sept 2026.

## Chat: Is there regeneration/editing of messages and thumbs up/down feedback?

### Takeaway
Yes — all three are Community/MIT open-source features in the chat UI: Regenerate (resend same prompt+history for a new answer), Edit (amend a past message, auto-resubmits and truncates all subsequent messages), and Feedback (thumbs up/down, purely qualitative, no effect on model behavior — intended for later export/RLHF-style review).

### Cited Findings
- "Regenerate: Resend a prompt back to the LLM with the same prompt and history to get a new answer." — [AnythingLLM Docs: chat-ui](https://docs.anythingllm.com/chat-ui)
- "Edit: Editing a message allows you to amend and automatically resubmit the conversation from that point to the LLM. Beware that this will truncate all messages below the edited content." — [AnythingLLM Docs: chat-ui](https://docs.anythingllm.com/chat-ui)
- "Feedback (Thumbs Up & Thumbs Down): Allow the user to leave qualitative feedback on an LLM response. Leaving feedback has no impact on message history or future responses." — [AnythingLLM Docs: chat-ui](https://docs.anythingllm.com/chat-ui)
- "Feedback metrics are most useful for exporting of chats to be able to sort through good responses for creating fine-tunes outside of AnythingLLM." — [AnythingLLM Docs: chat-ui](https://docs.anythingllm.com/chat-ui)
- The chat UI also includes Copy and Speak (TTS) actions alongside these — [AnythingLLM Docs: chat-ui](https://docs.anythingllm.com/chat-ui)
- A GitHub feature request "[FEAT]: Edit chat interaction" (Issue #1357) exists in the tracker; given the docs above already describe an Edit feature, this issue may predate the shipped feature, request an enhancement to it, or reflect a still-open refinement — status not confirmed — [GitHub Issue #1357](https://github.com/Mintplex-Labs/anything-llm/issues/1357)

### Inferences
- These are standard consumer-chat-app affordances now built into the OSS core, not paid/hosted-only differentiators.

### Gaps
- Could not confirm whether "Edit" creates a true branching conversation tree (keeping the old branch) or is strictly destructive (as "truncate" wording implies) — docs say truncation, so branching is likely NOT supported, but this should be flagged as inferred rather than explicitly confirmed as absent.

## Multi-user: What are the exact role names and permissions?

### Takeaway
AnythingLLM's multi-user mode (Community/MIT, open-source) defines exactly three roles — **Admin**, **Manager**, and **Default** — with Admin having full system control, Manager having broad workspace/user management but no system-level (LLM/Embedder/Vector DB/API key) config access, and Default limited strictly to explicitly-assigned workspaces with no settings access. A live GitHub issue indicates the Manager role's scope is considered too broad by the community/maintainers and is under review for reduction.

### Cited Findings
- "AnythingLLM supports multi-user with three roles: Admin, Manager, and Default, though this is available only in the Docker version." — [WebSearch synthesis of AnythingLLM docs](https://docs.useanything.com/features/security-and-access) (see also mirror [docs.anythingllm.com](https://docs.anythingllm.com))
- **Admin**: "Possesses the highest privilege level with 'full access to the entire system' including logs and analytics"; "Created as the default administrator account during multi-user setup" — [AnythingLLM Docs: Security & Access](https://docs.useanything.com/features/security-and-access)
- **Manager**: "Can access all workspaces and manage most properties"; "Restricted from modifying LLM, Embedder, and Vector database configurations" — [AnythingLLM Docs: Security & Access](https://docs.useanything.com/features/security-and-access)
- **Default**: "Most limited role with access restricted to 'workspaces they are explicitly added to'"; "Cannot view or edit system settings or other workspaces" — [AnythingLLM Docs: Security & Access](https://docs.useanything.com/features/security-and-access)
- A live/open GitHub issue titled "[FEAT]: Manager Role Has Excessive Privileges and Requires Scope Reduction" indicates active community/maintainer concern that the Manager role currently has more access than intended and is a candidate for future permission tightening — [GitHub Issue #5857](https://github.com/Mintplex-Labs/anything-llm/issues/5857)
- Earlier feature requests in the tracker history — "[FEAT]: Enhance User Roles to Allow Workspace Creation and Management" (#2700) and "[FEAT]: New user role that can view, create, modify and delete (their own) workspaces" (#797) — show the role system has evolved over time via community requests, implying the current three-role model with Manager's workspace-management powers may be a relatively evolved/later addition rather than present since initial multi-user launch — [GitHub Issue #2700](https://github.com/Mintplex-Labs/anything-llm/issues/2700), [GitHub Issue #797](https://github.com/Mintplex-Labs/anything-llm/issues/797)
- Original multi-user support was tracked as a foundational feature request: "Multi-user support for AnythingLLM instances" — [GitHub Issue #115](https://github.com/Mintplex-Labs/anything-llm/issues/115)

### Inferences
- The role model (Admin > Manager > Default) is a standard three-tier RBAC and is entirely free/OSS — no evidence of a paid tier gating roles.
- Because Issue #5857 is actively discussing scope reduction, the exact Manager permissions boundary should be treated as evolving; documented capabilities (no LLM/Embedder/Vector DB/API key config) reflect the current documented state but may narrow further in future releases.

### Gaps
- Could not verify the precise current-release permission matrix directly against `server/models/user.js` or `server/utils/middleware/*` source in the GitHub repo in this pass (not fetched); the docs page synthesis is the primary source used.
- Exact resolution/current status of Issue #5857 (open vs. resolved, and what changed) as of Sept 2026 was not verified.

## Multi-user: Can specific users/groups be restricted to specific workspaces?

### Takeaway
Yes — this is the defining behavior of the Default role: Default users only see/access workspaces an Admin (or Manager) has explicitly assigned them to. This is a Community/MIT open-source, Docker-only feature.

### Cited Findings
- "The default user role demonstrates workspace-level access restrictions—users only interact with workspaces to which administrators have explicitly granted permission, providing granular control over collaboration boundaries." — [AnythingLLM Docs: Security & Access](https://docs.useanything.com/features/security-and-access)
- "Default: Most limited role with access restricted to 'workspaces they are explicitly added to'" — [AnythingLLM Docs: Security & Access](https://docs.useanything.com/features/security-and-access)

### Inferences
- Access control is per-user assignment to workspaces (an allow-list model), not a separate "groups"/team construct — no evidence of a distinct "group" object was found in this research pass.

### Gaps
- Could not confirm whether AnythingLLM has any concept of user "groups" (as opposed to individual per-user workspace assignment) — no source surfaced this; likely NOT AVAILABLE but not explicitly confirmed absent by an official source.

## Multi-user: How is multi-user mode enabled, and what changes? Is it reversible?

### Takeaway
Multi-user mode is a one-way, permanent toggle enabled from instance Settings → Security, after which an Admin account/password is established and role-based access control activates instance-wide. It is Community/MIT open-source and documented as available in the Docker self-host version.

### Cited Findings
- "AnythingLLM's multi-user mode enables role-based access control across the platform. Once activated, 'you cannot revert back to single-user mode,' making it a permanent switch designed for shared environments." — [AnythingLLM Docs: Security & Access](https://docs.useanything.com/features/security-and-access)
- "Multi-user mode is enabled in Settings under Security. Toggle on 'Multi-User Mode' and set an admin password when prompted." — [WebSearch synthesis of AnythingLLM docs]
- "Admin... Created as the default administrator account during multi-user setup" — [AnythingLLM Docs: Security & Access](https://docs.useanything.com/features/security-and-access)
- A GitHub feature request "[FEAT]: Enable multi-user on boot" (Issue #1870) suggests that, at least historically, multi-user mode could not be pre-configured at container/first-boot time and required a manual post-install toggle — implying no environment-variable/first-run automation for this switch (at least as of that issue's filing) — [GitHub Issue #1870](https://github.com/Mintplex-Labs/anything-llm/issues/1870)

### Inferences
- The permanence of the multi-user switch is a significant operational consideration for anyone piloting AnythingLLM single-user before deciding on multi-tenant rollout — this decision cannot be easily undone via the UI.

### Gaps
- Could not confirm whether reverting multi-user mode is possible via direct database manipulation/support intervention (only that it's not reversible via the standard UI/settings).
- Could not confirm current status of Issue #1870 (whether multi-user-on-boot via env var has since shipped).

## Multi-user: Is there password protection / instance-level auth in single-user mode?

### Takeaway
Yes — single-user AnythingLLM instances support optional password protection that can be toggled on/off or reset by the logged-in administrator at any time; this is Community/MIT open-source.

### Cited Findings
- "Single-user instances support optional password protection. Administrators can 'turn off password protection at any time or reset the password to the instance while logged in.'" — [AnythingLLM Docs: Security & Access](https://docs.useanything.com/features/security-and-access)

### Inferences
- Single-user password protection is a lightweight, single-shared-password gate (not per-user accounts) distinct from the full multi-user RBAC system.

### Gaps
- None significant for this sub-question; the source is direct and explicit.

## Multi-user: Is there SSO support, and is it open-source or paid-only?

### Takeaway
No evidence of native SSO (SAML/OIDC) support was found in official AnythingLLM documentation or the sources retrieved in this research pass; this should be treated as a confirmed gap/likely "not available" in the OSS product as documented, pending direct verification against the GitHub repo's auth middleware.

### Cited Findings
- "The provided documentation contains no information about Single Sign-On (SSO) capabilities. This feature is not discussed in the available security and access documentation." — [AnythingLLM Docs: Security & Access](https://docs.useanything.com/features/security-and-access) (absence noted directly from the official Security & Access page)
- General web search for "AnythingLLM SSO single sign-on OIDC SAML" returned no AnythingLLM-specific results at all — only generic SSO/SAML/OIDC background articles unrelated to the product — [WebSearch results, query: "AnythingLLM SSO single sign-on OIDC SAML"]

### Inferences
- Given AnythingLLM's auth model is described purely in terms of "Admin/Manager/Default" local accounts and a single-user shared password, and no SSO documentation or hosted-cloud SSO marketing was found, SSO is most likely NOT AVAILABLE in the current OSS product, and there is no confirmed evidence of it existing even as a paid/hosted-only add-on.

### Gaps
- This is a genuine gap: no authoritative source (docs, GitHub issue, changelog) confirming or denying SSO/SAML/OIDC support was found. Recommend the report explicitly flag "no SSO found in research; unconfirmed" rather than asserting a hard "not available," since a dedicated GitHub repo search for "SAML" or "OIDC" strings was not performed in this pass (tool-call budget constraint).

## Multi-user: Desktop app vs Docker self-host vs hosted cloud — differences

### Takeaway
Multi-user mode (and by extension role-based access control and workspace-user assignment) is documented as available only in the Docker version; the Desktop app is implied/confirmed single-user in at least one specific respect (voice input is unavailable on Desktop), consistent with Desktop being a local single-user application.

### Cited Findings
- "AnythingLLM supports multi-user with three roles: Admin, Manager, and Default, though this is available only in the Docker version." — [AnythingLLM Docs: Security & Access, via WebSearch synthesis](https://docs.useanything.com/features/security-and-access)
- "Enable voice-to-text inputs for your LLM prompts. This feature is not available on Desktop." — [Text to Speech (TTS) – AnythingLLM Docs](https://docs.anythingllm.com/features/text-to-speech)
- AnythingLLM offers "a mobile application, a browser extension, and an embed widget" in addition to Desktop and Docker/self-host, per general product-overview search results — [WebSearch results, query: "AnythingLLM JS SDK Python SDK anythingllm-sdk npm"]

### Inferences
- The Desktop app is architecturally a single-user local instance and does not carry the Docker deployment's multi-tenant RBAC system — consistent with the report's stated hypothesis that desktop is single-user only.

### Gaps
- Could not directly confirm from an official source whether hosted-cloud AnythingLLM (if a Mintplex-operated cloud/SaaS offering currently exists) has different or additional multi-user/SSO capabilities beyond the self-hosted Docker version — no hosted-cloud-specific pricing/feature page was retrieved in this pass. Flag for follow-up: verify whether Mintplex Labs currently operates a hosted cloud product distinct from self-host Docker/Desktop.

## API: Is there a full REST API, and what does it cover?

### Takeaway
Yes — AnythingLLM ships a full developer REST API (documented via an OpenAPI 3.0 spec with roughly 58 endpoints) covering workspace management, document embedding, and chat, exposed through an interactive Swagger UI at `/api/docs` by default. This is a Community/MIT open-source feature (not paid-gated).

### Cited Findings
- "AnythingLLM offers 'a full developer API that you can use to manage, update, embed, and even chat with your workspaces.'" — [AnythingLLM Docs: API Access & Keys](https://docs.useanything.com/features/api)
- "By default, AnythingLLM exposes the Swagger API documentation at the /api/docs endpoint. The developer API lives at /api/docs (Swagger docs), and you can programmatically manage workspaces, embed documents, and send chat messages." — [WebSearch synthesis of AnythingLLM docs/configuration]
- "AnythingLLM has a well-defined OpenAPI spec at server/swagger/openapi.json (58 endpoints, OpenAPI 3.0)." — [WebSearch synthesis, referencing GitHub repo structure]
- "While this can be useful for development and testing, it is recommended to disable this endpoint in production deployments to prevent exposing your API structure and available endpoints. You can disable it by setting the DISABLE_SWAGGER_DOCS environment variable to 'true'." — [WebSearch synthesis of AnythingLLM Configuration docs](https://docs.anythingllm.com/configuration)
- A GitHub issue "Add comprehensive API reference documentation" (Issue #5288) suggests that, at least as of that filing, the community/maintainers considered the existing API reference documentation incomplete — [GitHub Issue #5288](https://github.com/Mintplex-Labs/anything-llm/issues/5288)
- A separate bug report: "Documentation URL incorrect on remote hosting" (Issue #561) suggests there have been historical issues with the `/api/docs` link resolving correctly on non-default/remote-hosted deployments — [GitHub Issue #561](https://github.com/Mintplex-Labs/anything-llm/issues/561)
- There is a separate official documentation source repo, `Mintplex-Labs/anythingllm-docs`, confirming docs.anythingllm.com content is maintained in a dedicated GitHub repo — [GitHub: Mintplex-Labs/anythingllm-docs](https://github.com/Mintplex-Labs/anythingllm-docs)

### Inferences
- The `/api/docs` Swagger UI being explicitly toggleable via `DISABLE_SWAGGER_DOCS` confirms it remains live/available by default as of current documentation, directly answering the "verify current state" requirement — it is present by default but recommended to disable in production.
- System-settings coverage (e.g., admin/system config endpoints) is plausible given "manage" is listed among API capabilities, but was not independently itemized by any source in this pass — treat granular system-settings API coverage as unconfirmed.

### Gaps
- Could not directly enumerate which specific endpoint categories exist beyond "workspaces, embed documents, chat" (e.g., explicit confirmation of user-management or system-settings endpoints in the API) from a primary source — the 58-endpoint/OpenAPI 3.0 figure came from a search-engine synthesis rather than a directly fetched/verified copy of `server/swagger/openapi.json`; recommend flagging this endpoint count as approximate/unverified.

## API: How is API key management handled?

### Takeaway
API keys are generated within the instance by accounts with sufficient permission, can be created/deleted on demand, and function as full-access bearer credentials to the API; this is a Community/MIT open-source feature. Exact quantity limits and granular scoping were not found and should be treated as a gap.

### Cited Findings
- "Keys are managed by accounts with appropriate access permissions" and users can "create and delete API keys on the fly if you are allowed permission to do so." — [AnythingLLM Docs: API Access & Keys](https://docs.useanything.com/features/api)
- "Anyone with the API key can use the AnythingLLM API, so do not share or publish this key anywhere" — [AnythingLLM Docs: API Access & Keys](https://docs.useanything.com/features/api)

### Inferences
- The "anyone with the key can use the API" phrasing suggests keys are not scoped to a specific workspace or a limited permission subset — i.e., an API key likely grants broad/full API access rather than fine-grained per-resource scoping, though this is an inference, not an explicit statement.

### Gaps
- Maximum number of API keys per account/instance: not found in any retrieved source.
- Whether keys can be scoped to specific workspaces, specific roles, or specific endpoint categories: not found/not confirmed — flag as likely NOT AVAILABLE (full-access-only keys) but unverified.
- Where exactly in the UI keys are generated (e.g., "Settings → API Keys") was described generically as "if you are allowed permission" but the precise settings path/screen name was not captured verbatim from a direct fetch.

## API: Are there official SDKs (JS, Python)?

### Takeaway
No official first-party JS or Python "SDK" package (in the sense of a client library wrapping the REST API) was confirmed; what does exist are an official Node.js-based CLI (`@mintplex-labs/anything-llm-cli`) for terminal chat and a separate "Hub CLI" (`@mintplex-labs/anythingllm-hub-cli`) for creating/uploading custom agent skills. This should be reported as a likely gap/no official SDK, tier: not confirmed as available.

### Cited Findings
- "AnythingLLM is written primarily in Node.js and built in public through an open-source GitHub repo... under the MIT license." — [GitHub: Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm)
- "AnythingLLM CLI - A command-line interface for chatting with your AnythingLLM instance from the terminal... installed via npm and accessed at `@mintplex-labs/anything-llm-cli`." — [npm: @mintplex-labs/anything-llm-cli](https://www.npmjs.com/package/@mintplex-labs/anything-llm-cli)
- "AnythingLLM Hub CLI - Available as `@mintplex-labs/anythingllm-hub-cli` on npm, which provides tools for creating and uploading agent skills." — [npm: @mintplex-labs/anythingllm-hub-cli](https://www.npmjs.com/package/@mintplex-labs/anythingllm-hub-cli)
- "NodeJS programming experience is required to create custom agent skills." — [AnythingLLM Docs: Introduction to custom agent skills](https://docs.anythingllm.com/agent/custom/introduction)
- "The search results don't contain detailed information about a dedicated Python SDK package." — [WebSearch synthesis, query: "AnythingLLM JS SDK Python SDK anythingllm-sdk npm"]

### Inferences
- Because AnythingLLM's API is a documented, standard OpenAPI/Swagger REST API, developers can integrate via any HTTP client or generate a client from the OpenAPI spec, even without an official SDK — but no first-party convenience SDK package (equivalent to, e.g., `openai` Python/JS packages) was confirmed to exist.

### Gaps
- Could not confirm with certainty that zero official SDK exists (only that search did not surface one) — recommend the report state this as "no official SDK found in research" rather than a hard denial, and suggest checking `github.com/Mintplex-Labs` org page directly for any dedicated SDK repos as a follow-up.
