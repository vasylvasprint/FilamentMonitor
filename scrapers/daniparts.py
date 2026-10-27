"""Scraper for DaniParts (daniparts.com).

Uses DaniParts REST API for exact prices, stock, weights, and product URLs.
NO FALLBACK OR MOCK PRICES ALLOWED.
"""
import asyncio
import logging
from typing import List, Dict
import httpx

from scrapers.base import ScraperBase
from scrapers.utils import parse_price, extract_weight_g, clean_url

logger = logging.getLogger(__name__)

GROUPS = [
    ("PETG", 6850),
    ("PLA", 6851),
    ("TPU", 6852),
    ("Nylon", 6848),
    ("Nylon", 6849),
]

HEADERS = {
    "authorization": "Token cf1a6793f669327a0417fbfed80e574f2ad8d26c",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "accept": "application/json, text/plain, */*",
    "referer": "https://daniparts.com/",
}


class DanipartsScraper(ScraperBase):
    async def scrape(self) -> List[Dict]:
        products: List[Dict] = []
        seen_articles = set()

        async with httpx.AsyncClient(headers=HEADERS, verify=False, timeout=15) as client:
            for default_type, group_id in GROUPS:
                # Fetch up to 2 pages (50 items per page)
                for page in range(1, 3):
                    payload = {
                        "product_group_id": group_id,
                        "page_number": page,
                        "customer_id": 4890,
                        "sell_currency_id": 2,
                        "rows_per_page": 50,
                        "show_mode": "ON_STOCK",
                    }
                    try:
                        r = await client.post("https://api.daniparts.com/api/search-by-product-group/", json=payload)
                        if r.status_code != 200:
                            break
                        data = r.json()
                        results = data.get("results", [])
                        if not results:
                            break

                        for item in results:
                            art = item.get("article_clean") or item.get("article")
                            if art in seen_articles:
                                continue
                            seen_articles.add(art)

                            name = item.get("name", "").strip()
                            if not name:
                                continue

                            # Price
                            price_val = item.get("price")
                            if not price_val or float(price_val) <= 0:
                                continue
                            price = float(price_val)

                            # Brand
                            brand_raw = item.get("brand")
                            brand = brand_raw if brand_raw else "DaniParts"

                            # Weight
                            weight = extract_weight_g(name) or 1000
                            if weight > 1100:
                                continue

                            # Stock
                            in_stock = not item.get("all_warehouses_is_empty", False)

                            # URL
                            url = f"https://daniparts.com/product/{brand}/{art}" if art else None

                            # Image
                            images = item.get("images", {})
                            img_url = images.get("thumb") if isinstance(images, dict) else None

                            snap = self._build_snapshot(
                                product_name=name,
                                price_uah=price,
                                weight_g=weight,
                                product_url=url,
                                image_url=img_url,
                                in_stock=in_stock,
                                brand=brand,
                                plastic_type=default_type,
                            )
                            if snap:
                                products.append(snap)
                    except Exception as e:
                        logger.warning(f"[DaniParts] Error querying group {group_id}: {e}")

        logger.info(f"[DaniParts] Total scraped: {len(products)}")
        return products
