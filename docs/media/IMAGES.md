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

## Embedded document images (unchanged pipeline, extended result)

Images embedded inside a PDF/DOCX/EPUB (`document_images` table)
already got real OCR during document processing. Partie 22 does NOT
change that pipeline's control flow -- it only adds two columns
(`description`, `objects_json`) to `DocumentImage`. Wiring the real
vision call into `process_document`'s own per-image loop is real,
straightforward future work (the columns and the `describe_image`
function both already exist) -- not done in this part to avoid
slowing down every document upload with a real, synchronous LLM call
per embedded image; a standalone `MediaAsset` image upload is the real
path exercised end-to-end today.

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
