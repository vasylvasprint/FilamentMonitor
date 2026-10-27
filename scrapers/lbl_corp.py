"""Scraper for LBL Corp (lbl-corp.com). Cartum platform."""
import logging
from typing import List, Dict
from bs4 import BeautifulSoup
from scrapers.base import ScraperBase
from scrapers.utils import parse_price

logger = logging.getLogger(__name__)

CATEGORIES = [
    "https://lbl-corp.com/copet-petg-plastik-08kg/",
    "https://lbl-corp.com/pla-plastik-08-kg/",
    "https://lbl-corp.com/plastyk-dlia-3d-druku/",
]


class LblCorpScraper(ScraperBase):
    async def scrape(self) -> List[Dict]:
        products = []
        for cat_url in CATEGORIES:
            html = await self._fetch_html_playwright(cat_url, wait_selector=".catalogCard-box")
            if not html:
                html = await self._fetch_html_static(cat_url)
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            cards = soup.select(".catalogCard-box, div[data-id]")
            for card in cards:
                try:
                    title_el = card.select_one(".catalogCard-title a, a[title]")
                    if not title_el:
                        continue
                    name = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://lbl-corp.com" + href

                    price_el = card.select_one(".catalogCard-price")
                    if not price_el:
                        price_el = card.select_one(".price, [class*='price']")
                    price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None

                    in_stock = True
                    avail_el = card.select_one(".catalogCard-availability, .catalogCard-status")
                    if avail_el and any(w in avail_el.get_text(strip=True).lower() for w in ["немає", "out of stock"]):
                        in_stock = False

                    img_el = card.select_one(".catalogCard-img, img")
                    img_url = img_el.get("src") if img_el else None
                    if img_url and not img_url.startswith("http"):
                        img_url = "https://lbl-corp.com" + img_url

                    snap = self._build_snapshot(
                        product_name=name,
                        price_uah=price,
                        product_url=href,
                        image_url=img_url,
                        in_stock=in_stock,
                        brand="LBL Corp",
                    )
                    if snap:
                        products.append(snap)
                except Exception as e:
                    logger.debug(f"[LBL Corp] Error parsing card: {e}")

        logger.info(f"[LBL Corp] Total scraped: {len(products)}")
        return products
