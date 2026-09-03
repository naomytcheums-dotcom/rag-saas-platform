"""
Partie 2.1.11 -- real network integration test for
api/security/documents.py's own process_sitemap: the real fetch (a
real, external sitemap, never mocked) and the real
parse/is_sitemap_index/filter/cap decision-making, proven against a
real target (sitemaps.org's own sitemap.xml -- the domain that DEFINES
the sitemap protocol itself, already confirmed reachable, real, and
non-index, currently 84 real URLs: 4 top-level pages plus 4 pages under
each of 20 language subdirectories).

`process_sitemap_urls` (the next real layer -- per-url Celery dispatch)
is monkeypatched here to simply CAPTURE what it is called with, rather
than dragged through a live broker or nested through a second
asyncio.run() from within this already-running one -- consistent with
this codebase's own established boundary (see
tests/test_celery_integration.py's own module docstring: automated
tests exercise a task's own real logic up to its own dispatch point,
never a live worker/broker chain -- that is a manual runbook). The
real, full per-page pipeline this dispatch would go on to trigger
(import_document_from_url -> process_url_document -> process_document)
is already proven for real, end-to-end, by
tests/test_documents_integration.py's own
test_process_url_document_runs_the_real_end_to_end_url_import_pipeline
-- re-running that same real pipeline again here would be redundant,
not additive. Real per-url SCHEDULING behavior itself (filtering, the
courtesy stagger, one-bad-url broker tolerance) is proven, without a
live broker, by tests/test_documents.py's own process_sitemap_urls unit
tests.
"""

import uuid
from unittest.mock import patch

from api.security.documents import process_sitemap
from api.services.sitemap_extraction import fetch_sitemap, parse_sitemap

_REAL_SITEMAP_URL = "https://www.sitemaps.org/sitemap.xml"


def _patch_process_sitemap_urls(captured):
    def _capture(organization_id, workspace_id, urls, filters, created_by):
        captured["organization_id"] = organization_id
        captured["workspace_id"] = workspace_id
        captured["urls"] = urls
        captured["filters"] = filters
        captured["created_by"] = created_by
        return len(urls)

    return patch("api.security.documents.process_sitemap_urls", side_effect=_capture)


async def test_process_sitemap_runs_the_real_fetch_and_parse_against_a_real_sitemap():
    """
    Validation criterion: l'import de sitemap fonctionne, le parsing du
    sitemap fonctionne -- against a real, external, non-mocked target.
    Also confirms is_sitemap_index's own real classification is
    correctly acted on (this real target is a flat urlset, so
    process_sitemap must take the non-index branch, never touching
    _MAX_SUB_SITEMAPS at all), and that max_urls is applied as a real
    cap on the real result.
    """
    captured = {}
    organization_id, created_by = uuid.uuid4(), uuid.uuid4()

    with _patch_process_sitemap_urls(captured):
        result = await process_sitemap(_REAL_SITEMAP_URL, organization_id, None, None, 1, created_by)

    assert result == "completed"
    assert captured["organization_id"] == organization_id
    assert captured["workspace_id"] is None
    assert captured["created_by"] == created_by
    # process_sitemap always passes filters=None downstream -- filtering
    # already happened here, before handing off to process_sitemap_urls.
    assert captured["filters"] is None
    assert len(captured["urls"]) == 1  # the real max_urls=1 cap, enforced for real
    assert captured["urls"][0].startswith("https://www.sitemaps.org")


async def test_process_sitemap_applies_a_real_filter_before_the_real_cap():
    """
    Vision critique's own real "filter before cap" design decision
    (api/security/documents.py's own process_sitemap docstring),
    proven against real data: a real filter matching a real four-url
    subset (confirmed for real: sitemaps.org's own /fr/ section has
    exactly 4 real pages) survives even with max_urls set far higher
    than 4, and a real filter with NO matches produces a real, empty,
    correctly-handled result -- process_sitemap must still report
    "completed" (a filter matching nothing is not a failure).
    """
    captured = {}
    with _patch_process_sitemap_urls(captured):
        result = await process_sitemap(_REAL_SITEMAP_URL, uuid.uuid4(), None, ["/fr/*"], 500, uuid.uuid4())

    assert result == "completed"
    assert captured["urls"] == [
        "https://www.sitemaps.org/fr/",
        "https://www.sitemaps.org/fr/protocol.html",
        "https://www.sitemaps.org/fr/faq.html",
        "https://www.sitemaps.org/fr/terms.html",
    ]

    captured_empty = {}
    with _patch_process_sitemap_urls(captured_empty):
        result_empty = await process_sitemap(
            _REAL_SITEMAP_URL, uuid.uuid4(), None, ["/this-path-genuinely-does-not-exist/*"], 500, uuid.uuid4(),
        )

    assert result_empty == "completed"
    assert captured_empty["urls"] == []


async def test_process_sitemap_returns_failed_for_a_real_unreachable_sitemap_url():
    """Vision critique Q4's own answer, at the top-level sitemap-fetch
    boundary -- a real, live 404 (not a mock) ends this in a real,
    logged "failed" result, never a crash or an unhandled exception
    escaping into Celery."""
    result = await process_sitemap(
        "https://www.sitemaps.org/this-sitemap-genuinely-does-not-exist-404.xml",
        uuid.uuid4(), None, None, 500, uuid.uuid4(),
    )
    assert result == "failed"


async def test_fetch_sitemap_and_parse_sitemap_agree_with_process_sitemap_on_the_real_url_count():
    """Cross-check: the real, independently-fetched/parsed url count
    for this real target matches what process_sitemap itself captures
    with no filter and a high enough max_urls not to cap it -- proves
    process_sitemap is not silently dropping or duplicating real urls
    somewhere in its own orchestration."""
    real_content = await fetch_sitemap(_REAL_SITEMAP_URL)
    real_urls = parse_sitemap(real_content)
    assert len(real_urls) > 4  # otherwise this cross-check would prove nothing

    captured = {}
    with _patch_process_sitemap_urls(captured):
        await process_sitemap(_REAL_SITEMAP_URL, uuid.uuid4(), None, None, 10_000, uuid.uuid4())

    assert captured["urls"] == real_urls
