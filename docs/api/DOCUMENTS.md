# Documents API

Backed by `api/routers/documents.py`. See [Documents](../user/DOCUMENTS.md)
for the end-user-facing behavior and [Chunking](../advanced/CHUNKING.md)/
[Embeddings](../advanced/EMBEDDINGS.md) for the processing pipeline.

## Upload

```
POST /organizations/{org_id}/documents
Content-Type: multipart/form-data
```

Returns the created document resource with a `status` of `processing`.
Processing (ingestion, chunking, embedding) happens in the background —
poll the document or listen for a webhook event (see
[Webhooks](WEBHOOKS.md)) for completion.

## List

```
GET /organizations/{org_id}/documents
```

Paginated — see [Pagination](PAGINATION.md).

## Get / Delete

Once created, a document is addressed directly by id (not nested under
`/organizations/{org_id}/`, same convention as conversations):

```
GET    /documents/{document_id}
DELETE /documents/{document_id}
DELETE /documents/{document_id}/permanent
```

Deleting a document removes its chunks/embeddings from search
immediately; it does not retroactively alter citations already present
in past generated answers.

## Status, versions, and reindexing

```
GET  /documents/{document_id}/status
GET  /documents/{document_id}/progress
GET  /documents/{document_id}/progress/stream
GET  /documents/{document_id}/versions
POST /documents/{document_id}/reindex
```

See also `api/routers/reindex_schedules.py` for scheduled (rather than
on-demand) reindexing.

## Batch upload

```
POST /organizations/{org_id}/documents/batch
```

See `api/routers/batch_jobs.py` for tracking a batch job's progress.
