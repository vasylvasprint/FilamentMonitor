"""Database schema initialization for both PostgreSQL (Supabase) and SQLite."""
from config import DEFAULT_STORES
from db.engine import get_connection, is_postgres


def init_db() -> None:
    """Create all tables and seed default stores if needed for active DB dialect."""
    conn = get_connection()

    if is_postgres():
        # ------------------------------------------------ PostgreSQL / Supabase
        conn.execute("""
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
        """)

        conn.execute("""
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
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_store ON price_snapshots(store_id, scraped_at DESC);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_type ON price_snapshots(plastic_type, scraped_at DESC);")

        conn.execute("""
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
        """)

        conn.execute("""
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
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_spool ON print_jobs(spool_id, printed_at DESC);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_printed_at ON print_jobs(printed_at DESC);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_urls (
                id           SERIAL PRIMARY KEY,
                url          VARCHAR(1024) NOT NULL UNIQUE,
                label        VARCHAR(255),
                added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scraped TIMESTAMP
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_colors (
                id           SERIAL PRIMARY KEY,
                name         VARCHAR(100) NOT NULL UNIQUE,
                hex_code     VARCHAR(50),
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Seed stores
        for store in DEFAULT_STORES:
            conn.execute(
                """
                INSERT INTO stores (name, base_url, category_url, scraper, needs_js, is_custom)
                SELECT :name, :base_url, :category_url, :scraper, :needs_js, FALSE
                WHERE NOT EXISTS (SELECT 1 FROM stores WHERE base_url = :base_url)
                """,
                {
                    "name": store["name"],
                    "base_url": store["base_url"],
                    "category_url": store["category_url"],
                    "scraper": store["scraper"],
                    "needs_js": bool(store["needs_js"]),
                },
            )

    else:
        # ------------------------------------------------ SQLite Local
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                base_url    TEXT    NOT NULL,
                category_url TEXT   NOT NULL,
                scraper     TEXT    NOT NULL DEFAULT 'custom',
                needs_js    BOOLEAN NOT NULL DEFAULT 0,
                is_active   BOOLEAN NOT NULL DEFAULT 1,
                is_custom   BOOLEAN NOT NULL DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id      INTEGER NOT NULL REFERENCES stores(id),
                scraped_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                product_name  TEXT    NOT NULL,
                brand         TEXT,
                plastic_type  TEXT,
                color         TEXT,
                weight_g      INTEGER,
                hardness      TEXT,
                price_uah     REAL,
                price_per_kg  REAL,
                price_per_g   REAL,
                product_url   TEXT,
                in_stock      BOOLEAN DEFAULT 1,
                image_url     TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_store
            ON price_snapshots(store_id, scraped_at DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_type
            ON price_snapshots(plastic_type, scraped_at DESC)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                brand                TEXT,
                store_name           TEXT,
                plastic_type         TEXT    NOT NULL,
                color                TEXT,
                hardness             TEXT,
                initial_weight_g     INTEGER NOT NULL,
                current_weight_g     INTEGER NOT NULL,
                empty_spool_weight_g INTEGER NOT NULL DEFAULT 200,
                purchase_price       REAL    NOT NULL DEFAULT 0,
                purchase_date        DATE    DEFAULT CURRENT_DATE,
                status               TEXT    NOT NULL DEFAULT 'active',
                notes                TEXT,
                snapshot_id          INTEGER REFERENCES price_snapshots(id),
                created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS print_jobs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                spool_id         INTEGER NOT NULL REFERENCES inventory(id),
                project_name     TEXT    NOT NULL,
                filament_used_g  REAL    NOT NULL,
                cost_uah         REAL,
                is_failed        BOOLEAN NOT NULL DEFAULT 0,
                gcode_filename   TEXT,
                notes            TEXT,
                printed_at       DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_spool
            ON print_jobs(spool_id, printed_at DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_printed_at
            ON print_jobs(printed_at DESC)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_urls (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                url          TEXT    NOT NULL UNIQUE,
                label        TEXT,
                added_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_scraped DATETIME
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_colors (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL UNIQUE,
                hex_code     TEXT,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for store in DEFAULT_STORES:
            conn.execute(
                """
                INSERT OR IGNORE INTO stores (name, base_url, category_url, scraper, needs_js, is_custom)
                SELECT ?, ?, ?, ?, ?, 0
                WHERE NOT EXISTS (SELECT 1 FROM stores WHERE base_url = ?)
                """,
                (
                    store["name"],
                    store["base_url"],
                    store["category_url"],
                    store["scraper"],
                    1 if store["needs_js"] else 0,
                    store["base_url"],
                ),
            )

    conn.commit()
    conn.close()
