"""Full audit and verification script for all 10 filament stores."""
import asyncio
import sys
import sqlite3
import re
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from config import DB_PATH
from db import queries
from scrapers.utils import parse_price, extract_weight_g

sys.stdout.reconfigure(encoding='utf-8')


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
        # 1. MonoFilament HPM JSON verification
        if "monofilament.com.ua" in url and "product_id=" in url:
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

        # 2. 3DPlast verification
        if site_price is None and "3dplast.ua" in url:
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = httpx.get(url, headers=headers, verify=False, timeout=8, follow_redirects=True)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    ins_el = soup.select_one("ins, .product-price")
                    if ins_el:
                        site_price = parse_price(ins_el.get_text(" ", strip=True))
                    if not site_price:
                        # Check gtag script
                        for s in soup.select("script"):
                            txt = s.get_text()
                            if '"value":' in txt and '"items":' in txt:
                                gm = re.search(r'"price":\s*(\d+(?:\.\d+)?)', txt)
                                if gm:
                                    site_price = float(gm.group(1))
                                    break
            except Exception:
                pass

        # 3. Pochatok verification
        if site_price is None and "pochatok-filament.com" in url:
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = httpx.get(url, headers=headers, verify=False, timeout=8, follow_redirects=True)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    price_el = soup.select_one(".product-price__price, .cs-goods-price__value, [data-qaid='product_price'], .price")
                    if price_el:
                        site_price = parse_price(price_el.get_text(" ", strip=True))
            except Exception:
                pass

        # 4. Playwright for SPA (Daniparts) or Cartum stores
        if site_price is None and pw_context:
            page = await pw_context.new_page()
            try:
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                content = await page.content()
                soup = BeautifulSoup(content, "lxml")

                # Try specific selectors
                price_el = soup.select_one(
                    ".catalogCard-price, .product-price, .price-new, ins, em, .js-store-prod-price, .price, h2"
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
    print("=" * 60)
    print("AUDIT VERIFICATION: 2 REAL PRODUCTS PER STORE (ALL 10 STORES)")
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
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM price_snapshots WHERE store_id = ? AND price_uah > 0 ORDER BY in_stock DESC, id ASC",
                (sid,),
            ).fetchall()
            conn.close()

            items = [dict(r) for r in rows]
            if not items:
                verification_rows.append({
                    "store": sname,
                    "name": "Немає товарів",
                    "url": s["category_url"],
                    "weight": "—",
                    "site_price": "—",
                    "db_price": "—",
                    "match": "❌ 0",
                })
                continue

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

            for prod in [p for p in [p1, p2] if p]:
                res = await verify_product_url(context, prod)
                res["store"] = sname
                verification_rows.append(res)
                print(f"[{sname}] {res['name'][:35]} | Site: {res['site_price']} | DB: {res['db_price']} | {res['match']}")

        await browser.close()

    print("\n" + "=" * 80)
    print("FINAL RECONCILIATION TABLE:")
    print("=" * 80)
    for r in verification_rows:
        print(f"| {r['store']} | {r['name']} | {r['url']} | {r['weight']} | {r['site_price']} | {r['db_price']} | {r['match']} |")


if __name__ == "__main__":
    asyncio.run(main())
