# Tutorial: Build Your First Assistant

## 1. Upload documents

Go to **Documents → Upload** and add a handful of source files (PDF or
Markdown work well to start). Wait for each to reach `ready` status —
see [Documents](../user/DOCUMENTS.md).

## 2. Ask a question

Go to **Chat → New conversation** and ask something the uploaded
documents can answer. Check the citations on the response — they should
point to the actual source passages, not a generic answer — see
[Citations](../user/CITATIONS.md).

## 3. Create a configured agent

Go to **Admin → Agents → New agent**. Give it:

- A system prompt describing its role (e.g. "You are a support
  assistant for Acme's product docs. Be concise, always cite sources.")
- A tool allowlist (start with none/minimal — see
  [Custom Tools](../developer/CUSTOM_TOOLS.md) if you need more later).

## 4. Chat with your agent

Back in **Chat**, select your new agent from the agent picker and ask
the same question again. Compare the tone/behavior against the default
assistant.

## Next

- [Upload & Query Documents](UPLOAD_AND_QUERY_DOCUMENTS.md) for more
  detail on the ingestion pipeline.
- [Embed the Widget](EMBED_THE_WIDGET.md) to put this assistant on a
  website.
