"""Global configuration constants for FilamentMonitor."""
import os
from pathlib import Path

# Project root
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# SQLite database path
DB_PATH = DATA_DIR / "filament.db"

# Weight filtering: strictly only keep standard spools <= MAX_WEIGHT_G (filters out 1.5, 2, 2.5, 3, 5 kg)
MAX_WEIGHT_G = 1250  # Upper threshold to include nominal 1kg / 1.18-1.2kg spools (e.g. Plexiwire 400m) while ignoring 2kg+

# Spool tare weight default (empty spool weight in grams)
DEFAULT_EMPTY_SPOOL_G = 200

# Low-stock alert threshold in grams
LOW_STOCK_ALERT_G = 150
CRITICAL_STOCK_ALERT_G = 50

# Plastic types
PLASTIC_TYPES = ["PETG", "TPU", "PLA", "ABS", "ASA", "Nylon", "CoPE", "PCTG", "Flex"]

# TPU hardness options
TPU_HARDNESS = ["95A", "90A", "85A", "80A", "40D"]

# Standard normalized colors in Ukrainian
STANDARD_COLORS = [
    "Чорний",
    "Білий",
    "Сірий",
    "Бежевий",
    "Червоний",
    "Синій",
    "Зелений",
    "Жовтий",
    "Помаранчевий",
    "Фіолетовий",
    "Рожевий",
    "Прозорий",
    "Сріблястий",
    "Золотий",
    "Коричневий",
    "Різнокольоровий",
]

# Filament status options
SPOOL_STATUSES = {
    "active": "В роботі",
    "sealed": "Запакована (нова)",
    "empty": "Закінчилася (архів)",
}

# Supported stores with direct category scrape URLs
DEFAULT_STORES = [
    {
        "name": "3D Smart",
        "base_url": "https://3d-smart.com.ua",
        "category_url": "https://3d-smart.com.ua/petg/",
        "scraper": "smart3d",
        "needs_js": False,
    },
    {
        "name": "LBL Corp",
        "base_url": "https://lbl-corp.com",
        "category_url": "https://lbl-corp.com/copet-petg-plastik-08kg/",
        "scraper": "lbl_corp",
        "needs_js": True,
    },
    {
        "name": "UKR3D",
        "base_url": "https://ukr3d.com.ua",
        "category_url": "https://ukr3d.com.ua/g145752746-plastik-petg/",
        "scraper": "ukr3d",
        "needs_js": True,
    },
    {
        "name": "Epic3D",
        "base_url": "https://epic3d.com.ua",
        "category_url": "https://epic3d.com.ua/petg/",
        "scraper": "epic3d",
        "needs_js": True,
    },
    {
        "name": "Plexiwire",
        "base_url": "https://shop.plexiwire.com.ua",
        "category_url": "https://shop.plexiwire.com.ua/petg-filament/",
        "scraper": "plexiwire",
        "needs_js": True,
    },
    {
        "name": "Filament.org.ua",
        "base_url": "https://filament.org.ua",
        "category_url": "https://filament.org.ua/petg",
        "scraper": "filament_org",
        "needs_js": True,
    },
    {
        "name": "3DPlast",
        "base_url": "https://3dplast.ua",
        "category_url": "https://3dplast.ua/filament-petg-124/",
        "scraper": "plast3d",
        "needs_js": False,
    },
    {
        "name": "MonoFilament",
        "base_url": "https://monofilament.com.ua",
        "category_url": "https://monofilament.com.ua/ua/products/standartnye-materialy/copet/",
        "scraper": "monofilament",
        "needs_js": True,
    },
    {
        "name": "Pochatok",
        "base_url": "https://pochatok-filament.com",
        "category_url": "https://pochatok-filament.com/ua/product_list",
        "scraper": "pochatok",
        "needs_js": False,
    },
    {
        "name": "Daniparts",
        "base_url": "https://daniparts.com",
        "category_url": "https://daniparts.com/categories/3d-druk-ta-obladnannya/6472",
        "scraper": "daniparts",
        "needs_js": False,
    },
]

# HTTP request settings
HTTP_TIMEOUT = 25  # seconds
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Playwright settings
PLAYWRIGHT_TIMEOUT = 25000  # ms
PLAYWRIGHT_WAIT_AFTER_LOAD = 2000  # ms
