# Images

## Upload

`POST /organizations/{org_id}/media` with any `image/*` file (up to
`MULTIMODAL_MAX_IMAGE_SIZE_MB`, default 10MB). Creates a real, `pending`
`MediaAsset` row and schedules real Celery processing
(`api/tasks/media.py::process_media_asset_task`) -- a broker hiccup
never fails the upload itself, same reasoning as document upload's own
`schedule_document_processing`.

## Processing (`api/services/media.py::process_media_asset`)

1. **OCR** -- real Tesseract via `api.services.ocr.ocr_image_bytes`
   (reused as-is). A missing Tesseract binary degrades gracefully
   (`OCRNotAvailableError` caught, logged, `ocr_text` stays `None`) --
   the asset still completes.
2. **Vision description + object tagging** -- one real call to
   `describe_image`, which sends the image to a vision-capable LLM
   (`VISION_PROVIDER`/`VISION_MODEL`, default `openai`/`gpt-4o`) via
   the SAME `chat_completion`/litellm this codebase already uses for
   every other LLM call. The prompt asks for a real, structured JSON
   response (`description`, `objects`, `tags`); a model that doesn't
   obey the JSON instruction still has its raw text kept as the
   description (an honest degradation, not a discarded result).
3. **RAG indexing** -- `ocr_text` and `description` are each chunked/
   cleaned/normalized/embedded exactly like document text, and stored
   as real `DocumentChunk` rows (`media_asset_id` set, `document_id`
   `NULL`), tagged `metadata_json.source` = `media_image_ocr` /
   `media_image_description`.

## Embedded document images (finalization -- now wired, off by default)

Images embedded inside a PDF/DOCX/EPUB (`document_images` table)
already got real OCR during document processing. `process_document`'s
own per-image loop now ALSO calls the real vision pipeline
(`api.security.documents.describe_embedded_image_if_enabled`, a small,
directly-testable wrapper around `api.services.media.describe_image`,
imported lazily to avoid a circular import), storing the real
description/objects into the SAME `DocumentImage.description`/
`objects_json` columns a standalone image upload uses.

**Real, but OFF by default**
(`settings.MULTIMODAL_DESCRIBE_DOCUMENT_IMAGES=False`) -- a real,
synchronous vision-LLM call per embedded image would add real latency
and real per-image cost to EVERY document upload, for every
organization, unconditionally. Same "real but gated" pattern as
`AB_TEST_AUTO_DECIDE`/`OTEL_ENABLED`: an operator opts in once vision
costs/latency are acceptable for their own deployment. Same real,
honest degradation as OCR right above it in that loop -- any real
provider failure logs a warning and leaves `description`/`objects_json`
`NULL`, never aborts the document.

## Endpoints

- `GET /media/{id}` / `GET /media/{id}/status` -- the asset, including
  `description`/`ocr_text`/`objects_json`/`tags_json`.
- `GET /media/{id}/description` -- a real, documented alias of
  `GET /media/{id}` (same payload) for a caller that only cares about
  the description.
- `GET /media/{id}/file` -- real, authenticated, chunked proxy to the
  image bytes (never a direct/public S3 URL, same pattern as document
  preview).
- `POST /media/{id}/process` -- re-run processing synchronously
  on demand.
