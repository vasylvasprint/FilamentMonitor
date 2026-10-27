"""Scraper for MonoFilament (monofilament.com.ua).

Uses OpenCart HPM endpoint for exact real-time prices, variant weights, and live stock.
NO FALLBACK OR MOCK PRICES ALLOWED.
"""
import asyncio
import logging
import re
from typing import List, Dict, Set
from bs4 import BeautifulSoup
import httpx

from scrapers.base import ScraperBase
from scrapers.utils import parse_price, extract_weight_g, clean_url, normalize_color, normalize_plastic_type

logger = logging.getLogger(__name__)

SUBCATEGORIES = [
    ("PETG", "https://monofilament.com.ua/ua/products/standartnye-materialy/copet/"),
    ("PLA", "https://monofilament.com.ua/ua/products/standartnye-materialy/pla/"),
    ("ABS", "https://monofilament.com.ua/ua/products/standartnye-materialy/abs/"),
    ("ABS", "https://monofilament.com.ua/ua/products/standartnye-materialy/abs-plus/"),
    ("Nylon", "https://monofilament.com.ua/ua/products/inzhinernye-plastiki/"),
]


class MonofilamentScraper(ScraperBase):
    async def scrape(self) -> List[Dict]:
        products: List[Dict] = []
        seen_pids: Set[str] = set()

        async with httpx.AsyncClient(verify=False, timeout=15, follow_redirects=True) as client:
            for default_type, cat_url in SUBCATEGORIES:
                # Scan up to 3 pages per category
                for page_num in range(1, 4):
                    url = f"{cat_url}?page={page_num}" if page_num > 1 else cat_url
                    try:
                        r = await client.get(url)
                        if r.status_code != 200:
                            break
                        soup = BeautifulSoup(r.text, "lxml")
                        cards = soup.select(".product-layout")
                        if not cards:
                            break

                        category_pids = []
                        for card in cards:
                            # 1) Option buttons (HPM)
                            buttons = card.select(".hpm-button")
                            if buttons:
                                for b in buttons:
                                    pid = b.get("data-pid")
                                    if pid and pid not in seen_pids:
                                        seen_pids.add(pid)
                                        category_pids.append(pid)
                            else:
                                # 2) Product without options
                                inp = card.select_one("input[name='product_id']")
                                pid = inp.get("value") if inp else None
                                if not pid:
                                    wl = card.select_one("button[onclick*='wishlist.add']")
                                    if wl:
                                        m = re.search(r"wishlist\.add\('(\d+)'\)", wl.get("onclick", ""))
                                        if m:
                                            pid = m.group(1)
                                if pid and pid not in seen_pids:
                                    seen_pids.add(pid)
                                    category_pids.append(pid)

                        # Fetch JSON for all collected PIDs concurrently in chunks
                        chunk_size = 15
                        for i in range(0, len(category_pids), chunk_size):
                            chunk = category_pids[i:i + chunk_size]
                            tasks = [
                                client.get(f"https://monofilament.com.ua/index.php?route=extension/module/hpmrr/product_json&pid={p}")
                                for p in chunk
                            ]
                            resps = await asyncio.gather(*tasks, return_exceptions=True)
                            for resp in resps:
                                if isinstance(resp, Exception) or resp.status_code != 200:
                                    continue
                                try:
                                    json_data = resp.json().get("success", {})
                                    if not json_data:
                                        continue

                                    raw_name = json_data.get("name", "").strip()
                                    if not raw_name:
                                        continue

                                    # Weight extraction
                                    weight = extract_weight_g(raw_name)
                                    if weight is None or weight > 1100:
                                        # Strict filtering: ignore > 1.1 kg
                                        continue

                                    # Real price from server
                                    price_raw = json_data.get("special") or json_data.get("price")
                                    price = parse_price(str(price_raw)) if price_raw else None
                                    if not price or price <= 0:
                                        # Strict rule: NO fallback or guessing allowed
                                        continue

                                    # Real stock
                                    qty = int(json_data.get("quantity") or 0)
                                    in_stock = qty > 0

                                    href = json_data.get("href")
                                    if href:
                                        href = href.replace("&amp;", "&")

                                    thumb = json_data.get("thumb")

                                    snap = self._build_snapshot(
                                        product_name=f"MonoFilament {raw_name}",
                                        price_uah=price,
                                        weight_g=weight,
                                        product_url=href,
                                        image_url=thumb,
                                        in_stock=in_stock,
                                        brand="MonoFilament",
                                        plastic_type=default_type,
                                    )
                                    if snap:
                                        products.append(snap)
                                except Exception as err:
                                    logger.debug(f"[MonoFilament] Error parsing JSON: {err}")

                    except Exception as e:
                        logger.warning(f"[MonoFilament] Error scraping {url}: {e}")

        logger.info(f"[MonoFilament] Total strictly parsed real products: {len(products)}")
        return products
