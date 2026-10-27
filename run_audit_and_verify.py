"""Full audit and verification script for all 10 filament stores."""
import asyncio
import sys
import sqlite3
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from config import DB_PATH
from db import queries
from scrapers import run_scraper
from scrapers.utils import parse_price, extract_weight_g

sys.stdout.reconfigure(encoding='utf-8')


async def scrape_all_stores():
    stores = queries.get_all_stores(active_only=True)
    print(f"Scraping {len(stores)} stores...")
    results_by_store = {}

    for s in stores:
        sid = s["id"]
        sname = s["name"]
        print(f"\n--- Running scraper for: {sname} (ID: {sid}) ---")
        try:
            items = await run_scraper(s)
            print(f"[{sname}] Scraped {len(items)} valid products.")
            if items:
                queries.save_price_snapshots(items)
                results_by_store[sname] = items
            else:
                results_by_store[sname] = []
        except Exception as e:
            print(f"[{sname}] ERROR: {e}")
            results_by_store[sname] = []

    return results_by_store


async def verify_product_url(pw_context, product: dict) -> dict:
    url = product.get("product_url")
    name = product.get("product_name")
    weight = product.get("weight_g")
    db_price = product.get("price_uah")
    store_name = product.get("brand") or "Store"

    site_price = None

    if not url:
        return {
            "name": name,
            "url": "No URL",
            "weight": f"{weight} г",
            "site_price": "—",
            "db_price": f"{db_price:.0f} ₴",
            "match": False,
        }

    try:
        # For MonoFilament, we can check via httpx or playwright
        if "monofilament.com.ua" in url and "product_id=" in url:
            import re
            m = re.search(r"product_id=(\d+)", url)
            if m:
                pid = m.group(1)
                r = httpx.get(
                    f"https://monofilament.com.ua/index.php?route=extension/module/hpmrr/product_json&pid={pid}",
                    verify=False,
                    timeout=10,
                )
                if r.status_code == 200:
                    d = r.json().get("success", {})
                    p_raw = d.get("special") or d.get("price")
                    site_price = parse_price(str(p_raw))

        # For static / prom sites: httpx first
        if site_price is None:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = httpx.get(url, headers=headers, verify=False, timeout=8, follow_redirects=True)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    price_el = soup.select_one(
                        ".cs-goods-price__value, .item-price, .product-price, .price-new, h2, .price"
                    )
                    if price_el:
                        site_price = parse_price(price_el.get_text(" ", strip=True))
            except Exception:
                pass

        # Fallback to Playwright if static did not get price
        if site_price is None and pw_context:
            page = await pw_context.new_page()
            try:
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                content = await page.content()
                soup = BeautifulSoup(content, "lxml")
                price_el = soup.select_one(
                    ".catalogCard-price, .product-price, .price-new, .price, .js-store-prod-price, h2"
                )
                if price_el:
                    site_price = parse_price(price_el.get_text(" ", strip=True))
            except Exception as pe:
                print(f"Playwright error for {url}: {pe}")
            finally:
                await page.close()

    except Exception as e:
        print(f"Error verifying {url}: {e}")

    match = False
    if site_price is not None and db_price is not None:
        match = abs(site_price - db_price) < 1.0

    return {
        "store": store_name,
        "name": name,
        "url": url,
        "weight": f"{weight} г",
        "site_price": f"{site_price:.0f} ₴" if site_price else "—",
        "db_price": f"{db_price:.0f} ₴" if db_price else "—",
        "match": "✅ Збігається" if match else "❌ Розбіжність",
    }


async def main():
    results = await scrape_all_stores()

    print("\n" + "=" * 60)
    print("STARTING AUDIT VERIFICATION OF 2 PRODUCTS PER STORE (20 TOTAL)")
    print("=" * 60)

    stores = queries.get_all_stores(active_only=True)
    verification_rows = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        for s in stores:
            sname = s["name"]
            sid = s["id"]
            # get all latest snapshots for this store from DB
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM price_snapshots WHERE store_id = ? AND price_uah > 0 ORDER BY in_stock DESC, id ASC",
                (sid,),
            ).fetchall()
            conn.close()

            items = [dict(r) for r in rows]
            if not items:
                print(f"[{sname}] No products in DB to verify!")
                verification_rows.append({
                    "store": sname,
                    "name": "Не знайдено товарів",
                    "url": s["category_url"],
                    "weight": "—",
                    "site_price": "—",
                    "db_price": "—",
                    "match": "❌ 0 товарів",
                })
                continue

            # Pick 2 products (preferring 1000g or 750g/850g)
            p1 = None
            p2 = None
            for it in items:
                if it.get("product_url"):
                    if not p1:
                        p1 = it
                    elif it.get("product_url") != p1.get("product_url"):
                        p2 = it
                        break
            if not p2 and len(items) > 1:
                p2 = items[1]
            elif not p2:
                p2 = p1

            to_check = [p for p in [p1, p2] if p]
            for prod in to_check:
                print(f"Verifying {sname}: {prod['product_name'][:40]} ({prod['product_url']})...")
                res = await verify_product_url(context, prod)
                res["store"] = sname
                verification_rows.append(res)
                print(f"  -> Site: {res['site_price']} | DB: {res['db_price']} | {res['match']}")

        await browser.close()

    print("\n" + "=" * 60)
    print("FINAL AUDIT TABLE (20 PRODUCTS):")
    print("=" * 60)
    for row in verification_rows:
        print(f"| {row['store']} | {row['name'][:35]} | {row['weight']} | Сайт: {row['site_price']} | БД: {row['db_price']} | {row['match']} |")


if __name__ == "__main__":
    asyncio.run(main())
