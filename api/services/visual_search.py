"""Partie 22 (3rd finalization) -- real CLIP-based visual search:
text-to-image (`POST /media/search/visual`) and image-to-image
(`POST /media/search/similar`), on top of `faiss-cpu` for the actual
nearest-neighbor ranking. Distinct from `api.services.media.search_media`
(the existing LLM-description/transcript TEXT search over
`DocumentChunk`) -- CLIP embeds an image and a text query into the
SAME real vector space, so "a photo of a bus" can match a bus PHOTO
directly, something a text-only embedding of an LLM-written
description could only ever approximate.

**Real, honest degradation, same category as OCR/ffmpeg/YOLO**:
`CLIPNotAvailableError` distinguishes "the real `transformers` CLIP
model couldn't be loaded" (no network on first download, or the
`transformers`/`torch` install itself is broken) from any other real
failure -- `api.services.media`'s own image-processing step catches it
and leaves `MediaAsset.clip_embedding` `NULL` rather than failing the
whole asset, exactly like YOLO/vision-LLM failures already do."""

import io
import logging
import threading

import numpy as np

from api.config import settings

logger = logging.getLogger(__name__)

_model = None
_processor = None
_model_lock = threading.Lock()


class CLIPNotAvailableError(RuntimeError):
    pass


def _get_clip():
    global _model, _processor
    if not settings.VISUAL_SEARCH_ENABLED:
        raise CLIPNotAvailableError("visual search is disabled (VISUAL_SEARCH_ENABLED=False)")
    if _model is not None:
        return _model, _processor
    with _model_lock:
        if _model is None:
            try:
                import os

                os.environ.setdefault("USE_TF", "0")
                from transformers import CLIPModel, CLIPProcessor
            except ImportError as exc:
                raise CLIPNotAvailableError("the real 'transformers' CLIP classes are not available") from exc
            try:
                _model = CLIPModel.from_pretrained(settings.VISUAL_SEARCH_CLIP_MODEL)
                _processor = CLIPProcessor.from_pretrained(settings.VISUAL_SEARCH_CLIP_MODEL)
            except Exception as exc:  # noqa: BLE001 -- a real download/load failure (e.g. no network) is just as real a "not available" case
                raise CLIPNotAvailableError(f"could not load the real CLIP model '{settings.VISUAL_SEARCH_CLIP_MODEL}': {exc}") from exc
    return _model, _processor


def _normalize(vector: np.ndarray) -> list[float]:
    """L2-normalizes so a plain dot product IS cosine similarity --
    both `embed_image_clip`/`embed_text_clip` below and every stored
    embedding share this same real convention, so FAISS's
    `IndexFlatIP` (inner product) below is genuinely computing cosine
    similarity, not an unnormalized, harder-to-compare raw dot product."""
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector.tolist()
    return (vector / norm).tolist()


def _pooled_projection(output):
    """Hardening Mission (§21, real-bug audit) -- a real, confirmed
    breaking change in `transformers` (reproduced directly against the
    installed 5.16.1, not assumed): `CLIPModel.get_image_features`/
    `get_text_features` no longer return a plain, already-projected
    tensor the way every published usage example (including this
    library's own docstring) still shows -- they return the full
    `BaseModelOutputWithPooling` from the underlying vision/text
    submodel, with its own `.pooler_output` field OVERWRITTEN in place
    to hold the real, projected joint-embedding-space vector (the exact
    value `get_image_features`/`get_text_features` used to return
    directly). Indexing `features[0]` on that object used to silently
    grab `.last_hidden_state`'s own first row instead -- a real, raw,
    per-patch/per-token hidden state, never a real image/text embedding
    at all, which is why `embed_image_clip`/`embed_text_clip` used to
    return a wrong-shaped, wrong-SPACE vector that could never actually
    compare image to text (the cosine-similarity-breaking shape
    mismatch an end-to-end test caught). Falls back to treating `output`
    as a plain tensor when `.pooler_output` doesn't exist, so this
    keeps working unchanged against an older `transformers` release
    that still returns the real tensor directly."""
    pooled = getattr(output, "pooler_output", output)
    return pooled[0].detach().numpy()


def embed_image_clip(image_bytes: bytes) -> list[float]:
    """Real CLIP image embedding -- used both to INDEX a real image at
    processing time and to embed a real query image for
    `search_similar`."""
    from PIL import Image

    model, processor = _get_clip()
    with Image.open(io.BytesIO(image_bytes)) as image:
        rgb_image = image.convert("RGB")
        inputs = processor(images=rgb_image, return_tensors="pt")
        output = model.get_image_features(**inputs)
    return _normalize(_pooled_projection(output))


def embed_text_clip(text: str) -> list[float]:
    """Real CLIP text embedding -- the SAME real vector space as
    `embed_image_clip` above, which is the entire point of CLIP: a real
    text query and a real image can be compared directly."""
    model, processor = _get_clip()
    inputs = processor(text=[text], return_tensors="pt", padding=True, truncation=True)
    output = model.get_text_features(**inputs)
    return _normalize(_pooled_projection(output))


def rank_by_clip_similarity(query_embedding: list[float], candidate_embeddings: list[list[float]], top_k: int) -> list[tuple[int, float]]:
    """Real nearest-neighbor ranking via `faiss.IndexFlatIP` -- returns
    `(candidate_index, score)` pairs, most similar first. A real,
    small, in-memory index built fresh per real query (this
    organization's own real image count is small enough that a
    persistent index isn't yet justified -- the same honest,
    documented scale note `api.services.retrieval_pipeline`'s own
    in-memory cosine ranking already makes for text search)."""
    import faiss

    matrix = np.asarray(candidate_embeddings, dtype="float32")
    faiss.normalize_L2(matrix)  # defensive -- embeddings are already normalized at embed time
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)

    query_matrix = np.asarray([query_embedding], dtype="float32")
    faiss.normalize_L2(query_matrix)
    scores, indices = index.search(query_matrix, min(top_k, len(candidate_embeddings)))

    return [(int(idx), float(score)) for idx, score in zip(indices[0], scores[0]) if idx != -1]
