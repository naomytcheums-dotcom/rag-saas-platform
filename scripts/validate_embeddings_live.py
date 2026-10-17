#!/usr/bin/env python
"""Real validation of 4.2.1-4.2.3 (OpenAI, Voyage AI, Cohere embeddings) with the product's `get_embeddings`.

    RUN_LIVE_VENDOR_VALIDATION=1 OPENAI_API_KEY=... VOYAGE_API_KEY=... COHERE_API_KEY=... python scripts/validate_embeddings_live.py

Embeds two short words per vendor that has a key (a few tokens) and checks the vector size against the catalogue the product relies on for its pgvector columns.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _live_vendor as live  # noqa: E402

VENDORS = {"openai": ("OPENAI_EMBEDDING_API_KEY", "OPENAI_API_KEY"), "voyage": ("VOYAGE_API_KEY",), "cohere": ("COHERE_API_KEY",)}


async def main() -> int:
    live.require_opt_in("OpenAI, Voyage AI, Cohere embeddings", "a few tokens, well under 1 cent")
    embeddings = live.product("api.services.embedding_providers")
    config = live.product("api.config")
    report = live.Report("embeddings")
    for provider, variables in VENDORS.items():
        present = [v for v in variables if live.have(v)]
        if not present:
            report.skipped(provider, f"none of {' / '.join(variables)} is in the process environment")
            continue
        if provider == "openai" and not live.have("OPENAI_EMBEDDING_API_KEY"):
            config.settings.OPENAI_EMBEDDING_API_KEY = os.environ["OPENAI_API_KEY"]

        async def one(provider=provider):
            vectors = await embeddings.get_embeddings(["alpha", "bravo"], provider=provider)
            model = {"openai": config.settings.OPENAI_EMBEDDING_MODEL, "voyage": config.settings.VOYAGE_EMBEDDING_MODEL, "cohere": config.settings.COHERE_EMBEDDING_MODEL}[provider]
            expected = embeddings.get_embedding_dimensions(provider, model.removeprefix(f"{provider}/"))
            assert len(vectors) == 2 and len(vectors[0]) == expected, f"got {len(vectors[0])} dimensions, the catalogue says {expected}"
            assert vectors[0] != vectors[1]
            return {"model": model, "dimensions": len(vectors[0])}

        await report.check(provider, one)
        if provider == "voyage" or provider == "openai":
            async def wrong_key(provider=provider):
                keys = {"openai": "OPENAI_EMBEDDING_API_KEY", "voyage": "VOYAGE_API_KEY"}
                setattr(config.settings, keys[provider], "invalid-key-for-validation")
                try:
                    await embeddings.get_embeddings(["x"], provider=provider)
                except embeddings.EmbeddingAuthenticationError:
                    return {"mapped": "EmbeddingAuthenticationError"}
                raise AssertionError("a wrong key was not reported as an authentication error")
            await report.check(f"{provider}-wrong-key", wrong_key)
    return report.finish()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
