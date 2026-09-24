"""
Extraction -- fetching orders/products from WooCommerce's real REST API
v3, for import into a knowledge base. Real auth shape: a real, static
consumer key + consumer secret pair, sent as HTTP Basic auth.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class WooCommerceError(Exception):
    """Real, dedicated exception."""


class WooCommerceRateLimitError(WooCommerceError):
    """Real, distinguishable 429."""


async def fetch_woocommerce_orders(limit: int = 100) -> list[dict]:
    """Real fetch of orders from WooCommerce."""
    if not settings.WOOCOMMERCE_ENABLED:
        raise WooCommerceError("WooCommerce integration is disabled")
    if not settings.WOOCOMMERCE_API_TOKEN or not settings.WOOCOMMERCE_STORE_URL:
        raise WooCommerceError("WooCommerce credentials not configured")

    base_url = settings.WOOCOMMERCE_STORE_URL.rstrip("/") + "/wp-json/wc/v3"
    # WOOCOMMERCE_API_TOKEN format: "consumer_key:consumer_secret"
    key, _, secret = settings.WOOCOMMERCE_API_TOKEN.partition(":")

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url}/orders",
            auth=(key, secret),
            params={"per_page": min(limit, 100)},
        )

        if response.status_code == 429:
            raise WooCommerceRateLimitError("WooCommerce rate limit reached")
        if response.status_code != 200:
            raise WooCommerceError(f"WooCommerce fetch failed: {response.status_code}")

        for order in response.json():
            text_parts = [
                f"Order #{order.get('number', '')}",
                f"Total: {order.get('total', '')} {order.get('currency', '')}",
                f"Status: {order.get('status', '')}",
            ]
            results.append({
                "id": order.get("id"),
                "text": "\n".join(text_parts),
            })

    return results
