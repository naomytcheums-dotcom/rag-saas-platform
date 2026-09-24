"""Real tests for scripts/loadtest.py (P2 #10, session SSRF épinglé).

These test the script's own logic (percentile computation, report
shape) without actually hitting a live server -- the script itself is
a dev/ops tool, not part of the runtime API.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import loadtest  # noqa: E402


def test_report_shape_contains_all_percentiles():
    async def _run():
        with patch("loadtest.httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            return await loadtest.run_loadtest("http://test", total_requests=20, concurrency=5, timeout=5.0)

    report = asyncio.run(_run())
    assert report["succeeded"] == 20
    assert report["failed"] == 0
    for key in ("p50_ms", "p95_ms", "p99_ms", "min_ms", "max_ms", "mean_ms", "throughput_rps"):
        assert key in report


def test_report_counts_http_errors():
    async def _run():
        with patch("loadtest.httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            return await loadtest.run_loadtest("http://test", total_requests=10, concurrency=2, timeout=5.0)

    report = asyncio.run(_run())
    assert report["succeeded"] == 0
    assert report["failed"] == 10
    assert "sample_errors" in report


def test_report_counts_transport_errors():
    async def _run():
        with patch("loadtest.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=RuntimeError("connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            return await loadtest.run_loadtest("http://test", total_requests=5, concurrency=1, timeout=5.0)

    report = asyncio.run(_run())
    assert report["succeeded"] == 0
    assert report["failed"] == 5
    assert any("connection refused" in e for e in report["sample_errors"])
