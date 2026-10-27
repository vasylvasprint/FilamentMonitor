"""Scraper for Pochatok Filament (pochatok-filament.com / pochatok-filament.com.ua).

NO FALLBACK OR MOCK PRICES ALLOWED.
"""
import asyncio
import logging
from typing import List, Dict
from bs4 import BeautifulSoup
import httpx

from scrapers.base import ScraperBase
from scrapers.utils import parse_price, extract_weight_g, clean_url

logger = logging.getLogger(__name__)

URLS = [
    "https://pochatok-filament.com/ua/product_list",
    "https://pochatok-filament.com/ua/product_list/page_2",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
}


class PochatokScraper(ScraperBase):
    async def scrape(self) -> List[Dict]:
        products: List[Dict] = []
        seen_urls = set()

        async with httpx.AsyncClient(headers=HEADERS, verify=False, timeout=15, follow_redirects=True) as client:
            for cat_url in URLS:
                try:
                    r = await client.get(cat_url)
                    if r.status_code != 200:
                        continue
                    soup = BeautifulSoup(r.text, "lxml")
                    cards = soup.select("[data-product-id]")
                    if not cards:
                        break

                    for card in cards:
                        try:
                            title_el = card.select_one("a.cs-goods-title, .cs-product-gallery__title a")
                            if not title_el:
                                continue
                            name = title_el.get_text(strip=True)
                            if not name or len(name) < 4:
                                continue

                            href = title_el.get("href", "")
                            if href and not href.startswith("http"):
                                href = "https://pochatok-filament.com" + href
                            if href in seen_urls:
                                continue
                            if href:
                                seen_urls.add(href)

                            # Price
                            price_el = card.select_one(".cs-goods-price__value, .price, [class*='price']")
                            price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None
                            if not price or price <= 0:
                                continue

                            # Weight
                            weight = extract_weight_g(name)
                            if weight is None:
                                weight = 1000
                            if weight > 1250:
                                continue

                            in_stock = True
                            card_text = card.get_text(" ", strip=True).lower()
                            if any(w in card_text for w in ["немає", "немає в наявності", "out of stock"]):
                                in_stock = False

                            img_el = card.select_one("img.cs-product-gallery__img, img")
                            img_url = img_el.get("src") if img_el else None

                            snap = self._build_snapshot(
                                product_name=name,
                                price_uah=price,
                                weight_g=weight,
                                product_url=href,
                                image_url=img_url,
                                in_stock=in_stock,
                                brand="Pochatok",
                                plastic_type="PLA",
                            )
                            if snap:
                                products.append(snap)
                        except Exception as e:
                            logger.debug(f"[Pochatok] Error parsing card: {e}")

                except Exception as e:
                    logger.warning(f"[Pochatok] HTTP error for {cat_url}: {e}")

        logger.info(f"[Pochatok] Total scraped: {len(products)}")
        return products
