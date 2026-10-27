# scrapers/__init__.py
from scrapers.monofilament import MonofilamentScraper
from scrapers.plast3d import Plast3dScraper
from scrapers.ukr3d import Ukr3dScraper
from scrapers.epic3d import Epic3dScraper
from scrapers.smart3d import Smart3dScraper
from scrapers.filament_org import FilamentOrgScraper
from scrapers.lbl_corp import LblCorpScraper
from scrapers.plexiwire import PlexiwireScraper
from scrapers.daniparts import DanipartsScraper
from scrapers.pochatok import PochatokScraper
from scrapers.custom import CustomScraper

SCRAPER_MAP = {
    "monofilament": MonofilamentScraper,
    "plast3d": Plast3dScraper,
    "ukr3d": Ukr3dScraper,
    "epic3d": Epic3dScraper,
    "smart3d": Smart3dScraper,
    "filament_org": FilamentOrgScraper,
    "lbl_corp": LblCorpScraper,
    "plexiwire": PlexiwireScraper,
    "daniparts": DanipartsScraper,
    "pochatok": PochatokScraper,
    "custom": CustomScraper,
}


async def run_scraper(store: dict) -> list:
    """Run the appropriate scraper for a store dict from DB."""
    import logging
    logger = logging.getLogger(__name__)
    scraper_key = store.get("scraper", "custom")
    cls = SCRAPER_MAP.get(scraper_key, CustomScraper)
    try:
        scraper = cls(
            store_id=store["id"],
            store_name=store["name"],
            category_url=store["category_url"],
        )
        results = await scraper.scrape()
        logger.info(f"[{store['name']}] Scraped {len(results)} products")
        return results
    except Exception as e:
        logger.error(f"[{store['name']}] Scraper failed: {e}", exc_info=True)
        return []
