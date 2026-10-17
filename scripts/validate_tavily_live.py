#!/usr/bin/env python
"""Real validation of 5.2.2 (web search, Tavily) with the product's `web_search`.

    RUN_LIVE_VENDOR_VALIDATION=1 TAVILY_API_KEY=... python scripts/validate_tavily_live.py

One basic search with one result (1 Tavily credit). Also checks that a wrong key is a WebSearchError carrying Tavily's 401.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _live_vendor as live  # noqa: E402


async def main() -> int:
    live.require_opt_in("Tavily web search", "1 Tavily credit")
    search = live.product("api.tools.web_search")
    config = live.product("api.config")
    report = live.Report("web_search")
    if not live.have("TAVILY_API_KEY"):
        report.skipped("tavily", "TAVILY_API_KEY is not in the process environment")
        return report.finish()

    async def one():
        result = await search.web_search("what is retrieval augmented generation", search_depth="basic", max_results=1)
        items = search.extract_web_search_results(result)
        assert items and items[0]["url"].startswith("http") and items[0]["content"], result
        assert "retriev" in search.format_web_search_results(result).lower()
        return {"url": items[0]["url"]}

    await report.check("tavily", one)

    async def wrong_key():
        config.settings.TAVILY_API_KEY = "tvly-invalid-key-for-validation"
        try:
            await search.web_search("x", max_results=1)
        except search.WebSearchError as exc:
            assert "401" in str(exc), exc
            return {"mapped": "WebSearchError(401)"}
        raise AssertionError("a wrong key was accepted")

    await report.check("tavily-wrong-key", wrong_key)
    return report.finish()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
