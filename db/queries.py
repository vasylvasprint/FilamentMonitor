"""All SQL queries (CRUD) for FilamentMonitor, supporting PostgreSQL (Supabase) & SQLite."""
from typing import List, Optional, Dict, Any

from db.engine import get_connection, is_postgres
from db.models import Store, PriceSnapshot, InventorySpool, PrintJob, CustomUrl
from scrapers.utils import normalize_color


# ════════════════════════════════════════════════════════════════════ STORES

def get_all_stores(active_only: bool = False) -> List[Dict]:
    conn = get_connection()
    q = "SELECT * FROM stores"
    if active_only:
        q += " WHERE is_active = TRUE" if is_postgres() else " WHERE is_active = 1"
    q += " ORDER BY name"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_store_active(store_id: int, is_active: bool) -> None:
    conn = get_connection()
    val = is_active if is_postgres() else (1 if is_active else 0)
    conn.execute("UPDATE stores SET is_active = ? WHERE id = ?", (val, store_id))
    conn.commit()
    conn.close()


def add_custom_store(name: str, base_url: str, category_url: str) -> int:
    conn = get_connection()
    if is_postgres():
        res = conn.execute(
            """INSERT INTO stores (name, base_url, category_url, scraper, needs_js, is_custom)
               VALUES (?, ?, ?, 'custom', TRUE, TRUE) RETURNING id""",
            (name, base_url, category_url),
        )
        row = res.fetchone()
        store_id = row["id"] if row else 0
    else:
        cur = conn.execute(
            """INSERT INTO stores (name, base_url, category_url, scraper, needs_js, is_custom)
               VALUES (?, ?, ?, 'custom', 1, 1)""",
            (name, base_url, category_url),
        )
        store_id = cur.lastrowid
    conn.commit()
    conn.close()
    return store_id


# ══════════════════════════════════════════════════════════ PRICE SNAPSHOTS

def save_price_snapshots(snapshots: List[Dict]) -> int:
    """Bulk insert price snapshots. Returns count inserted."""
    if not snapshots:
        return 0
    conn = get_connection()
    cur = conn.executemany(
        """INSERT INTO price_snapshots
           (store_id, product_name, brand, plastic_type, color, weight_g, hardness,
            price_uah, price_per_kg, price_per_g, product_url, in_stock, image_url)
           VALUES (:store_id, :product_name, :brand, :plastic_type, :color, :weight_g,
                   :hardness, :price_uah, :price_per_kg, :price_per_g, :product_url,
                   :in_stock, :image_url)""",
        snapshots,
    )
    conn.commit()
    count = cur.rowcount if cur.rowcount and cur.rowcount > 0 else len(snapshots)
    conn.close()
    return count


def get_latest_prices(
    plastic_types: Optional[List[str]] = None,
    in_stock_only: bool = False,
    store_ids: Optional[List[int]] = None,
    selected_colors: Optional[List[str]] = None,
    color_search: Optional[str] = None,
    search_query: Optional[str] = None,
    hardness: Optional[str] = None,
    **kwargs,
) -> List[Dict]:
    """Return only the most recent snapshot per (store, product_url/name) combo with flexible filters."""
    conn = get_connection()
    q = """
        WITH ranked AS (
            SELECT ps.*,
                   s.name AS store_name,
                   ROW_NUMBER() OVER (
                       PARTITION BY ps.store_id, ps.product_url
                       ORDER BY ps.scraped_at DESC
                   ) AS rn
            FROM price_snapshots ps
            JOIN stores s ON ps.store_id = s.id
            WHERE ps.weight_g IS NOT NULL
        )
        SELECT * FROM ranked WHERE rn = 1
    """
    conditions = []
    params: List[Any] = []

    # Plastic type filter
    if plastic_types and len(plastic_types) > 0:
        placeholders = ",".join("?" * len(plastic_types))
        conditions.append(f"plastic_type IN ({placeholders})")
        params.extend(plastic_types)

    # In stock filter
    if in_stock_only:
        conditions.append("in_stock = TRUE" if is_postgres() else "in_stock = 1")

    # Store filter: ONLY apply if store_ids has items. If empty or None -> all stores!
    if store_ids and len(store_ids) > 0:
        placeholders = ",".join("?" * len(store_ids))
        conditions.append(f"store_id IN ({placeholders})")
        params.extend(store_ids)

    # Normalized color multiselect filter
    if selected_colors and len(selected_colors) > 0:
        color_conditions = []
        for col in selected_colors:
            if col == "Не вказано" or col == "—":
                color_conditions.append("(color = 'Не вказано' OR color = '—' OR color IS NULL)")
            else:
                color_conditions.append("color = ?")
                params.append(col)
        if color_conditions:
            conditions.append("(" + " OR ".join(color_conditions) + ")")

    # Hardness for TPU
    if hardness and hardness != "Всі":
        conditions.append("hardness = ?")
        params.append(hardness)

    # Combine search_query and legacy color_search seamlessly
    unified_query = search_query or color_search
    if unified_query and unified_query.strip():
        tokens = unified_query.strip().split()
        for token in tokens:
            pattern = f"%{token.lower()}%"
            conditions.append("""(
                LOWER(product_name) LIKE ? OR
                LOWER(color) LIKE ? OR
                LOWER(brand) LIKE ? OR
                LOWER(plastic_type) LIKE ?
            )""")
            params.extend([pattern, pattern, pattern, pattern])

    if conditions:
        q = f"SELECT * FROM ({q}) sub WHERE " + " AND ".join(conditions)
    q += " ORDER BY price_per_kg ASC NULLS LAST"

    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_total_snapshots_count() -> int:
    """Return total count of snapshots in DB."""
    conn = get_connection()
    row = conn.execute("SELECT count(*) as c FROM price_snapshots").fetchone()
    conn.close()
    return row["c"] if row else 0


