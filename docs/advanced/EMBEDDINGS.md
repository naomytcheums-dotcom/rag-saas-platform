# Embeddings

## Text embeddings

The baseline embedding model, validated in the original single-tenant
demo, is `sentence-transformers/all-MiniLM-L6-v2` — a fast, free, local
model chosen deliberately as a baseline rather than the most capable
available option (see
[`src/README.md`](../../src/README.md#tech-stack) for the tradeoff
discussion). The multi-tenant platform's embedding configuration
(`api/services/embedding_config.py`) supports selecting a provider/model
per organization rather than hardcoding this baseline everywhere.

## Provider gaps

Not every provider supports every embedding operation the platform
might want — `embedding_config.py` documents unsupported
provider/operation combinations explicitly, following the same "fail
fast with a real, named error, never a silent fallback" pattern used
elsewhere (e.g. fine-tuning's `ProviderNotSupportedError`, see
[Fine-tuning](FINE_TUNING.md)).

## Visual embeddings (CLIP)

Images use a separate embedding path: CLIP
(`openai/clip-vit-base-patch32`), producing embeddings in a shared
image/text space so a text query can match an image and vice versa —
see [Media & Vision](MEDIA_AND_VISION.md).

## Storage

Text embeddings are stored in PostgreSQL via `pgvector`; CLIP
embeddings are stored on `MediaAsset.clip_embedding` and indexed with a
faiss `IndexFlatIP` for similarity search — see
[Database](../developer/DATABASE.md).
