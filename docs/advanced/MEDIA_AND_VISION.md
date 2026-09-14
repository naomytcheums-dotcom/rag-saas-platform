# Media & Vision

Full documentation: [`docs/media/OVERVIEW.md`](../media/OVERVIEW.md),
[`IMAGES.md`](../media/IMAGES.md), [`AUDIO.md`](../media/AUDIO.md),
[`VIDEO.md`](../media/VIDEO.md), [`SEARCH.md`](../media/SEARCH.md).

## Image processing

Uploaded images go through three real, local processing steps:

1. **Vision description** — a textual description is generated so
   image content is searchable alongside text documents.
2. **Object detection** — local inference via YOLOv8 (`ultralytics`),
   not a third-party API call.
3. **CLIP embedding** — `openai/clip-vit-base-patch32`, enabling
   semantic visual search (see below).

## Visual search

CLIP embeddings live in a shared image/text space, so both
image-to-image and text-to-image search are real semantic operations,
not keyword matching against generated descriptions — indexed with a
faiss `IndexFlatIP` for similarity ranking. Confirmed end-to-end against
real test images during development (distinct images correctly ranked
by actual semantic similarity, not just by shared caption words). See
[Search](../media/SEARCH.md).

## Audio and video

Processed for transcription/description depending on configuration —
see [Audio](../media/AUDIO.md) and [Video](../media/VIDEO.md).

## Vision-in-documents

Images embedded within uploaded documents (not just standalone image
uploads) also go through vision description, wired into the same
document-processing pipeline — off by default, enabled per
organization.
