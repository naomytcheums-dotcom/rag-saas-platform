#!/usr/bin/env python
"""Real validation of 4.1.1-4.1.4 (Claude, GPT, Gemini, Mistral through LiteLLM) with the product's own `chat_completion_with_usage`.

    RUN_LIVE_VENDOR_VALIDATION=1 ANTHROPIC_API_KEY=... OPENAI_API_KEY=... GEMINI_API_KEY=... MISTRAL_API_KEY=... python scripts/validate_llm_live.py

Sends one 8-token completion per vendor that has a key in the process environment (a fraction of a cent each). Also checks that a WRONG key is
reported as an authentication error (the retry/error mapping against the real vendor), with a deliberately invalid key for the first vendor present.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _live_vendor as live  # noqa: E402

KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "mistral": "MISTRAL_API_KEY"}


async def main() -> int:
    live.require_opt_in("Anthropic, OpenAI, Google Gemini, Mistral", "well under 1 cent")
    providers = live.product("api.services.llm_providers")
    config = live.product("api.config")
    report = live.Report("llm")
    first_present = None
    for provider, variable in KEYS.items():
        if not live.have(variable):
            report.skipped(provider, f"{variable} is not in the process environment")
            continue
        first_present = first_present or provider

        async def one(provider=provider):
            result = await providers.chat_completion_with_usage([{"role": "user", "content": "Reply with the single word: pong"}], provider=provider, max_tokens=8, max_retries=1)
            assert result["content"], "empty answer"
            assert result["usage"] and result["usage"]["prompt_tokens"], "no usage reported"
            return {"model": result["model"], "answer": result["content"][:40], "usage": result["usage"]}

        await report.check(provider, one)
    if first_present:
        async def wrong_key():
            setattr(config.settings, KEYS[first_present], "invalid-key-for-validation")
            try:
                await providers.chat_completion([{"role": "user", "content": "hi"}], provider=first_present, max_tokens=4, max_retries=0)
            except providers.LLMAuthenticationError:
                return {"mapped": "LLMAuthenticationError"}
            raise AssertionError("a wrong key was not reported as an authentication error")
        await report.check(f"{first_present}-wrong-key", wrong_key)
    return report.finish()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
