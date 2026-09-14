# Media

The platform can process images, audio, and video as media assets, not
just text documents. See [`docs/media/OVERVIEW.md`](../media/OVERVIEW.md)
for the full technical overview.

## Uploading media

Upload from **Documents** the same way as a text document — the
platform detects the media type and routes it through the appropriate
processing pipeline: [Images](../media/IMAGES.md),
[Audio](../media/AUDIO.md), [Video](../media/VIDEO.md).

## What happens to an image

- A textual description is generated (vision) so the image content is
  searchable like any other document.
- Objects in the image are detected (local inference, YOLOv8) and
  recorded.
- A CLIP embedding is generated for visual search.

## Visual search

From **Documents → Search**, switch to the visual search tab to find
images either by uploading a similar image or by typing a text
description — matching is done by real semantic similarity (CLIP
embeddings + a faiss index), not just keyword matching against
generated descriptions. See [`docs/media/SEARCH.md`](../media/SEARCH.md).

## Audio and video

Audio and video assets are processed for transcription/description
depending on configuration — see [`docs/media/AUDIO.md`](../media/AUDIO.md)
and [`docs/media/VIDEO.md`](../media/VIDEO.md).
