# Onyx (formerly Danswer): Chat, Agents/Actions/Tool-calling, and Deep Research — Current State (2026)

## Key Question 1: Chat UI, citations, feedback, sharing, Personas/Assistants, exportability

### Takeaway
Onyx's chat is a full-featured, multi-turn interface (message editing/regeneration, per-session model/reasoning/temperature controls, streaming) with inline citations backed by a sources sidebar, thumbs-up/down feedback to admins, and link-based chat sharing. "Persona," "Assistant," and "Agent" are explicitly the same concept in current Onyx terminology, configurable with system prompt, tool/Action selection, knowledge scoping (Document Sets or hierarchical file/folder selection), and per-agent default model — all free/CE (MIT). There is an "Explore Agents" gallery for org-published agents, but no evidence of a public cross-org marketplace. No explicit chat-history export feature was found in official docs (gap).

### Cited Findings
- "The terms Personas, Assistants, and Agents are used interchangeably throughout Onyx" and refer to the same concept — [Onyx Docs: Core Concepts](https://docs.onyx.app/developers/core_concepts)
- Built-in Agents: id 0 "Search Agent" (uses Search Tool over the knowledge base), id -1 "General Agent" (basic chat, no tools), id -2 "Paraphrase Agent" (search + exact-snippet quoting), id -3 "Art Agent" (image/visual generation) — [Onyx Docs: Core Concepts](https://docs.onyx.app/developers/core_concepts)
- Custom Agents can be created in the Admin Panel or via the API (`GET /persona` endpoint lists agent IDs) — [Onyx Docs: Core Concepts](https://docs.onyx.app/developers/core_concepts)
- Agent creation fields include: name/description/icon, instructions/system prompt, "Conversation Starters," knowledge attachment via Document Sets or (with OpenSearch) hierarchical file/folder selection, and a default LLM per agent; explicitly selecting knowledge narrows the agent's scope to only that knowledge, otherwise it defaults to user-uploaded files and accessible public connectors — [Onyx Docs: Custom Agents / Admins Overview](https://docs.onyx.app/admins/agents/overview)
- Agents can be shared organization-wide, to specific users/groups, or marked "Featured" to appear at the top of the "Explore Agents" page in the chat sidebar; no cross-org marketplace/gallery of pre-built personas is documented — [Onyx Docs: Custom Agents](https://docs.onyx.app/admins/agents/overview)
- Changelog v4.4.0 (2026-07-21): "Featured agents with labels can highlight without being public" — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.2.0: "Agent sharing rebuilt with per-share permissions and explicit ownership transfer" — [Onyx Changelog](https://docs.onyx.app/changelog)
- Chat lets users "modify your inputs by clicking the user messages or regenerate the LLM response" — [Onyx Docs: Chat UI](https://docs.onyx.app/overview/core_features/chat)
- The right sidebar shows "sources and citations that were used in generating the answer," sourced from Internal Search and/or Web Search — [Onyx Docs: Chat UI](https://docs.onyx.app/overview/core_features/chat)
- A "Copy with references" feature on the Cited Sources panel copies the answer plus a deduplicated, first-citation-ordered source list as Markdown — [PR #14917 feat(chat): copy answers with references](https://github.com/onyx-dot-app/onyx/pull/14917)
- GitHub issue tracked: "Inline citations nest progressively across turns in multi-turn chat" using `[[n]](url)` bracket-numbered footnote-style citations — [GitHub Issue #12634](https://github.com/onyx-dot-app/onyx/issues/12634)
- Feedback: "thumbs-up/thumbs-down buttons when hovering an LLM response," sent to admins — [Onyx Docs: Chat UI](https://docs.onyx.app/overview/core_features/chat)
- Chat sharing: "share chats with other team members by using the share-chat button in the top right (left of the Sources sidebar)" — [Onyx Docs: Chat UI](https://docs.onyx.app/overview/core_features/chat)
- Deep Research is toggled via an hourglass icon in chat for "multi-cycle thinking for complex questions" — [Onyx Docs: Chat UI](https://docs.onyx.app/overview/core_features/chat)
- Model selection is available per chat session, choosing among configured LLM providers — [Onyx Docs: Chat UI](https://docs.onyx.app/overview/core_features/chat)
- Users can upload files or select URLs to add context to a chat session — [Onyx Docs: Chat UI](https://docs.onyx.app/overview/core_features/chat)
- Changelog v4.5.0 (2026-08-04): "Chat gains per-session reasoning and temperature controls" with model-specific support detection — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.7.0 (2026-09-04): "Multi-model chat improvements including swipeable carousels on narrow screens and pinned response headers" (implies side-by-side multi-model comparison in chat) — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.6.0 (2026-08-20): "Shared chats render full multi-model comparison"; also "Incognito mode keeps conversations out of durable records with configurable retention" and "Deep Research toggle no longer appears inside project chats, where selecting it always failed — deep research isn't supported in project chats" — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.6.0: a chat or Deep Research run "no longer lives and dies with your browser connection. Runs now execute to completion on the server regardless of client disconnects, and the stream records itself as it goes." — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.3.0 (approx. mid-2026): "Conversation-aware search scoping" decides which connected sources to cover based on agent routing — [Onyx Changelog](https://docs.onyx.app/changelog)
- Onyx Community Edition (CE) is MIT-licensed and "covers all of the core features for Chat, RAG, Agents, and Actions"; Enterprise Edition (EE) targets "organizations with special requirements—such as usage auditing, granular access controls, and white-labeling," available self-hosted or via Onyx Cloud — [Onyx Docs: Open Source Statement](https://docs.onyx.app/overview/miscellaneous/open_source_statement)
- Documented EE-gated features (explicit list): OIDC/SAML SSO, Permission Sync Connectors (auto-inherit external permissions), Whitelabeling, User Groups & RBAC, group-based access control for Connectors/Document Sets/Agents (v4.7+), Usage Analytics, Encrypted Secrets, Enterprise Edition APIs, Priority Support, and Hook Extensions (custom pipeline logic) — [Onyx Docs: Enterprise Edition](https://docs.onyx.app/deployment/miscellaneous/enterprise_edition)
- The Enterprise Edition doc does not list personas/agents, deep research, MCP, actions/tools, or basic chat sharing as EE-gated — [Onyx Docs: Enterprise Edition](https://docs.onyx.app/deployment/miscellaneous/enterprise_edition)

### Inferences
- Because Chat, RAG, Agents, and Actions are explicitly stated as part of CE, and Deep Research is explicitly stated as free for every organization, the entire chat/persona/deep-research feature set covered by this report is Community Edition (open-source, MIT) functionality; EE gating applies to org-management/security/branding features (SSO, RBAC, audit, whitelabel), not to the chat/agent/research feature set itself.
- The "Explore Agents" page functions as an internal, per-organization gallery of published/featured agents rather than a public cross-tenant marketplace — no evidence of an Onyx-hosted public persona marketplace was found.
- Citation style is a numbered, footnote/bracket format (`[[n]](url)`) rendered inline in the answer text, cross-referenced to a "Cited Sources" panel/sidebar — a footnote-with-source-card hybrid, not simple hyperlinked text.

### Gaps
- No official documentation was found describing a dedicated "export chat history" feature (e.g., PDF/Markdown/JSON export of full chat transcripts) beyond the answer-level "Copy with references" feature; unclear whether full-session export exists.
- No official confirmation of a comment-based (vs. thumbs-only) feedback mechanism on individual answers.
- Could not confirm whether "stopping generation" (a stop/cancel button during streaming) is currently supported — not explicitly mentioned in the fetched Chat UI docs page, though this is a near-universal chat feature and its absence from docs likely reflects doc terseness rather than actual absence.

---

## Key Question 2: Agents/Actions/Tool-calling, built-in tools, custom tools, MCP

### Takeaway
Onyx supports LLM tool/action calling with several built-in Actions (Knowledge/Internal Search, Web Search, Image Generation via DALL-E 3, and an opt-in Coding Agent with bash/file tools), lets admins define fully custom Actions via OpenAPI spec import, and — as of 2026 — supports the Model Context Protocol (MCP) as **both an MCP client** (Onyx agents can call tools on external MCP servers) **and an MCP server** (external MCP clients like Claude Desktop/Cursor can query Onyx's knowledge base). This is active, fast-moving CE functionality with frequent 2026 releases refining OAuth, timeouts, and access control.

### Cited Findings
- "Actions & MCP" let Onyx agents interact with external applications with flexible auth options — [Onyx Docs: Actions & MCP](https://docs.onyx.app/overview/core_features/actions) (title confirmed via search); [GitHub onyx-dot-app/onyx README](https://github.com/onyx-dot-app/onyx)
- "Actions (also called Tools in the backend) are the functions that your Agents can perform to interact with external systems and services." Admins define custom Actions in the Admin Panel using an OpenAPI specification — [Onyx Docs: Actions Overview](https://docs.onyx.app/actions/overview) (per search-result synthesis, confirmed against docs.onyx.app site structure)
- Built-in Actions include: Knowledge (search over knowledge connected through Connectors), Image Generation (DALL-E 3), Internet/Web Search (via Serper, Google PSE, Brave, SearXNG, plus an in-house web crawler and Firecrawl/Exa support) — [Onyx Docs: Actions Overview / Core Concepts](https://docs.onyx.app/developers/core_concepts)
- Custom Agents "allow you to build AI Agents with unique instructions, knowledge, and actions" — [GitHub onyx-dot-app/onyx README](https://github.com/onyx-dot-app/onyx)
- Changelog v4.0.0: "Coding Agent with file download and bash tool access (opt-in, disabled by default)" — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.7.0 (2026-09-04): "Forced tool calls work on GLM models rejecting non-`auto` tool_choice values" (indicates active, model-specific tool-calling compatibility engineering) — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.3.0: large spreadsheets streamed row-by-row; PDF extraction isolated in a subprocess (tool/action execution robustness work) — [Onyx Changelog](https://docs.onyx.app/changelog)
- **MCP — dual role confirmed**: "Onyx can be configured to be an MCP client and allow your Agents to retrieve data or perform operations." Separately, "Onyx can also act as an MCP server to connect Claude, Cursor, and other AI tools to your Onyx knowledge base." — [Onyx Docs: MCP](https://docs.onyx.app/admins/actions/mcp)
- MCP client setup: Admin Panel → MCP Actions dashboard → "Add an MCP Server" (name, description, Server URL reachable from the Onyx instance); supports managed and self-hosted servers over **HTTP transport only** (stdio not currently supported); auth options are No Auth, API Key (shared or per-individual), OAuth (with CIMD/DCR support), or Pass-Through OAuth — [Onyx Docs: MCP](https://docs.onyx.app/admins/actions/mcp)
- After connecting an MCP server, admins can list its available tools and select a subset to expose to Agents — [Onyx Docs: MCP](https://docs.onyx.app/admins/actions/mcp)
- Third-party community MCP servers exist that expose Onyx itself to MCP clients, e.g. ByWaleed/onyx-mcp ("comprehensive, secure Model Context Protocol server for Onyx... exposes Onyx search, chat, agents, projects, documents, connectors, ingestion, and deployment-specific APIs") and lupuletic/onyx-mcp-server — these are third-party/community, not part of the core onyx-dot-app/onyx repo — [GitHub ByWaleed/onyx-mcp](https://github.com/ByWaleed/onyx-mcp); [GitHub lupuletic/onyx-mcp-server](https://github.com/lupuletic/onyx-mcp-server)
- Changelog v4.4.0 (2026-07-21): "Group and public access control for MCP servers; OAuth tokens refresh proactively" — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.5.0 (2026-08-04): "Scheduled tasks can pre-approve MCP tools, so scheduled runs stop blocking on approval prompts" — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.6.0 (2026-08-20): "OAuth got a round of fixes: servers that only demand auth at tool execution (such as BigQuery) now discover consent correctly"; also OAuth connections requesting offline access now avoid token expiration after one hour — [Onyx Changelog](https://docs.onyx.app/changelog)
- Changelog v4.7.0 (2026-09-04): "MCP tool calls receive dedicated 300-second timeout (configurable via `MCP_SERVER_API_REQUEST_TIMEOUT_SECONDS`)" — [Onyx Changelog](https://docs.onyx.app/changelog)
- DeepWiki (third-party, community-generated documentation aggregator, not official) states the Onyx MCP server "act[s] as a bridge between the Onyx backend and any LLM client that supports the MCP standard" — [DeepWiki: MCP Server and External Integrations](https://deepwiki.com/onyx-dot-app/onyx/12.5-mcp-server-and-external-integrations) (lower-confidence, third-party source; consistent with official docs)

### Inferences
- MCP support is CE (not EE-gated): the MCP docs page gives no licensing caveat, and the changelog shows MCP feature work (OAuth, access control, timeouts) shipping steadily through 2026 as ordinary product iteration, consistent with it being core/open-source functionality alongside other Actions.
- MCP integration is HTTP/Streamable-HTTP-transport only in Onyx; local/stdio MCP servers are not supported as of the current docs, meaning self-hosted MCP servers must be reachable over the network from the Onyx instance.
- Tool-calling compatibility work (e.g., GLM `tool_choice` fix) indicates Onyx tool/action calling is implemented against the OpenAI-style function/tool-calling API convention, with provider-specific compatibility shims added as needed.

### Gaps
- Could not verify from official docs whether Onyx supports arbitrary code execution as a distinct "Code Interpreter" action separate from the "Coding Agent" (bash/file tools) feature — search snippets mention "Code Execution" as a built-in action but this wasn't independently confirmed on an official docs page in this pass.
- Did not verify the full canonical list of "5 built-in Actions" claimed by a secondary source (search summary) against a primary docs page fetch of `docs.onyx.app/actions/overview` (attempted via search only, not direct fetch) — treat the "5 built-in actions" count as unverified/lower-confidence.
- No official statement found on whether MCP was present at all in the Danswer era or is entirely new to Onyx (i.e., not a renamed pre-existing feature) — reasonably inferred to be new given MCP protocol's own 2024-2025 origin, but not explicitly dated in Onyx's own materials.

---

## Key Question 3: Deep Research mode

### Takeaway
Onyx's "Deep Research" is a distinct, user-toggleable chat mode (not automatic, not available in "project chats") implementing a multi-agent, hierarchical pipeline — clarification → planning → orchestrator → parallel research sub-agents → report generation with inline numbered citations — and is part of the free Community Edition, not EE-gated. As of a claimed "Deep Research Bench" leaderboard placement (self-reported, February 2026), Onyx positions this as a flagship differentiator; it now also runs to completion server-side independent of client connection.

### Cited Findings
- Onyx Deep Research uses a 2-level agent hierarchy specifically designed to avoid "deep-frying" (information degradation from excessive agent-to-agent layering) — [Onyx Blog: Building the Best Deep Research](https://www.onyx.app/blog/building-the-best-deep-research)
- Pipeline stages: **Clarification Agent** (decides if clarifying questions would help), **Planning Agent** (produces a high-level plan "to cover all angles of the user query"), **Orchestrator Agent** (the primary loop delegating research tasks to subagents as tool calls, monitoring progress and able to "make high level directional changes fairly easily"), **Research Agents** (lower-level investigations with access to search tools), **Report Agents** (generate intermediate and final reports with citations) — [Onyx Blog: Building the Best Deep Research](https://www.onyx.app/blog/building-the-best-deep-research)
- Final deliverables include numbered citations (`[1]`, `[2]`, `[3]`) with inline source attribution — [Onyx Blog: Building the Best Deep Research](https://www.onyx.app/blog/building-the-best-deep-research)
- Deep Research is triggered via a UI toggle (hourglass icon) in chat, described as enabling "multi-cycle thinking for complex questions" — i.e., it is an explicit mode/toggle, not automatic default behavior — [Onyx Docs: Chat UI](https://docs.onyx.app/overview/core_features/chat)
- Deep Research is explicitly unsupported inside "project chats": "The Deep Research toggle no longer appears inside project chats, where selecting it always failed — deep research isn't supported in project chats" (v4.6.0, 2026-08-20 fix) — [Onyx Changelog](https://docs.onyx.app/changelog)
- Deep Research runs (like other chat runs) now execute to completion server-side regardless of client disconnect, with the stream recording itself as it progresses (v4.6.0) — [Onyx Changelog](https://docs.onyx.app/changelog)
- "Onyx's core capabilities—including RAG, deep research, custom agents, and more—[are] completely free for every organization, regardless of size or budget," i.e., Deep Research is Community Edition, not Enterprise-only — [Onyx Docs: Open Source Statement](https://docs.onyx.app/overview/miscellaneous/open_source_statement)
- "As of February 2026, Onyx was at the top of the leaderboard for deep research capabilities" — reported via web-search synthesis referencing Onyx's own deep-research-bench submission repository — [GitHub: onyx-dot-app/onyx_deep_research_bench](https://github.com/onyx-dot-app/onyx_deep_research_bench); note this is a self-submitted benchmark entry, so the "top of leaderboard" framing should be treated as an Onyx-sourced claim, not independently adjudicated fact.
- Onyx supports all major LLM providers for its features generally, both self-hosted (Ollama, LiteLLM, vLLM) and proprietary (Anthropic, OpenAI, Gemini) — [GitHub onyx-dot-app/onyx README](https://github.com/onyx-dot-app/onyx)

### Inferences
- The clarification/planning/orchestrator/report-agent architecture is explicitly sub-question decomposition plus iterative refinement: the Planning Agent front-loads task decomposition and the Orchestrator can redirect subagents mid-run based on findings, matching the "iterative search-and-refine with sub-question decomposition and multi-source synthesis into a report" pattern named in the research objective.
- Deep Research is a distinct, opt-in UI mode (toggle) rather than an automatic escalation behavior — the chat model/reasoning controls (v4.5.0) are separate, session-level settings from the Deep Research toggle itself.

### Gaps
- The Onyx blog post did not specify a hard requirement for a "reasoning-capable" model (e.g., o1/o3-style or extended-thinking models) to run Deep Research; it discusses tool optimization "for the LLMs you actually want to support" in general terms but gives no explicit minimum-model requirement. This is a genuine gap — could not confirm whether Deep Research requires a specific reasoning-tier model or works with any configured chat model.
- Could not independently verify the "top of the leaderboard" deep-research-bench claim against a neutral third-party leaderboard page (only the Onyx-run benchmark submission repo and a search-engine paraphrase were found); treat as an Onyx self-reported/marketing claim pending independent verification.
- No explicit statement found on whether Deep Research was present in the Danswer era (pre-rename) or is a feature introduced entirely under the Onyx brand — given the dedicated 2026 blog post and active 2026 changelog churn (v4.5–v4.7), it appears to be a currently actively-developed, relatively recent (not legacy/deprecated) feature, but an exact introduction date was not found.
