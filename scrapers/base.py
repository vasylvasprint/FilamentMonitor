"""Base scraper class and shared scraping infrastructure."""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import re

import httpx
from bs4 import BeautifulSoup

from config import HTTP_HEADERS, HTTP_TIMEOUT, PLAYWRIGHT_TIMEOUT, PLAYWRIGHT_WAIT_AFTER_LOAD
from scrapers.utils import clean_url, extract_weight_g, normalize_plastic_type, extract_hardness, normalize_color, compute_prices, parse_price

logger = logging.getLogger(__name__)


class ScraperBase(ABC):
    """Abstract base class for all filament scrapers."""

    def __init__(self, store_id: int, store_name: str, category_url: str):
        self.store_id = store_id
        self.store_name = store_name
        self.category_url = clean_url(category_url)

    @abstractmethod
    async def scrape(self) -> List[Dict]:
        """Scrape all products. Returns list of price snapshot dicts."""
        ...

    def _get_default_weight(self) -> int:
        """Return store-specific default weight when weight is not stated in product title."""
        name_lower = self.store_name.lower()
        if "lbl" in name_lower:
            return 750
        elif "plexiwire" in name_lower:
            return 900
        elif "3dplast" in name_lower:
            return 850
        return 1000

    def _build_snapshot(
        self,
        product_name: str,
        price_uah: Optional[float],
        weight_g: Optional[int] = None,
        product_url: Optional[str] = None,
        image_url: Optional[str] = None,
        in_stock: bool = True,
        brand: Optional[str] = None,
        color: Optional[str] = None,
        plastic_type: Optional[str] = None,
        hardness: Optional[str] = None,
    ) -> Optional[Dict]:
        """Build a normalized price snapshot dict. Filters out weight > 1100g."""
        from config import MAX_WEIGHT_G

        if not product_name or not price_uah or price_uah <= 0:
            return None

        # Auto-extract weight from title / URL if not explicitly provided
        if weight_g is None:
            weight_g = extract_weight_g(product_name)
            if weight_g is None and product_url:
                weight_g = extract_weight_g(product_url)
            # If still None, assign store default weight
            if weight_g is None:
                weight_g = self._get_default_weight()

        # Hard filtering: strictly filter out spools > 1.1 kg (1100g)
        if weight_g > MAX_WEIGHT_G:
            return None

        # Auto-detect plastic type
        if plastic_type is None or plastic_type == "—":
            plastic_type = normalize_plastic_type(product_name)

        # Auto-detect color
        if color is None or color == "—" or color == "nan":
            color = normalize_color(product_name)

        # Hardness for TPU
        if hardness is None and plastic_type == "TPU":
            hardness = extract_hardness(product_name)

        # Compute prices
        price_per_kg, price_per_g = compute_prices(price_uah, weight_g)

        # Ensure clean brand
        if not brand or brand.lower() == "nan":
            brand = self.store_name

        return {
            "store_id": self.store_id,
            "product_name": product_name.strip(),
            "brand": brand,
            "plastic_type": plastic_type or "PLA",
            "color": color if color and color != "nan" else "—",
            "weight_g": weight_g,
            "hardness": hardness,
            "price_uah": round(price_uah, 2),
            "price_per_kg": price_per_kg,
            "price_per_g": price_per_g,
            "product_url": clean_url(product_url) if product_url else None,
            "in_stock": 1 if in_stock else 0,
            "image_url": image_url,
        }

    async def _fetch_html_static(self, url: str) -> Optional[str]:
        """Fetch page HTML using httpx."""
        try:
            async with httpx.AsyncClient(
                headers=HTTP_HEADERS,
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
                verify=False,
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
                return None
        except Exception as e:
            logger.warning(f"[{self.store_name}] HTTP error for {url}: {e}")
            return None

    async def _fetch_html_playwright(self, url: str, wait_selector: Optional[str] = None) -> Optional[str]:
        """Fetch page HTML using Playwright."""
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=HTTP_HEADERS["User-Agent"],
                    locale="uk-UA",
                )
                page = await context.new_page()
                await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=8000)
                    except Exception:
                        pass
                await page.wait_for_timeout(PLAYWRIGHT_WAIT_AFTER_LOAD)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await page.wait_for_timeout(1000)
                html = await page.content()
                await browser.close()
                return html
        except Exception as e:
            logger.warning(f"[{self.store_name}] Playwright error for {url}: {e}. Falling back to static HTTP fetch.")
            return await self._fetch_html_static(url)
