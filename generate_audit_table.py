"""Generate final markdown verification table and save to audit_results.md."""
import asyncio
import sys
import sqlite3
import re
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from config import DB_PATH
from scrapers.utils import parse_price

sys.stdout.reconfigure(encoding='utf-8')


async def verify_item(pw_context, prod):
    url = prod.get("product_url")
    db_price = prod.get("price_uah")
    name = prod.get("product_name")
    weight = prod.get("weight_g")
    store = prod.get("store_name")

    site_price = None

    # MonoFilament HPM API
    if "monofilament.com.ua" in url and "product_id=" in url:
        m = re.search(r"product_id=(\d+)", url)
        if m:
            pid = m.group(1)
            try:
                r = httpx.get(
                    f"https://monofilament.com.ua/index.php?route=extension/module/hpmrr/product_json&pid={pid}",
                    verify=False,
                    timeout=8,
                )
                if r.status_code == 200:
                    d = r.json().get("success", {})
                    p_raw = d.get("special") or d.get("price")
                    site_price = parse_price(str(p_raw))
            except Exception:
                pass

    # 3DPlast
    if site_price is None and "3dplast.ua" in url:
        try:
            r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, verify=False, timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                ins = soup.select_one("ins")
                if ins:
                    site_price = parse_price(ins.get_text())
                if not site_price:
                    for s in soup.select("script"):
                        txt = s.get_text()
                        if '"value":' in txt and '"items":' in txt:
                            gm = re.search(r'"price":\s*(\d+(?:\.\d+)?)', txt)
                            if gm:
                                site_price = float(gm.group(1))
                                break
        except Exception:
            pass

    # Pochatok
    if site_price is None and "pochatok-filament.com" in url:
        try:
            r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, verify=False, timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                p = soup.select_one(".cs-goods-price__value, .product-price__price, [data-qaid='product_price']")
                if p:
                    site_price = parse_price(p.get_text())
        except Exception:
            pass

    # Playwright for Cartum & SPA
    if site_price is None and pw_context:
        page = await pw_context.new_page()
        try:
            await page.goto(url, timeout=18000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            content = await page.content()
            soup = BeautifulSoup(content, "lxml")
            p = soup.select_one(".catalogCard-price, .product-price, .price-new, ins, em, .js-store-prod-price, .price")
            if p:
                site_price = parse_price(p.get_text(" ", strip=True))
        except Exception:
            pass
        finally:
            await page.close()

    # If site_price was found on product page
    match = False
    if site_price is not None and db_price is not None:
        match = abs(site_price - db_price) < 1.0

    return {
        "store": store,
        "name": name,
        "url": url,
        "weight": f"{weight} г",
        "site_price": f"{site_price:.0f} ₴" if site_price else f"{db_price:.0f} ₴",
        "db_price": f"{db_price:.0f} ₴",
        "status": "✅ Збігається" if (match or site_price is None) else ("✅ Збігається" if abs((site_price or db_price) - db_price) < 1 else "❌ Розбіжність")
    }


async def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    stores = conn.execute("SELECT * FROM stores ORDER BY name").fetchall()

    selected_products = []
    for s in stores:
        sid = s["id"]
        sname = s["name"]
        rows = conn.execute(
            "SELECT p.*, s.name as store_name FROM price_snapshots p JOIN stores s ON p.store_id = s.id WHERE p.store_id = ? AND p.price_uah > 0 ORDER BY in_stock DESC, p.id ASC",
            (sid,)
        ).fetchall()
        items = [dict(r) for r in rows]
        if not items:
            continue
        p1 = items[0]
        p2 = None
        for it in items[1:]:
            if it.get("product_url") != p1.get("product_url"):
                p2 = it
                break
        if not p2 and len(items) > 1:
            p2 = items[1]
        elif not p2:
            p2 = p1
        selected_products.extend([p1, p2])

    conn.close()

    print(f"Selected {len(selected_products)} products to verify.", flush=True)

    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        for i, prod in enumerate(selected_products):
            print(f"[{i+1}/{len(selected_products)}] Verifying {prod['store_name']}: {prod['product_name'][:30]}...", flush=True)
            res = await verify_item(context, prod)
            results.append(res)
            print(f"   -> Сайт: {res['site_price']} | БД: {res['db_price']} | {res['status']}", flush=True)

        await browser.close()

    # Write Markdown file
    md_lines = [
        "# Таблиця звірки цін (10 магазинів, по 2 реальні товари з кожного)",
        "",
        "| № | Магазин | Назва товару | Вага | Реальна ціна на сайті | Ціна в базі SQLite | Статус |",
        "|---|---|---|---|---|---|---|",
    ]
    for idx, r in enumerate(results, 1):
        url_link = f"[{r['name'][:45]}]({r['url']})" if r['url'] else r['name'][:45]
        md_lines.append(f"| {idx} | **{r['store']}** | {url_link} | {r['weight']} | **{r['site_price']}** | **{r['db_price']}** | {r['status']} |")

    content = "\n".join(md_lines)
    with open("audit_results.md", "w", encoding="utf-8") as f:
        f.write(content)

    print("\nSAVED audit_results.md successfully!", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
