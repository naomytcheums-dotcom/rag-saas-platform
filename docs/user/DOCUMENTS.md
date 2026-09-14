# Documents

## Uploading

Go to **Documents → Upload**. Common formats (PDF, Markdown, plain
text, and others depending on your deployment's configuration) are
supported. Files are uploaded to object storage and processed in the
background.

## Processing pipeline

Once uploaded, a document goes through:

1. **Ingestion** — text extraction and cleanup.
2. **Chunking** — splitting into retrieval-sized passages (see
   [Chunking](../advanced/CHUNKING.md) for the technical detail).
3. **Embedding** — each chunk is embedded for semantic search.

A document's status reflects where it is in this pipeline; it becomes
searchable once processing completes.

## External sources

Besides direct upload, documents can be pulled in from connected
external sources (Slack, Teams, Discord, n8n, Airbyte, and others) — see
[Integrations](../developer/INTEGRATIONS.md).

## Reindexing

If retrieval settings change, documents can be reindexed — either
on-demand or on a schedule configured by an admin.

## Deleting a document

Deleting a document removes it and its chunks/embeddings from search.
This does not retroactively change citations in already-generated past
answers.
