import asyncio
import sys
from db.queries import get_all_stores, save_price_snapshots
from scrapers import run_scraper
from db.schema import get_connection

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    stores = get_all_stores(active_only=True)
    print(f"Starting scraping for {len(stores)} stores...")
    
    total_saved = 0
    for store in stores:
        print(f"\n--- Scraping [{store['name']}] ({store['scraper']}) ---")
        try:
            items = await run_scraper(store)
            print(f"[{store['name']}] Got {len(items)} items")
            if items:
                count = save_price_snapshots(items)
                total_saved += count
                # show first 2 items
                for it in items[:2]:
                    print(f"   * {it['product_name'][:45]} | {it['plastic_type']} | {it['weight_g']}g | {it['price_uah']} ₴ | {it['price_per_kg']} ₴/кг")
        except Exception as e:
            print(f"[{store['name']}] Error: {e}")
            
    conn = get_connection()
    count_db = conn.execute("SELECT count(*) as c FROM price_snapshots").fetchone()['c']
    with_prices = conn.execute("SELECT count(*) as c FROM price_snapshots WHERE price_uah > 0 AND price_per_kg > 0").fetchone()['c']
    conn.close()
    print(f"\n==========================================")
    print(f"SCRAPING COMPLETE!")
    print(f"Total rows in DB: {count_db}")
    print(f"Valid items with price > 0 & price_per_kg > 0: {with_prices}")
    print(f"==========================================")

if __name__ == '__main__':
    asyncio.run(main())
