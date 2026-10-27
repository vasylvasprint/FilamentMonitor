"""Clear price_snapshots and re-sync stores table."""
import sqlite3
from config import DB_PATH, DEFAULT_STORES

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Clear old inaccurate snapshots
    cur.execute("DELETE FROM price_snapshots;")
    print("Deleted all old price_snapshots.")

    # Recreate or update stores
    cur.execute("DELETE FROM stores;")
    for s in DEFAULT_STORES:
        cur.execute(
            """INSERT INTO stores (name, base_url, category_url, scraper, is_active, needs_js)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (s["name"], s["base_url"], s["category_url"], s["scraper"], 1 if s.get("needs_js") else 0),
        )
    conn.commit()
    print("Re-seeded 10 stores cleanly:")
    for row in cur.execute("SELECT id, name, category_url, scraper FROM stores").fetchall():
        print(f"  [{row['id']}] {row['name']} | scraper={row['scraper']} | {row['category_url']}")

    conn.close()

if __name__ == '__main__':
    main()
