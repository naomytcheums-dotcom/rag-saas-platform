# AnythingLLM: Embedded Widget, Admin, and Deployment Forms

## 1. How is the embeddable chat widget set up and which workspace does it point to?

### Takeaway
The embed widget is a **Docker-only** (self-hosted) feature — not available on Desktop or (per docs) with custom Agents on Cloud. It is created in-app per workspace, generates a unique `data-embed-id`, and is dropped onto any external site via a `<script>` tag pointing at a compiled JS bundle and a backend API URL; every embed is bound to exactly one workspace, from which it inherits chat defaults unless overridden. Tier: **Open-source/Community (MIT)** for the self-hosted/Docker deployment; confirmed unavailable on Desktop.

### Cited Findings
- "The embedded chat widget feature is exclusive to the Docker version of AnythingLLM." — [AnythingLLM Docs: Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- After widget creation, users receive "a link that you can publish on your website using a simple `<script>` tag." — [AnythingLLM Docs: Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- "The workspace setting determin[es] which workspace your chat window will be based on, and all defaults [are] inherited from the selected workspace unless overridden by specific configuration options." — [AnythingLLM Docs: Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- Required script attributes: `data-embed-id` (unique identifier for the embed configuration), `data-base-api-url` (e.g. `http://localhost:3001/api/embed`), and a `src` pointing to the compiled widget script. — [anythingllm-embed README](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/README.md)
- The embed widget submodule is built/developed with `yarn` (`yarn dev` for local dev server, `yarn build` for production bundle) inside the `embed/` directory of the main repo. — [anythingllm-embed README](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/README.md)
- Two chat operating modes are configurable per embed: "Chat" (answers any question) vs. "Query" (restricted to document-grounded answers only). — [AnythingLLM Docs: Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- Multi-user access and the embeddable chat widget are called out as **Docker-only** features, absent from the Desktop app. — [AnythingLLM.com desktop-app description via WebSearch synthesis of docs.anythingllm.com/installation-docker/overview and related pages](https://docs.anythingllm.com/installation-docker/overview)
- Dynamic per-embed overrides exist for LLM model selection, temperature, and system prompt (`data-model`, `data-temperature`, `data-prompt`). — [anythingllm-embed README](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/README.md)

### Inferences
- Because the widget always resolves to one workspace's knowledge base/config, embedding the same widget on multiple sites effectively multiplies access points into that single workspace, which is why domain allow-listing and per-session/day chat caps exist as the primary abuse controls (see below).

### Gaps
- No official visual example/screenshot of the exact embed-creation UI flow (steps to click through in-app) was retrieved; only the resulting configuration surface is documented.
- Could not confirm whether iframe-based embedding (as opposed to script-tag) is fully shipped — docs mark iframe embedding as "work-in-progress." — [anythingllm-embed README](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/README.md)

---

## 2. What customization options does the widget support (branding, position, color, greeting, icon, assistant name)?

### Takeaway
The widget exposes a fairly rich set of `data-*` attributes for visual/behavioral customization — position (4 corners), icon style, hex color theming, custom brand image, greeting text, assistant display name, window sizing, language, and footer/sponsor removal — all configured via the script tag, no paid gate documented. Tier: **Open-source/Community (MIT)**, part of self-hosted Docker.

### Cited Findings
- `data-position`: "Adjusts the positioning of the embed chat widget and open chat button, with default bottom-right and options of bottom-right, bottom-left, top-right, top-left." — [WebSearch summary of AnythingLLM Docs Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- `data-assistant-name`: "Sets the chat assistant name that appears above each chat message." — [WebSearch summary of AnythingLLM Docs Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- `data-no-sponsor` hides the sponsor/attribution footer of the open chat window; `data-no-header` hides the header bar; `data-sponsor-link` / `data-sponsor-text` customize the footer link/text instead of removing it. — [WebSearch summary of AnythingLLM Docs Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- `data-window-height` / `data-window-width`: set chat window dimensions with CSS units (px, %, rem). — [WebSearch summary of AnythingLLM Docs Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- Icon styles are selectable: `plus`, `chatBubble`, `support`, `search`, `magic`; button/bubble colors are set via hex codes; a custom brand image URL can be supplied; custom greeting text and assistant naming are both supported; text sizing is configurable. — [anythingllm-embed README](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/README.md)
- `data-language` sets the widget's interface language (defaults to English); `data-open-on-load` auto-opens the widget on page load; `data-show-thoughts` displays the model's reasoning/thought process; `data-support-email` adds a support contact option. — [anythingllm-embed README](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/README.md)

### Inferences
- The customization surface is entirely declarative (HTML data-attributes), meaning site owners can restyle/rebrand the widget without needing to touch AnythingLLM's own admin UI or rebuild the bundle — but also that there is no separate "widget theme" saved server-side beyond what's baked into the script tag per page.

### Gaps
- A GitHub issue titled "How do I rebrand the embedded chat widget?" (Mintplex-Labs/anything-llm #987) suggests some users find full rebrand (e.g., removing all "AnythingLLM"/"ALLM" mentions) non-trivial or incomplete via documented attributes alone; the issue's resolution/current status was not fetched. — [GitHub issue #987 title, from WebSearch results](https://github.com/Mintplex-Labs/anything-llm/issues/987)

---

## 3. Does the widget support domain allow-listing / restricting where it can be embedded?

### Takeaway
Yes — domain allow-listing is a first-class, admin-configurable feature per embed, defaulting to "open to any origin" unless explicitly restricted, with a server-wide environment variable to flip that default to deny-by-default. Tier: **Open-source/Community (MIT)**.

### Cited Findings
- "Domain Restrictions: An allowlist feature filters requests by domain. Leaving this field empty permits usage from any site." — [AnythingLLM Docs: Chat Widgets, via WebFetch](https://docs.useanything.com/features/chat-widgets)
- "By default, a public chat embed widget created without an allowed-domains allowlist responds to requests from any origin. Setting the `EMBED_REQUIRE_ALLOWLIST` environment variable makes embeds that have no allowlist configured reject all requests (deny-by-default). This is useful for administrators who want to ensure an embed cannot be queried cross-origin until its allowed domains are explicitly set." — [WebSearch summary, sourced to AnythingLLM docs/config content](https://docs.anythingllm.com/configuration)

### Inferences
- The default-open behavior means unconfigured embeds are usable from any page that has the embed ID and API URL — a real exposure risk admins must actively remediate by setting an allowlist or the `EMBED_REQUIRE_ALLOWLIST` env var.

### Gaps
- Exact list of accepted allowlist formats (exact domain vs. wildcard subdomains, protocol-sensitivity) was not directly confirmed from primary docs text.

---

## 4. Does the widget support the same chat features as the main app (streaming, citations)?

### Takeaway
Direct documentation confirming streaming/citations parity for the embed widget could not be retrieved; only indirect evidence exists (e.g., `data-show-thoughts` implies exposure of model reasoning, and "Query" mode implies document-grounded answers, which typically pairs with citations in AnythingLLM's main chat UI). This is a **gap**, not a confirmed claim.

### Cited Findings
- The widget supports a "Query" mode that "restricts responses to document-related inquiries only," implying RAG grounding similar to main-app workspace chat. — [WebSearch summary, AnythingLLM Docs: Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- `data-show-thoughts` "display[s] AI reasoning process to users" in the embed. — [anythingllm-embed README](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/README.md)
- Users in the embed "cannot access context snippets and receive randomized session IDs" — implying the widget deliberately withholds full source/citation detail (context snippets) that the main app chat exposes to logged-in users. — [anythingllm-embed README](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/README.md)

### Inferences
- The explicit statement that embed users "cannot access context snippets" suggests the embed widget's citation/source-document exposure is intentionally reduced compared to the main authenticated app, where citations and source chunks are typically shown.

### Gaps
- No explicit confirmation of token-by-token streaming behavior in the embed widget (vs. main app) was found in the sources retrieved.
- No explicit statement on whether citations (source document references) are rendered in the embed widget UI at all, beyond the "no context snippets" note above.

---

## 5. Is widget usage/analytics tracked, and where is it viewable? Any usage limits or paid-tier gating?

### Takeaway
Usage limits are built in and configurable per embed (max chats/day, max chats/session, both toggleable to unlimited), and these limits are the primary anti-abuse/cost-control mechanism — there is no evidence of a paid-tier gate on the widget itself (it's a Docker/self-hosted MIT feature). Dedicated widget-specific analytics dashboards were not found in sources reviewed; general system-wide Event Logs (see Admin section) are the closest tracked-activity surface.

### Cited Findings
- "Usage Limits: Max chats per day (24-hour period); Max chats per session. Both support unlimited settings when configured to zero." — [WebSearch summary, AnythingLLM Docs: Chat Widgets](https://docs.useanything.com/features/chat-widgets)
- The anythingllm-embed README recommends admins "limit both the number of chats an embedding can process and per-session" to prevent abuse, confirming these limits exist as an operator control rather than a monetization lever. — [anythingllm-embed README](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/README.md)
- Embed widget availability itself is described as Docker-only (i.e., gated by deployment form, not by a paid subscription) — see Section 1 sources.

### Inferences
- Because embed limits are set to zero for "unlimited" and configured per-embed rather than metered against a billing plan, the feature reads as usage-governance (cost/DoS control against the underlying LLM/vector DB), not commercial tier-gating — consistent with the overall MIT/self-hosted nature of the Docker deployment.

### Gaps
- Could not find a dedicated "widget analytics" page/dashboard (e.g., chat volume charts, per-domain breakdown) in the docs retrieved. It's unclear whether widget-originated chats are distinguishable in Event Logs from normal workspace chats — this is unconfirmed.
- No information found on whether AnythingLLM Cloud's paid tiers impose different (stricter/laxer) embed limits than self-hosted Docker, since Cloud's own limitations page did not mention the embed widget specifically.

---

## 6. What system settings are available to admins (LLM preference, embedding preference, vector DB preference, whitelisting, max users, etc.)?

### Takeaway
Admins configure LLM provider, embedding provider, and vector database provider centrally per-instance (all swappable), plus multi-user role-based access (Admin/Manager/Default) and embed-level domain allowlisting; a specific "max users" cap setting was not confirmed to exist. Tier: **Open-source/Community (MIT)** — these are core self-hosted/Docker admin settings.

### Cited Findings
- Supported LLM providers include "OpenAI, Anthropic, Google Gemini, Azure OpenAI, AWS Bedrock, Ollama, LM Studio, and 20+ additional providers including DeepSeek and Groq." — [Mintplex-Labs/anything-llm README](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md)
- Supported vector databases: "LanceDB (default), PGVector, Pinecone, Chroma, Weaviate, Qdrant, and Milvus." — [Mintplex-Labs/anything-llm README](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md)
- Embedding options include native/built-in embedders plus integrations with OpenAI, Cohere, and Voyage AI; speech: PiperTTS and ElevenLabs. — [Mintplex-Labs/anything-llm README](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md)
- "Multi-user mode is designed as a one-way configuration change" — implying admins choose upfront whether to enable multi-user (Admin/Manager/Default roles) since it can't easily be reverted. — [WebSearch summary referencing AnythingLLM docs](https://docs.anythingllm.com/installation-docker/overview)
- The Docker version, unlike Desktop, adds "proper access control with Admin, Manager, and Default roles, plus embeddable chat widgets for websites and white-labeling." — [WebSearch summary of multiple docs/guide sources](https://docs.anythingllm.com/installation-docker/overview)
- Embed-level allowlisting and the `EMBED_REQUIRE_ALLOWLIST` deny-by-default environment variable (see Section 3) function as a domain-restriction admin control specifically for embeds — not evidenced as a general instance-wide domain whitelist for the main app login.

### Inferences
- The Admin/Manager/Default RBAC + embed-only domain-restriction pattern suggests AnythingLLM's "whitelisting" concept is scoped to the embed feature rather than a general instance-access whitelist (e.g., no evidence of restricting main-app login by corporate email domain).

### Gaps
- No documentation found describing a "max users" limit/setting for self-hosted multi-user mode; likely unlimited since it's self-hosted MIT software, but this is not explicitly confirmed either way.
- Full enumeration of "20+ additional [LLM] providers" beyond those named was not retrieved in detail.

---

## 7. Branding/white-label options for admins: app name, logo, favicon, login page — free/open-source or restricted?

### Takeaway
White-labeling (custom logo on login page and throughout the app, custom login welcome messages, custom footer links/icons) is documented as a **Docker-only, self-hosted feature**, appearing to be free/open-source (part of MIT Docker deployment) rather than paid-only — though favicon and full app-name replacement are not explicitly confirmed as configurable.

### Cited Findings
- "Replace the AnythingLLM branded logo that appears on the login page and throughout the app with your own brand's logo." — [AnythingLLM Docs: Customization, via WebFetch](https://docs.useanything.com/features/customization)
- Custom welcome messages: ability to customize the default message shown upon login before workspace selection, "allowing admins to personalize greetings or explain workspace purposes." — [AnythingLLM Docs: Customization](https://docs.useanything.com/features/customization)
- Custom footer links/icons: "The footer icons can be replaced with custom links and icons to provide quick access to relevant resources or web pages." — [AnythingLLM Docs: Customization](https://docs.useanything.com/features/customization)
- "These customization features are exclusively available in AnythingLLM's self-hosted Docker deployment, not in the Desktop or Cloud versions." — [WebFetch synthesis of AnythingLLM Docs: Customization](https://docs.useanything.com/features/customization)
- A closed/older GitHub feature request "[FEAT]: 'White label' possibility" (#1256) and "[FEAT]: Custom login screen icon" (#1432) exist in the Mintplex-Labs/anything-llm issue tracker, indicating community demand and iterative rollout of white-label capability over time. — [GitHub issues #1256 and #1432, titles from WebSearch](https://github.com/Mintplex-Labs/anything-llm/issues/1256)

### Inferences
- Because these customization docs explicitly state Cloud and Desktop are excluded, white-labeling functions as a differentiator that favors the self-hosted/Docker deployment path — somewhat unusual since Cloud is the paid managed option; it suggests Cloud instances currently keep default AnythingLLM branding.

### Gaps
- Favicon customization and full instance "app name" replacement (e.g., browser tab title, not just logo image) were not explicitly confirmed as available or unavailable in the docs retrieved.
- Could not verify current (2026) status of GitHub issues #1256/#1432 (open, closed, or shipped) — titles only were retrieved via search snippet, not the issue bodies/comments.

---

## 8. Usage/event logs — is there an audit log? What's tracked?

### Takeaway
Yes — AnythingLLM has a built-in, always-on, locally-stored Event Logs feature restricted to Admin/Manager roles in multi-user mode, tracking login attempts, messages sent, settings changes, and document uploads. Tier: **Open-source/Community (MIT)**.

### Cited Findings
- Event Logs page "allows users to view and monitor various events that occur within the application, providing insights into user activities and system-related events." Access restricted to "admin or manager roles in multi-user mode." Logs are "always enabled and stored locally," providing "an audit trail of administrative actions and security events." — [WebSearch summary citing docs.anythingllm.com/features/event-logs](https://docs.anythingllm.com/features/event-logs)
- Tracked event types include: "User login attempts (successful and failed)", "Messages sent by users", "Changes made to application settings", "Document uploads." — [AnythingLLM Docs: Event Logs, via WebFetch](https://docs.anythingllm.com/features/event-logs)
- "Each event in the Event Logs page includes relevant information, such as the event type, associated user (if applicable), timestamp, and any additional details specific to the event type." — [AnythingLLM Docs: Event Logs](https://docs.anythingllm.com/features/event-logs)

### Inferences
- "Stored locally" + "always enabled" suggests logs are not shippable to an external SIEM out of the box; export/retention controls, if any, are not documented, which could be a gap for enterprise compliance use cases.

### Gaps
- No retention policy (log rotation/expiry) documented.
- No confirmed export mechanism (CSV/JSON download, API) for Event Logs.
- Could not confirm whether Event Logs distinguish embed-widget-originated chat events from main-app chat events (relevant to Section 5's gap).

---

## 9. Workspace chat exports / data export for admins

### Gaps
No source specifically documenting a workspace chat export or bulk data-export admin feature was retrieved in this research pass (searches focused on event logs and telemetry did not surface an explicit "export chats" or "export workspace data" doc page). This should be flagged to the report writer as unconfirmed rather than assumed absent — AnythingLLM's general document-management features imply data is stored in a local SQLite DB and vector store, which a technically inclined admin could access directly, but no documented one-click "export" admin UI feature was found.

---

## 10. Default telemetry — what's collected, and can it be disabled?

### Takeaway
AnythingLLM collects anonymous telemetry via PostHog by default (self-hosted), explicitly excluding PII, document content, or chat logs, and it can be disabled either via an environment variable or an in-app toggle. AnythingLLM Cloud separately states telemetry is anonymous and user-disable-able through the app UI, alongside account/billing data collected by Stripe. Tier: **Open-source/Community (MIT)** — telemetry-off is a supported, first-class configuration, not a paid feature.

### Cited Findings
- "Set `DISABLE_TELEMETRY` in your server or docker `.env` settings to 'true' to opt out of telemetry." Also "in-app... going to the sidebar > Privacy and disabling telemetry." — [WebSearch summary citing docs.anythingllm.com/features/privacy-and-data-handling](https://docs.anythingllm.com/features/privacy-and-data-handling)
- "The Telemetry provider is PostHog - an open-source telemetry collection service. Collected data is strictly anonymous and contains no Personally Identifiable Information (PII), document content, chat logs, fingerprinting data, or any other sensitive information." — [WebSearch summary citing AnythingLLM privacy/data-handling docs](https://docs.anythingllm.com/features/privacy-and-data-handling)
- "If telemetry is disabled we don't collect anything. However, if you disable telemetry, you would still see outbound connections to the following services [if using]... an external tool, LLM, Embedding models, or Vector databases, you will still see outbound connections to the respective service provider." — [WebSearch summary citing AnythingLLM docs](https://docs.anythingllm.com/features/privacy-and-data-handling)
- AnythingLLM Cloud privacy policy: registration data collected includes "name, email, and organization details," plus "address and credit card information (collected by payment processor Stripe)"; usage data collected with consent; "anonymous telemetry data from instances"; team may access instances "solely for the purposes of debugging, maintenance, and regular customer satisfaction services." "Users have the option to disable telemetry collection through the application user interface." "We do not share, make visible, or disseminate any generated content, uploaded materials, or activity generated on your instance beyond anonymous telemetry data." — [AnythingLLM Docs: Cloud Privacy Policy, via WebFetch](https://docs.anythingllm.com/cloud/privacy-policy)
- An open GitHub issue "[CHORE]: Propagate telemetry disabled setting to third-..." (Mintplex-Labs/anything-llm #4534) suggests the telemetry-disable setting historically did not fully propagate to all third-party integrations/services, indicating a known implementation gap. — [GitHub issue #4534 title, from WebSearch](https://github.com/Mintplex-Labs/anything-llm/issues/4534)

### Inferences
- The existence of issue #4534 implies that as of some point, disabling telemetry in-app or via env var may not have been 100% comprehensive across all third-party service touchpoints — worth flagging as a caveat rather than treating the opt-out as absolute across all subsystems.

### Gaps
- Could not confirm current (2026) resolution status of GitHub issue #4534.
- No granular breakdown of exactly which anonymous metrics/events PostHog captures (e.g., feature-usage counts, session duration) was found beyond the "no PII/content" assurance.

---

## 11. Docker self-host deployment — what's included?

### Takeaway
Docker is the reference/full-featured self-host deployment: multi-user RBAC (Admin/Manager/Default), embeddable chat widgets, white-labeling, and the complete provider matrix (20+ LLMs, 7 vector DBs, external embedders/TTS) — all under the MIT license, free of charge.

### Cited Findings
- "The Docker version is built for teams and servers, adding proper access control with Admin, Manager, and Default roles, plus embeddable chat widgets for websites and white-labeling." — [WebSearch synthesis of docs.anythingllm.com/installation-docker/overview and related pages](https://docs.anythingllm.com/installation-docker/overview)
- "Multi-user access and the embeddable chat widget are Docker-only. The desktop app does not include them. Additionally, agent features require Docker." — [WebSearch synthesis](https://docs.anythingllm.com/installation-docker/overview)
- Repo licensing: "MIT license with active community contribution model." — [Mintplex-Labs/anything-llm README](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md)
- Architecture: "frontend (Vite + React), Node.js backend, document processing collector, and optional browser extension and mobile applications." — [Mintplex-Labs/anything-llm README](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md)
- Also documented: "Container: Docker with bare metal alternative" as a deployment path (i.e., Docker is not strictly mandatory — a non-containerized/bare-metal install is also supported). — [Mintplex-Labs/anything-llm README](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md)

### Inferences
- Docker being the only deployment form with agents, multi-user, embeds, and white-labeling makes it the de facto "full product" tier of the open-source offering, with Desktop as a deliberately stripped-down single-user variant and Cloud as a managed version of (most, but not all — see Section 13) of Docker's capability set.

### Gaps
- Exact Docker image tags/compose file contents (e.g., which services ship in `docker-compose.yml`) were not inspected in this pass.

---

## 12. Desktop app — Electron-based? What's different vs. Docker?

### Takeaway
The Desktop app (Mac/Windows/Linux) is a single-user, all-local-storage installer with a bundled LLM engine, CPU embedder, and LanceDB, explicitly lacking multi-user roles, the embeddable widget, white-labeling, and (per one Docker-vs-Desktop comparison) agent features. Whether it's literally Electron-based was not directly confirmed in retrieved sources (a reasonable technical inference for a "one-click install" cross-platform desktop app, but not verified).

### Cited Findings
- "The desktop app (macOS, Windows, Linux) is for single users running everything locally with a built-in LLM engine, CPU-based embedder, and bundled LanceDB. One-click install, no configuration needed." — [WebSearch synthesis of docs.anythingllm.com/installation-docker/overview and related pages](https://docs.anythingllm.com/installation-docker/overview)
- "The Desktop app is single-user only, while the Docker version supports multi-user with three roles: Admin, Manager, and Default." — [WebSearch synthesis](https://docs.anythingllm.com/installation-docker/overview)
- "Multi-user access and the embeddable chat widget are Docker-only. The desktop app does not include them. Additionally, agent features require Docker." — [WebSearch synthesis](https://docs.anythingllm.com/installation-docker/overview)
- "In summary: use the desktop app for personal, single-user use, and Docker for team collaboration with multi-user support and advanced features." — [WebSearch synthesis](https://docs.anythingllm.com/installation-docker/overview)
- README lists "Desktop: Mac, Windows, and Linux applications available" among deployment options, alongside "optional browser extension and mobile applications" as part of overall project architecture. — [Mintplex-Labs/anything-llm README](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md)

### Inferences
- Given AnythingLLM's frontend stack is Vite + React (per README) and the Desktop app is a self-contained one-click cross-platform installer with a bundled LLM engine, it is very likely Electron-based (the standard approach for shipping a React web app as a native desktop binary with bundled local services), but this was not explicitly stated in any fetched source, so it remains an inference, not a confirmed fact.

### Gaps
- No primary source explicitly states "Electron" as the desktop packaging technology — this claim could not be verified and should be presented as a likely-but-unconfirmed inference in the final report.
- Exact "bundled LLM engine" identity (e.g., which local runtime/model ships by default in Desktop) was not detailed in sources retrieved.

---

## 13. Cloud-hosted/managed offering — does Mintplex Labs offer a hosted SaaS version? Name, cost, differences?

### Takeaway
Yes — "AnythingLLM Cloud" is Mintplex Labs' current managed SaaS offering (confirmed live as of this research, per docs.anythingllm.com/cloud/overview and anythingllm.com/pricing), priced at three tiers: Basic $50/month, Pro $99/month, and custom-priced Enterprise; it runs isolated single-tenant instances on AWS but has documented functional restrictions vs. self-hosted (no custom Agents, no MCP support, no bundled/local LLM, embedder capacity limits).

### Cited Findings
- AnythingLLM Cloud is a managed service offering "isolated and private instances of AnythingLLM," each on "a separate AWS server that is automatically maintained by the core team." — [AnythingLLM Docs: Cloud Overview, via WebFetch](https://docs.anythingllm.com/cloud/overview)
- Cloud is positioned as "the easiest way to trial and scale AnythingLLM" vs. self-hosted. — [AnythingLLM Docs: Cloud Overview](https://docs.anythingllm.com/cloud/overview)
- Pricing (from anythingllm.com/pricing, current site): **Basic — $50/month**: private instance, custom subdomain, "RAG, agents, and work right out of the box," requires user's own LLM API key. **Pro — $99/month**: private instance, same RAG/agents/work-out-of-the-box framing, "designed for larger teams," 72-hour support response commitment. **Enterprise — custom pricing**: on-premise deployment options, tailored SLAs, custom integrations, "SSO, RBAC, and more." — [anythingllm.com/pricing, via WebFetch](https://anythingllm.com/pricing)
- Self-hosted Docker remains free/$0, framed against Cloud as "own it" vs. "renting" — i.e., Cloud is explicitly the paid/managed tier and self-host is the free/open-source tier. — [anythingllm.com/pricing, via WebFetch](https://anythingllm.com/pricing)
- Cloud documented limitations vs. self-host: no bundled LLM ("The hosted cloud lacks a bundled language model due to hardware constraints. Users must connect to external cloud providers or run their own local LLMs instead."); the built-in embedder "will not block you from trying to embed a 5,000pg PDF, but it will crash your instance"; "Accuracy Optimized" search mode can cause slowdowns on large workspaces, requiring "Default" mode instead; "We do not support custom Agents in the hosted cloud due to security concerns as well [as] other general limitations to running arbitrary code in a hosted environment"; "No MCP Support" for the same reasons; Starter tier has "minimal compute resources" and both tiers "lack GPU support and have limited CPU/RAM." — [AnythingLLM Docs: Cloud Limitations, via WebFetch](https://docs.anythingllm.com/cloud/limitations)
- Note a naming/tier discrepancy across sources: the Cloud Limitations page refers to "Starter" and "Professional" tiers, while the current pricing page (anythingllm.com/pricing) lists "Basic," "Pro," and "Enterprise" — likely reflecting a tier rename over time; both should be flagged to the report writer as the same product family, but exact current tier names should default to the live pricing page (Basic/Pro/Enterprise) as of this research date.
- A separate earlier web search also surfaced "AnythingLLM cloud hosting starts at $50/month" and described it as "built for businesses or teams that need the power of AnythingLLM, but want a managed instance... so they don't have to sweat the technical details," consistent with the $50 Basic tier above. — [WebSearch aggregated summary citing useanything.com/pricing / anythingllm.com/cloud](https://anythingllm.com/cloud)

### Inferences
- The Cloud limitations (no custom Agents, no MCP, no bundled local LLM) mean Cloud is a functional subset of Docker self-host, not a superset — despite being the paid option. This is an important, somewhat counter-intuitive nuance: paying for Cloud buys convenience/managed-ops, not more features than self-host.
- The Enterprise tier's "on-premise deployment options" suggests Mintplex Labs also offers a hybrid/enterprise-managed deployment distinct from both the multi-tenant-adjacent Cloud SaaS and pure community self-host — effectively a fourth deployment form (assisted/custom on-prem) gated behind sales conversation and custom pricing.

### Gaps
- Exact current (Sept 2026) resource specs (RAM/CPU/storage) per Basic/Pro tier were not itemized in sources retrieved beyond the qualitative "Starter... minimal compute" / "Professional... more capacity" language from the Limitations page.
- Could not confirm whether Basic/Pro Cloud tiers include the embeddable widget or white-labeling (Section 7's Customization docs explicitly excluded Cloud from white-labeling, but did not address the widget specifically for Cloud).

---

## 14. Differences in available vector DBs / LLM providers / features across deployment forms

### Takeaway
Docker/self-hosted exposes the full provider matrix (20+ LLMs, 7 vector DBs) plus multi-user, embeds, agents, MCP, and white-labeling; Desktop is deliberately narrowed to a single bundled local stack (built-in LLM engine, CPU embedder, bundled LanceDB) with no multi-user/embeds/agents; Cloud uses the same general provider ecosystem as Docker but explicitly disables Agents and MCP and lacks a bundled/local LLM option, while also excluding white-labeling.

### Cited Findings
- Full LLM/vector DB/embedding provider list applies to the general (Docker-oriented) product: OpenAI, Anthropic, Google Gemini, Azure OpenAI, AWS Bedrock, Ollama, LM Studio, DeepSeek, Groq, "20+ additional providers"; vector DBs: LanceDB (default), PGVector, Pinecone, Chroma, Weaviate, Qdrant, Milvus; embeddings: native + OpenAI, Cohere, Voyage AI; speech: PiperTTS, ElevenLabs. — [Mintplex-Labs/anything-llm README](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md)
- Desktop bundles "a built-in LLM engine, CPU-based embedder, and bundled LanceDB" — i.e., a fixed, non-swappable-by-default local stack rather than the full external-provider matrix (though Desktop can likely still be pointed at external providers/API keys; this specific point of "can Desktop also use OpenAI/Anthropic etc." was not directly confirmed). — [WebSearch synthesis of docs.anythingllm.com/installation-docker/overview](https://docs.anythingllm.com/installation-docker/overview)
- Cloud explicitly lacks a bundled LLM ("must connect to external cloud providers or run their own local LLMs instead") and disables custom Agents and MCP. — [AnythingLLM Docs: Cloud Limitations](https://docs.anythingllm.com/cloud/limitations)

### Inferences
- The provider-matrix breadth (LLMs/vector DBs) appears to be a shared codebase capability available wherever the underlying settings UI is exposed; the meaningful differences across deployment forms are less about which providers can be selected and more about which higher-level features (multi-user, embeds, agents, MCP, white-labeling) are enabled/reachable in each form.

### Gaps
- Could not directly confirm whether Desktop app users can still manually configure external LLM/vector DB providers (e.g., point Desktop at Pinecone or OpenAI) or whether Desktop is hard-locked to its bundled local stack only.

---

## 15. Kubernetes/Helm chart support and one-click deploy options

### Takeaway
Mintplex Labs maintains an official Helm chart repository, and the main README lists one-click deploy buttons for Railway, Render, DigitalOcean, AWS, GCP, and RepoCloud, alongside standard Docker/bare-metal install. A separate community-maintained Helm chart (`la-cc/anything-llm-helm-chart`) also exists on ArtifactHub. Tier: **Open-source/Community (MIT)** for all of these deployment mechanisms.

### Cited Findings
- One-click deployment platforms named in the README: "Railway, Render, DigitalOcean, AWS, GCP, and RepoCloud." — [Mintplex-Labs/anything-llm README](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md)
- Official Mintplex Labs Helm chart repository: "GitHub - Mintplex-Labs/helm-charts: Helm Charts for AnythingLLM and other resources maintained by Mintplex Labs Inc." — [GitHub: Mintplex-Labs/helm-charts, via WebSearch](https://github.com/Mintplex-Labs/helm-charts)
- "AnythingLLM provides an official Helm chart located in `cloud-deployments/helm/charts/anythingllm/` that orchestrates deployment on Kubernetes clusters. The chart manages deployment, service exposure, persistent storage, configuration, and secrets." — [WebSearch summary citing DeepWiki Kubernetes-and-Helm page](https://deepwiki.com/Mintplex-Labs/anything-llm/2.2-kubernetes-and-helm)
- A community chart also exists: "la-cc/anything-llm-helm-chart... allows you to deploy anything-llm, but also allows you to deploy anything-llm with different components like chromadb, nvidia-device-plugin, ollama, and more," published on ArtifactHub. — [ArtifactHub: anything-llm helm chart, via WebSearch](https://artifacthub.io/packages/helm/anything-llm-helm-chart/anything-llm)
- Typical deployment command pattern for the chart: `helm template anything-llm-hks anything-llm/anything-llm -f values.yaml | k apply -f -`, with non-sensitive config in a `values.yaml` `config` section rendered to a ConfigMap, and secrets handled via Kubernetes-native mechanisms. — [WebSearch summary citing ArtifactHub/DeepWiki content](https://artifacthub.io/packages/helm/anything-llm-helm-chart/anything-llm)

### Inferences
- The existence of both an official Mintplex Labs chart and a well-documented independent community chart suggests Kubernetes deployment is a recognized, moderately mature path for AnythingLLM, beyond just Docker Compose — appropriate to mention as a supported (if more DIY) deployment form in a competitive feature inventory.

### Gaps
- DeepWiki (a third-party AI-generated wiki, not an official Mintplex Labs source) was relied on for some Helm chart path/mechanics details ("cloud-deployments/helm/charts/anythingllm/") — this should be treated as lower-confidence/secondary and ideally re-verified directly against the `Mintplex-Labs/helm-charts` repo contents if higher confidence is required.
- Version/maintenance recency of the official Helm chart repo (last commit date, chart version) was not checked.
