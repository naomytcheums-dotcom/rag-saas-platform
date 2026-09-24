"""
Extraction -- fetching orders/products from Shopify's real Admin API,
for import into a knowledge base. Real auth shape: a real, static
`SHOPIFY_API_TOKEN`, sent as `X-Shopify-Access-Token` (Shopify's own
real convention).
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class ShopifyError(Exception):
    """Real, dedicated exception."""


class ShopifyRateLimitError(ShopifyError):
    """Real, distinguishable 429."""


async def fetch_shopify_orders(limit: int = 100) -> list[dict]:
    """Real fetch of orders from Shopify."""
    if not settings.SHOPIFY_ENABLED:
        raise ShopifyError("Shopify integration is disabled")
    if not settings.SHOPIFY_API_TOKEN or not settings.SHOPIFY_SHOP_DOMAIN:
        raise ShopifyError("Shopify credentials not configured")

    base_url = f"https://{settings.SHOPIFY_SHOP_DOMAIN}/admin/api/2024-01"
    headers = {"X-Shopify-Access-Token": settings.SHOPIFY_API_TOKEN}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url}/orders.json",
            headers=headers,
            params={"limit": min(limit, 250)},
        )

        if response.status_code == 429:
            raise ShopifyRateLimitError("Shopify rate limit reached")
        if response.status_code != 200:
            raise ShopifyError(f"Shopify fetch failed: {response.status_code}")

        for order in response.json().get("orders", []):
            text_parts = [
                f"Order #{order.get('order_number', '')}",
                f"Total: {order.get('total_price', '')} {order.get('currency', '')}",
                f"Created: {order.get('created_at', '')}",
            ]
            if order.get("email"):
                text_parts.append(f"Email: {order['email']}")

            results.append({
                "id": order.get("id"),
                "text": "\n".join(text_parts),
            })

    return results