def get_last_scrape_time() -> Optional[str]:
    conn = get_connection()
    row = conn.execute(
        "SELECT MAX(scraped_at) as t FROM price_snapshots"
    ).fetchone()
    conn.close()
    return str(row["t"]) if row and row["t"] else None


def get_custom_colors() -> List[str]:
    """Retrieve all user-saved custom colors from the database."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT name FROM custom_colors ORDER BY name ASC").fetchall()
        return [r["name"] for r in rows if r.get("name")]
    except Exception:
        return []
    finally:
        conn.close()


def add_custom_color(name: str, hex_code: Optional[str] = None) -> None:
    """Save a user-defined custom color to the database."""
    if not name or not name.strip() or name.strip() in ("—", "nan"):
        return
    clean_name = name.strip()
    conn = get_connection()
    try:
        if is_postgres():
            conn.execute(
                """INSERT INTO custom_colors (name, hex_code)
                   VALUES (:name, :hex_code)
                   ON CONFLICT (name) DO NOTHING""",
                {"name": clean_name, "hex_code": hex_code},
            )
        else:
            conn.execute(
                """INSERT OR IGNORE INTO custom_colors (name, hex_code)
                   VALUES (?, ?)""",
                (clean_name, hex_code),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_distinct_colors() -> List[str]:
    """Get all existing distinct normalized colors from DB (snapshots, inventory, custom_colors)."""
    from config import STANDARD_COLORS
    conn = get_connection()
    db_colors = set()
    
    # 1. From price_snapshots
    try:
        rows = conn.execute(
            "SELECT DISTINCT color FROM price_snapshots WHERE color IS NOT NULL AND color != 'nan' AND color != '—'"
        ).fetchall()
        for r in rows:
            if r.get("color") and r["color"].strip():
                db_colors.add(r["color"].strip())
    except Exception:
        pass

    # 2. From inventory spools
    try:
        rows_inv = conn.execute(
            "SELECT DISTINCT color FROM inventory WHERE color IS NOT NULL AND color != 'nan' AND color != '—'"
        ).fetchall()
        for r in rows_inv:
            if r.get("color") and r["color"].strip():
                db_colors.add(r["color"].strip())
    except Exception:
        pass

    # 3. From custom_colors table
    try:
        rows_cust = conn.execute("SELECT name FROM custom_colors").fetchall()
        for r in rows_cust:
            if r.get("name") and r["name"].strip():
                db_colors.add(r["name"].strip())
    except Exception:
        pass

    conn.close()

    # Build final sorted list: popular standard colors first, followed by custom/inventory colors
    result = [c for c in STANDARD_COLORS]
    for c in sorted(db_colors):
        if c not in result and c not in ("—", "Не вказано", "nan"):
            result.append(c)

    return result


def update_all_colors_in_db() -> int:
    """Normalize colors for all existing price snapshots in DB."""
    conn = get_connection()
    rows = conn.execute("SELECT id, product_name FROM price_snapshots").fetchall()
    updates = []
    for r in rows:
        norm_col = normalize_color(r["product_name"])
        updates.append({"color": norm_col, "id": r["id"]})
    
    conn.executemany("UPDATE price_snapshots SET color = :color WHERE id = :id", updates)
    conn.commit()
    count = len(updates)
    conn.close()
    return count


# ════════════════════════════════════════════════════════════════ INVENTORY

def get_inventory(status_filter: Optional[List[str]] = None) -> List[Dict]:
    conn = get_connection()
    q = "SELECT * FROM inventory"
    params = []
    if status_filter:
        placeholders = ",".join("?" * len(status_filter))
        q += f" WHERE status IN ({placeholders})"
        params.extend(status_filter)
    q += " ORDER BY created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_spool(spool: Dict) -> int:
    conn = get_connection()
    if is_postgres():
        res = conn.execute(
            """INSERT INTO inventory
               (brand, store_name, plastic_type, color, hardness,
                initial_weight_g, current_weight_g, empty_spool_weight_g,
                purchase_price, purchase_date, status, notes, snapshot_id)
               VALUES (:brand, :store_name, :plastic_type, :color, :hardness,
                       :initial_weight_g, :current_weight_g, :empty_spool_weight_g,
                       :purchase_price, :purchase_date, :status, :notes, :snapshot_id)
               RETURNING id""",
            spool,
        )
        row = res.fetchone()
        spool_id = row["id"] if row else 0
    else:
        cur = conn.execute(
            """INSERT INTO inventory
               (brand, store_name, plastic_type, color, hardness,
                initial_weight_g, current_weight_g, empty_spool_weight_g,
                purchase_price, purchase_date, status, notes, snapshot_id)
               VALUES (:brand, :store_name, :plastic_type, :color, :hardness,
                       :initial_weight_g, :current_weight_g, :empty_spool_weight_g,
                       :purchase_price, :purchase_date, :status, :notes, :snapshot_id)""",
            spool,
        )
        spool_id = cur.lastrowid
    conn.commit()
    conn.close()
    return spool_id


def update_spool_weight(spool_id: int, new_weight_g: int) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE inventory SET current_weight_g = ? WHERE id = ?",
        (new_weight_g, spool_id),
    )
    conn.commit()
    conn.close()


def update_spool_status(spool_id: int, status: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE inventory SET status = ? WHERE id = ?",
        (status, spool_id),
    )
    conn.commit()
    conn.close()


def delete_spool(spool_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM inventory WHERE id = ?", (spool_id,))
    conn.commit()
    conn.close()


def get_spool_by_id(spool_id: int) -> Optional[Dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM inventory WHERE id = ?", (spool_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ══════════════════════════════════════════════════════════════ PRINT JOBS

def add_print_job(job: Dict) -> int:
    conn = get_connection()
    # Decrement spool weight safely
    if is_postgres():
        conn.execute(
            """UPDATE inventory
               SET current_weight_g = GREATEST(0, current_weight_g - ?)
               WHERE id = ?""",
            (job["filament_used_g"], job["spool_id"]),
        )
        res = conn.execute(
            """INSERT INTO print_jobs
               (spool_id, project_name, filament_used_g, cost_uah,
                is_failed, gcode_filename, notes)
               VALUES (:spool_id, :project_name, :filament_used_g, :cost_uah,
                       :is_failed, :gcode_filename, :notes)
               RETURNING id""",
            job,
        )
        row = res.fetchone()
        job_id = row["id"] if row else 0
    else:
        conn.execute(
            """UPDATE inventory
               SET current_weight_g = MAX(0, current_weight_g - ?)
               WHERE id = ?""",
            (job["filament_used_g"], job["spool_id"]),
        )
        cur = conn.execute(
            """INSERT INTO print_jobs
               (spool_id, project_name, filament_used_g, cost_uah,
                is_failed, gcode_filename, notes)
               VALUES (:spool_id, :project_name, :filament_used_g, :cost_uah,
                       :is_failed, :gcode_filename, :notes)""",
            job,
        )
        job_id = cur.lastrowid
    conn.commit()
    conn.close()
    return job_id


def get_print_jobs(limit: int = 50) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT pj.*, i.plastic_type, i.color, i.brand, i.hardness
           FROM print_jobs pj
           JOIN inventory i ON pj.spool_id = i.id
           ORDER BY pj.printed_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_print_job(job_id: int, spool_id: int, filament_used_g: float) -> None:
    """Delete a print job and restore spool weight."""
    conn = get_connection()
    conn.execute("DELETE FROM print_jobs WHERE id = ?", (job_id,))
    if is_postgres():
        conn.execute(
            """UPDATE inventory
               SET current_weight_g = LEAST(initial_weight_g, current_weight_g + ?)
               WHERE id = ?""",
            (filament_used_g, spool_id),
        )
    else:
        conn.execute(
            """UPDATE inventory
               SET current_weight_g = MIN(initial_weight_g, current_weight_g + ?)
               WHERE id = ?""",
            (filament_used_g, spool_id),
        )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════ ANALYTICS

def get_analytics_summary() -> Dict:
    conn = get_connection()
    is_pg = is_postgres()

    month_col_expr = "to_char(printed_at, 'YYYY-MM')" if is_pg else "strftime('%Y-%m', printed_at)"
    now_month_expr = "to_char(CURRENT_TIMESTAMP, 'YYYY-MM')" if is_pg else "strftime('%Y-%m', 'now')"

    stock = conn.execute(
        """SELECT
               SUM(current_weight_g) AS total_g,
               SUM(purchase_price * CAST(current_weight_g AS REAL) / NULLIF(initial_weight_g, 0)) AS total_value
           FROM inventory
           WHERE status != 'empty'"""
    ).fetchone()

    month_usage = conn.execute(
        f"""SELECT
               SUM(filament_used_g) AS used_g,
               SUM(cost_uah) AS used_uah
           FROM print_jobs
           WHERE {month_col_expr} = {now_month_expr}"""
    ).fetchone()

    failed_expr = "SUM(CASE WHEN is_failed = TRUE THEN 1 ELSE 0 END)" if is_pg else "SUM(CASE WHEN is_failed = 1 THEN 1 ELSE 0 END)"

    all_time = conn.execute(
        f"""SELECT
               SUM(filament_used_g) AS used_g,
               SUM(cost_uah) AS used_uah,
               COUNT(*) AS total_jobs,
               {failed_expr} AS failed_jobs
           FROM print_jobs"""
    ).fetchone()

    avg_by_type = conn.execute(
        """SELECT plastic_type,
               AVG(purchase_price / NULLIF(initial_weight_g, 0) * 1000) AS avg_price_per_kg,
               COUNT(*) AS spool_count
           FROM inventory
           GROUP BY plastic_type
           ORDER BY avg_price_per_kg DESC"""
    ).fetchall()

    monthly = conn.execute(
        f"""SELECT {month_col_expr} AS month,
               SUM(filament_used_g) AS used_g,
               SUM(cost_uah) AS cost_uah
           FROM print_jobs
           GROUP BY {month_col_expr}
           ORDER BY month"""
    ).fetchall()

    type_dist = conn.execute(
        """SELECT plastic_type, SUM(current_weight_g) AS total_g
           FROM inventory WHERE status != 'empty'
           GROUP BY plastic_type"""
    ).fetchall()

    store_prices = conn.execute(
        """WITH latest AS (
               SELECT store_id, plastic_type, price_per_kg,
                      ROW_NUMBER() OVER (PARTITION BY store_id, plastic_type ORDER BY scraped_at DESC) AS rn
               FROM price_snapshots WHERE price_per_kg IS NOT NULL
           )
           SELECT s.name AS store_name, l.plastic_type, AVG(l.price_per_kg) AS avg_price_per_kg
           FROM latest l JOIN stores s ON l.store_id = s.id
           WHERE l.rn = 1
           GROUP BY s.name, l.plastic_type
           ORDER BY l.plastic_type, avg_price_per_kg"""
    ).fetchall()

    conn.close()
    return {
        "total_g": stock["total_g"] if stock and stock["total_g"] else 0,
        "total_value": stock["total_value"] if stock and stock["total_value"] else 0,
        "month_used_g": month_usage["used_g"] if month_usage and month_usage["used_g"] else 0,
        "month_used_uah": month_usage["used_uah"] if month_usage and month_usage["used_uah"] else 0,
        "all_used_g": all_time["used_g"] if all_time and all_time["used_g"] else 0,
        "all_used_uah": all_time["used_uah"] if all_time and all_time["used_uah"] else 0,
        "total_jobs": all_time["total_jobs"] if all_time and all_time["total_jobs"] else 0,
        "failed_jobs": all_time["failed_jobs"] if all_time and all_time["failed_jobs"] else 0,
        "avg_by_type": [dict(r) for r in avg_by_type],
        "monthly": [dict(r) for r in monthly],
        "type_dist": [dict(r) for r in type_dist],
        "store_prices": [dict(r) for r in store_prices],
    }
