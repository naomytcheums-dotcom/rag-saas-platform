# Multi-modal search

## One real, consolidated endpoint, not three

The literal Partie 22 spec names `POST /media/search`,
`/media/search/visual`, and `/media/search/audio` as 3 separate
routes. The real underlying search
(`api.services.media.search_media`) is ONE function over ONE chunk
table, filterable by `media_type` -- 3 routes for the same real query
with a different default filter would be redundant surface, not a
real functional difference (this session's own standing "correct
DeepSeek's own incoherent/duplicate asks" instruction). `POST
/media/search` takes `{query, media_type?, top_k?}`; `media_type`
narrows to `image`/`audio`/`video` (the literal spec's "visual"/"audio"
search), omitted searches everything.

## How it works

Reuses the exact real infrastructure `api/security/documents.py`'s
`process_document` already uses for document search, just filtered to
media-derived chunks:

1. The real query is embedded with the SAME model
   (`organization_settings.embedding_model`) every document search
   uses.
2. Real cosine similarity (`api.services.retrieval_pipeline.
   cosine_similarities`, made public specifically for this reuse) is
   computed against every `DocumentChunk` row that has a real
   `media_asset_id` (i.e., every real transcript/description/OCR/frame
   chunk), scoped to the caller's own organization.
3. Results are ranked and returned with the SOURCE media asset
   (filename, media_type) and which real extraction produced the
   matched text (`media_transcript`, `media_image_description`,
   `media_image_ocr`, `media_frame_description`, `media_video_summary`).

## Why one shared index, not a second vector store

This part's own pre-build audit found a real precedent worth
following directly: document text already goes through
`chunk_text -> clean_text/normalize_text -> generate_embeddings ->
DocumentChunk`. Building a second, parallel vector index for media
would mean dual-writing/maintaining two stores that could drift out
of sync, for no real functional gain -- `document_chunks.document_id`
was made nullable and a new `media_asset_id` column added instead
(migration `0104`), so a single real search pipeline covers both
documents and media.

## Cross-organization isolation

`POST /media/search` resolves the caller's own organization
memberships server-side and only ever searches THOSE organizations'
chunks -- never a caller-supplied `organization_id` a client could
tamper with.
