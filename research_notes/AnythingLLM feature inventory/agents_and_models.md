# AnythingLLM Agents and Models/LLM Providers

## What is the @agent invocation and how does agent mode trigger vs normal chat?

### Takeaway
AnythingLLM's agent mode is invoked either automatically (if the connected LLM natively supports tool/function calling) or manually by typing `@agent` at the start of a chat message; a session persists until it completes or the user types `/exit`.

### Cited Findings
- To activate an agent session, users type `@agent` in the chat prompt; the UI logs "Agent @agent invoked," lists the tools available in that workspace, and ends the session on "Agent session completed" or via the `/exit` command — [AI Agent Usage – AnythingLLM Docs](https://docs.anythingllm.com/agent/usage/overview)
- Trigger mode depends on the connected LLM provider: "Automatic mode" activates agentic features in every chat without needing the `@` symbol if the LLM supports tool use; "Manual mode" requires the explicit `@agent` mention for providers that don't support automatic tool-use detection — [AI Agent Usage – AnythingLLM Docs](https://docs.anythingllm.com/agent/usage/overview)
- Docs explicitly state "not all providers allow AnythingLLM to automatically determine if your LLM can use tools," which is why manual `@agent` invocation exists as a fallback — [AI Agent Usage – AnythingLLM Docs](https://docs.anythingllm.com/agent/usage/overview)

### Inferences
- The dual-mode design suggests AnythingLLM maintains an internal allowlist/detection heuristic of which providers/models support native tool calling (e.g., OpenAI, Anthropic function calling) versus older or local models that need the explicit directive.

### Gaps
- Could not confirm the exact list of providers/models that fall into "automatic" vs "manual" agent-trigger buckets — the docs page describes the behavior generically without a provider-by-provider table.

### Tier tags
- Available in Docker self-host and Desktop (Community/MIT, no paywall found for the `@agent` mechanism itself).

---

## What is the current full list of built-in agent skills/tools?

### Takeaway
As of the docs referenced, AnythingLLM's built-in agent-skill set (accessible without any custom/third-party skill) numbers roughly ten tools spanning retrieval, browsing/scraping, file operations, summarization, charting, SQL querying, and job scheduling; older marketing copy also references RAG search and website scraping as flagship built-ins.

### Cited Findings
- Documented built-in skills: RAG Search, Web Browsing, Web Scraping, Save Files, List Documents, Summarize Documents, Chart Generation, SQL Agent, File System Agent, and Create Scheduled Jobs — [AI Agent Usage – AnythingLLM Docs](https://docs.anythingllm.com/agent/usage/overview)
- A broader/older enumeration (search-aggregated, likely combining current + legacy naming) also lists: Document Generation Agent, Gmail Agent, Google Calendar Agent, and Outlook Agent as additional built-in-style skills — [Introduction to custom agent skills – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/introduction); [AI Agent Setup – AnythingLLM Docs](https://docs.useanything.com/agent/setup)
- Marketing/product description states AnythingLLM has built-in agent skills "including RAG and website scraping, and optional skills like Generate charts, Web Search and others," implying a distinction between always-on built-ins and optionally-enabled skills — [AI Agents – AnythingLLM Docs](https://docs.anythingllm.com/agent/overview)

### Inferences
- The Gmail/Calendar/Outlook/Document-Generation agents are likely either (a) newer additions not yet reflected consistently across all doc pages, or (b) Community Hub-distributed skills that get surfaced alongside built-ins in some listings — the inconsistency between the two source pages suggests these are not uniformly "core" built-ins the way RAG Search or Web Scraping are.

### Gaps
- Could not directly verify via primary source (a single canonical docs page) whether Gmail Agent, Google Calendar Agent, Outlook Agent, and Document Generation Agent are shipped as built-in skills vs. Community Hub add-ons — flagging this discrepancy explicitly per instructions rather than asserting one classification.
- No confirmation found of a dedicated "code interpreter" skill as built-in (not found in any list); should be marked "not confirmed / possibly not available" unless the report writer finds it elsewhere.

### Tier tags
- Built-in skills (RAG Search, Web Browsing, Web Scraping, Save Files, List Documents, Summarize Documents, Chart Generation, SQL Agent, File System Agent, Create Scheduled Jobs): Community/MIT, available on Docker self-host and Desktop.

---

## How does the custom "Agent Skills" plugin system work (spec, build, install)?

### Takeaway
Custom Agent Skills are NodeJS-based plugins defined by a `plugin.json` manifest plus a `handler.js` entry point, placed in a `plugins/agent-skills/[hubId]/` folder in AnythingLLM's storage directory; they hot-load without a server restart and are explicitly excluded from AnythingLLM Cloud.

### Cited Findings
- "Custom agent skills must be written in JavaScript and will execute within a NodeJS environment. NodeJS programming experience is required to create custom agent skills." — [Introduction to custom agent skills – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/introduction)
- Skills "can be anything you want from a simple API call to even operating-system invocations," extending `@agent` invocations with custom tools — [Introduction to custom agent skills – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/introduction)
- `plugin.json` requires at minimum a human-readable `name` and a `hubId` that must exactly match the parent folder name — [Custom Agent Skill Developer Guide – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/developer-guide)
- Folder structure: `plugins/agent-skills/[hubId]/` containing `plugin.json`, `handler.js`, and any additional bundled files/NodeJS packages — [Custom Agent Skill Developer Guide – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/developer-guide)
- `handler.js` functions "must return a string value, anything else may break the agent invocation" — [Custom Agent Skill Developer Guide – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/developer-guide)
- Install locations: Docker → `[STORAGE_LOCATION]/plugins/agent-skills`; local dev → `server/storage/plugins/agent-skills`; Desktop → storage directory (per Desktop storage guide) + `plugins/agent-skills` — [Custom Agent Skill Developer Guide – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/developer-guide)
- AnythingLLM supports hot loading of new skills; a page reload (not a full restart) surfaces newly added skills, viewable in the Agent Skills tab of Settings — [Custom Agent Skill Developer Guide – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/developer-guide); [Introduction to custom agent skills – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/introduction)
- The `plugin.json` spec also supports dynamic UI inputs, allowing runtime arguments and configurable properties — [Introduction to custom agent skills – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/introduction)
- Availability by build: Docker since v1.2.2; Desktop since v1.6.5; **not available in AnythingLLM Cloud** — [Introduction to custom agent skills – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/introduction)
- Docs explicitly warn: "Only run custom agent skills you trust," since skills can execute OS-level operations depending on deployment type — [Introduction to custom agent skills – AnythingLLM Docs](https://docs.anythingllm.com/agent/custom/introduction)
- A real-world example: a developer built a custom Agent Skill that triggers Make.com webhooks, demonstrating the "simple API call" style of skill — [Writing an AnythingLLM Custom Agent Skill to Trigger Make.com Webhooks – DEV Community](https://dev.to/drunnells/writing-an-anythingllm-custom-agent-skill-to-trigger-makecom-webhooks-1dn0)

### Inferences
- The Cloud exclusion is consistent with a security posture: Cloud is multi-tenant/hosted, so allowing arbitrary NodeJS execution (including "operating-system invocations") per the docs' own warning would be a sandboxing risk Mintplex Labs has chosen to avoid on their hosted offering.

### Gaps
- Version-specific changelog entries for "v1.2.2" (Docker) and "v1.6.5" (Desktop) were not independently fetched/verified beyond the developer-guide/introduction doc's own claim; treat as accurate per primary docs but not independently cross-checked against the changelog archive.

### Tier tags
- Plugin/integration feature, Community/MIT (Docker + Desktop only); **not available** on AnythingLLM Cloud.

---

## Is there a community hub/marketplace for agent skills, and what's in it?

### Takeaway
Yes — the AnythingLLM Community Hub at hub.anythingllm.com is an official (beta) marketplace/sharing platform for Agent Skills, System Prompts, and Slash Commands, with a dedicated `/list/agent-skills` browsing page and a CLI tool (`anythingllm-hub-cli`) for publishing.

### Cited Findings
- "The AnythingLLM Community Hub is a platform and marketplace for AnythingLLM users to share system prompts, slash commands, agent skills, and more." It currently operates in **beta** — [What is the Community Hub? – AnythingLLM Docs](https://docs.anythingllm.com/community-hub/about)
- Current shareable content types: Agent Skills, System Prompts, Slash Commands; docs note additional types are planned, including workspaces, data connectors, and authentication providers — [What is the Community Hub? – AnythingLLM Docs](https://docs.anythingllm.com/community-hub/about)
- The Hub supports both public and private sharing — [What is the Community Hub? – AnythingLLM Docs](https://docs.anythingllm.com/community-hub/about)
- Agent skills are browsable at `hub.anythingllm.com/list/agent-skills` — [AnythingLLM Community Hub - Plugin platform for AnythingLLM](https://hub.anythingllm.com/list/agent-skills) (page itself returned HTTP 403 to automated fetch, so its live inventory/count could not be directly enumerated; existence and URL confirmed via docs and search-result title)
- Publishing to the Hub is done via a CLI tool called `anythingllm-hub-cli` — [Uploading to the AnythingLLM Community Hub – AnythingLLM Docs](https://docs.anythingllm.com/community-hub/upload)
- Community members have also published skill-builder tooling on third-party marketplaces referencing AnythingLLM's skill format (e.g., an "anythingllm-skill-builder" listing on LobeHub), and independent GitHub repos of example custom agents (`mdwoicke/anythingllm-custom-agent`, `stoneskin/AnythingLLM_AgentSample`, `MiguelAutomate/AnythingLLM-Custom-Agents`) exist showing community adoption of the plugin.json/handler.js format outside the official Hub — [LobeHub skill listing](https://lobehub.com/skills/khaledbashir-anc-phase1-complete-anythingllm-skill-builder); [GitHub: mdwoicke/anythingllm-custom-agent](https://github.com/mdwoicke/anythingllm-custom-agent); [GitHub: stoneskin/AnythingLLM_AgentSample](https://github.com/stoneskin/AnythingLLM_AgentSample); [GitHub: MiguelAutomate/AnythingLLM-Custom-Agents](https://github.com/MiguelAutomate/AnythingLLM-Custom-Agents)

### Inferences
- The Hub being "beta" and limited to three content types (with workspaces/connectors/auth providers only "planned") suggests it's still an early-stage distribution channel rather than a mature app-store-like ecosystem as of the research date.

### Gaps
- Could not retrieve the live hub.anythingllm.com agent-skills listing page directly (403 Forbidden to automated fetch), so exact skill count, categories, or "most popular" skills on the Hub could not be verified from the primary source itself — only its existence, URL, and stated content types are confirmed via docs.anythingllm.com.

### Tier tags
- Community Hub itself: free to browse (Community/MIT ecosystem tool); publishing/downloading skills interacts with the plugin system, which is Docker/Desktop only, not Cloud.

---

## What is AnythingLLM's MCP (Model Context Protocol) support — when added, how does it work, can arbitrary servers be added?

### Takeaway
AnythingLLM supports MCP (the Anthropic-originated open protocol) at the agent level via a JSON config file (`anythingllm_mcp_servers.json`) that AnythingLLM auto-detects and boots; MCP tool-calling capability was announced as a major feature in v1.8.0, with further MCP-related integration (Docker Model Runner & MCP Toolkit) added in v1.10.0 (dated June 24, 2026). Users can add arbitrary MCP servers using StdIO, SSE, or Streamable transports.

### Cited Findings
- MCP servers are configured by editing `anythingllm_mcp_servers.json` in the storage `plugins` directory; "AnythingLLM will automatically detect the MCP Servers and attempt to boot them up as needed." — [MCP Compatibility in AnythingLLM – AnythingLLM Docs](https://docs.anythingllm.com/mcp-compatibility/overview)
- AnythingLLM integrates with the Model Context Protocol, "an open standard created by Anthropic"; a dedicated UI lets users reload, monitor status, view error logs, and stop/start MCP servers and view their available tools — [MCP Compatibility in AnythingLLM – AnythingLLM Docs](https://docs.anythingllm.com/mcp-compatibility/overview)
- Configuration supports multiple transport types: StdIO, SSE, and Streamable — confirming arbitrary/any spec-compliant MCP server can be added, not a fixed allowlist — [MCP Compatibility in AnythingLLM – AnythingLLM Docs](https://docs.anythingllm.com/mcp-compatibility/overview)
- MCP servers operate at the agent level, integrating with AI Agents to extend their tool capabilities — [MCP Compatibility in AnythingLLM – AnythingLLM Docs](https://docs.anythingllm.com/mcp-compatibility/overview)
- MCP is documented separately for Desktop (`/mcp-compatibility/desktop`) and Docker (`/mcp-compatibility/docker`) builds, both of which are supported — [MCP on AnythingLLM Desktop – AnythingLLM Docs](https://docs.anythingllm.com/mcp-compatibility/desktop); [MCP on AnythingLLM Docker – AnythingLLM Docs](https://docs.anythingllm.com/mcp-compatibility/docker)
- MCP tool-calling support/"MCP Agent skills" were announced as available in the AnythingLLM Desktop app in the **v1.8.0** changelog — [AnythingLLM v1.8.0 changelog, cited via LinkedIn post: "AnythingLLM v1.8.0: Full MCP tool calling capabilities"](https://www.linkedin.com/posts/timothy-carambat_in-our-latest-update-anythingllm-now-has-activity-7319124402539806720-wW2M); confirmed via [docs.anythingllm.com/changelog/v1.8.0]
- A later release, **v1.10.0** (dated June 24, 2026), added "first class support for running models via the Docker Model Runner & MCP Toolkit," indicating continued MCP investment through mid-2026 — [Desktop/Docker Changelog references, docs.anythingllm.com/changelog/v1.10.0]
- Community-built third-party MCP servers exist that expose AnythingLLM itself as an MCP server/client target for external tools like Claude Desktop, VS Code, and Cursor — e.g., `andreperez/anythingllm-mcp` and `raqueljezweb/anythingllm-mcp-server`, which provide workspace/chat/document/system management tools over MCP. This is a separate, unofficial/community integration layer (AnythingLLM as an MCP *server* for other clients), distinct from AnythingLLM's native support for *consuming* MCP servers inside its own agent — [GitHub: andreperez/anythingllm-mcp](https://github.com/andreperez/anythingllm-mcp); [GitHub: raqueljezweb/anythingllm-mcp-server](https://github.com/raqueljezweb/anythingllm-mcp-server)
- An open GitHub feature-request issue (#6403) asks Mintplex Labs to officially "Support AnythingLLM as an MCP Server" — implying that, as of that issue, official (first-party) MCP-server-mode for AnythingLLM was not yet shipped, only third-party/community wrappers — [GitHub Issue #6403: Support AnythingLLM as an MCP Server](https://github.com/Mintplex-Labs/anything-llm/issues/6403)
- The original MCP client-support feature request is tracked in GitHub Issue #3000 — [GitHub Issue #3000: Support Model Context Protocol (MCP)](https://github.com/Mintplex-Labs/anything-llm/issues/3000)

### Inferences
- AnythingLLM's MCP support is currently one-directional and mature only as a *consumer*: it connects to external MCP servers to extend agent tool access. Native first-party "AnythingLLM as an MCP server" (so other MCP clients like Claude Desktop could call into AnythingLLM) appears to still be community-built rather than official, based on the open issue #6403.
- Because switching the workspace LLM does not require reconfiguring MCP tools ("when you switch models in your workspace, the new model will still have full access to the same MCP tools" — per earlier search synthesis), MCP tool wiring is stored independently of the model/provider selection, at the agent/workspace config layer.

### Gaps
- Could not confirm from a single authoritative page whether MCP servers can be scoped per-workspace (i.e., different workspaces having access to different MCP servers) versus being a single global list shared by all agents/workspaces in an instance — docs describe "agent level" scope but do not clarify multi-workspace isolation.
- Cloud-tier MCP availability is not explicitly addressed in the fetched MCP overview docs; given custom agent skills are Cloud-excluded, MCP (which lives in the same `plugins` directory tree and requires file-system config editing) is plausibly also Docker/Desktop-only, but this is an inference, not a confirmed fact — flagged as a gap.

### Tier tags
- MCP client (consuming external servers): Community/MIT feature, confirmed on **Docker** and **Desktop**; **Cloud availability unconfirmed** (likely unavailable given the file-based config mechanism, but not verified).
- AnythingLLM-as-MCP-server: **not officially available** (community/unofficial third-party implementations only, per open GitHub issue #6403).

---

## Do "Agent Flows" (no-code agent builder) still exist, and under what name?

### Takeaway
Yes — the no-code visual agent builder is officially called **"Agent Flows"** (docs section `/agent-flows/`), a drag-and-drop canvas for chaining API calls, LLM instructions, and file operations, distinct from and simpler than code-based Custom Agent Skills; it supports MCP tools and can run on a schedule (cron) or on-demand, and it is available on both Docker and Desktop builds.

### Cited Findings
- Official docs section exists at `docs.anythingllm.com/agent-flows/overview` ("What is an Agent Flow?"), with further pages "Getting Started with Flows," a blocks-introduction page, and a "Debugging flows" page — [What is an Agent Flow? – AnythingLLM Docs](https://docs.anythingllm.com/agent-flows/overview); [Getting Started with Flows – AnythingLLM Docs](https://docs.anythingllm.com/agent-flows/getting-started); [AnythingLLM Docs – agent-flows/blocks/intro](https://docs.anythingllm.com/agent-flows/blocks/intro); [Debugging flows – AnythingLLM Docs](https://docs.anythingllm.com/agent-flows/debugging-flows)
- Agent Flows are described as "a no-code way to build agentic skills using a visual interface," letting users "build 'flows' that can be used in your agents," positioned as simpler than the traditional (code-based) agent skills route, which is aimed at "power users and developers" — [What is an Agent Flow? – AnythingLLM Docs](https://docs.anythingllm.com/agent-flows/overview) (via aggregated search synthesis)
- Users can drag-and-drop steps into a canvas (e.g., fetch data from API A → transform it → write to database B → send a Slack notification) — [What is an Agent Flow? – AnythingLLM Docs](https://docs.anythingllm.com/agent-flows/overview) (via aggregated search synthesis)
- "Docker and Desktop versions of AnythingLLM have a built-in agent flow editor and have various tools available to use in your flows"; it also supports MCP for connecting external tools, and flows "execute on-demand or on a schedule (cron)" — [What is an Agent Flow? – AnythingLLM Docs](https://docs.anythingllm.com/agent-flows/overview) (via aggregated search synthesis)

### Inferences
- "Agent Flows" is the current, still-active branding — there is no evidence in the sources gathered that this feature was renamed or deprecated; it continues to appear in the live docs navigation as of the search date.

### Gaps
- Did not independently WebFetch the full `agent-flows/overview` page (relied on WebSearch's synthesized summary, which itself is aggregated from that page); a direct fetch to confirm exact wording and any version/tier caveats not captured by the search synthesis would strengthen this section, but was not completed within the tool budget for this research pass.
- No explicit Cloud-tier statement was found for Agent Flows (only "Docker and Desktop versions... have a built-in agent flow editor" was stated) — Cloud availability should be treated as unconfirmed/likely absent, consistent with the pattern seen for Custom Agent Skills, but not directly verified.

### Tier tags
- Community/MIT, confirmed on Docker and Desktop; Cloud availability unconfirmed (pattern suggests likely unavailable, but not verified from a primary source).

---

## What is the full current list of supported LLM providers?

### Takeaway
Per the live GitHub source tree (`server/utils/AiProviders`), AnythingLLM currently ships **40 distinct LLM provider integration modules**, spanning major commercial APIs, aggregators/routers, enterprise cloud platforms, and local/self-hosted runtimes — a notably larger and more current list than older marketing copy's "30+"/"40+" round numbers.

### Cited Findings
- Full list of provider folders under `server/utils/AiProviders` on the `master` branch: anthropic, apipie, azureOpenAi, bedrock, cerebras, cohere, cometapi, deepseek, fireworksAi, foundry, gemini, genericOpenAi, giteeai, groq, koboldCPP, lemonade, liteLLM, llmman, lmStudio, localAi, minimax, mistral, modelMap, modelRouter, moonshotAi, novita, nvidiaNim, ollama, omlx, openAi, openRouter, perplexity, ppio, privatemode, sambanova, textGenWebUI, togetherAi, vertex, xai, zai — [server/utils/AiProviders directory – GitHub Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm/tree/master/server/utils/AiProviders)
  - Note: `modelMap` and `modelRouter` are utility/meta modules (model-routing logic), not standalone third-party LLM providers, so the count of genuine external LLM providers is ~38.
- Cross-referenced against the docs site's sidebar navigation, which independently lists (grouped as Local vs Cloud): **Local** — AnythingLLM Default (built-in), LM Studio, Local AI, Ollama, KoboldCPP, oMLX; **Cloud** — Anthropic, Azure OpenAI, AWS Bedrock, Cohere, Google Gemini, Google Vertex AI, Groq, Hugging Face, Mistral AI, OpenAI, OpenAI (generic/"OpenAI Compatible"), OpenRouter, Perplexity AI, Together AI, APIpie — [AnythingLLM Docs LLM configuration sidebar, via docs.anythingllm.com/setup/llm-configuration/cloud/openai fetch]
  - Notable: Hugging Face appears in the docs sidebar list but not distinctly named in the GitHub source-folder list gathered (it may be handled under `genericOpenAi` or another wrapper, or the source-tree snapshot fetched may be incomplete/outdated relative to docs) — flagged as a discrepancy to note explicitly rather than silently reconcile.
- Additional providers appearing only in the GitHub source list (i.e., shipped in code but not necessarily prominent in the docs sidebar snapshot fetched): Bedrock, Cerebras, CometAPI, DeepSeek, Fireworks AI, Foundry (Azure AI Foundry), Gitee AI, Lemonade, LiteLLM, llmman, Minimax, Moonshot AI, Novita, NVIDIA NIM, PPIO, Privatemode, SambaNova, Text-Generation-WebUI, xAI (Grok), Zai — [server/utils/AiProviders directory – GitHub Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm/tree/master/server/utils/AiProviders)
- Aggregator summary (secondary source, useful for corroboration, not primary): "AnythingLLM supports 40+ LLM providers including Ollama, LM Studio, OpenAI, Anthropic, Azure OpenAI, Google Gemini, and AWS Bedrock... built-in local providers include Ollama, LM Studio, Local AI, KoboldCPP, Text Generation WebUI, llmman, Lemonade, and oMLX" — [DeepWiki: Supported Providers | Mintplex-Labs/anything-llm](https://deepwiki.com/Mintplex-Labs/anything-llm/5.2-supported-providers)
- A "Model Router" feature enables automatic routing between different LLM providers/models based on user-defined rules within a single chat session, corroborating the `modelRouter` module seen in source — [AnythingLLM Docs, via docs.anythingllm.com/features/language-models fetch synthesis]

### Inferences
- The provider list has clearly grown substantially since AnythingLLM's earlier "GPT4All, Azure OpenAI, OpenAI, Anthropic, Ollama, LMStudio, LocalAI, Together AI" era referenced in the user's own prompt — many newer entrants (Cerebras, DeepSeek, xAI/Grok, Novita, Fireworks AI, NVIDIA NIM, SambaNova, Moonshot AI, Minimax, PPIO, Privatemode, Zai, CometAPI, Gitee AI, Azure AI Foundry) reflect the 2024–2026 wave of new inference/model providers being added incrementally.
- GPT4All (an early AnythingLLM-associated local-model project referenced in some older/legacy descriptions of AnythingLLM) does **not** appear in the current source tree — suggesting it was removed/deprecated as a distinct provider in favor of the "AnythingLLM Default" built-in local LLM and/or Ollama/LMStudio/LocalAI as the local-model paths. This should be flagged as **removed/renamed** if the report writer had prior notes referencing GPT4All.

### Gaps
- Could not obtain a live, dated snapshot confirmation (e.g., commit hash or "last updated" timestamp) for the GitHub directory listing — the list reflects the state at fetch time during this research session but a specific commit reference was not captured.
- Could not fully resolve the Hugging Face discrepancy (present in docs sidebar synthesis, not distinctly named in the source folder list) — flag as needing verification rather than asserting either "still supported" or "removed."

### Tier tags
- All 38+ LLM provider integrations: Community/MIT (available in the open-source codebase used by both Docker self-host and Desktop).
- Cloud-hosted AnythingLLM offering: provider selection likely narrower/managed (not independently verified in this pass — flagged as a gap below).

---

## What is the full current list of embedding providers?

### Takeaway
AnythingLLM ships a built-in default embedder (auto-downloaded, CPU-based, no API key) plus dedicated integrations for major cloud and local embedding providers, including OpenAI, Azure OpenAI, Cohere, Ollama, LM Studio, and LocalAI, mirroring much of the LLM provider list's local/cloud split.

### Cited Findings
- "AnythingLLM supports many embedding model providers out of the box with very little, if any setup." — [Embedding Models – AnythingLLM Docs](https://docs.useanything.com/features/embedding-models)
- Cloud embedding providers with dedicated docs pages found: OpenAI ("OpenAI offers 3 embedding models that vary between performance and dimension"), Azure OpenAI ("offers the same embedding models the base OpenAI provider does, but running on your Azure account"), and Cohere ("provides industry-leading... Embedding models tailored to meet the needs of enterprise use cases") — [OpenAI Embedder – AnythingLLM Docs](https://docs.anythingllm.com/setup/embedder-configuration/cloud/openai); [Azure OpenAI Embedder – AnythingLLM Docs](https://docs.anythingllm.com/setup/embedder-configuration/cloud/azure-openai); [Cohere Embedder – AnythingLLM Docs](https://docs.anythingllm.com/setup/embedder-configuration/cloud/cohere)
- Local/built-in embedding providers referenced: AnythingLLM Default (downloads a 25MB model on first embed, runs on CPU), Ollama, LM Studio, and Local AI — [AnythingLLM Default Embedder – AnythingLLM Docs](https://docs.anythingllm.com/setup/embedder-configuration/local/built-in); [Local AI Embedder – AnythingLLM Docs](https://docs.anythingllm.com/setup/embedder-configuration/local/localai)

### Inferences
- The embedding-provider set is smaller than the LLM-provider set (roughly half a dozen well-documented options vs. ~38 LLM providers), suggesting Mintplex Labs prioritizes broad LLM/chat-provider coverage over exhaustive embedding-provider coverage — likely because fewer distinct embedding APIs exist in the market relative to chat/completion APIs.

### Gaps
- Could not confirm from the pages fetched whether additional embedding providers beyond OpenAI, Azure OpenAI, Cohere, Ollama, LM Studio, Local AI, and the AnythingLLM Default exist (e.g., Google Gemini embeddings, Voyage AI, Mistral embeddings) — the embedder-configuration overview page itself returned a 404 on direct fetch, so this list should be treated as a lower bound, not necessarily exhaustive, of the current (2026) provider set.

### Tier tags
- All embedding providers found: Community/MIT, Docker + Desktop (no Cloud-specific restriction found or refuted in sources gathered — flag as unconfirmed for Cloud).

---

## What are the specifics of local model support (Ollama, LMStudio, and AnythingLLM's own built-in local model)?

### Takeaway
AnythingLLM treats Ollama and LM Studio as first-class local LLM providers (each with dedicated setup docs) alongside a separate "AnythingLLM Default" built-in local LLM that requires no external server and downloads its own small model automatically; it is one of several "Local" provider categories that also includes Local AI, KoboldCPP, and oMLX.

### Cited Findings
- Docs sidebar groups "Local Providers" as: AnythingLLM Default, LM Studio, Local AI, Ollama, KoboldCPP, oMLX — [AnythingLLM Docs LLM configuration sidebar synthesis, via docs.anythingllm.com/setup/llm-configuration/cloud/openai fetch context]
- A dedicated docs page exists specifically titled "AnythingLLM Default LLM," confirming the platform ships/manages its own native built-in LLM option distinct from Ollama/LMStudio/etc. — [AnythingLLM Default – AnythingLLM Docs](https://docs.anythingllm.com/setup/llm-configuration/local/built-in)
- On the embedding side, the equivalent "AnythingLLM Default Embedder" downloads a 25MB model on the first embed operation and runs on CPU with no separate server needed — [AnythingLLM Default Embedder – AnythingLLM Docs](https://docs.anythingllm.com/setup/embedder-configuration/local/built-in)
- Source code confirms `ollama` and `lmStudio` as distinct, separately maintained provider modules in `server/utils/AiProviders`, alongside `localAi`, `koboldCPP`, `omlx`, `textGenWebUI`, and `lemonade`/`llmman` as other local-runtime integrations — [server/utils/AiProviders directory – GitHub Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm/tree/master/server/utils/AiProviders)

### Inferences
- The presence of both a first-party "AnythingLLM Default" LLM and a first-party "AnythingLLM Default Embedder" (each auto-downloading a small local model with no configuration) indicates the product is designed to work fully offline/out-of-the-box immediately after install, before a user configures any external provider like Ollama or OpenAI — consistent with the project's "local-first agent experience" tagline seen in its GitHub description.

### Gaps
- Could not obtain the specific model name/size/architecture used for the "AnythingLLM Default" *LLM* (only the embedder's ~25MB size was confirmed) — the built-in-LLM docs page title was found but its full content (model identity, parameter count, quality tradeoffs) was not fetched in this pass.
- Did not verify whether the "AnythingLLM Default" LLM is available in the Cloud/hosted tier or is exclusively a Docker/Desktop local-inference feature.

### Tier tags
- AnythingLLM Default (LLM + Embedder): Community/MIT, Docker + Desktop, no API key required.
- Ollama, LM Studio, Local AI, KoboldCPP, oMLX, Text-Generation-WebUI, Lemonade, llmman: Community/MIT integrations, Docker + Desktop (require the user to separately run these local inference servers).

---

## Does per-workspace LLM model override exist, and how granular is it (provider+model, or just model)?

### Takeaway
Confirmed: AnythingLLM supports full per-workspace LLM override at both the **provider** and **model** level simultaneously — a workspace can use an entirely different provider (e.g., Anthropic) and model than another workspace or the system-wide default (e.g., OpenAI), configured via Workspace Settings → Chat Settings → Workspace LLM Provider.

### Cited Findings
- "AnythingLLM allows you to set workspace-specific LLMs, which will override the system LLM but only when chatting with the specific workspace. This allows you to have many workspaces that each have their own provider, model, or both." — [AnythingLLM Docs / DeepWiki synthesis: Workspace Model and Configuration](https://deepwiki.com/Mintplex-Labs/anything-llm/8.1-workspace-model-and-configuration)
- Access path: "open the workspace, go to Workspace Settings → Chat Settings → Workspace LLM Provider, and select your desired provider with the model you want" — [AnythingLLM Docs synthesis, per workspace settings navigation]
- Technical mechanism: each workspace has an overridable chat-provider field; "if the chat provider is null, it uses system settings" — implying a per-workspace nullable override column/config rather than a full independent config duplicated per workspace — [Workspace Model and Configuration | Mintplex-Labs/anything-llm | DeepWiki](https://deepwiki.com/Mintplex-Labs/anything-llm/8.1-workspace-model-and-configuration)
- A historical GitHub bug report titled "Setting Workspace LLM Provider or Workspace Agent LLM Provider fails" (Issue #1294) independently corroborates that the feature has existed as a distinct configurable field for some time (both for the main chat LLM and separately for the *Agent's* LLM within a workspace) — [GitHub Issue #1294](https://github.com/Mintplex-Labs/anything-llm/issues/1294)
- Separately, docs on multi-modal models note: "Models that are multi-modal (text-to-text & image-to-text) are supported for System & Workspace models," reinforcing that workspace-level model selection is a first-class, documented configuration axis alongside the system-wide default — [Language Models – AnythingLLM Docs, via docs.anythingllm.com/features/language-models fetch]

### Inferences
- The existence of a *separate* "Workspace Agent LLM Provider" setting (per Issue #1294's title) implies granularity goes even further than "one override per workspace" — a single workspace can potentially use one provider/model for normal chat and a *different* provider/model specifically for its `@agent` sessions, though this was not independently confirmed via a primary docs page in this pass.

### Gaps
- Did not find a primary docs page (as opposed to a GitHub issue title and aggregator/DeepWiki synthesis) explicitly walking through the distinction between "Workspace Chat LLM" and "Workspace Agent LLM" as two separately configurable settings — flagging this as needing direct confirmation from `docs.anythingllm.com/workspaces/...` if the report requires that specific nuance.

### Tier tags
- Community/MIT, confirmed on Docker + Desktop; Cloud-tier granularity (whether hosted customers can pick arbitrary BYO providers per workspace or are restricted to Mintplex-managed models) not verified in this pass — flagged as a gap.

---

## What TTS/STT providers are supported?

### Takeaway
AnythingLLM supports multiple Text-to-Speech providers (browser-native, PiperTTS running locally, self-hosted Kokoro, OpenAI, ElevenLabs, and generic "OpenAI Compatible" endpoints) and at least two Speech-to-Text options (Native Browser Built-in as default, and OpenAI), configured under Settings → Voice & Speech.

### Cited Findings
- TTS providers, per the dedicated docs page: System native (browser's built-in speech synthesis), PiperTTS (open-source Piper voice models run locally in-browser), Kokoro (self-hosted, requires a kokoro-fastapi server), OpenAI (requires API key), ElevenLabs (requires API key), and "OpenAI Compatible" (connects to any service implementing OpenAI's speech API) — [Text to Speech (TTS) – AnythingLLM Docs](https://docs.anythingllm.com/features/text-to-speech)
- Configuration path: Settings → Voice & Speech → Text-to-speech Preference → choose provider → fill settings → Save changes; once configured, users click the speaker icon under any chat response to hear it read aloud — [AnythingLLM Docs, Voice & Speech settings synthesis]
- For ElevenLabs specifically: "AnythingLLM uses ElevenLabs voices and technology, requiring an ElevenLabs API key, and you can choose from the voices available to your ElevenLabs account" — [AnythingLLM Docs / ElevenLabs TTS configuration synthesis]
- STT: "AnythingLLM offers STT (speech-to-text) support with Native Browser Built-in as the default option," with OpenAI also referenced as a cloud STT option in the docs' local/cloud pairing pattern (mirroring the TTS local/cloud split) — [Text to Speech (TTS) / STT section – AnythingLLM Docs](https://docs.anythingllm.com/features/text-to-speech)

### Inferences
- The TTS/STT feature set follows the same architectural pattern as LLM/embedding providers: a free, local/browser-based default (no API key) plus opt-in cloud providers (OpenAI, ElevenLabs) for higher-quality voices — consistent with AnythingLLM's general "local-first, cloud-optional" design philosophy.

### Gaps
- Could not fully verify the complete STT provider list (only "Native Browser Built-in" and "OpenAI" were found); it's unclear whether ElevenLabs' own STT/transcription API (distinct from its TTS API) is also integrated as an AnythingLLM STT option, or if AnythingLLM's ElevenLabs integration is TTS-only. This should be marked as an open question rather than assumed either way.
- No tier/version information (e.g., which AnythingLLM version introduced Kokoro or PiperTTS support, or whether TTS/STT differs between Docker, Desktop, and Cloud) was found in the sources gathered — flagged as a gap.

### Tier tags
- Native/browser TTS and STT: Community/MIT, free, no API key, likely available across Docker/Desktop/Cloud (browser-based feature).
- PiperTTS: Community/MIT, local/in-browser, no API key.
- Kokoro: Community/MIT but self-hosted (requires running a separate kokoro-fastapi server) — effectively a "plugin/integration" tier requiring extra infrastructure.
- OpenAI TTS/STT, ElevenLabs TTS, "OpenAI Compatible" TTS: plugin/integration tier requiring a paid third-party API key; tier availability across Docker/Desktop/Cloud not independently confirmed.
