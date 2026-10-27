"""Scraper for 3D Plast (3dplast.ua). Static HTML."""
import logging
from typing import List, Dict
from bs4 import BeautifulSoup
from scrapers.base import ScraperBase
from scrapers.utils import parse_price, extract_weight_g

logger = logging.getLogger(__name__)

CATEGORIES = [
    ("PETG", "https://3dplast.ua/filament-petg-124/"),
    ("PLA", "https://3dplast.ua/filament-pla-121/"),
    ("ABS", "https://3dplast.ua/filament-abs-126/"),
]


class Plast3dScraper(ScraperBase):
    async def scrape(self) -> List[Dict]:
        products = []
        seen_urls = set()

        for default_type, cat_url in CATEGORIES:
            html = await self._fetch_html_static(cat_url)
            if not html:
                html = await self._fetch_html_playwright(cat_url)
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            cards = soup.select("div.archive-wrap__list--products > div.item")
            for card in cards:
                try:
                    title_el = card.select_one("a.item-title, a[title]")
                    if not title_el:
                        continue
                    name = title_el.get_text(strip=True)
                    if not name or len(name) < 4:
                        continue

                    href = title_el.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://3dplast.ua" + href
                    if href in seen_urls:
                        continue
                    if href:
                        seen_urls.add(href)

                    # Extract price strictly from price element
                    price_el = card.select_one(".item-price, .price, [class*='price']")
                    price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None
                    if not price or price <= 0:
                        continue

                    in_stock = True
                    stock_el = card.select_one(".item-stock")
                    if stock_el and "немає" in stock_el.get_text(strip=True).lower():
                        in_stock = False

                    img_el = card.select_one("img")
                    img_url = img_el.get("src") if img_el else None

                    weight = extract_weight_g(name) or 850
                    if weight > 1100:
                        continue

                    snap = self._build_snapshot(
                        product_name=name,
                        price_uah=price,
                        weight_g=weight,
                        product_url=href,
                        image_url=img_url,
                        in_stock=in_stock,
                        brand="3D Plast",
                        plastic_type=default_type,
                    )
                    if snap:
                        products.append(snap)
                except Exception as e:
                    logger.debug(f"[3D Plast] Error parsing card: {e}")

        logger.info(f"[3D Plast] Total scraped: {len(products)}")
        return products
