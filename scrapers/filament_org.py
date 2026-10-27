"""Scraper for Filament Market (filament.org.ua). Tilda platform."""
import logging
from typing import List, Dict
from bs4 import BeautifulSoup
from scrapers.base import ScraperBase
from scrapers.utils import parse_price, extract_weight_g

logger = logging.getLogger(__name__)

CATEGORIES = [
    ("PETG", "https://filament.org.ua/petg"),
    ("PLA", "https://filament.org.ua/ecopla"),
    ("PLA", "https://filament.org.ua/silkpla"),
    ("PLA", "https://filament.org.ua/plamatt"),
    ("PLA", "https://filament.org.ua/magicpla"),
    ("TPU", "https://filament.org.ua/tpu"),
    ("ABS", "https://filament.org.ua/abs"),
]


class FilamentOrgScraper(ScraperBase):
    async def scrape(self) -> List[Dict]:
        products = []
        seen_keys = set()

        for default_type, cat_url in CATEGORIES:
            html = await self._fetch_html_playwright(cat_url, wait_selector=".js-product")
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")

            # 1) Check main single product with options on this page
            single = soup.select_one(".js-product-single, .t744, .t754")
            if single:
                title_el = single.select_one(".js-product-name, .t-name, .t-title, h1")
                base_name = title_el.get_text(strip=True) if title_el else f"Filament {default_type}"
                price_el = single.select_one(".js-store-prod-price, .t-store__card__price, .t-price")
                base_price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None

                # Check if there are color select options
                options = single.select("select option")
                valid_options = [opt for opt in options if opt.get_text(strip=True) and "виберіть" not in opt.get_text(strip=True).lower()]

                if valid_options and base_price:
                    for opt in valid_options:
                        color_name = opt.get_text(strip=True)
                        is_disabled = opt.has_attr("disabled") or "disabled" in opt.get("class", [])
                        in_stock = not is_disabled
                        full_name = f"Filament Market {base_name} {color_name} 1 кг"
                        key = (full_name, cat_url)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)

                        snap = self._build_snapshot(
                            product_name=full_name,
                            price_uah=base_price,
                            weight_g=1000,
                            product_url=cat_url,
                            in_stock=in_stock,
                            brand="Filament Market",
                            plastic_type=default_type,
                            color=color_name,
                        )
                        if snap:
                            products.append(snap)
                elif base_price:
                    full_name = f"Filament Market {base_name} 1 кг"
                    key = (full_name, cat_url)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        snap = self._build_snapshot(
                            product_name=full_name,
                            price_uah=base_price,
                            weight_g=1000,
                            product_url=cat_url,
                            in_stock=True,
                            brand="Filament Market",
                            plastic_type=default_type,
                        )
                        if snap:
                            products.append(snap)

            # 2) Cards in grid
            cards = soup.select(".t-store__card")
            for card in cards:
                try:
                    title_el = card.select_one(".t-store__card__title, .js-store-prod-name, .t-name")
                    name = title_el.get_text(strip=True) if title_el else card.get("data-product-name")
                    if not name:
                        continue

                    price_el = card.select_one(".js-store-prod-price, .t-store__card__price")
                    price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None
                    if not price and card.get("data-product-price"):
                        price = parse_price(card.get("data-product-price"))
                    if not price or price <= 0:
                        continue

                    href = card.get("data-product-url") or cat_url
                    inv = int(card.get("data-product-inv") or 1)
                    in_stock = inv > 0

                    full_name = f"Filament Market {name} 1 кг"
                    key = (full_name, href)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    snap = self._build_snapshot(
                        product_name=full_name,
                        price_uah=price,
                        weight_g=1000,
                        product_url=href,
                        image_url=card.get("data-product-img"),
                        in_stock=in_stock,
                        brand="Filament Market",
                        plastic_type=default_type,
                    )
                    if snap:
                        products.append(snap)
                except Exception as e:
                    logger.debug(f"[Filament.org.ua] Error card: {e}")

        logger.info(f"[Filament.org.ua] Total scraped: {len(products)}")
        return products
