# AnythingLLM: Workspaces and Documents/RAG Ingestion

## What is the definitive CURRENT list of per-workspace settings, and which exist in the 2026 codebase?

### Takeaway
AnythingLLM is fully open-source (MIT license, self-hosted via Docker or desktop app) with no separate "hosted/cloud" tier identified in current sources — all functionality described below applies to the self-hosted OSS product. The `workspaces` table in the live Prisma schema confirms system prompt override, chat mode, LLM provider/model override, temperature, similarity threshold, top-N context snippets, and chat history length all exist as real, persisted fields today. A separate `agentProvider`/`agentModel` pair also exists for overriding the model used specifically in Agent mode, distinct from the main chat model.

### Cited Findings
- The live `workspaces` model in `server/prisma/schema.prisma` (fetched from the `master` branch) contains these fields: `openAiTemp` (Float, nullable — temperature), `openAiHistory` (Int, default 20 — chat history length), `openAiPrompt` (String, nullable — system prompt override), `similarityThreshold` (Float, nullable, default 0.25), `chatProvider` (String, nullable — per-workspace LLM provider override), `chatModel` (String, nullable — per-workspace LLM model override), `topN` (Int, nullable, default 4 — max context snippets/chunks returned to the LLM), `chatMode` (String, nullable, default "chat"), `agentProvider` / `agentModel` (String, nullable — separate LLM override for Agent mode specifically), `queryRefusalResponse` (String, nullable — custom message returned in Query mode when no relevant context is found), `vectorSearchMode` (String, nullable, default "default"), `vectorTag`, `pfpFilename` (workspace avatar) — [schema.prisma](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/server/prisma/schema.prisma)
- Workspaces have three chat modes: **Agent Mode** (recommended for v1.11.1+, auto-invokes agent-skills/tools/MCPs via the LLM's native tool-calling), **Chat Mode** (blends document context with the model's general knowledge, more conversational/flexible), and **Query Mode** (restricted to answering only from uploaded documents, explicitly states when it can't find relevant info) — [Chat Modes docs](https://docs.anythingllm.com/features/chat-modes)
- Chat mode is changed per-workspace via the gear icon → "Chat Settings" tab — [Chat Modes docs](https://docs.anythingllm.com/features/chat-modes)
- Document similarity threshold is configurable per workspace via Vector Database Settings with four presets: "No restriction," Low (≥.25), Medium (≥.50), High (≥.75) — [Chat Modes docs](https://docs.anythingllm.com/features/chat-modes)
- During chat, retrieval results are filtered using the workspace's `similarityThreshold` and `topN` values, and settings including temperature, history length, and similarity threshold are validated by `Workspace.validateFields` before being persisted — [DeepWiki: Workspace Model and Configuration](https://deepwiki.com/Mintplex-Labs/anything-llm/8.1-workspace-model-and-configuration)
- Workspaces are described as maintaining "isolated environments" for chat configuration (LLM provider, model, temperature, history) — [DeepWiki: Workspace System](https://deepwiki.com/Mintplex-Labs/anything-llm/8-workspace-system)

### Inferences
- Because `chatProvider`/`chatModel` are separate columns from `agentProvider`/`agentModel`, a workspace can run its normal chat on one LLM (e.g., a fast local Ollama model) while using a different, more capable model specifically when Agent Mode's tool-calling is invoked.
- `vectorSearchMode` with a default of `"default"` suggests at least one alternate retrieval strategy exists (likely a stricter/rerank-style mode), but its alternate value(s) were not confirmed in these sources — flagged as a gap below.
- The presence of `queryRefusalResponse` as a stored, customizable string confirms Query Mode's "no relevant info found" behavior is admin-configurable per workspace, not a hardcoded message.

### Gaps
- **Data/context isolation mechanics**: I could not directly confirm from a primary source (docs or code) exactly how vector data isolation between workspaces is implemented at the vector-DB layer (e.g., whether it's namespace-based per provider, separate collections/indexes, or a shared collection filtered by `vectorTag`/workspace ID metadata). The schema shows a `vectorTag` field on the workspace record, suggesting metadata-tag-based filtering is at least one mechanism, but this needs code-level confirmation in the vector DB provider files, which I did not fetch in this pass.
- **`vectorSearchMode` alternate values**: the default is `"default"` per the schema, but I did not find documentation enumerating other valid modes (e.g., rerank, hybrid search) — worth checking `server/utils/helpers/index.js` or the workspace update route validation logic directly.
- **Cloud/hosted tier tiering**: I found no evidence in current sources of a distinct "AnythingLLM Cloud" paid tier with different workspace limits vs. self-hosted; all settings appear identical across Docker and desktop app since AnythingLLM's primary distribution model is self-hosted OSS. This should be treated as "not confirmed" rather than "confirmed absent" — a targeted search of mintplexlabs.com pricing pages was not performed in this pass.

## What is the definitive CURRENT list of supported vector databases as of the latest release in 2026?

### Takeaway
The `server/utils/vectorDbProviders` directory on the `master` branch currently contains ten provider implementations: LanceDB (default, embedded/local), Astra DB, Chroma, Chroma Cloud, Milvus, PGVector, Pinecone, Qdrant, Weaviate, and Zilliz (Zilliz Cloud, the managed Milvus offering) — all under the same MIT-licensed OSS codebase, no paid-only vector DB options identified.

### Cited Findings
- Directory listing of `server/utils/vectorDbProviders` on GitHub `master` shows subfolders/files for: Astra, Chroma, Chroma Cloud, Lance, Milvus, PGVector, Pinecone, Qdrant, Weaviate, Zilliz, plus a shared `base.js` interface — [GitHub: vectorDbProviders](https://github.com/Mintplex-Labs/anything-llm/tree/master/server/utils/vectorDbProviders)

### Inferences
- LanceDB is very likely still the zero-config default (embedded, no external service needed), consistent with AnythingLLM's "works out of the box" positioning, though this specific "default" framing was not re-confirmed against a 2026-dated docs page in this pass — treat as a carryover from well-established prior knowledge rather than a freshly cited 2026 claim.
- All ten are exposed as OSS/self-hosted options with no indication any is gated behind a paid tier.

### Gaps
- I did not fetch a docs.anythingllm.com page enumerating vector databases with UI screenshots/setup instructions to corroborate the code-derived list with an official docs-side list — the code directory listing is treated as the primary, most current source per the task's own suggestion to check the codebase directly.
- No changelog entry was checked to see if any provider was added/removed very recently in 2026 (e.g., Chroma Cloud is a distinct entry from Chroma, suggesting a relatively recent split — exact addition date not confirmed).

## What is the definitive CURRENT list of embedding providers?

### Takeaway
The `server/utils/EmbeddingEngines` directory currently lists 14 embedding engine integrations, spanning the built-in native embedder, major commercial APIs, and self-hosted/open options.

### Cited Findings
- Directory listing of `server/utils/EmbeddingEngines` on GitHub `master` shows: Azure OpenAI, Cohere, Gemini, Generic OpenAI, Lemonade, LiteLLM, LM Studio, Local AI, Mistral, Native (the built-in "AnythingLLM Embedder"), Ollama, OpenAI, OpenRouter, and Voyage AI — [GitHub: EmbeddingEngines](https://github.com/Mintplex-Labs/anything-llm/tree/master/server/utils/EmbeddingEngines)

### Inferences
- "Native" corresponds to the built-in, no-external-dependency "AnythingLLM Embedder" referenced in the task's prompt — confirming that option still exists in the current codebase.
- The presence of both "Lemonade" and "OpenRouter" as dedicated embedding engine folders indicates newer additions beyond the commonly-cited older list (OpenAI/Azure/Ollama/LocalAI/LMStudio/Cohere/Voyage/LiteLLM/Generic OpenAI) — these two plus Gemini and Mistral appear to be more recent additions relative to older blog-post-era lists, though exact version/date of addition was not confirmed via changelog in this pass.

### Gaps
- Did not cross-check against docs.anythingllm.com's embedding provider setup docs or the CHANGELOG.md for exact version numbers when Lemonade, OpenRouter, Gemini, or Mistral embedding support was added.

## What is the definitive CURRENT list of document collectors/connectors?

### Takeaway
Confirmed directly from `collector/extensions/index.js` source code: the current connector set is GitHub/generic Git repo loader (`RepoLoader`, branch-aware), YouTube Transcript, Website Depth (recursive link crawler), Confluence, Drupal Wiki, Obsidian Vault, and Paperless-NGX, plus a "resync" mechanism for re-fetching previously connected sources. Generic web page scraping and raw text submission are handled by separate collector endpoints (not in the `extensions` folder). GitLab-specific handling is folded into the generic repo loader rather than a standalone extension file. No "sitemap" or "audio/video transcription" extension was found in this specific folder — audio transcription is handled elsewhere in the collector (via Whisper-based conversion of uploaded audio files, not as a URL-based "connector").

### Cited Findings
- `collector/extensions/index.js` imports and exposes these connector modules: `RepoLoader` (generic repo/branch loader — covers GitHub and, per community bug reports, GitLab), `YoutubeTranscript`, `WebsiteDepth`, `Confluence`, `DrupalWiki`, `ObsidianVault`, `PaperlessNgx`, plus a `resync` submodule for `RESYNC_METHODS` — [raw index.js](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/collector/extensions/index.js)
- The `collector/extensions` folder itself contains only `index.js` and a `resync/` subfolder (which in turn contains its own `index.js`) — the actual connector logic classes (`RepoLoader`, `ObsidianVault`, etc.) live in `collector/utils/extensions/` — [GitHub: collector/extensions](https://github.com/Mintplex-Labs/anything-llm/tree/master/collector/extensions)
- GitLab's connector "can pull issues in addition to code," and the `GitLabRepoLoader` supports fetching files, issues (including discussions), and wiki pages — per community/DeepWiki summary — [DeepWiki: Data Connectors](https://deepwiki.com/Mintplex-Labs/anything-llm/9.3-data-connectors); corroborated by GitHub issue discussion of the GitLab connector's behavior — [GitHub Issue #4571](https://github.com/Mintplex-Labs/anything-llm/issues/4571), [GitHub Issue #2315](https://github.com/Mintplex-Labs/anything-llm/issues/2315)
- Generic web scraping is handled via a `scrapeGenericUrl`-style endpoint, and raw text ingestion via a `/process-raw-text` endpoint — both are collector routes distinct from the `extensions` connector modules — [DeepWiki: Document Ingestion](https://deepwiki.com/Mintplex-Labs/anything-llm/9-document-ingestion)
- YouTube extraction pulls closed captions/transcripts, preferring human-transcribed tracks over auto-generated ones when available — [DeepWiki: Data Connectors](https://deepwiki.com/Mintplex-Labs/anything-llm/9.3-data-connectors)
- URL/URI download connector can "pull remote files (PDFs, Docx, etc.) directly into the WATCH_DIRECTORY" — [DeepWiki: Data Connectors](https://deepwiki.com/Mintplex-Labs/anything-llm/9.3-data-connectors)
- A third-party (non-official) Obsidian sync plugin also exists separately from AnythingLLM's own built-in Obsidian Vault connector — [tejasunku/anything-obsidian on GitHub](https://github.com/tejasunku/anything-obsidian) — this is NOT part of the official Mintplex Labs codebase and should not be conflated with the built-in `ObsidianVault` extension confirmed above.
- A community feature request for a dedicated Confluence connector (#1180, #690) predates confirmation that Confluence is now built in; the current `index.js` import of `Confluence` confirms it has since shipped — [Issue #1180](https://github.com/Mintplex-Labs/anything-llm/issues/1180), [Issue #690](https://github.com/Mintplex-Labs/anything-llm/issues/690), corroborated by the live source import.

### Inferences
- "Sitemap" as a distinct connector type (mentioned in the task's suggested list) does not appear as its own module in the current `extensions` folder; it may be folded into "Website Depth" (a recursive crawler) rather than existing as a separate sitemap-XML-parsing connector. This should be treated as **not confirmed present as a standalone feature** rather than confirmed absent, since I did not inspect `WebsiteDepth`'s implementation directly.
- Audio/video transcription appears to be a **file-processing capability** (via the collector's `convertAudioToWav` utility feeding a Whisper-based converter, confirmed by the `ACCEPTED_MIMES` audio types below) rather than a URL-based "connector" — i.e., users upload audio/video files rather than pointing AnythingLLM at a URL to scrape.

### Gaps
- Did not inspect `collector/utils/extensions/RepoLoader` source directly to confirm whether GitLab is a fully separate code path or truly shares the same loader class as GitHub — relying on secondary (issue-thread/DeepWiki) characterization here.
- Could not confirm whether "sitemap.xml" ingestion exists as a discrete, named feature anywhere in collector code — flagged as unconfirmed, not denied.
- Did not verify recent CHANGELOG.md entries for connector additions/removals in 2025-2026 (e.g., whether Paperless-NGX or Drupal Wiki are recent additions) — would need a direct fetch of CHANGELOG.md to date these precisely.

## Are chunking settings exposed in the UI, and what are the default/configurable parameters? How does citation work?

### Takeaway
Chunking is exposed to end users as a "Text Splitter & Chunking" workspace setting with two configurable fields — Text Chunk Size and Text Chunk Overlap — and re-embeds documents when changed. The underlying splitter is a RecursiveCharacterTextSplitter with default chunkSize/chunkOverlap of 1000/20 characters. Full official documentation of the citation/source-attribution UI behavior in chat was not found in the sources reached this session — flagged as a gap requiring a targeted docs fetch of the citations page.

### Cited Findings
- AnythingLLM's document ingestion pipeline splits text using a `RecursiveCharacterTextSplitter` with a fixed default `chunkSize`/`chunkOverlap` of 1000/20 characters — [DeepWiki: Text Splitting and Chunking](https://deepwiki.com/Mintplex-Labs/anything-llm/6.3-text-splitting-and-chunking)
- The workspace/admin UI exposes this under "Text Splitter & Chunking" with two fields: "Text Chunk Size" and "Text Chunk Overlap" — changing either requires re-processing (re-embedding) already-ingested documents — sourced from community discussion/blog summary — [GitHub Issue #490 (Chunking and Text Splitter customization)](https://github.com/Mintplex-Labs/anything-llm/issues/490)
- A chunk size is capped in guidance at up to 1000 characters, with automatic constraint enforcement based on the selected embedder model's token/context limits — [community summary via web search, unverified primary source]
- An open feature request (#6364) asks for "structure-aware chunking option (per heading/topic)" for structured documents like SOPs, indicating this is NOT yet a built-in feature as of the request's filing — i.e., only fixed-size recursive character chunking is currently supported, not semantic/structure-aware chunking — [GitHub Issue #6364](https://github.com/Mintplex-Labs/anything-llm/issues/6364)
- A separate bug report (#4116) notes a discrepancy where "embedded chunk is lesser than the chunk created from documents," suggesting chunk-size enforcement interacts with embedder-side truncation in practice — [GitHub Issue #4116](https://github.com/Mintplex-Labs/anything-llm/issues/4116)

### Inferences
- Because #6364 (structure-aware/per-heading chunking) is still an open feature request, current AnythingLLM chunking is size-based only (character count with overlap), not semantic or heading-aware — this is a meaningful limitation to flag relative to some competing RAG platforms.

### Gaps
- **Citations/source attribution behavior**: I was unable to fetch a page that explicitly documents whether AnythingLLM shows inline citations (e.g., numbered references in the answer text) vs. a simple "Sources" list of retrieved document chunks appended below a chat response. The `docs.anythingllm.com/chatting-with-documents/introduction` page was fetched but explicitly did not address this topic in the returned content. This is a clear gap requiring a follow-up fetch of a docs page specifically about citations (a page likely exists at a URL like `docs.anythingllm.com/features/citations` or similar, not fetched in this session due to tool-call budget).
- Whether chunk size/overlap limits or presets differ between embedder providers (e.g., whether Voyage AI or Cohere impose different max chunk sizes than the Native embedder) was not confirmed.

## Full list of supported document ingestion file formats, and any file-size/count limits, self-host vs. hosted differences

### Takeaway
The collector's `ACCEPTED_MIMES` constant (as summarized from `collector/utils/constants.js`) confirms a broad format list spanning plain text/markup, Office documents, PDF/ebook formats, audio, and some image/video types — though `.doc` (legacy binary Word) is explicitly NOT yet supported. No specific file-size or document-count limit, nor any self-host-vs-hosted distinction, was found in the sources reached this session.

### Cited Findings
- Supported formats reconstructed from `ACCEPTED_MIMES` in `collector/utils/constants.js`: **Text/markup** — `.txt`, `.md`, `.org`, `.adoc`, `.rst`, `.csv`, `.json`, `.html`; **Office** — `.docx`, `.pptx`, `.xlsx`, `.odt`, `.odp`; **Other document formats** — `.pdf`, `.mbox`, `.epub`; **Audio** — `.wav`, `.mp3`, `.ogg`, `.oga`, `.opus`, `.m4a`, `.webm`; **Image** — `.png`, `.jpg`, `.webp`; **Video** — `.mp4`, `.mpeg` — [source file, summarized](https://github.com/Mintplex-Labs/anything-llm/blob/master/collector/utils/constants.js) (note: I obtained this via an AI-summarized fetch rather than reading the raw file's exact array contents directly, since the summarization tool processed the raw content — see Gaps)
- Legacy `.doc` (pre-2007 binary Word format) support is explicitly noted as "pending development," i.e., not currently supported — [same summarized source]
- A `server/storage/documents/DOCUMENTS.md` file exists in the repo describing document storage format, referenced via search results but not fetched directly this session — [GitHub: DOCUMENTS.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/server/storage/documents/DOCUMENTS.md)
- AnythingLLM's document guide broadly describes drag-and-drop upload via the chat window `+` icon, without enumerating exact formats on that particular docs page — [Using Documents in AnythingLLM](https://docs.anythingllm.com/chatting-with-documents/introduction)

### Inferences
- Given the collector runs Whisper-based audio conversion (`convertAudioToWav` directory confirmed in the collector's top-level folder structure), the audio/video formats listed are plausible as inputs to a speech-to-text pipeline rather than being embedded as raw audio — consistent with "audio/video transcription" as a document-ingestion path rather than a live connector.

### Gaps
- **File size / document count limits**: no source found in this session specifying a maximum upload file size or per-workspace document count limit (self-hosted deployments are typically limited only by local disk/vector-DB capacity and any reverse-proxy upload limits, but this was not explicitly documented in sources reached).
- **Self-host vs. hosted/cloud differences**: I found no evidence of a distinct "AnythingLLM Cloud" hosted product with different limits from self-hosted Docker/desktop in the sources reached this session. This is treated as an open gap, not a confirmed "no such tier exists" — a dedicated check of mintplexlabs.com or app.anythingllm.com marketing pages would be needed to close this gap definitively.
- The exact raw contents of `ACCEPTED_MIMES` were relayed through an AI summarization step rather than read verbatim by me — treat the specific format list above as high-confidence but not a verbatim-verified quote of the source array; a direct raw-file read would be needed to fully verify (e.g., to check for additional formats like `.tsv` or `.log` that a summary might drop).
