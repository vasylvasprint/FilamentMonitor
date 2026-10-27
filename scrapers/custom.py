"""Generic scraper for user-added store URLs — Playwright with multi-pattern heuristics."""
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

from scrapers.base import ScraperBase
from scrapers.utils import parse_price, extract_weight_g

logger = logging.getLogger(__name__)

# Ordered patterns to try — pick whichever finds the most products
PATTERNS = [
    {"card": ".product-layout", "name": ".caption h4 a", "price": ".price"},
    {"card": ".product-item", "name": ".product-title a", "price": ".price-new"},
    {"card": ".good", "name": ".good__title a", "price": ".good__price"},
    {"card": ".js-product", "name": ".js-store-prod-name", "price": ".js-store-prod-price"},
    {"card": "article.product", "name": "h2 a", "price": "[class*='price']"},
    {"card": ".catalog-item", "name": "h3 a", "price": ".price"},
]

# Additional fallback selectors for prices and names when patterns fail
FALLBACK_NAME_SELECTORS = [
    "h1 a", "h2 a", "h3 a", "h4 a",
    ".product-title a", ".product-name a",
    ".title a", ".name a",
]
FALLBACK_PRICE_SELECTORS = [
    ".price", ".price-new", ".current-price", '[class*="price"]',
    ".cost", ".amount",
]


class CustomScraper(ScraperBase):
    """Generic scraper for user-defined URLs using heuristic pattern matching."""

    async def scrape(self) -> List[Dict]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(f"[{self.store_name}] Playwright not installed")
            return []

        results: List[Dict] = []

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(locale="uk-UA")
                page = await context.new_page()

                try:
                    await page.goto(self.category_url, timeout=30000, wait_until="networkidle")
                except Exception as e:
                    logger.warning(f"[{self.store_name}] Page load warning: {e}")

                # Scroll to trigger lazy loads
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

                html = await page.content()
                await browser.close()

            results = self._parse_best_pattern(html)
        except Exception as e:
            logger.error(f"[{self.store_name}] Playwright scrape error: {e}", exc_info=True)

        logger.info(f"[{self.store_name}] Total products scraped: {len(results)}")
        return results

    def _parse_best_pattern(self, html: str) -> List[Dict]:
        """Try all patterns, return results from the one that finds the most products."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        base_url = self._get_base_url()
        best_results: List[Dict] = []

        for pattern in PATTERNS:
            try:
                candidates = self._apply_pattern(soup, pattern, base_url)
                logger.info(
                    f"[{self.store_name}] Pattern {pattern['card']!r}: {len(candidates)} products"
                )
                if len(candidates) > len(best_results):
                    best_results = candidates
            except Exception as e:
                logger.debug(f"[{self.store_name}] Pattern error for {pattern}: {e}")

        if not best_results:
            logger.warning(f"[{self.store_name}] No pattern found products; trying fallback heuristic")
            best_results = self._fallback_parse(soup, base_url)

        return best_results

    def _apply_pattern(
        self,
        soup,
        pattern: Dict[str, str],
        base_url: str,
    ) -> List[Dict]:
        """Apply a single card/name/price pattern and return matched snapshots."""
        products: List[Dict] = []
        cards = soup.select(pattern["card"])
        if not cards:
            return []

        for card in cards:
            try:
                name_el = card.select_one(pattern["name"])
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name:
                    continue

                href = name_el.get("href", "")
                if not href:
                    a_el = card.select_one("a[href]")
                    href = a_el.get("href", "") if a_el else ""
                if href and not href.startswith("http"):
                    href = urljoin(base_url, href)
                product_url = href or None

                price_el = card.select_one(pattern["price"])
                price = parse_price(price_el.get_text(strip=True)) if price_el else None

                img_el = card.select_one("img")
                image_url = None
                if img_el:
                    image_url = img_el.get("src") or img_el.get("data-src")
                    if image_url and not image_url.startswith("http"):
                        image_url = urljoin(base_url, image_url)

                snap = self._build_snapshot(
                    product_name=name,
                    price_uah=price,
                    weight_g=None,
                    product_url=product_url,
                    image_url=image_url,
                    in_stock=True,
                )
                if snap:
                    products.append(snap)
            except Exception as e:
                logger.debug(f"[{self.store_name}] Card parse error: {e}")

        return products

    def _fallback_parse(self, soup, base_url: str) -> List[Dict]:
        """
        Last-resort: find any elements that look like product names + prices
        using a broad sweep of common selectors.
        """
        products: List[Dict] = []

        # Try to find name elements
        name_elements = []
        for sel in FALLBACK_NAME_SELECTORS:
            name_elements = soup.select(sel)
            if name_elements:
                break

        if not name_elements:
            logger.warning(f"[{self.store_name}] Fallback: no name elements found")
            return []

        for name_el in name_elements:
            try:
                name = name_el.get_text(strip=True)
                if not name or len(name) < 3:
                    continue

                href = name_el.get("href", "")
                if href and not href.startswith("http"):
                    href = urljoin(base_url, href)
                product_url = href or None

                # Try to find price near the element
                price = None
                parent = name_el.parent
                for _ in range(4):
                    if parent is None:
                        break
                    for price_sel in FALLBACK_PRICE_SELECTORS:
                        price_el = parent.select_one(price_sel)
                        if price_el:
                            price = parse_price(price_el.get_text(strip=True))
                            if price:
                                break
                    if price:
                        break
                    parent = getattr(parent, "parent", None)

                snap = self._build_snapshot(
                    product_name=name,
                    price_uah=price,
                    weight_g=None,
                    product_url=product_url,
                    image_url=None,
                    in_stock=True,
                )
                if snap:
                    products.append(snap)
            except Exception as e:
                logger.debug(f"[{self.store_name}] Fallback parse error: {e}")

        return products

    def _get_base_url(self) -> str:
        """Extract scheme + netloc from category_url."""
        parsed = urlparse(self.category_url)
        return f"{parsed.scheme}://{parsed.netloc}"


if __name__ == "__main__":
    import asyncio

    async def main():
        s = CustomScraper(
            store_id=99,
            store_name="Custom Test",
            category_url="https://monofilament.com.ua/products/standartnye-materialy/",
        )
        results = await s.scrape()
        for r in results[:5]:
            print(r)

    asyncio.run(main())
