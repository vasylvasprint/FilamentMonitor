"""Data migration tool from local SQLite (data/filament.db) to PostgreSQL (Supabase).

Usage:
    python migrate_to_postgres.py "postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres"

Or configure DATABASE_URL in .streamlit/secrets.toml and run:
    python migrate_to_postgres.py
"""
import sys
import os
import sqlite3
from typing import Optional
from pathlib import Path

# Set UTF-8 encoding for console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import sqlalchemy as sa
from config import DB_PATH
from db.engine import normalize_postgres_url, get_database_url


def get_target_url() -> Optional[str]:
    # 1. Command-line argument
    if len(sys.argv) > 1:
        arg_url = sys.argv[1].strip()
        if arg_url and not arg_url.startswith("-"):
            return arg_url

    # 2. Streamlit secrets or environment variable
    url = get_database_url()
    if url:
        return url

    return None


def init_postgres_schema(pg_conn):
    """Create all required tables in target PostgreSQL database."""
    print("📦 [1/6] Ініціалізація структури таблиць у PostgreSQL...")
    
    pg_conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS stores (
            id           SERIAL PRIMARY KEY,
            name         VARCHAR(255) NOT NULL,
            base_url     VARCHAR(512) NOT NULL,
            category_url VARCHAR(1024) NOT NULL,
            scraper      VARCHAR(100) NOT NULL DEFAULT 'custom',
            needs_js     BOOLEAN NOT NULL DEFAULT FALSE,
            is_active    BOOLEAN NOT NULL DEFAULT TRUE,
            is_custom    BOOLEAN NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS price_snapshots (
            id           SERIAL PRIMARY KEY,
            store_id     INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
            scraped_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            product_name TEXT NOT NULL,
            brand        VARCHAR(255),
            plastic_type VARCHAR(100),
            color        VARCHAR(100),
            weight_g     INTEGER,
            hardness     VARCHAR(50),
            price_uah    DOUBLE PRECISION,
            price_per_kg DOUBLE PRECISION,
            price_per_g  DOUBLE PRECISION,
            product_url  TEXT,
            in_stock     BOOLEAN DEFAULT TRUE,
            image_url    TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_store ON price_snapshots(store_id, scraped_at DESC);
        CREATE INDEX IF NOT EXISTS idx_snapshots_type ON price_snapshots(plastic_type, scraped_at DESC);

        CREATE TABLE IF NOT EXISTS inventory (
            id                   SERIAL PRIMARY KEY,
            brand                VARCHAR(255),
            store_name           VARCHAR(255),
            plastic_type         VARCHAR(100) NOT NULL,
            color                VARCHAR(100),
            hardness             VARCHAR(50),
            initial_weight_g     INTEGER NOT NULL,
            current_weight_g     INTEGER NOT NULL,
            empty_spool_weight_g INTEGER NOT NULL DEFAULT 200,
            purchase_price       DOUBLE PRECISION NOT NULL DEFAULT 0,
            purchase_date        DATE DEFAULT CURRENT_DATE,
            status               VARCHAR(50) NOT NULL DEFAULT 'active',
            notes                TEXT,
            snapshot_id          INTEGER REFERENCES price_snapshots(id) ON DELETE SET NULL,
            created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS print_jobs (
            id              SERIAL PRIMARY KEY,
            spool_id        INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
            project_name    VARCHAR(255) NOT NULL,
            filament_used_g DOUBLE PRECISION NOT NULL,
            cost_uah        DOUBLE PRECISION,
            is_failed       BOOLEAN NOT NULL DEFAULT FALSE,
            gcode_filename  VARCHAR(255),
            notes           TEXT,
            printed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_spool ON print_jobs(spool_id, printed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_printed_at ON print_jobs(printed_at DESC);

        CREATE TABLE IF NOT EXISTS custom_urls (
            id           SERIAL PRIMARY KEY,
            url          VARCHAR(1024) NOT NULL UNIQUE,
            label        VARCHAR(255),
            added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_scraped TIMESTAMP
        );
    """))
    pg_conn.commit()
    print("   ✓ Схему успішно перевірено/створено.")


def migrate():
    target_url = get_target_url()
    if not target_url or "[ВСТАВ" in target_url or "YOUR-PASSWORD" in target_url:
        print("=" * 70)
        print("❌ ПОМИЛКА: Не вказано валідний DATABASE_URL для PostgreSQL (Supabase)!")
        print("=" * 70)
        print("\nБудь ласка, запустіть міграцію одним із способів:")
        print("1. Передайте URI аргументом команди:")
        print('   python migrate_to_postgres.py "postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres"')
        print("\n2. Або додайте рядок у .streamlit/secrets.toml:")
        print('   DATABASE_URL = "postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres"')
        print("   та виконайте: python migrate_to_postgres.py\n")
        sys.exit(1)

    norm_url = normalize_postgres_url(target_url)
    print("=" * 70)
    print("🚀 Початок міграції локальної бази SQLite -> Хмарна PostgreSQL (Supabase)")
    print(f"Джерело: {DB_PATH.resolve()}")
    # Mask password in logs
    masked_url = re.sub(r':([^@]+)@', ':****@', norm_url)
    print(f"Призначення: {masked_url}")
    print("=" * 70)

    if not DB_PATH.exists():
        print(f"❌ Файл локальної бази {DB_PATH} не знайдено!")
        sys.exit(1)

    # 1. Connect to SQLite
    sqlite_conn = sqlite3.connect(str(DB_PATH))
    sqlite_conn.row_factory = sqlite3.Row

    # 2. Connect to PostgreSQL
    try:
        pg_engine = sa.create_engine(norm_url, pool_pre_ping=True)
        pg_conn = pg_engine.connect()
    except Exception as e:
        print(f"❌ Не вдалося підключитися до PostgreSQL: {e}")
        sys.exit(1)

    try:
        # Schema initialization
        init_postgres_schema(pg_conn)

        # ------------------------------------------------------------- 1. STORES
        print("🚚 [2/6] Перенесення таблиці `stores`...")
        stores = sqlite_conn.execute("SELECT * FROM stores ORDER BY id").fetchall()
        for s in stores:
            pg_conn.execute(
                sa.text("""
                    INSERT INTO stores (id, name, base_url, category_url, scraper, needs_js, is_active, is_custom, created_at)
                    VALUES (:id, :name, :base_url, :category_url, :scraper, :needs_js, :is_active, :is_custom, :created_at)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        base_url = EXCLUDED.base_url,
                        category_url = EXCLUDED.category_url,
                        scraper = EXCLUDED.scraper,
                        needs_js = EXCLUDED.needs_js,
                        is_active = EXCLUDED.is_active,
                        is_custom = EXCLUDED.is_custom;
                """),
                {
                    "id": s["id"],
                    "name": s["name"],
                    "base_url": s["base_url"],
                    "category_url": s["category_url"],
                    "scraper": s["scraper"],
                    "needs_js": bool(s["needs_js"]),
                    "is_active": bool(s["is_active"]),
                    "is_custom": bool(s["is_custom"]),
                    "created_at": s["created_at"],
                },
            )
        pg_conn.commit()
        # Reset sequence
        pg_conn.execute(sa.text("SELECT setval(pg_get_serial_sequence('stores', 'id'), COALESCE(MAX(id), 1)) FROM stores;"))
        pg_conn.commit()
        print(f"   ✓ Перенесено {len(stores)} магазинів.")

        # --------------------------------------------------- 2. PRICE SNAPSHOTS
        print("🚚 [3/6] Перенесення таблиці `price_snapshots`...")
        snapshots = sqlite_conn.execute("SELECT * FROM price_snapshots ORDER BY id").fetchall()
        batch_size = 200
        total_snapshots = len(snapshots)
        
        for i in range(0, total_snapshots, batch_size):
            batch = snapshots[i:i + batch_size]
            params = []
            for snap in batch:
                params.append({
                    "id": snap["id"],
                    "store_id": snap["store_id"],
                    "scraped_at": snap["scraped_at"],
                    "product_name": snap["product_name"],
                    "brand": snap["brand"],
                    "plastic_type": snap["plastic_type"],
                    "color": snap["color"],
                    "weight_g": snap["weight_g"],
                    "hardness": snap["hardness"],
                    "price_uah": snap["price_uah"],
                    "price_per_kg": snap["price_per_kg"],
                    "price_per_g": snap["price_per_g"],
                    "product_url": snap["product_url"],
                    "in_stock": bool(snap["in_stock"]),
                    "image_url": snap["image_url"],
                })
            
            pg_conn.execute(
                sa.text("""
                    INSERT INTO price_snapshots 
                    (id, store_id, scraped_at, product_name, brand, plastic_type, color, weight_g, hardness,
                     price_uah, price_per_kg, price_per_g, product_url, in_stock, image_url)
                    VALUES (:id, :store_id, :scraped_at, :product_name, :brand, :plastic_type, :color, :weight_g, :hardness,
                            :price_uah, :price_per_kg, :price_per_g, :product_url, :in_stock, :image_url)
                    ON CONFLICT (id) DO NOTHING;
                """),
                params
            )
            pg_conn.commit()
            print(f"   → Завантажено {min(i + batch_size, total_snapshots)} / {total_snapshots} записів...")

        pg_conn.execute(sa.text("SELECT setval(pg_get_serial_sequence('price_snapshots', 'id'), COALESCE(MAX(id), 1)) FROM price_snapshots;"))
        pg_conn.commit()
        print(f"   ✓ Успішно перенесено {total_snapshots} знімків цін.")

        # ---------------------------------------------------------- 3. INVENTORY
        print("🚚 [4/6] Перенесення таблиці `inventory`...")
        spools = sqlite_conn.execute("SELECT * FROM inventory ORDER BY id").fetchall()
        for sp in spools:
            pg_conn.execute(
                sa.text("""
                    INSERT INTO inventory
                    (id, brand, store_name, plastic_type, color, hardness, initial_weight_g, current_weight_g,
                     empty_spool_weight_g, purchase_price, purchase_date, status, notes, snapshot_id, created_at)
                    VALUES (:id, :brand, :store_name, :plastic_type, :color, :hardness, :initial_weight_g, :current_weight_g,
                            :empty_spool_weight_g, :purchase_price, :purchase_date, :status, :notes, :snapshot_id, :created_at)
                    ON CONFLICT (id) DO UPDATE SET
                        current_weight_g = EXCLUDED.current_weight_g,
                        status = EXCLUDED.status,
                        notes = EXCLUDED.notes;
                """),
                {
                    "id": sp["id"],
                    "brand": sp["brand"],
                    "store_name": sp["store_name"],
                    "plastic_type": sp["plastic_type"],
                    "color": sp["color"],
                    "hardness": sp["hardness"],
                    "initial_weight_g": sp["initial_weight_g"],
                    "current_weight_g": sp["current_weight_g"],
                    "empty_spool_weight_g": sp["empty_spool_weight_g"],
                    "purchase_price": sp["purchase_price"],
                    "purchase_date": sp["purchase_date"],
                    "status": sp["status"],
                    "notes": sp["notes"],
                    "snapshot_id": sp["snapshot_id"],
                    "created_at": sp["created_at"],
                },
            )
        pg_conn.commit()
        if spools:
            pg_conn.execute(sa.text("SELECT setval(pg_get_serial_sequence('inventory', 'id'), COALESCE(MAX(id), 1)) FROM inventory;"))
            pg_conn.commit()
        print(f"   ✓ Перенесено {len(spools)} котушок зі складу.")

        # --------------------------------------------------------- 4. PRINT JOBS
        print("🚚 [5/6] Перенесення журналу друку `print_jobs`...")
        jobs = sqlite_conn.execute("SELECT * FROM print_jobs ORDER BY id").fetchall()
        for j in jobs:
            pg_conn.execute(
                sa.text("""
                    INSERT INTO print_jobs
                    (id, spool_id, project_name, filament_used_g, cost_uah, is_failed, gcode_filename, notes, printed_at)
                    VALUES (:id, :spool_id, :project_name, :filament_used_g, :cost_uah, :is_failed, :gcode_filename, :notes, :printed_at)
                    ON CONFLICT (id) DO NOTHING;
                """),
                {
                    "id": j["id"],
                    "spool_id": j["spool_id"],
                    "project_name": j["project_name"],
                    "filament_used_g": j["filament_used_g"],
                    "cost_uah": j["cost_uah"],
                    "is_failed": bool(j["is_failed"]),
                    "gcode_filename": j["gcode_filename"],
                    "notes": j["notes"],
                    "printed_at": j["printed_at"],
                },
            )
        pg_conn.commit()
        if jobs:
            pg_conn.execute(sa.text("SELECT setval(pg_get_serial_sequence('print_jobs', 'id'), COALESCE(MAX(id), 1)) FROM print_jobs;"))
            pg_conn.commit()
        print(f"   ✓ Перенесено {len(jobs)} завдань друку.")

        # -------------------------------------------------------- 5. CUSTOM URLS
        print("🚚 [6/6] Перенесення таблиці `custom_urls`...")
        urls = sqlite_conn.execute("SELECT * FROM custom_urls ORDER BY id").fetchall()
        for u in urls:
            pg_conn.execute(
                sa.text("""
                    INSERT INTO custom_urls (id, url, label, added_at, last_scraped)
                    VALUES (:id, :url, :label, :added_at, :last_scraped)
                    ON CONFLICT (id) DO NOTHING;
                """),
                {
                    "id": u["id"],
                    "url": u["url"],
                    "label": u["label"],
                    "added_at": u["added_at"],
                    "last_scraped": u["last_scraped"],
                },
            )
        pg_conn.commit()
        if urls:
            pg_conn.execute(sa.text("SELECT setval(pg_get_serial_sequence('custom_urls', 'id'), COALESCE(MAX(id), 1)) FROM custom_urls;"))
            pg_conn.commit()
        print(f"   ✓ Перенесено {len(urls)} користувацьких посилань.")

        # Verification
        print("\n" + "=" * 70)
        print("🎉 МІГРАЦІЯ УСПІШНО ЗАВЕРШЕНА!")
        print("=" * 70)
        s_count = pg_conn.execute(sa.text("SELECT count(*) FROM stores")).scalar()
        p_count = pg_conn.execute(sa.text("SELECT count(*) FROM price_snapshots")).scalar()
        i_count = pg_conn.execute(sa.text("SELECT count(*) FROM inventory")).scalar()
        j_count = pg_conn.execute(sa.text("SELECT count(*) FROM print_jobs")).scalar()
        print(f"📊 Дані в хмарній PostgreSQL:")
        print(f"   - Магазинів (stores): {s_count}")
        print(f"   - Знімків цін (price_snapshots): {p_count}")
        print(f"   - Котушок на складі (inventory): {i_count}")
        print(f"   - Записів у журналі (print_jobs): {j_count}")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Помилка під час міграції даних: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    migrate()
